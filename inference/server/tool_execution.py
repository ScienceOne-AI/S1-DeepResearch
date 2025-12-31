from typing import Any, Tuple
import json
import asyncio
from utils.configs import USE_TONGYI_FORMAT_RETURN


async def execute_tool_call(name: str, arguments: Any, all_tools, logger=None) -> Tuple[str, str]:
    """
    Execute a single tool call locally. Returns (tool_name, tool_response_json_str).
    """
    if name == "parse_error_tool_call":
        if USE_TONGYI_FORMAT_RETURN:
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

    func = functools.partial(tool['function'], **arguments)
    if name == "browse_url":
        timeout = 5400 # browse 1.5h
    else:
        timeout = 1800 # other tools 30 mins
    try:
        out = await asyncio.wait_for(loop.run_in_executor(None, func), timeout=timeout)
        result = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
    except asyncio.TimeoutError:
        if USE_TONGYI_FORMAT_RETURN:
            result = f"The tool call timed out: execution exceeded {timeout} seconds for tool '{name}'."
        else:
            result = json.dumps({"error": f"Tool call timeout: exceeded {timeout}s", "tool": name, "arguments": arguments}, ensure_ascii=False)
        if logger:
            logger.error(result)
    except TypeError as te:
        if USE_TONGYI_FORMAT_RETURN:
            result = f"Tool '{name}' failed due to argument mismatch: {str(te)}. Input arguments: {arguments}."
        else:
            result = json.dumps({"error": f"Argument mismatch for tool '{name}': {str(te)}", "received": arguments}, ensure_ascii=False)
        if logger:
            logger.error(result)
    except Exception as e:
        if USE_TONGYI_FORMAT_RETURN:
            result = f"Tool '{name}' encountered an error: {str(e)}."
        else:
            result = json.dumps({"error": f"Tool '{name}' raised an exception: {str(e)}"}, ensure_ascii=False)
        if logger:
            logger.error(result)

    return name, result