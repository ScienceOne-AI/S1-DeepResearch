import yaml
import os
import sys
from urllib.parse import urljoin
from typing import Callable, Dict, Any
from utils.configs import TOOLS_SERVER_BASE_ENDPOINT_URL, USE_TONGYI_FORMAT_RETURN, WEB_BASED_TOOLS_USE_CACHE
from tool_kits.base import BaseToolkit


class WideVisitToolkit(BaseToolkit):
    NAME = "visit"
    TOOLS_SERVER_BASE_ENDPOINT = TOOLS_SERVER_BASE_ENDPOINT_URL
    ENTRY_POINT = "wide_visit"
    DESCRIPTION = "Visit webpage(s) and return the summary of the content."
    TIMEOUT = 600
    TOOL_PARAMS = {
        "url": {
                "type": ["string", "array"],
                "items": {
                    "type": "string"
                    },
                "minItems": 1,
                "description": "The URL(s) of the webpage(s) to visit. Can be a single URL or an array of URLs."
        },
        "goal": {
                "type": "string",
                "description": "The goal of the visit for webpage(s)."
        }
    }
    TOOL_PARAMS_REQUIRED = ["url", "goal"]
    USE_CACHE = WEB_BASED_TOOLS_USE_CACHE
    USE_TONGYI_FORMAT = USE_TONGYI_FORMAT_RETURN