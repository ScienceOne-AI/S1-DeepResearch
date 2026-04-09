import os
import sys

from tool_kits import (
    AskQuestionAboutImageToolkit,
    AskQuestionAboutVideoToolkit,
    ExecuteCodeToolkit,
    WideSearchToolkit,
    ImageSearchToolkit,
    ScholarSearchToolkit,
    FileWideParseToolkit,
    WideVisitToolkit,
    BashToolkit,
)

from urllib.parse import urljoin
from typing import Callable, Dict, Any

# 基于 docker 的所有工具
def return_all_tools(tool_urls=None, use_cache=None, use_tongyi_format=None):
    # initialize all tools (alphabetically sorted)
    # 后续根据 key 找到实际调用的是哪个工具
    tool_kwargs = {}
    if tool_urls is not None:
        tool_kwargs["server_url"] = tool_urls
    if use_cache is not None:
        tool_kwargs["use_cache"] = use_cache
    if use_tongyi_format is not None:
        tool_kwargs["is_tongyi_format"] = use_tongyi_format

    # 只有需要 deep_research format 才能传 **tool_kwargs
    tools = {
        "ask_question_about_image": AskQuestionAboutImageToolkit(),
        "ask_question_about_video": AskQuestionAboutVideoToolkit(),
        "execute_code": ExecuteCodeToolkit(),
        "wide_search": WideSearchToolkit(**tool_kwargs),
        "image_search": ImageSearchToolkit(**tool_kwargs),
        "scholar_search": ScholarSearchToolkit(**tool_kwargs),
        "file_wide_parse": FileWideParseToolkit(**tool_kwargs),
        "wide_visit": WideVisitToolkit(**tool_kwargs),
        "bash": BashToolkit(),
    }

    ALL_TOOLS: Dict[str, Dict[str, Any]] = {}


    # for competibility with the old code
    for tool_name, tool in tools.items():
        ALL_TOOLS[tool_name] = {
            "name": tool.name,
            "description": tool.description,
            "strict": True,
            "parameters": tool.params,
            "function": tool.forward, # 工具执行函数
            "schema_json": tool.json
        }

    return ALL_TOOLS

