import json
import os
from typing import List, Dict, Any
import re
import ast

from utils.common import extract_candidate_object, _prefix_files

def extract_aihubmix_tool_calls(text: str, available_tools = [], file_base_dirs: List | None = None, file_prefix = None, prefix_mode = "inference") -> List[Dict[str, Any]]:

    TOOL_CALL_BLOCK_RE = re.compile(
        # r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
        r"<tool_call>\s*(.*?)\s*</tool_call>",  # 匹配整个 tool_call 块，包括其中的 code 标签，而不是只匹配 JSON 对象
        re.DOTALL | re.IGNORECASE,
    )

    calls = []

    if len(available_tools) == 0:
        return calls 

    tool_names = [value['name'] for key, value in available_tools.items()] # 废弃

    for m in TOOL_CALL_BLOCK_RE.finditer(text or ""):
        block = m.group(1).strip()
        print(f"<tool_call> block: {block}")
        try:
            obj = extract_candidate_object(block)
            tool_name = obj.get("name", "")
            tool_arguments = obj.get("arguments", {})

            # 列表形式的搜索
            if tool_name == "search":
                search_query = tool_arguments.get('query', None)    
                if search_query is None:
                    raise ValueError(f"query is not found in the tool arguments: {tool_arguments}")
                if isinstance(search_query, list) or isinstance(search_query, str):
                    calls.append({"name": "wide_search", "arguments": {"query": search_query}})
                else:
                    raise ValueError(f"Unknown query type: {type(search_query)}")
            # 列表形式的谷歌搜索
            elif tool_name == "google_scholar":
                search_query = tool_arguments.get('query', None)    
                if search_query is None:
                    raise ValueError(f"query is not found in the tool arguments: {tool_arguments}")
                if isinstance(search_query, list) or isinstance(search_query, str):
                    calls.append({"name": "scholar_search", "arguments": {"query": search_query}})
                else:
                    raise ValueError(f"Unknown query type: {type(search_query)}")
            # visit 列表形式
            elif tool_name == "visit":
                visit_goal = tool_arguments.get('goal', None)
                visit_url = tool_arguments.get('url', None)
                if visit_goal is None:
                    raise ValueError(f"goal is not found in the tool arguments: {tool_arguments}")
                if visit_url is None:
                    raise ValueError(f"url is not found in the tool arguments: {tool_arguments}")   

                if isinstance(visit_url, list) or isinstance(visit_url, str):
                    calls.append({"name": "wide_visit", "arguments": {"url": visit_url, "goal": visit_goal}})
                else:
                    raise ValueError(f"Unknown url type: {type(visit_url)}")
            # 文件解析 列表形式
            elif tool_name == "parse_file":
                files = tool_arguments.get('files', None)
                if files is None:
                    raise ValueError(f"files is not found in the tool arguments: {tool_arguments}")
                if isinstance(files, list) or isinstance(files, str):
                    calls.append(
                        {
                            "name": "file_wide_parse",
                            "arguments": {"files": _prefix_files(file_base_dirs, files, file_prefix, prefix_mode)},
                        }
                    )
                else:
                    raise ValueError(f"Unknown url type: {type(files)}")
            # 图像搜索
            elif tool_name == "image_search":
                search_query = tool_arguments.get('query', None)
                if search_query is None:
                    raise ValueError(f"query is not found in the tool arguments: {tool_arguments}")
                if isinstance(search_query, list) or isinstance(search_query, str):
                    calls.append({"name": "image_search", "arguments": {"query": search_query}})
                else:
                    raise ValueError(f"Unknown query type: {type(search_query)}")
            # 图像问答
            elif tool_name == "ask_question_about_image":
                image_path = tool_arguments.get("image_path", None)
                question = tool_arguments.get("question", None)
                if image_path is None:
                    raise ValueError(f"image_path is not found in the tool arguments: {tool_arguments}")
                if question is None:
                    raise ValueError(f"question is not found in the tool arguments: {tool_arguments}")
                if (isinstance(image_path, str) or isinstance(image_path, list)) and isinstance(question, str):
                    calls.append(
                        {
                            "name": "ask_question_about_image",
                            "arguments": {"image_path": _prefix_files(file_base_dirs, image_path, file_prefix, prefix_mode), "question": question},
                        }
                    )
                else:
                    raise ValueError(
                        f"Unknown image_path/question type: "
                        f"image_path({type(image_path)}), question({type(question)})"
                    )
            # 视频问答
            elif tool_name == "ask_question_about_video":
                video_path = tool_arguments.get("video_path", None)
                question = tool_arguments.get("question", None)
                if video_path is None:
                    raise ValueError(f"video_path is not found in the tool arguments: {tool_arguments}")
                if question is None:
                    raise ValueError(f"question is not found in the tool arguments: {tool_arguments}")
                if (isinstance(video_path, str) or isinstance(video_path, list)) and isinstance(question, str):
                    calls.append(
                        {
                            "name": "ask_question_about_video",
                            "arguments": {"video_path": _prefix_files(file_base_dirs, video_path, file_prefix, prefix_mode), "question": question},
                        }
                    )
                else:
                    raise ValueError(
                        f"Unknown video_path/question type: "
                        f"video_path({type(video_path)}), question({type(question)})"
                    )
            elif tool_name == "execute_code":
                code = tool_arguments.get('code', None)
                if code is None:
                    raise ValueError(f"code is not found in the tool arguments: {tool_arguments}")
                code_lines = code.splitlines()
                clean_lines = [""]
                for line in code_lines:
                    stripped = line.strip()
                    if not (
                        stripped.startswith('```python ,') or
                        stripped.startswith('```python,') or
                        stripped.startswith('```python') or
                        stripped.startswith('```') or
                        stripped.startswith('<code>') or
                        stripped.startswith('</code>')
                    ):
                        clean_lines.append(line)
                code_raw = "\n".join(clean_lines).strip()
                calls.append({"name": "execute_code", "arguments": {"code": code_raw}})
            elif tool_name == "browse_url":
                task_prompt = tool_arguments.get('task_prompt', None)
                start_url = tool_arguments.get('start_url', None)
                round_limit = tool_arguments.get('round_limit', 12)
                if task_prompt is None:
                    raise ValueError(f"task_prompt is not found in the tool arguments: {tool_arguments}")
                if start_url is None:
                    raise ValueError(f"start_url is not found in the tool arguments: {tool_arguments}")

                if isinstance(task_prompt, str) and isinstance(start_url, str):
                    calls.append({"name": "browse_url", "arguments": {"start_url": start_url, "task_prompt": task_prompt, "round_limit": round_limit}})
                else:
                    raise ValueError(
                        f"Unknown url or task_prompt type in browse_url tool: "
                        f"start_url({start_url}, type={type(start_url)}), "
                        f"task_prompt({task_prompt}, type={type(task_prompt)}). "
                    )
            elif tool_name == "bash":
                command = tool_arguments.get("command", None)
                if command is None:
                    raise ValueError(f"command is not found in the tool arguments: {tool_arguments}")
                if not isinstance(command, str):
                    raise ValueError(f"Unknown command type: {type(command)}")
                calls.append({"name": "bash", "arguments": {"command": command}})
            


        except Exception as e:
            calls.append({"name": "parse_error_tool_call", "arguments": {"parse_error": str(e), "raw": block}})
        print(f"extract_tool_calls calls: {calls}")
    
    return calls
