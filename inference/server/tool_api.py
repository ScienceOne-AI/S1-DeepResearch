import os
import sys

from tool_kits import (
    ExecuteCodeToolkit,
    WideSearchToolkit,
    ScholarSearchToolkit,
    FileWideParseToolkit,
    WideVisitToolkit,
)

from urllib.parse import urljoin
from typing import Callable, Dict, Any

def return_all_tools():
    # initialize all tools (alphabetically sorted)
    tools = {
        "execute_code": ExecuteCodeToolkit(),
        "wide_search": WideSearchToolkit(),
        "scholar_search": ScholarSearchToolkit(),
        "file_wide_parse": FileWideParseToolkit(),
        "wide_visit": WideVisitToolkit(),
    }

    ALL_TOOLS: Dict[str, Dict[str, Any]] = {}


    # for competibility with the old code
    for tool_name, tool in tools.items():
        ALL_TOOLS[tool_name] = {
            "name": tool.name,
            "description": tool.description,
            "strict": True,
            "parameters": tool.params,
            "function": tool.forward,
            "schema_json": tool.json
        }

    return ALL_TOOLS


