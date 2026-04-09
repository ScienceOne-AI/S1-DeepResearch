import yaml
import os
import sys
from urllib.parse import urljoin
from typing import Callable, Dict, Any
from utils.configs import TOOLS_SERVER_BASE_ENDPOINT_URL, WEB_BASED_TOOLS_USE_CACHE
from tool_kits.base import BaseToolkit


class AskQuestionAboutVideoToolkit(BaseToolkit):
    NAME = "ask_question_about_video"
    TOOLS_SERVER_BASE_ENDPOINT = TOOLS_SERVER_BASE_ENDPOINT_URL
    ENTRY_POINT = "ask_question_about_video"
    DESCRIPTION = f"Ask a question about one or more videos."
    TIMEOUT = 600
    TOOL_PARAMS = {
        "video_path": {
            "type": "array",
            "items": {
                "type": "string",
                "description": "Local path or URL to the video file.",
            },
            "minItems": 1,
            "description": "Array of local paths or URLs to video files.",
        },
        "question": {
            "type": "string",
            "description": "The question to ask about the video.",
        },
    }
    TOOL_PARAMS_REQUIRED = ["video_path", "question"]
    USE_CACHE = WEB_BASED_TOOLS_USE_CACHE
