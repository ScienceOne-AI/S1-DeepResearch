import asyncio
from copy import deepcopy
import json
import copy
from typing import Awaitable, Callable, Dict, List
import requests
import aiohttp
from openai import AsyncAzureOpenAI, AsyncOpenAI, OpenAI
import random
from collections import defaultdict

from utils.common import reorder_keys
from utils.configs import AIHUBMIX_KEY, ALIYUN_KEY, AZURE_KEY, CLIENT_TIMEOUT, VOLCANO_KEY

class LLMClient:
    """
    调用远端启动的 vllm 接口
    """

    def __init__(
        self,
        url: List,
        model_names: List,
        client_timeout: int | float | None = None,
        api_keys: dict | None = None,
        max_retries: int = 0,
    ):
        self.base_urls = url
        self.model_names = model_names
        self.client_timeout = client_timeout or CLIENT_TIMEOUT
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff_seconds = 30.0
        self.api_keys = api_keys or {
            "aihubmix": AIHUBMIX_KEY,
            "azure": AZURE_KEY,
            "volcano": VOLCANO_KEY,
            "aliyun": ALIYUN_KEY,
        }
        # 优化的路由分配结构:
        # 用一个 dict 记录 query_id => url（一一绑定，方便直接查找 query_id 所属 url，而不用遍历所有列表）
        self.queryid_to_url: Dict[str, str] = {}
        # 统计每个 url 当前负载（每个 url 被分配了多少个 query_id），直接用 defaultdict(int)
        self.url_load: Dict[str, int] = defaultdict(int)
        for u in self.base_urls:
            self.url_load[u] = 0

    def pop_query_id(self, query_id: str):
        """
        将 query 弹出 url 记录表
        """
        url = self.queryid_to_url.pop(query_id, None)
        if url is not None:
            if url in self.url_load and self.url_load[url] > 0:
                self.url_load[url] -= 1

    def allocate_url_by_query_id(self, query_id: str, logger = None) -> str:
        # 已有绑定
        if query_id in self.queryid_to_url:
            return self.queryid_to_url[query_id]
        # 分配给当前负载最小的 url
        
        min_load_url = min(self.url_load.items(), key=lambda x: x[1])[0]
        self.queryid_to_url[query_id] = min_load_url
        self.url_load[min_load_url] += 1
        if logger:
            logger.info(f"[vllm allocate] {query_id} allocated to {min_load_url}, Running: {self.url_load[min_load_url]} reqs")
        return min_load_url

    async def _run_with_retry(
        self,
        request_name: str,
        request_coro_factory: Callable[[], Awaitable[dict]],
        logger = None,
        query_id: str = "",
    ) -> dict:
        total_attempts = self.max_retries + 1
        last_error: Exception | None = None
        query_suffix = f", query_id={query_id}" if query_id else ""

        for attempt in range(1, total_attempts + 1):
            if logger is not None and attempt > 1:
                logger.info(
                    "[llm retry] %s retry attempt %d/%d started%s",
                    request_name,
                    attempt,
                    total_attempts,
                    query_suffix,
                )
            try:
                result = await request_coro_factory()
                if isinstance(result, dict) and result.get("error"):
                    raise RuntimeError(str(result["error"]))
                if logger is not None and attempt > 1:
                    logger.info(
                        "[llm retry] %s attempt %d/%d succeeded%s",
                        request_name,
                        attempt,
                        total_attempts,
                        query_suffix,
                    )
                return result
            except Exception as exc:
                last_error = exc
                if logger is not None:
                    logger.warning(
                        "[llm retry] %s attempt %d/%d failed%s: %s",
                        request_name,
                        attempt,
                        total_attempts,
                        query_suffix,
                        exc,
                    )
                if attempt >= total_attempts:
                    break
                retry_delay = self.retry_backoff_seconds * attempt
                if logger is not None:
                    logger.info(
                        "[llm retry] %s will retry in %.1fs%s",
                        request_name,
                        retry_delay,
                        query_suffix,
                    )
                await asyncio.sleep(retry_delay)

        if last_error is None:
            raise RuntimeError(f"{request_name} failed without an explicit error{query_suffix}")
        raise last_error

    async def chat(self, messages: List[Dict[str, str]], tool_list = [], temperature=0.7, top_p=0.95, extra_payload: dict = {}, logger= None, query_id = "") -> dict:
        """
        注意：requests.post 是同步阻塞的，不适用于 async def，即它会在请求时阻塞当前协程，不能发挥异步优势。
        当前函数用 aiohttp 替代了 requests，实现了真正的异步非阻塞网络请求，可以提升异步环境下的并发性能，
        不会像同步阻塞那样导致协程队列卡顿或效率低下。
        extra_payload 支持传入任意额外的 payload 参数（如 presence_penalty 等），会覆盖默认值。
        """
        payload = {
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
        }
        payload.update(extra_payload)
        if len(tool_list) > 0:
            payload['tools'] = tool_list

        # 选择 URL，优先根据 query_id 做负载均衡&一致性调度
        if query_id:
            chosen_url = self.allocate_url_by_query_id(query_id, logger)
        else:
            chosen_url = random.choice(self.base_urls)

        chosen_idx = self.base_urls.index(chosen_url)
        choose_model = self.model_names[chosen_idx]

        payload['model'] = choose_model # 兼容 vllm

        resp_json = None

        async def _request_once() -> dict:
            nonlocal resp_json
            async with aiohttp.ClientSession() as session:
                async with session.post(chosen_url, json=payload, timeout=self.client_timeout) as resp:
                    resp.raise_for_status()
                    resp_json = await resp.json()
                    return {
                        "content": resp_json['choices'][0]['message']['content'],
                        "usage": resp_json['usage'],
                        "error": ""
                    }

        try:
            return await self._run_with_retry(
                request_name=f"chat url={chosen_url} model={choose_model}",
                request_coro_factory=_request_once,
                logger=logger,
                query_id=query_id,
            )
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
                                tool_list = [], 
                                temperature=0.7, 
                                top_p=0.95, 
                                logger = None, 
                                api_key=None,
                                query_id: str = "") -> dict:
        idx = random.randrange(len(self.base_urls))
        chosen_url = self.base_urls[idx]
        chosen_model = self.model_names[idx]

        if 'claude' in chosen_model or 'glm' in chosen_model:
            # 路由成 requests 调用的方式，这样就可以和火山引擎兼容
            # 此时需要传递 idx 来保证选取的还是这个模型和 URL
            return await self._call_request_chat(raw_messages, tool_list, temperature, top_p, logger, api_key, idx, query_id)

        client = OpenAI(
            base_url = chosen_url,
            api_key = api_key,
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

        async def _request_once() -> dict:
            nonlocal response_json, meta_data, tool_call_ids

            tool_call_ids = []
            meta_data = {
                "role": "assistant",
                "content": ""
            }
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
            try:
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, func),
                    timeout=self.client_timeout
                )
            except Exception as run_executor_exc:
                print(f"[client error] {run_executor_exc}")
                raise

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
                    tool_calls += "<tool_call>\n" + json.dumps(now_tool_call, ensure_ascii=False) + "\n</tool_call>\n"
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

            return {
                "next_messages": next_messages,
                "log_messages": [reorder_keys(rep) for rep in response_json['output']],
                "meta_data": meta_data,
                "tool_call_ids": tool_call_ids,
                "usage": response_json['usage'],
            }

        try:
            return await self._run_with_retry(
                request_name=f"openai_chat url={chosen_url} model={chosen_model}",
                request_coro_factory=_request_once,
                logger=logger,
                query_id=query_id,
            )
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
                "usage": response_json['usage'] if response_json is not None and 'usage' in response_json else None,
                "error": str(e)
            }

    async def _call_request_chat(self, 
                                raw_messages: List[Dict[str, str]], 
                                tool_list = [], 
                                temperature=0.7, 
                                top_p=0.95, 
                                logger = None, 
                                api_key=None,
                                idx = None,
                                query_id: str = "") -> dict:
        idx = random.randrange(len(self.base_urls)) if idx is None else idx
        chosen_url = self.base_urls[idx]
        chosen_model = self.model_names[idx]

        messages = copy.deepcopy(raw_messages)

        if "claude" in chosen_model:
            headers={
                "X-Api-Key": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            # claude 真服了， tool_list 也不统一
            for tool in tool_list:
                if isinstance(tool, dict):
                    tool['type'] = 'custom'
                    if 'parameters' in tool:
                        tool['input_schema'] = tool.pop('parameters')
        elif any(x in chosen_model for x in ["glm", "doubao"]):
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        else:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'x-ark-moderation-scene': 'skip-ark-moderation'
            }

        # 默认都需要改成 text
        for msg in messages:
            if isinstance(msg, dict) and msg.get('role') == 'user' and isinstance(msg.get('content'), list):
                for item in msg['content']:
                    if isinstance(item, dict) and item.get('type') == 'input_text':
                        item['type'] = 'text'

        data=json.dumps({
            "model": chosen_model, # 替换模型 id
            "messages": messages,
            "max_tokens": 128000,
            "thinking" :{
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

        async def _request_once() -> dict:
            nonlocal response_json, tool_call_ids, meta_data, answer_content_list, summary_list, log_messages
            tool_call_ids = []
            meta_data = {
                "role": "assistant",
                "content": ""
            }
            answer_content_list = []
            summary_list = []
            log_messages = []

            timeout = aiohttp.ClientTimeout(total=self.client_timeout)
            connector = aiohttp.TCPConnector(ssl=False)
            # aiohttp 的 ClientSession.post 方法不支持 verify=False 参数，证书校验需要在 TCPConnector 里开启
            # 所以需要在 ClientSession 构造时传入 connector
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.post(chosen_url, data=data, headers=headers) as resp:
                    resp.raise_for_status()
                    response_json = await resp.json()

            tool_calls = ""

            if "content" in response_json:
                # 说明当前就是 cladue 的调用结果，直接把 content 列表拼回去就可以了
                log_messages = [{"role": "assistant", "content": response_json['content']}]
                next_messages = messages + log_messages
                for msg in response_json['content']:
                    if msg['type'] == "tool_use":
                        tool_call_ids.append(msg['id'])
                        now_tool_call = {
                            "name": msg['name'],
                            "arguments": msg['input']
                        }
                        tool_calls += "<tool_call>\n" + json.dumps(now_tool_call, ensure_ascii=False) + "\n</tool_call>\n"
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
                if "tool_calls" in msg and msg['tool_calls']:
                    for tool_call in msg['tool_calls']:
                        tool_call_ids.append(tool_call['id'])
                        now_tool_call = {
                            "name": tool_call['function']['name'],
                            "arguments": json.loads(tool_call['function']['arguments'])
                        }
                        # 保证dict序列化为json字符串时使用双引号
                        tool_calls += "<tool_call>\n" + json.dumps(now_tool_call, ensure_ascii=False) + "\n</tool_call>\n"
            else:
                raise RuntimeError(f"Unexpected response payload: {response_json}")

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

            return {
                "next_messages": next_messages,
                "log_messages": log_messages,
                "meta_data": meta_data,
                "tool_call_ids": tool_call_ids,
                "usage": response_json['usage'],
            }

        try:
            return await self._run_with_retry(
                request_name=f"request_chat url={chosen_url} model={chosen_model}",
                request_coro_factory=_request_once,
                logger=logger,
                query_id=query_id,
            )
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
                "usage": response_json['usage'] if response_json is not None and 'usage' in response_json else None,
                "error": str(e)
            }

    async def _call_aliyun_chat(self,
                                raw_messages: List[Dict[str, str]],
                                tool_list = [],
                                temperature=0.7,
                                top_p=0.95,
                                logger = None,
                                api_key=None,
                                query_id: str = "") -> dict:
        idx = random.randrange(len(self.base_urls))
        chosen_url = self.base_urls[idx]
        chosen_model = self.model_names[idx]
        if chosen_url.rstrip("/").endswith("/chat/completions"):
            chosen_url = chosen_url.rstrip("/")[: -len("/chat/completions")]

        client = OpenAI(
            api_key=api_key,
            base_url=chosen_url,
        )

        messages = copy.deepcopy(raw_messages)
        response_json = None
        answer_content_list = []
        summary_list = []
        log_messages = []

        tool_call_ids = []
        tool_calls = ""

        meta_data = {
            "role": "assistant",
            "content": ""
        }

        async def _request_once() -> dict:
            nonlocal response_json, answer_content_list, summary_list, log_messages, tool_call_ids, tool_calls, meta_data
            response_json = None
            answer_content_list = []
            summary_list = []
            log_messages = []
            tool_call_ids = []
            tool_calls = ""
            meta_data = {
                "role": "assistant",
                "content": ""
            }

            loop = asyncio.get_event_loop()
            request_kwargs = {
                "model": chosen_model,
                "messages": messages,
                "temperature": temperature,
                "top_p": top_p,
                "extra_body": {"enable_thinking": True},
            }
            if tool_list:
                request_kwargs["tools"] = tool_list
            func = lambda: client.chat.completions.create(**request_kwargs)
            completion = await asyncio.wait_for(
                loop.run_in_executor(None, func),
                timeout=self.client_timeout
            )
            response_json = completion.model_dump()
            tmp_messages = response_json['choices'][0]['message']
            log_messages = [tmp_messages]
            next_messages = messages + [tmp_messages]
            msg = tmp_messages
            if "reasoning_content" in msg:
                summary_list.append(msg['reasoning_content'])
            if "content" in msg:
                answer_content_list.append(msg['content'])
            if "tool_calls" in msg and msg['tool_calls']:
                for tool_call in msg['tool_calls']:
                    tool_call_ids.append(tool_call['id'])
                    arguments_raw = tool_call['function']['arguments']
                    try:
                        arguments_obj = json.loads(arguments_raw)
                    except Exception:
                        arguments_obj = arguments_raw
                    now_tool_call = {
                        "name": tool_call['function']['name'],
                        "arguments": arguments_obj
                    }
                    tool_calls += "<tool_call>\n" + json.dumps(now_tool_call, ensure_ascii=False) + "\n</tool_call>\n"
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

            return {
                "next_messages": next_messages,
                "log_messages": log_messages,
                "meta_data": meta_data,
                "tool_call_ids": tool_call_ids,
                "usage": response_json['usage'],
            }

        try:
            return await self._run_with_retry(
                request_name=f"aliyun_chat url={chosen_url} model={chosen_model}",
                request_coro_factory=_request_once,
                logger=logger,
                query_id=query_id,
            )
        except Exception as e:
            try:
                if logger is not None:
                    logger.info("[aliyun response] %s", response_json)
            except:
                pass

            return {
                "next_messages": messages,
                "log_messages": [],
                "meta_data": meta_data,
                "tool_call_ids": tool_call_ids,
                "usage": response_json['usage'] if response_json is not None and 'usage' in response_json else None,
                "error": str(e)
            }

    async def aihubmix_chat(self, raw_messages: List[Dict[str, str]], tool_list = [], temperature=0.7, top_p=0.95, logger = None, query_id: str = "") -> dict:
        return await self._call_openai_chat(
            raw_messages=raw_messages,
            tool_list=tool_list,
            temperature=temperature,
            top_p=top_p,
            logger=logger,
            api_key=self.api_keys.get("aihubmix"),
            query_id=query_id,
        )

    async def azure_chat(self, raw_messages: List[Dict[str, str]], tool_list = [], temperature=0.7, top_p=0.95, logger = None, query_id: str = "") -> dict:
        return await self._call_openai_chat(
            raw_messages=raw_messages,
            tool_list=tool_list,
            temperature=temperature,
            top_p=top_p,
            logger=logger,
            api_key=self.api_keys.get("azure"),
            query_id=query_id,
        )

    async def volcano_chat(self, raw_messages: List[Dict[str, str]], tool_list = [], temperature=0.7, top_p=0.95, logger = None, query_id: str = "") -> dict:
        return await self._call_request_chat(
            raw_messages=raw_messages,
            tool_list=tool_list,
            temperature=temperature,
            top_p=top_p,
            logger=logger,
            api_key=self.api_keys.get("volcano"),
            query_id=query_id,
        )

    async def aliyun_chat(self, raw_messages: List[Dict[str, str]], tool_list = [], temperature=0.7, top_p=0.95, logger = None, query_id: str = "") -> dict:
        return await self._call_aliyun_chat(
            raw_messages=raw_messages,
            tool_list=tool_list,
            temperature=temperature,
            top_p=top_p,
            logger=logger,
            api_key=self.api_keys.get("aliyun"),
            query_id=query_id,
        )
