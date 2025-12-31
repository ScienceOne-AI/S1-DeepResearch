import base64
import io
import json
from typing import Dict, Any, List, Tuple
from datetime import datetime

from PIL import Image
from utils.common import today_date
import os

from utils.configs import ONLINE_PLATFORM

def fill_system_slots(system_prompt: str) -> str:

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fixed_toolserver_output_dir = "workspace/agent_eval/log/tool_outputs"
    system_prompt = system_prompt.replace("<CACHE_PATH_PLACEHOLDER>", fixed_toolserver_output_dir)
    system_prompt = system_prompt.replace("<CURRENT_TIME_PLACEHOLDER>", current_time)
    return system_prompt

def build_tool_sigs(tools_mapping: Dict[str, Any]) -> list:
    """
    Build the tool signatures list from a tool registry.
    """
    tool_sigs = build_tongyi_schema(tools_mapping)
    return tool_sigs

def build_tongyi_schema(tools_mapping:dict) -> list:
    return [value['schema_json'] for value in tools_mapping.values()]

def build_openai_schema(tools_mapping) -> list:
    tool_list = []
    for value in tools_mapping.values():
        now_tool = value['schema_json']['function']
        now_tool['type'] = "function"
        tool_list.append(now_tool)
    return tool_list

def build_tools_preamble(tools_mapping) -> str:
    """
    Construct the Tools section as your chat_template renders it when `tools` is provided.
    This is embedded in the system content so the model knows how to call functions.
    """

    if len(tools_mapping) == 0:
        return ""

    tool_sigs = build_tool_sigs(tools_mapping)
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


def build_user_payload(user_query: str, file_path: str, system_format:str) -> str:
    """
    Build the user payload as your chat_template expects.
    The user's query is wrapped as a JSON object with 'query' field, as your system prompt specifies.
    """
    content = [{"type": "text", "text": user_query}]

    if file_path:
        content[0]['text'] += f"""\n\nHere are the necessary files: {file_path}"""

    return content


def build_initial_messages(user_query: str, file_path: str, system: str, system_format: str, tool_mapping:Dict) -> List[Dict[str, str]]:
    """
    Build the initial messages per your system prompt + Tools preamble.
    The user's query is wrapped as a JSON object with 'query' field, as your system prompt specifies.
    """
    
    if system_format == "tongyi_deepresearch":
        system_content = system + str(today_date())  # add current date to system prompt to adjust tongyi's format
    elif system_format in ONLINE_PLATFORM:
        system_content = system
    else:
        system_content = f"{system}{build_tools_preamble(tool_mapping)}".strip()
    user_payload = build_user_payload(user_query, file_path, system_format)
    if "claude" in system_format:
        messages = [
            {"role": "user", "content": user_payload},
        ]
    else:
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_payload},
        ]
    return messages

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