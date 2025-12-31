import asyncio
from copy import deepcopy
import json
import copy
from typing import List, Dict
import requests
import aiohttp
from openai import AsyncAzureOpenAI, AsyncOpenAI, OpenAI
import random
from collections import defaultdict

from utils.common import reorder_keys
from utils.configs import AIHUBMIX_KEY, AZURE_KEY, CLIENTTIMEOUT, volcano_KEY

class LLMClient:
    """
    Client for forwarding requests to remote vllm APIs.
    """

    def __init__(self, url: List, model_names: List):
        self.base_urls = url
        self.model_names = model_names
        self.queryid_to_url: Dict[str, str] = {}
        self.url_load: Dict[str, int] = defaultdict(int)
        for u in self.base_urls:
            self.url_load[u] = 0

    def pop_query_id(self, query_id: str):
        """
        Remove query from URL records.
        """
        url = self.queryid_to_url.pop(query_id, None)
        if url is not None:
            if url in self.url_load and self.url_load[url] > 0:
                self.url_load[url] -= 1

    def allocate_url_by_query_id(self, query_id: str, logger=None) -> str:
        # If already bound
        if query_id in self.queryid_to_url:
            return self.queryid_to_url[query_id]
        # Allocate to URL with least current load
        min_load_url = min(self.url_load.items(), key=lambda x: x[1])[0]
        self.queryid_to_url[query_id] = min_load_url
        self.url_load[min_load_url] += 1
        if logger:
            logger.info(f"[vllm allocate] {query_id} allocated to {min_load_url}, Running: {self.url_load[min_load_url]} reqs")
        return min_load_url

    async def chat(self, messages: List[Dict[str, str]], tool_list=[], temperature=0.7, top_p=0.95, logger=None, query_id="") -> dict:
        payload = {
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p
        }
        if len(tool_list) > 0:
            payload['tools'] = tool_list

        # Select URL, priority by load-balancing and consistency on query_id mapping
        if query_id:
            chosen_url = self.allocate_url_by_query_id(query_id, logger)
        else:
            chosen_url = random.choice(self.base_urls)

        resp_json = None
        async with aiohttp.ClientSession() as session:
            async with session.post(chosen_url, json=payload, timeout=CLIENTTIMEOUT) as resp:
                try:
                    resp_json = await resp.json()
                    return {
                        "content": resp_json['choices'][0]['message']['content'],
                        "usage": resp_json['usage'],
                        "error": ""
                    }
                except Exception as e:
                    try:
                        if logger is not None:
                            logger.info("[vllm response] %s", resp_json)
                    except:
                        pass
                    return {
                        "content": "",
                        "usage": {
                            'completion_tokens': -1,
                            'prompt_tokens': -1,
                            'prompt_tokens_details': None,
                            'total_tokens': -1
                        },
                        "error": str(e)
                    }

    async def _call_openai_chat(self,
                                raw_messages: List[Dict[str, str]],
                                tool_list=[],
                                temperature=0.7,
                                top_p=0.95,
                                logger=None,
                                api_key=None) -> dict:
        idx = random.randrange(len(self.base_urls))
        chosen_url = self.base_urls[idx]
        chosen_model = self.model_names[idx]

        if 'claude' in chosen_model:
            return await self._call_request_chat(raw_messages, tool_list, temperature, top_p, logger, api_key, idx)

        client = OpenAI(
            base_url=chosen_url,
            api_key=api_key,
        )

        meta_data = {
            "role": "assistant",
            "content": ""
        }
        tool_call_ids = []
        response_json = None
        messages = copy.deepcopy(raw_messages)

        for msg in messages:
            if isinstance(msg, dict) and msg.get('role') == 'user' and isinstance(msg.get('content'), list):
                for item in msg['content']:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        item['type'] = 'input_text'

        try:
            loop = asyncio.get_event_loop()
            if chosen_model in ["gpt-4.1", "gpt-4o"]:
                func = lambda: client.responses.create(
                    input=messages,
                    model=chosen_model,
                    tools=tool_list
                )
            else:
                func = lambda: client.responses.create(
                    input=messages,
                    model=chosen_model,
                    tools=tool_list,
                    reasoning={'effort': 'medium', 'summary': 'detailed'}
                )
            response = await asyncio.wait_for(
                loop.run_in_executor(None, func),
                timeout=CLIENTTIMEOUT
            )

            response_json = response.model_dump()

            next_messages = messages + response.output

            summary_list = []
            answer_content_list = []

            tool_calls = ""
            for msg in response_json['output']:
                if msg['type'] == 'reasoning':
                    summary_items = msg.get("summary", [])
                    summary_list.extend(s for s in summary_items if s.get("type") == "summary_text")
                elif msg['type'] == 'function_call':
                    now_tool_call = {
                        "name": msg['name'],
                        "arguments": json.loads(msg['arguments'])
                    }
                    tool_call_ids.append(msg['call_id'])
                    tool_calls += f"<tool_call>\n{now_tool_call}\n</tool_call>\n"
                elif msg['type'] == 'message':
                    for block in msg.get("content", []):
                        if block.get("type") == "output_text":
                            answer_content_list.append(block.get("text", "").strip())

            reasoning_content = "\n".join([i.get('text', "") for i in summary_list if i.get("text", "")]).strip()
            content = "\n".join(answer_content_list).strip()
            tool_calls = tool_calls.strip()
            meta_data_content = ""
            meta_data_content += "<think>\n"
            meta_data_content += f"{reasoning_content}\n</think>" if reasoning_content else "</think>"
            meta_data_content += f"\n{content}"
            meta_data_content += f"\n" if content else ""
            meta_data_content += f"{tool_calls}" if tool_calls else ""

            meta_data['content'] = meta_data_content

            final_response = {
                "next_messages": next_messages,
                "log_messages": [reorder_keys(rep) for rep in response_json['output']],
                "meta_data": meta_data,
                "tool_call_ids": tool_call_ids,
                "usage": response_json['usage'],
            }

            return final_response

        except Exception as e:
            try:
                if logger is not None:
                    logger.info("[vllm response] %s", response_json)
            except:
                pass

            return {
                "next_messages": messages,
                "log_messages": [],
                "meta_data": meta_data,
                "tool_call_ids": tool_call_ids,
                "usage": response_json['usage'],
                "error": str(e)
            }

    async def _call_request_chat(self,
                                raw_messages: List[Dict[str, str]],
                                tool_list=[],
                                temperature=0.7,
                                top_p=0.95,
                                logger=None,
                                api_key=None,
                                idx=None) -> dict:
        idx = random.randrange(len(self.base_urls)) if idx is None else idx
        chosen_url = self.base_urls[idx]
        chosen_model = self.model_names[idx]

        messages = copy.deepcopy(raw_messages)

        if "claude" in chosen_model:
            headers = {
                "X-Api-Key": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            for tool in tool_list:
                if isinstance(tool, dict):
                    tool['type'] = 'custom'
                    if 'parameters' in tool:
                        tool['input_schema'] = tool.pop('parameters')

        else:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'x-ark-moderation-scene': 'skip-ark-moderation'
            }

        for msg in messages:
            if isinstance(msg, dict) and msg.get('role') == 'user' and isinstance(msg.get('content'), list):
                for item in msg['content']:
                    if isinstance(item, dict) and item.get('type') == 'input_text':
                        item['type'] = 'text'

        data = json.dumps({
            "model": chosen_model,  # Model id to be replaced
            "messages": messages,
            "max_tokens": 16000,
            "thinking": {
                "type": "enabled",
                "budget_tokens": 15000
            },
            "tools": tool_list,
        })

        response_json = {}

        tool_call_ids = []
        meta_data = {
            "role": "assistant",
            "content": ""
        }
        answer_content_list = []
        summary_list = []
        log_messages = []

        try:
            timeout = aiohttp.ClientTimeout(total=CLIENTTIMEOUT)
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                    async with session.post(chosen_url, data=data, headers=headers) as resp:
                        response_json = await resp.json()

            tool_calls = ""

            if "content" in response_json:
                log_messages = [{"role": "assistant", "content": response_json['content']}]
                next_messages = messages + log_messages
                for msg in response_json['content']:
                    if msg['type'] == "tool_use":
                        tool_call_ids.append(msg['id'])
                        now_tool_call = {
                            "name": msg['name'],
                            "arguments": msg['input']
                        }
                        tool_calls += f"<tool_call>\n{now_tool_call}\n</tool_call>\n"
                    elif msg['type'] == "text":
                        answer_content_list.append(msg['text'])
                    elif msg['type'] == 'thinking':
                        summary_list.append(msg['thinking'])

            elif "choices" in response_json and len(response_json['choices']):
                tmp_messages = response_json['choices'][0]['message']
                log_messages = [tmp_messages]
                next_messages = messages + [tmp_messages]
                msg = tmp_messages
                if "reasoning_content" in msg:
                    summary_list.append(msg['reasoning_content'])
                if "content" in msg:
                    answer_content_list.append(msg['content'])
                if "tool_calls" in msg:
                    for tool_call in msg['tool_calls']:
                        tool_call_ids.append(tool_call['id'])
                        now_tool_call = {
                            "name": tool_call['function']['name'],
                            "arguments": json.loads(tool_call['function']['arguments'])
                        }
                        tool_calls += f"<tool_call>\n{now_tool_call}\n</tool_call>\n"
            reasoning_content = "\n".join(summary_list).strip()
            content = "\n".join(answer_content_list).strip()
            tool_calls = tool_calls.strip()
            meta_data_content = ""
            meta_data_content += "<think>\n"
            meta_data_content += f"{reasoning_content}\n</think>" if reasoning_content else "</think>"
            meta_data_content += f"\n{content}"
            meta_data_content += f"\n" if content else ""
            meta_data_content += f"{tool_calls}" if tool_calls else ""

            meta_data['content'] = meta_data_content

            final_response = {
                "next_messages": next_messages,
                "log_messages": log_messages,
                "meta_data": meta_data,
                "tool_call_ids": tool_call_ids,
                "usage": response_json['usage'],
            }

            return final_response

        except Exception as e:
            try:
                if logger is not None:
                    logger.info("[vllm response] %s", response_json)
            except:
                pass

            return {
                "next_messages": messages,
                "log_messages": [],
                "meta_data": meta_data,
                "tool_call_ids": tool_call_ids,
                "usage": response_json['usage'],
                "error": str(e)
            }

    async def aihubmix_chat(self, raw_messages: List[Dict[str, str]], tool_list=[], temperature=0.7, top_p=0.95, logger=None) -> dict:
        return await self._call_openai_chat(
            raw_messages=raw_messages,
            tool_list=tool_list,
            temperature=temperature,
            top_p=top_p,
            logger=logger,
            api_key=AIHUBMIX_KEY,
        )

    async def azure_chat(self, raw_messages: List[Dict[str, str]], tool_list=[], temperature=0.7, top_p=0.95, logger=None) -> dict:
        return await self._call_openai_chat(
            raw_messages=raw_messages,
            tool_list=tool_list,
            temperature=temperature,
            top_p=top_p,
            logger=logger,
            api_key=AZURE_KEY,
        )

    async def volcano_chat(self, raw_messages: List[Dict[str, str]], tool_list=[], temperature=0.7, top_p=0.95, logger=None) -> dict:
        return await self._call_request_chat(
            raw_messages=raw_messages,
            tool_list=tool_list,
            temperature=temperature,
            top_p=top_p,
            logger=logger,
            api_key=volcano_KEY,
        )

