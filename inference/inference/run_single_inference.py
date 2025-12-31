import asyncio
import copy
import logging
import sys
import os
import time
import datetime
import json

from utils.configs import ONLINE_PLATFORM

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from typing import Any, Dict, List, Tuple

from server.llm_api import LLMClient
from server.tool_api import return_all_tools
from server.tool_execution import execute_tool_call

from utils.build_prompt import (
    build_initial_messages,
    build_openai_schema,
    build_tongyi_schema,
    build_user_payload,
    get_tools_json,
    wrap_tool_responses_into_user_message,
)
from utils.common import get_query_uuid
from utils.extract_schemas_tongyi import extract_tongyi_tool_calls
from utils.extract_schemas_aihubmix import extract_aihubmix_tool_calls
from utils.logger import save_result_to_log_dir, setup_logger_for_query
from utils.prompts import TONGYI_DEEPRESEARCH_SYSTEM_PROMPT

async def run_one_query(
    llm: LLMClient,
    user_query: str,
    file_path: str,
    system: str,
    max_rounds: int,
    temperature: float,
    debug: bool = False,
    args=None,
    progress: dict = None,
    all_tools: Dict = None,
    system_format: str = "tongyi_deepresearch", 
    log_label:str = ""
) -> Dict[str, Any]:
    """
    Run a complete multi-step tool-calling session until the model stops calling tools
    or max_rounds is reached. Returns a dict with the transcript and final answer.
    """
    query_id = get_query_uuid(user_query)
    logger, log_file_path = setup_logger_for_query(query_id, project_root, log_label)
    if debug:
        print(f"[run_single_inference.py] Logging configured. Query log file: {log_file_path}")

    messages = build_initial_messages(user_query, file_path, system=system, system_format = system_format, tool_mapping=all_tools)
    transcript: List[Dict[str, str]] = list(messages)  # shallow copy

    # For json log
    log_messages: List[Dict[str, str]] = []
    # Add system and user
    log_messages.append({"role": "system", "content": system})
    log_messages.append({"role": "user", "content": build_user_payload(user_query, file_path, system_format)})

    for round_idx in range(1, max_rounds + 1):
        llm_start = time.time()
        logger.info(f"[round {round_idx}] Round {round_idx} starting...")
        tool_call_ids = []
        if system_format == "tongyi_deepresearch":
            response = await llm.chat(messages, temperature=temperature, logger=logger, query_id=query_id)
            assistant_text = response['content']
            usage = response['usage']
            if debug and response['error']:
                logger.info(f"[round {round_idx}] llm.chat error: {response['error']}")
            llm_elapsed_time = time.time() - llm_start
            transcript.append({"role": "assistant", "content": assistant_text, "elapsed_time": llm_elapsed_time, "usage": usage})
            log_messages.append({"role": "assistant", "content": assistant_text, "elapsed_time": llm_elapsed_time, "usage": usage})
            tool_calls = extract_tongyi_tool_calls(assistant_text)
        elif system_format in ONLINE_PLATFORM:
            if system_format == "azure":
                response = await llm.azure_chat(messages, temperature=temperature, tool_list=build_openai_schema(all_tools), logger=logger)
            elif system_format in ["aihubmix", "aihubmix_claude"]:
                response = await llm.aihubmix_chat(messages, temperature=temperature, tool_list=build_openai_schema(all_tools), logger=logger)
            elif system_format == "volcano":
                response = await llm.volcano_chat(messages, temperature=temperature, tool_list=build_tongyi_schema(all_tools), logger=logger)

            usage = response['usage']
            messages = response['next_messages']
            now_log_messages =  response['log_messages'] 
            tool_call_ids = response['tool_call_ids']
            meta_data = response['meta_data'] 
            llm_elapsed_time = time.time() - llm_start
            
            if debug and 'error' in response:
                logger.info(f"[round {round_idx}] llm.chat error: {response['error']}")
            
            transcript.append({**meta_data, "elapsed_time": llm_elapsed_time, "usage": usage})
            log_messages.extend(now_log_messages)
            tool_calls = extract_aihubmix_tool_calls(meta_data['content'], all_tools)
            assistant_text = meta_data['content']
        else:
            raise ValueError(f"[system_format={system_format} failed] Please define a function to extract calls like `utils -> extract_schemas -> extract_tongyi_tool_calls`")

        if debug:
            logger.info(f"[round {round_idx}] tool_calls: {tool_calls}")


        result_obj = {
            "query_id": query_id,
            "tools": get_tools_json(all_tools) if all_tools is not None else "[]",
            "messages": copy.deepcopy(log_messages),
            "final_answer": assistant_text,
            "transcript": copy.deepcopy(transcript),
            "rounds": round_idx,
            "stopped_reason": "no_tool_calls" if not tool_calls else None
        }

        if progress is not None:
            progress['result'] = copy.deepcopy(result_obj)

        if not tool_calls:
            logger.info("[run_one_query] Stopping: no tool calls in round %d", round_idx)
            save_result_to_log_dir(query_id, result_obj, project_root, log_label)
            return result_obj


        # Execute all tool calls sequentially for this assistant turn (the model may emit multiple).
        responses: List[Tuple[str, str]] = []
        tool_total_time = 0.0
        for idx, call in enumerate(tool_calls):
            name = call.get("name")
            args = call.get("arguments", {})
            tool_start = time.time()
            resp = await execute_tool_call(name, args, all_tools, logger)
            tool_elapsed = time.time() - tool_start
            tool_total_time += tool_elapsed
            responses.append(resp)
            # Log each tool response as a message
            if system_format in ONLINE_PLATFORM:
                if system_format in ["azure", "aihubmix"]:
                    tool_response = {
                        "type": "function_call_output",  
                        "call_id": tool_call_ids[idx], 
                        "output": resp[1], 
                    }
                elif system_format in ["aihubmix_claude"]:
                    tool_response = {
                        "role": "user",
                        "content": [{
                            "type": "tool_result",  
                            "tool_use_id": tool_call_ids[idx], 
                            "content": resp[1], 
                        }]
                    }
                elif system_format in ["volcano"]:
                    tool_response = {
                        "role": "tool",  
                        "tool_call_id": tool_call_ids[idx], 
                        "content": resp[1], 
                    }
                messages.append(copy.deepcopy(tool_response))
                tool_response["elapsed_time"] = tool_elapsed 
                log_messages.append(tool_response)
            else:
                log_messages.append({"role": "tool", "content": resp[1], "elapsed_time": tool_elapsed})
        # Feed tool responses back as a single 'user' message (matching the template behavior)
        tool_user_msg = wrap_tool_responses_into_user_message(responses)
        if system_format not in ONLINE_PLATFORM:
            messages.extend([{"role": "assistant", "content": assistant_text}, tool_user_msg])

        transcript.extend([tool_user_msg])

    # If we get here, we hit the max rounds without a clean finish
    logger.info("[run_one_query] Max rounds (%d) exceeded for query: %s", max_rounds, user_query)
    result_obj = {
        "query_id": query_id,
        "tools": get_tools_json(all_tools) if all_tools is not None else "[]",
        "messages": copy.deepcopy(log_messages),
        "final_answer": transcript[-1]["content"] if transcript else "",
        "transcript": copy.deepcopy(transcript),
        "rounds": max_rounds,
        "stopped_reason": "max_rounds_exceeded"
    }
    if progress is not None:
        progress['result'] = copy.deepcopy(result_obj)

    save_result_to_log_dir(query_id, result_obj, project_root, log_label)
    return result_obj


# ----------- main --------------
if __name__ == "__main__":

    async def main():
        llm_client_urls = ["http://10.20.4.18:10777/vllm_generate"]
        llm_client = LLMClient(llm_client_urls)
        all_tools = return_all_tools()
        user_query = "今天北京和合肥的温度如何？如果把北京的温度开根号，加上合肥的温度的阶乘，最后的值是多少？"
        file_path = ""
        system_prompt = TONGYI_DEEPRESEARCH_SYSTEM_PROMPT
        max_rounds = 15
        temperature = 0.4
        debug = True

        result = await run_one_query(
            llm=llm_client,
            user_query=user_query,
            file_path=file_path,
            system=system_prompt,
            max_rounds=max_rounds,
            temperature=temperature,
            debug=debug,
            all_tools=all_tools,
            system_format = "tongyi_deepresearch", 
            log_label = "tesmodified:   inference/run_single_inference.pyt"
        )

    asyncio.run(main())