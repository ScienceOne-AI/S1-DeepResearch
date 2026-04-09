import yaml
import os
import sys
from urllib.parse import urljoin
from typing import Callable, Dict, Any
from utils.configs import TOOLS_SERVER_BASE_ENDPOINT_URL, USE_NLP_FORMAT_RETURN, WEB_BASED_TOOLS_USE_CACHE
from tool_kits.base import BaseToolkit


class ImageSearchToolkit(BaseToolkit):
    NAME = "image_search"
    TOOLS_SERVER_BASE_ENDPOINT = TOOLS_SERVER_BASE_ENDPOINT_URL
    ENTRY_POINT = "image_search"
    DESCRIPTION = f"Search images by query and return a list of related images. Accepts multiple complementary search queries in a single call."
    TIMEOUT = 600
    TOOL_PARAMS = {
        "query": {
            "type": "array",
            "items": {
                "type": "string",
                "description": "A single image search query string.",
            },
            "minItems": 1,
            "description": "Array of query strings. Multiple complementary search queries can be provided in one request for image search.",
        },
    }
    TOOL_PARAMS_REQUIRED = ["query"]
    USE_CACHE = WEB_BASED_TOOLS_USE_CACHE
    USE_TONGYI_FORMAT = USE_NLP_FORMAT_RETURN
    
