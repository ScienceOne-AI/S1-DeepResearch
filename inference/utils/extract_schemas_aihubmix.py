import json
from typing import List, Dict, Any
import re
import ast

def extract_aihubmix_tool_calls(text: str, available_tools = []) -> List[Dict[str, Any]]:
    TOOL_CALL_BLOCK_RE = re.compile(
        # r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
        r"<tool_call>\s*(.*?)\s*</tool_call>", 
        re.DOTALL | re.IGNORECASE,
    )

    calls = []

    if len(available_tools) == 0:
        return calls 

    tool_names = [value['name'] for key, value in available_tools.items()]

    for m in TOOL_CALL_BLOCK_RE.finditer(text or ""):
        block = m.group(1).strip()
        print(f"block: {block}")
        try:
            try:
                obj = json.loads(block)
            except:
                obj = ast.literal_eval(block)
            tool_name = obj.get("name", "")
            tool_arguments = obj.get("arguments", {})

            if tool_name not in tool_names:
                raise ValueError(f"Unknown tool name: {tool_name}")

            if tool_name == "search":
                search_query = tool_arguments.get('query', None)    
                if search_query is None:
                    raise ValueError(f"query is not found in the tool arguments: {tool_arguments}")
                if isinstance(search_query, list) or isinstance(search_query, str):
                    calls.append({"name": "wide_search", "arguments": {"query": search_query}})
                else:
                    raise ValueError(f"Unknown query type: {type(search_query)}")
            elif tool_name == "google_scholar":
                search_query = tool_arguments.get('query', None)    
                if search_query is None:
                    raise ValueError(f"query is not found in the tool arguments: {tool_arguments}")
                if isinstance(search_query, list) or isinstance(search_query, str):
                    calls.append({"name": "scholar_search", "arguments": {"query": search_query}})
                else:
                    raise ValueError(f"Unknown query type: {type(search_query)}")
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
            elif tool_name == "parse_file":
                files = tool_arguments.get('files', None)
                if files is None:
                    raise ValueError(f"files is not found in the tool arguments: {tool_arguments}")
                if isinstance(files, list) or isinstance(files, str):
                    calls.append({"name": "file_wide_parse", "arguments": {"files": files}})
                else:
                    raise ValueError(f"Unknown url type: {type(files)}")
            elif tool_name == "execute_code":
                code = tool_arguments.get('code', None)
                if code is None:
                    raise ValueError(f"code is not found in the tool arguments: {tool_arguments}")
                calls.append({"name": "execute_code", "arguments": {"code": code}})
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
        except Exception as e:
            calls.append({"name": "parse_error_tool_call", "arguments": {"parse_error": str(e), "raw": block}})
        print(f"extract_tool_calls calls: {calls}")
    
    return calls