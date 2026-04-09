import asyncio
import copy
import logging
import sys
import os
import time
import datetime
import json



# 获取项目根目录路径，并加入 sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from typing import Any, Dict, List, Tuple
from anyio import Path

from server.llm_api import LLMClient
from server.tool_api import return_all_tools
from server.tool_execution import execute_tool_call
from utils.configs import LITERATURE_SEED_DATA_DIR, ONLINE_PLATFORM

from utils.build_prompt import (
    _build_summary_message,
    build_initial_messages,
    build_openai_schema,
    build_tongyi_schema,
    build_user_payload,
    get_tools_json,
    wrap_tool_responses_into_user_message,
)
from utils.common import _estimate_message_tokens, count_tokens, get_query_uuid
from utils.extract_schemas_nlp import extract_nlp_tool_calls # 更新工具读取逻辑
from utils.extract_schemas_online import extract_aihubmix_tool_calls # 新增 aihubmix 的工具读取逻辑
from utils.logger import save_result_to_log_dir, setup_logger_for_query  # 新增：用于结果的json序列化
from utils.skill_prompt import normalize_skill_dir_path

# 读取 json 文件，对于每一行 qa 执行任务
async def run_one_query(
    llm: LLMClient,
    user_query: str,
    file_path: List,
    system: str,
    max_rounds: int,
    temperature: float,
    top_p: float = 0.95,
    extra_payload: dict = {},
    debug: bool = False,
    args=None,
    progress: dict = {},  # 新增参数
    all_tools: Dict = {},
    system_format: str = "deep_research", 
    log_label:str = "",
    file_prefix:str = "",
    discard_all_mode: bool = False,
    model_max_context_tokens: int = 128000,
    discard_ratio: float = 0.8,
    tokenizer_path: str = "models/tokenizer",
    logging_root=None,
    skill_source_dirs: List[str] | None = None,
    system_skill_text: str | None = None,
    # 默认采用 deep_research 的 system_format，如果是其他模型，就采用 system + tool_list_shcema 的形式拼接
) -> List[Dict[str, Any]]:
    """
    Run a complete multi-step tool-calling session until the model stops calling tools
    or max_rounds is reached. Returns a dict with the transcript and final answer.
    """
    query_id = get_query_uuid(user_query) + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    
    project_root = logging_root if logging_root else PROJECT_ROOT

    logger, log_file_path = setup_logger_for_query(query_id, project_root, log_label)
    if debug:
        print(f"[run_single_inference.py] Logging configured. Query log file: {log_file_path}")

    def copy_file_to_docker_path(file_paths:List) -> List:
        """
        文件存在性检查和文件拷贝
        将文件拷贝到挂载到 docker 内部的路经下，然后返回文件名称
        e.g.  
        处理过程：/test/test_file.jsonl -> /LITERATURE_SEED_DATA_DIR/log_label/query_id/test_file.jsonl
        返回内容：[test_file.jsonl]

        同时，skills 文件也会检测，如果满足存在 skills/skill_name 的 skill，就会把它拷贝到 data/{log_label}/{query_id} 文件夹下面
        """
        file_names = []
        dest_dir = f"data/{log_label}/{query_id}"
        os.makedirs(dest_dir, exist_ok=True)
        for fp in file_paths:
            if fp:
                if os.path.isfile(fp):
                    logger.info(f"[File load] Get file `{fp}` for id={id}, query_id={query_id}")
                    dest_path = os.path.join(dest_dir, Path(fp).name)
                    try:
                        import shutil
                        shutil.copy2(fp, dest_path)
                        logger.info(f"[File copy] Copied file to `{dest_path}`")
                    except Exception as e:
                        logger.error(f"[File copy error] Failed to copy file `{fp}` to `{dest_path}`: {e}")
                    file_names.append(Path(fp).name)
                else:
                    logger.warning(f"File not found for id={id}, query_id={query_id}: expected {fp}")

        copied_skill_dirs = set()
        for skill_dir in (skill_source_dirs or []):
            if not skill_dir:
                continue
            abs_skill_dir = skill_dir if os.path.isabs(skill_dir) else os.path.join(PROJECT_ROOT, skill_dir)
            if os.path.isfile(abs_skill_dir) and os.path.basename(abs_skill_dir) == "SKILL.md":
                abs_skill_dir = os.path.dirname(abs_skill_dir)
            if not os.path.isdir(abs_skill_dir):
                logger.warning(f"[Skill copy] Skill abs_skill_dir not found: {abs_skill_dir}")
                continue
            normalized_skill_dir = normalize_skill_dir_path(abs_skill_dir)
            rel_after_skills = normalized_skill_dir
            if rel_after_skills.startswith("skills/"):
                rel_after_skills = rel_after_skills[len("skills/"):]
            if not rel_after_skills:
                logger.warning(f"[Skill copy] Skill rel_after_skills not found: {rel_after_skills}")
                # 说明这个 skill 不存在呗，那也需要 continue
                continue
            dest_skill_dir = os.path.join(dest_dir, "skills", rel_after_skills)
            if dest_skill_dir in copied_skill_dirs:
                continue
            copied_skill_dirs.add(dest_skill_dir)
            try:
                import shutil
                shutil.copytree(abs_skill_dir, dest_skill_dir, dirs_exist_ok=True)
                logger.info(f"[Skill copy] Copied skill dir `{abs_skill_dir}` -> `{dest_skill_dir}`")
            except Exception as e:
                logger.error(f"[Skill copy error] Failed to copy skill dir `{abs_skill_dir}` -> `{dest_skill_dir}`: {e}")
        # 若 file_names 为空，则传空字符串，否则传列表
        send_file_path = file_names if file_names else []
        
        return send_file_path

    # 将文件拷贝至 docker 内部
    file_path = copy_file_to_docker_path(file_path)
    # 定义 file_prefix 前缀，用于 ask_xxx, parse_file 等工具能够找到这个附件文件在哪
    file_prefix = os.path.join(LITERATURE_SEED_DATA_DIR, log_label, query_id)

    messages = build_initial_messages(
        user_query,
        file_path,
        system=system,
        system_format=system_format,
        tool_mapping=all_tools,
        system_skill_text=system_skill_text,
    )
    processed_system_start = copy.deepcopy(messages[0])
    # 找到 messages 中第一个 role 为 user 的 dict
    processed_user_start = next((copy.deepcopy(msg) for msg in messages if msg.get('role') == 'user'), None)
    if processed_user_start is None:
        processed_user_start = {"role": "user", "content": user_query}
    transcript: List[Dict[str, Any]] = list(messages)  # shallow copy
    result_objs: List[Dict[str, Any]] = []
    discard_count = 0
    discard_threshold = int(model_max_context_tokens * discard_ratio)

    # For json log
    log_messages: List[Dict[str, Any]] = []
    # Add system and user
    log_messages.append({"role": "system", "content": system}) # 没有把动态的拼接回去，原始的 system prompt
    log_messages.append({"role": "user", "content": build_user_payload(user_query, file_path, system_format)})

    round_idx = 1
    while round_idx <= max_rounds:
        tmp_token_numbers = _estimate_message_tokens(log_messages, tokenizer_path)
        if discard_all_mode and _estimate_message_tokens(log_messages, tokenizer_path) >= discard_threshold:
            print(f"当前 token 数量：{tmp_token_numbers} > 阈值：{discard_threshold}...")
            discard_count += 1
            summary_dict = await _build_summary_message(llm, messages, temperature, logger, query_id, system_format)
            discard_marker = {
                "role": "assistant",
                "content": '<tool_call>{"name": "new_context_tool", "arguments": {"begin_new_context": True}}</tool_call>',
            }
            discard_tool_result = {"role": "tool", "content": summary_dict['content'], "usage": summary_dict['usage']}
            discard_tool_result_for_transcript = {"role": "user", "content": f"{summary_dict['content']}", "usage": summary_dict['usage']}
            discard_follow_up = {"role": "assistant", "content": "Start new conversation to continue the task..."}
            discard_log_messages = copy.deepcopy(log_messages) + [discard_marker, discard_tool_result, discard_follow_up]
            # discard_transcript 中 role: tool 需要替换成 user
            discard_transcript = copy.deepcopy(transcript) + [discard_marker, discard_tool_result_for_transcript, discard_follow_up]
            discard_result = {
                "query_id": query_id,
                "tools": get_tools_json(all_tools) if all_tools is not None else "[]",
                "messages": discard_log_messages,
                "final_answer": discard_follow_up["content"],
                "transcript": discard_transcript,
                "rounds": round_idx,
                "stopped_reason": f"discard_all_{discard_count:02d}",
            }
            result_objs.append(discard_result)
            if progress is not None:
                progress["result"] = copy.deepcopy(result_objs)
            # 兜底，上下文还是在 summary 的时候爆了（导致 summary_dict['content'] 为空)，回退到 user query
            summary_start = {"role": "user", "content": summary_dict['content'] if summary_dict['content'] else processed_user_start['content']}
            if not summary_dict['content']:
                logger.info(f"Summary failed due to exceeding max context length, fallback to user query: {processed_user_start['content']}")
            log_system_start = {"role": "system", "content": system}
            transcript = copy.deepcopy([processed_system_start, summary_start] if processed_system_start['role'] == 'system' else [summary_start])
            log_messages = copy.deepcopy([log_system_start, summary_start])
            # fix: messages 没有改，所以后续长度还在不断增加，messages 也需要重置
            messages = copy.deepcopy([processed_system_start, summary_start] if processed_system_start['role'] == 'system' else [summary_start])
            # 同时 round_idx 也需要重置
            round_idx = 1
            continue

        llm_start = time.time()
        logger.info(f"[round {round_idx}] Round {round_idx} starting...")
        tool_call_ids = [] # 用于在线平台的 tool_id 记录
        # 不同的调用方式采用不同的 chat，tongyi 不需要传入 tool_list，aihubmix 需要把 aihubmix_chat 传入
        response = {}
        if system_format == "deep_research":
            response = await llm.chat(messages, temperature=temperature, top_p=top_p, extra_payload=extra_payload, logger=logger, query_id=query_id)
            assistant_text = response['content']
            usage = response['usage']
            if debug and response['error']:
                logger.info(f"[round {round_idx}] llm.chat error: {response['error']}")
            llm_elapsed_time = time.time() - llm_start
            # 修复用于部分模型的输出中已经预制了 <think>，我们需要将它补全
            assistant_fix_prefix_think_text = assistant_text if assistant_text.lstrip().startswith("<think>") else "<think>\n" + assistant_text.lstrip()
            transcript.append({"role": "assistant", "content": assistant_fix_prefix_think_text, "elapsed_time": llm_elapsed_time, "usage": usage})
            log_messages.append({"role": "assistant", "content": assistant_text, "elapsed_time": llm_elapsed_time, "usage": usage})
            tool_calls = extract_nlp_tool_calls(assistant_text, file_prefix=file_prefix, prefix_mode="benchmark")
        elif system_format in ONLINE_PLATFORM:
            if system_format == "azure":
                response = await llm.azure_chat(messages, temperature=temperature, tool_list=build_openai_schema(all_tools), logger=logger, query_id=query_id)
            elif system_format in ["aihubmix", "aihubmix_claude"]:
                response = await llm.aihubmix_chat(messages, temperature=temperature, tool_list=build_openai_schema(all_tools), logger=logger, query_id=query_id)
            elif system_format in ["aihubmix_glm"]:
                response = await llm.aihubmix_chat(messages, temperature=temperature, tool_list=build_tongyi_schema(all_tools), logger=logger, query_id=query_id)
            elif system_format == "volcano":
                response = await llm.volcano_chat(messages, temperature=temperature, tool_list=build_tongyi_schema(all_tools), logger=logger, query_id=query_id)
            elif system_format == "aliyun":
                response = await llm.aliyun_chat(messages, temperature=temperature, tool_list=build_tongyi_schema(all_tools), logger=logger, query_id=query_id)

            usage = response['usage']
            messages = response['next_messages'] # 带 openai 类的下一次 message，用于回传给在线平台（和平台交互用）
            now_log_messages =  response['log_messages'] # 带 openai 类的下一次 message，本地记录，会把一些耗时等信息也打印到 dict 里面（本地落盘用）
            tool_call_ids = response['tool_call_ids']
            meta_data = response['meta_data'] # 人工拼接的形成的 {"role":"...", "content": "..."}
            llm_elapsed_time = time.time() - llm_start
            
            if debug and 'error' in response:
                logger.info(f"[round {round_idx}] llm.chat error: {response['error']}")
            
            transcript.append({**meta_data, "elapsed_time": llm_elapsed_time, "usage": usage})
            log_messages.extend(now_log_messages)
            tool_calls = extract_aihubmix_tool_calls(meta_data['content'], all_tools, file_prefix=file_prefix, prefix_mode="benchmark")
            assistant_text = meta_data['content']
        else:
            raise ValueError(f"[system_format={system_format} failed] Please define a function to extract calls like `utils -> extract_schemas -> extract_nlp_tool_calls`")

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

        # 新增：每轮都更新 progress['result']
        if progress is not None:
            progress['result'] = copy.deepcopy(result_objs + [result_obj])

        #如果没有工具调用就到这里为止停止调用了
        if not tool_calls:
            logger.info("[run_one_query] Stopping: no tool calls in round %d", round_idx)
            result_obj["stopped_reason"] = "discard_all_final" if discard_count > 0 else "no_tool_calls"
            result_objs.append(result_obj)
            # 保存最终结果到logs_base_dir
            save_result_to_log_dir(query_id, result_objs, project_root, log_label)
            return result_objs


        # Execute all tool calls sequentially for this assistant turn (the model may emit multiple).
        responses: List[Tuple[str, str]] = []
        tool_total_time = 0.0
        for idx, call in enumerate(tool_calls):
            name = call.get("name")
            args = call.get("arguments", {})
            tool_start = time.time()
            resp = await execute_tool_call(name, args, all_tools, logger, None, f"{log_label}/{query_id}") # fix 传递的 conversation id 和 skill 上传的路径一致，这样子才能够找到对应的文件
            tool_elapsed = time.time() - tool_start
            tool_total_time += tool_elapsed
            responses.append(resp)
            # Log each tool response as a message
            if system_format in ONLINE_PLATFORM:
                tool_response = {}
                if system_format in ["azure", "aihubmix"]:
                    tool_response = {
                        "type": "function_call_output",  
                        "call_id": tool_call_ids[idx], # 在线平台需要和 工具 id 绑定
                        "output": resp[1], # 工具执行结果
                    }
                elif system_format in ["aihubmix_claude"]:
                    tool_response = {
                        "role": "user",
                        "content": [{
                            "type": "tool_result",  
                            "tool_use_id": tool_call_ids[idx], # 在线平台需要和 工具 id 绑定
                            "content": resp[1], # 工具执行结果
                        }]
                    }
                elif system_format in ["volcano", "aihubmix_glm"]:
                    tool_response = {
                        "role": "tool",
                        "tool_call_id": tool_call_ids[idx], # 在线平台需要和 工具 id 绑定
                        "content": resp[1], # 工具执行结果
                    }
                elif system_format in ["aliyun"]:
                    tool_response = {
                        "role": "tool",
                        "tool_call_id": tool_call_ids[idx], # 在线平台需要和 工具 id 绑定
                        "content": resp[1], # 工具执行结果
                    }
                messages.append(copy.deepcopy(tool_response))
                tool_response["elapsed_time"] = tool_elapsed # 这个参数不能传进去
                log_messages.append(tool_response)
            else:
                log_messages.append({"role": "tool", "content": resp[1], "elapsed_time": tool_elapsed})
        # Feed tool responses back as a single 'user' message (matching the template behavior)
        tool_user_msg = wrap_tool_responses_into_user_message(responses)
        if system_format not in ONLINE_PLATFORM:
            messages.extend([{"role": "assistant", "content": assistant_text}, tool_user_msg])

        transcript.extend([tool_user_msg])
        round_idx += 1

    # If we get here, we hit the max rounds without a clean finish
    logger.info("[run_one_query] Max rounds (%d) exceeded for query: %s", max_rounds, user_query)

    result_obj = {
        "query_id": query_id,
        "tools": get_tools_json(all_tools) if all_tools is not None else "[]",
        "messages": copy.deepcopy(log_messages),
        "final_answer": transcript[-1]["content"] if transcript else "",
        "transcript": copy.deepcopy(transcript),
        "rounds": max_rounds,
        "stopped_reason": "discard_all_final" if discard_count > 0 else "max_rounds_exceeded"
    }
    if progress is not None:
        progress['result'] = copy.deepcopy(result_objs + [result_obj])
    result_objs.append(result_obj)
    # 保存最终结果到logs_base_dir
    save_result_to_log_dir(query_id, result_objs, project_root, log_label)
    return result_objs
