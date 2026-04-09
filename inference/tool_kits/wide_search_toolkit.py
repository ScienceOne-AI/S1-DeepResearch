import yaml
import os
import sys
from urllib.parse import urljoin
from typing import Callable, Dict, Any
from utils.configs import TOOLS_SERVER_BASE_ENDPOINT_URL, USE_NLP_FORMAT_RETURN, WEB_BASED_TOOLS_USE_CACHE
from tool_kits.base import BaseToolkit


class WideSearchToolkit(BaseToolkit):
    NAME = "search"
    TOOLS_SERVER_BASE_ENDPOINT = TOOLS_SERVER_BASE_ENDPOINT_URL
    ENTRY_POINT = "wide_search"
    DESCRIPTION = f"Perform Google web searches then returns a string of the top search results. Accepts multiple queries."
    TIMEOUT = 600
    TOOL_PARAMS = {
        "query": {
            "type": "array",
            "items": {
                "type": "string",
                "description": "The search query.",
            },
            "minItems": 1,
            "description": "The list of search queries.",
        },
    }
    TOOL_PARAMS_REQUIRED = ["query"]
    USE_CACHE = WEB_BASED_TOOLS_USE_CACHE
    USE_TONGYI_FORMAT = USE_NLP_FORMAT_RETURN
