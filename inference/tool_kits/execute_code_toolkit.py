import yaml
import os
import sys
from urllib.parse import urljoin
from typing import Callable, Dict, Any
from utils.configs import TOOLS_SERVER_BASE_ENDPOINT_URL, WEB_BASED_TOOLS_USE_CACHE
from tool_kits.base import BaseToolkit


class ExecuteCodeToolkit(BaseToolkit):
    NAME = "execute_code"
    TOOLS_SERVER_BASE_ENDPOINT = TOOLS_SERVER_BASE_ENDPOINT_URL
    ENTRY_POINT = "execute_code"
    DESCRIPTION = f"Execute a given code snippet, such as processing data code, training a machine learning or deep learning model code, analysising data code, executing a workflow, etc."
    TIMEOUT = 900
    TOOL_PARAMS = {
        "code": {
            "type": "string",
            "description": "The input code to the Code Interpreter tool call.",
        },
    }
    TOOL_PARAMS_REQUIRED = ["code"]
    USE_CACHE = WEB_BASED_TOOLS_USE_CACHE