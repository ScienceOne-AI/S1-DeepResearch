import yaml
import os
import sys
from urllib.parse import urljoin
from typing import Callable, Dict, Any
from utils.configs import TOOLS_SERVER_BASE_ENDPOINT_URL, WEB_BASED_TOOLS_USE_CACHE
from tool_kits.base import BaseToolkit


class BashToolkit(BaseToolkit):
    NAME = "bash"
    TOOLS_SERVER_BASE_ENDPOINT = TOOLS_SERVER_BASE_ENDPOINT_URL
    ENTRY_POINT = "bash"
    DESCRIPTION = (
        "Execute a shell script in the current working directory. "
        "Use this tool to run one or more shell commands as a single script or "
        "execute script files (e.g. `python script.py`)."
    )
    TIMEOUT = 900
    TOOL_PARAMS = {
        "command": {
            "type": "string",
            "description": (
                "A shell script to execute. Multiple commands are allowed and will be "
                "executed sequentially in the same shell session. Use relative paths by default."
            ),
        },
    }
    TOOL_PARAMS_REQUIRED = ["command"]
    USE_CACHE = WEB_BASED_TOOLS_USE_CACHE
