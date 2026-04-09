import ast
import json
import os
from typing import List, Dict, Any
import re

from utils.common import extract_candidate_object, _prefix_files


def extract_nlp_tool_calls(text: str, file_base_dirs: List | None = None, file_prefix = None, prefix_mode = "inference") -> List[Dict[str, Any]]:

    TOOL_CALL_BLOCK_RE = re.compile(
        r"<tool_call>\s*(.*?)\s*</tool_call>",  # 匹配整个 tool_call 块，包括其中的 code 标签，而不是只匹配 JSON 对象
        re.DOTALL | re.IGNORECASE,
    )

    calls = []
    for m in TOOL_CALL_BLOCK_RE.finditer(text or ""):
        block = m.group(1).strip()
        print(f"<tool_call> block: {block}")
        try:
            # 代码
            if "pythoninterpreter" in block.lower():
                try:
                    # 找到 "pythoninterpreter" 这一行，从这一行之后作为 code_block
                    lines = block.splitlines()
                    # 找到含有 'pythoninterpreter' 的行号
                    start = None
                    for i, line in enumerate(lines):
                        if "pythoninterpreter" in line.lower():
                            start = i
                            break
                    if start is not None:
                        code_block = "\n".join(lines[start+1:])
                    else:
                        code_block = ""
                except Exception as e:
                    code_block = ""
                # 删除以 "```python ," 或 "```python," 或 "```python" 或 "```" 开头的行
                code_lines = code_block.splitlines()
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
            elif "bash" in block.lower():
                try:
                    lines = block.splitlines()
                    start = None
                    for i, line in enumerate(lines):
                        if "bash" in line.lower():
                            start = i
                            break
                    if start is not None:
                        code_block = "\n".join(lines[start+1:])
                    else:
                        code_block = ""
                except Exception as e:
                    code_block = ""
                code_lines = code_block.splitlines()
                clean_lines = [""]
                # bash 工具
                for line in code_lines:
                    stripped = line.strip()
                    if not (
                        stripped.startswith('```bash ,') or
                        stripped.startswith('```bash,') or
                        stripped.startswith('```bash') or
                        stripped.startswith('```') or
                        stripped.startswith('<bash>') or
                        stripped.startswith('</bash>')
                    ):
                        clean_lines.append(line)
                code_raw = "\n".join(clean_lines).strip()
                calls.append({"name": "bash", "arguments": {"command": code_raw}})
            else:
                obj = extract_candidate_object(block)
                tool_name = obj.get("name", "")
                tool_arguments = obj.get("arguments", {})
                # 模型有时会将 arguments 序列化为字符串，兼容处理
                if isinstance(tool_arguments, str):
                    try:
                        tool_arguments = json.loads(tool_arguments)
                    except Exception:
                        try:
                            import json5
                            tool_arguments = json5.loads(tool_arguments)
                        except Exception:
                            tool_arguments = {}

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
                elif tool_name in ("execute_code", "python_interpreter"):
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
                else:
                    raise ValueError(f"Unknown tool name: {tool_name}")

        except Exception as e:
            calls.append({"name": "parse_error_tool_call", "arguments": {"parse_error": str(e), "raw": block}})
        print(f"extract_tool_calls calls: {calls}")
    
    return calls
