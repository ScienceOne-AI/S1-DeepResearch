import json
from typing import List, Dict, Any
import re

def extract_tongyi_tool_calls(text: str) -> List[Dict[str, Any]]:
    """

    Find all <tool_call>...</tool_call> blocks and parse the inner JSON object.
    Returns a list of {"name": str, "arguments": dict} dicts.

    The tool calls are mapped to our tool names using the map_tongyi_tool_to_our_tool function.
    """

    TOOL_CALL_BLOCK_RE = re.compile(
        # r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
        r"<tool_call>\s*(.*?)\s*</tool_call>",
        re.DOTALL | re.IGNORECASE,
    )

    calls = []
    for m in TOOL_CALL_BLOCK_RE.finditer(text or ""):
        block = m.group(1).strip()
        print(f"block: {block}")
        try:
            if "pythoninterpreter" in block.lower():
                code_raw=block.split('<code>')[1].split('</code>')[0].strip()
                calls.append({"name": "execute_code", "arguments": {"code": code_raw}})
            else:
                obj = json.loads(block)
                tool_name = obj.get("name", "")
                tool_arguments = obj.get("arguments", {})

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
                else:
                    raise ValueError(f"Unknown tool name: {tool_name}")

        except Exception as e:
            calls.append({"name": "parse_error_tool_call", "arguments": {"parse_error": str(e), "raw": block}})
        print(f"extract_tool_calls calls: {calls}")
    
    return calls