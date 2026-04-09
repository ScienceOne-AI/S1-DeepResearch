import yaml
import os
import sys
from urllib.parse import urljoin
from typing import Callable, Dict, Any
from utils.configs import TOOLS_SERVER_BASE_ENDPOINT_URL, WEB_BASED_TOOLS_USE_CACHE
from tool_kits.base import BaseToolkit


class AskQuestionAboutImageToolkit(BaseToolkit):
    NAME = "ask_question_about_image"
    TOOLS_SERVER_BASE_ENDPOINT = TOOLS_SERVER_BASE_ENDPOINT_URL
    ENTRY_POINT = "ask_question_about_image"
    DESCRIPTION = f"Identify image content and answer questions about one or more images."
    TIMEOUT = 600
    TOOL_PARAMS = {
        "image_path": {
            "type": "array",
            "items": {
                "type": "string",
                "description": "Local path or URL to an image file.",
            },
            "minItems": 1,
            "description": "Array of local paths or URLs to image files.",
        },
        "question": {
            "type": "string",
            "description": "Query about the image content.",
        },
    }
    TOOL_PARAMS_REQUIRED = ["image_path", "question"]
    USE_CACHE = WEB_BASED_TOOLS_USE_CACHE
