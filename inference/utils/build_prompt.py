import base64
import io
import json
import re
from typing import Dict, Any, List, Tuple
from datetime import datetime

from PIL import Image
from server.llm_api import LLMClient
from utils.common import today_date
import os

from utils.configs import ONLINE_PLATFORM
from utils.prompts import SUMMARY_SYSTEM_PROMPT

# 特殊标记如 <CURRENT_TIME_PLACEHOLDER> replace
def fill_system_slots(system_prompt: str) -> str:

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fixed_toolserver_output_dir = "workspace/agent_eval/log/tool_outputs"
    system_prompt = system_prompt.replace("<CACHE_PATH_PLACEHOLDER>", fixed_toolserver_output_dir)
    # 可选：如果 system_prompt 需要插入时间，可以这样：
    system_prompt = system_prompt.replace("<CURRENT_TIME_PLACEHOLDER>", current_time)

    return system_prompt


# 工具构造成 openai 的工具 list 中的形式
def build_tool_sigs(tools_mapping: Dict[str, Any]) -> list:
    """
    Build the tool signatures list from a tool registry.
    """
    tool_sigs = build_tongyi_schema(tools_mapping)
    return tool_sigs

def build_tongyi_schema(tools_mapping:dict) -> list:
    return [value['schema_json'] for value in tools_mapping.values()]

def build_openai_schema(tools_mapping) -> list:
    # openai 和 deep_research 的工具拼接方式还不一样
    tool_list = []
    for value in tools_mapping.values():
        now_tool = value['schema_json']['function']
        now_tool['type'] = "function"
        # now_tool['strict'] = True
        tool_list.append(now_tool)
    return tool_list

# 在 qwen3 原生使用，当前 deep research 不会用到
def build_tools_preamble(tools_mapping) -> str:
    """
    Construct the Tools section as your chat_template renders it when `tools` is provided.
    This is embedded in the system content so the model knows how to call functions.
    """

    if len(tools_mapping) == 0:
        return ""

    tool_sigs = build_tool_sigs(tools_mapping)
    # copy from qwen3's chat_template
    preamble = (
        "\n\n# Tools\n\n"
        "You may call one or more functions to assist with the user query.\n\n"
        "You are provided with function signatures within <tools></tools> XML tags:\n"
        "<tools>\n"
        + "\n".join(json.dumps(sig, ensure_ascii=False) for sig in tool_sigs) +
        "\n</tools>\n\n"
        "For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:\n"
        "<tool_call>\n"
        '{"name": <function-name>, "arguments": <args-json-object>}\n'
        "</tool_call>"
    )
    return preamble

# tool_list 的 json 形式返回
def get_tools_json(tools_mapping) -> str:
    """
    Return the tools signatures as a JSON string.
    """
    tool_sigs = build_tool_sigs(tools_mapping)
    return json.dumps(tool_sigs, ensure_ascii=False)


def image_to_base64(image_path:str) -> str:
    """Convert image to base64 string"""
    buffered = io.BytesIO()
    image = Image.open(image_path)
    image.save(buffered, format="JPEG", quality=85, optimize=True)
    return base64.b64encode(buffered.getvalue()).decode()


# 问题最后添加多模态相关的文件路径描述
def build_user_payload(user_query: str, file_path: List, system_format:str) -> List:
    """
    Build the user payload as your chat_template expects.
    The user's query is wrapped as a JSON object with 'query' field, as your system prompt specifies.
    """
    content = [{"type": "text", "text": user_query}]

    if file_path:
        file_lines = '\n'.join([f"* {str(f)}" for f in file_path])
        content[0]['text'] += f"\n\nHere are the necessary files:\n{file_lines}"

    return content


def _inject_skills_into_system(system_content: str, skill_text: str | None) -> str:
    if not skill_text:
        return system_content
    stripped = skill_text.strip()
    if not stripped:
        return system_content
    block = "\n\n" + stripped
    
    matches = list(re.finditer(r"(?im)^\s*# Note\b", system_content))
    if matches:
        insert_pos = matches[-1].start()
        return system_content[:insert_pos] + block + "\n\n" + system_content[insert_pos:]
    return system_content + block


def build_initial_messages(
    user_query: str,
    file_path: List,
    system: str,
    system_format: str,
    tool_mapping: Dict,
    system_skill_text: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Build the initial messages per your system prompt + Tools preamble.
    The user's query is wrapped as a JSON object with 'query' field, as your system prompt specifies.
    """
    
    if system_format == "deep_research":
        system_content = system + str(today_date())  # add current date to system prompt to adjust deep_research's format
    elif system_format in ONLINE_PLATFORM:
        # 在线的通过传 tool_list 自己拼接，因此不需要手动拼接
        system_content = system
    else:
        system_content = f"{system}{build_tools_preamble(tool_mapping)}".strip()
    system_content = _inject_skills_into_system(system_content, system_skill_text)
    user_payload = build_user_payload(user_query, file_path, system_format)
    if "claude" in system_format:
        # 补一下 system prompt
        user_payload[0]['text'] = system_content + "\n\n" + user_payload[0]['text']
        messages = [
            {"role": "user", "content": user_payload},
        ]
    else:
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_payload},
        ]
    return messages

# 工具结果拼到 user message 里面
def wrap_tool_responses_into_user_message(responses: List[Tuple[str, str]]) -> Dict[str, str]:
    """
    The chat_template expects tool results to appear inside a user turn as multiple
    <tool_response>...</tool_response> blocks.
    """
    blocks = []
    for tool_name, tool_json in responses:
        blocks.append("<tool_response>\n" + tool_json + "\n</tool_response>")
    content = "\n".join(blocks)
    return {"role": "user", "content": content}


async def _build_summary_message(llm: LLMClient, messages: List[Dict[str, Any]], temperature: float, logger, query_id: str="", system_format:str = "deep_research") -> dict:
    if messages[0]['role'] == "system":
        payload_text = json.dumps(messages[1:], ensure_ascii=False, indent=2)
    else:
        payload_text = json.dumps(messages, ensure_ascii=False, indent=2)
    summary_prompt_messages = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": payload_text},
    ]
    summary_resp = {}
    if system_format == "deep_research":
        summary_resp = await llm.chat(summary_prompt_messages, temperature=temperature, logger=logger, query_id=query_id)
        # summary 上下文的信息缓存到 run.log 里面
        logger.info("[summary_resp] %s", summary_resp)
        meta_content = summary_resp['content']
        think_end_tag = "</think>"
        if think_end_tag in meta_content:
            idx = meta_content.index(think_end_tag) + len(think_end_tag)
            summary_resp['content'] = meta_content[idx:].strip()
        else:
            summary_resp['content'] = meta_content.strip()
    elif system_format in ONLINE_PLATFORM:
        if system_format == "azure":
            summary_resp = await llm.azure_chat(summary_prompt_messages, temperature=temperature, logger=logger)
        elif system_format in ["aihubmix", "aihubmix_claude"]:
            summary_resp = await llm.aihubmix_chat(summary_prompt_messages, temperature=temperature, logger=logger)
        elif system_format in ["aihubmix_glm"]:
            summary_resp = await llm.aihubmix_chat(summary_prompt_messages, temperature=temperature, logger=logger)
        elif system_format == "volcano":
            summary_resp = await llm.volcano_chat(summary_prompt_messages, temperature=temperature, logger=logger)
        elif system_format == "aliyun":
            summary_resp = await llm.aliyun_chat(summary_prompt_messages, temperature=temperature, logger=logger)

        logger.info("[summary_resp] %s", summary_resp)
        
        meta_data = summary_resp['meta_data']
        meta_content = meta_data['content']
        think_end_tag = "</think>"
        if think_end_tag in meta_content:
            idx = meta_content.index(think_end_tag) + len(think_end_tag)
            summary_resp['content'] = meta_content[idx:].strip()
        else:
            summary_resp['content'] = meta_content.strip()
    else:
        raise ValueError(f"[system_format={system_format} failed] Please define a function to extract calls like `utils -> extract_schemas -> extract_nlp_tool_calls`")

    summary_text = (summary_resp.get("content") or "").strip()
    if "<summary>" not in summary_text:
        summary_text = f"<summary>\n{summary_text}\n</summary>"
    summary_resp['content'] = summary_text
    return summary_resp
