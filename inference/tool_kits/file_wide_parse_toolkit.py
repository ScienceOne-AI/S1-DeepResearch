import yaml
import os
import sys
from urllib.parse import urljoin
from typing import Callable, Dict, Any
from utils.configs import TOOLS_SERVER_BASE_ENDPOINT_URL, USE_TONGYI_FORMAT_RETURN, WEB_BASED_TOOLS_USE_CACHE
from tool_kits.base import BaseToolkit


class FileWideParseToolkit(BaseToolkit):
    NAME = "parse_file"
    TOOLS_SERVER_BASE_ENDPOINT = TOOLS_SERVER_BASE_ENDPOINT_URL
    ENTRY_POINT = "file_wide_parse"
    DESCRIPTION = f"This is a tool that can be used to parse multiple user uploaded local files such as PDF, DOCX, PPTX, TXT, CSV, XLSX, DOC, ZIP, MP4, MP3."
    TIMEOUT = 600
    TOOL_PARAMS = {
        "files": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "The file name of the user uploaded local files to be parsed."
        },
    }
    TOOL_PARAMS_REQUIRED = ["files"]
    USE_CACHE = WEB_BASED_TOOLS_USE_CACHE
    USE_TONGYI_FORMAT = USE_TONGYI_FORMAT_RETURN