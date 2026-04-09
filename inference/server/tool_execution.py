from typing import Any, Tuple
import json
import asyncio
import os
import uuid
import importlib.util
from pathlib import Path
from utils.configs import USE_NLP_FORMAT_RETURN


async def execute_tool_call(name: Any, arguments: Any, all_tools, logger=None, USE_NLP_FORMAT_RETURN: bool | None = None, query_id = "") -> Tuple[str, str]:
    """
    Execute a single tool call locally. Returns (tool_name, tool_response_json_str).
    """
    if USE_NLP_FORMAT_RETURN is None:
        USE_NLP_FORMAT_RETURN = USE_NLP_FORMAT_RETURN
    if name == "parse_error_tool_call":
        if USE_NLP_FORMAT_RETURN:
            result = f"Error: Tool call is not a valid JSON. Tool call must contain a valid \"name\" and \"arguments\" field. Parse error: {arguments.get('parse_error', '')}"
        else:
            result = json.dumps({"error": f"Parse error: {arguments.get('parse_error', '')}", "raw": arguments.get('raw', '')}, ensure_ascii=False)
        if logger:
            logger.error(result)
        return name or "parse_error_tool_call", result

    tool = all_tools.get(name)
    if tool is None:
        result = json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
        if logger:
            logger.error(result)
        return name or "unknown", result

    # Ensure arguments is a dict
    if not isinstance(arguments, dict):
        arguments = {"_": arguments}

    import functools
    loop = asyncio.get_running_loop()
    
    arguments["conversation_id"] = query_id

    func = functools.partial(tool['function'], **arguments)
    # 根据工具名称选择不同的超时时间
    if name == "browse_url":
        timeout = 5400 # browse 是 1.5 小时
    else:
        timeout = 1800 # 其他工具就是 30 分钟
    try:
        out = await asyncio.wait_for(loop.run_in_executor(None, func), timeout=timeout)
        result = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False) # 返回结果一定是字符串
    except asyncio.TimeoutError:
        if USE_NLP_FORMAT_RETURN:
            result = f"The tool call timed out: execution exceeded {timeout} seconds for tool '{name}'."
        else:
            result = json.dumps({"error": f"Tool call timeout: exceeded {timeout}s", "tool": name, "arguments": arguments}, ensure_ascii=False)
        if logger:
            logger.error(result)
    except TypeError as te:
        if USE_NLP_FORMAT_RETURN:
            result = f"Tool '{name}' failed due to argument mismatch: {str(te)}. Input arguments: {arguments}."
        else:
            result = json.dumps({"error": f"Argument mismatch for tool '{name}': {str(te)}", "received": arguments}, ensure_ascii=False)
        if logger:
            logger.error(result)
    except Exception as e:
        if USE_NLP_FORMAT_RETURN:
            result = f"Tool '{name}' encountered an error: {str(e)}."
        else:
            result = json.dumps({"error": f"Tool '{name}' raised an exception: {str(e)}"}, ensure_ascii=False)
        if logger:
            logger.error(result)

    return name, result
