import yaml
import os
import sys
from urllib.parse import urljoin
from typing import Callable, Dict, Any
from utils.configs import TOOLS_SERVER_BASE_ENDPOINT_URL, USE_TONGYI_FORMAT_RETURN, WEB_BASED_TOOLS_USE_CACHE
from tool_kits.base import BaseToolkit


class ScholarSearchToolkit(BaseToolkit):
    NAME = "google_scholar"
    TOOLS_SERVER_BASE_ENDPOINT = TOOLS_SERVER_BASE_ENDPOINT_URL
    ENTRY_POINT = "scholar_search"
    DESCRIPTION = f"Leverage Google Scholar to retrieve relevant information from academic publications. Accepts multiple queries."
    TIMEOUT = 600
    TOOL_PARAMS = {
        "query": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "The list of search queries for Google Scholar. Accepts one or more query strings."
        },
    }
    TOOL_PARAMS_REQUIRED = ["query"]
    USE_CACHE = WEB_BASED_TOOLS_USE_CACHE
    USE_TONGYI_FORMAT = USE_TONGYI_FORMAT_RETURN