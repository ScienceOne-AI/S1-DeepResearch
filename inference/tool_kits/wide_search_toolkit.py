import yaml
import os
import sys
from urllib.parse import urljoin
from typing import Callable, Dict, Any
from utils.configs import TOOLS_SERVER_BASE_ENDPOINT_URL, USE_TONGYI_FORMAT_RETURN, WEB_BASED_TOOLS_USE_CACHE
from tool_kits.base import BaseToolkit


class WideSearchToolkit(BaseToolkit):
    NAME = "search"
    TOOLS_SERVER_BASE_ENDPOINT = TOOLS_SERVER_BASE_ENDPOINT_URL
    ENTRY_POINT = "wide_search"
    DESCRIPTION = f"Performs batched web searches: supply an array 'query'; the tool retrieves the top 10 results for each query in one call."
    TIMEOUT = 600
    TOOL_PARAMS = {
        "query": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "Array of query strings. Include multiple complementary search queries in a single call."
        },
    }
    TOOL_PARAMS_REQUIRED = ["query"]
    USE_CACHE = WEB_BASED_TOOLS_USE_CACHE
    USE_TONGYI_FORMAT = USE_TONGYI_FORMAT_RETURN