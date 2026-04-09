import os
import random
import json
import threading
import queue
import asyncio
from typing import Any
from urllib.parse import urljoin

import httpx

import time
import uuid

class BaseToolkit():
    """A tool for assisting test tasks."""

    NAME = "tool_base"
    DESCRIPTION = f"The tool backbone of all real tools."
    TIMEOUT = 60
    TOOLS_SERVER_BASE_ENDPOINT = []
    ENTRY_POINT = ""
    TOOL_PARAMS = {}
    TOOL_PARAMS_REQUIRED = []
    USE_CACHE = False

    def __init__(
        self,
        name: str = "",
        description: str = "",
        params: dict = {},
        required_params: list[str] = [],
        server_url: str | list[str] = [],
        entry_point: str = "",
        timeout: float | None = None,
        request_id: str = "",
        use_cache: bool | None = None,
        is_tongyi_format: bool | None = None,
        **kwargs,
    ):
        # 这行代码的意思是：获取当前实例(self)的类（即class），并把它赋值给变量cls。
        # 这样可以在初始化方法中使用cls来访问类属性，比如cls.NAME等，无论是否通过继承生成子类。
        cls = type(self)
        self.name = name or getattr(cls, "NAME", "")
        self.description = description or getattr(cls, "DESCRIPTION", "")
        self.params = params or getattr(cls, "TOOL_PARAMS", {})
        self.required_params = required_params or getattr(cls, "TOOL_PARAMS_REQUIRED", [])
        self.server_url = server_url or getattr(cls, "TOOLS_SERVER_BASE_ENDPOINT", "")
        self.entry_point = entry_point or getattr(cls, "ENTRY_POINT", "") or getattr(cls, "NAME", "")
        
        if timeout is not None:
            self.timeout = timeout
        else:
            self.timeout = getattr(cls, "TIMEOUT", 600)

        if use_cache is not None:
            self.use_cache = use_cache
        else:
            self.use_cache = getattr(cls, "USE_CACHE", False)

        if is_tongyi_format is not None:
            self.is_tongyi_format = is_tongyi_format
        else:
            self.is_tongyi_format = getattr(cls, "USE_TONGYI_FORMAT", None)

        self.set_request_id(request_id=request_id)

        self._init_client()

    def _init_client(self):
        """
        Initialize the HTTP client for making requests.
        """
        # httpx 是一个用于发送 HTTP 请求的库，这里用它来创建一个客户端对象，方便后续发送 HTTP 请求到工具服务器。
        self.client = httpx.Client()

    @property
    def json(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": self.params,
                    "required": self.required_params,
                },
            },
        }

    def _post(self, pload: dict[str, Any]) -> Any:
        """
        Post request to the tool server and return the response.
        """

        # support multiple server urls for load balancing
        server_url = random.choice(self.server_url) if isinstance(self.server_url, list) else self.server_url
        tool_endpoint = urljoin(server_url, self.entry_point) # url + 访问接口

        # with httpx.Client() as client:
        try:
            resp = self.client.post(tool_endpoint, json=pload, timeout=self.timeout)
            if not resp.is_success:
                return  f"{resp.status_code} {resp.text}"
            data = resp.json()
            return data.get("result", "")
                    
        except Exception as e:
            raise e

    # **kwargs 是 Python 中的一种语法，用于将所有额外的关键字参数以字典形式收集起来
    # 例如: forward(a=1, b=2) 时，kwargs={'a': 1, 'b': 2}
    def forward(self, **kwargs):
        """
        Execute this tool.

        Args:
            keyword arguments: Arguments to be submitted to this tool.

        Returns:
            ToolOutput: An object containing either the tool's results or an error message.
        """
        
        # request_id, use_cache, and real params for the tool
        try:
            payload = {}

            # Ensure request_id and use_cache is present
            # timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
            timestamp = time.strftime("%Y%m%d%", time.localtime())
            if self.request_id:
                payload["request_id"] = f"{self.request_id}_{self.name}_{timestamp}"
            else:
                # payload["request_id"] = f"{self.name}_{timestamp}"
                payload["request_id"] = self.name

            payload["use_cache"] = self.use_cache
            # Ensure is_tongyi_format is inside params
            if self.is_tongyi_format is not None:
                kwargs['is_tongyi_format'] = self.is_tongyi_format
            payload['params'] = kwargs

            conversation_id = kwargs.pop('conversation_id', None)
            if conversation_id is not None:
                payload['conversation_id'] = conversation_id

            # print("payload:", payload)
            raw = self._post(payload)
            return raw

        except Exception as e:
            raise e
    
    

    def set_request_id(self, request_id: str):
        """
        Set the request ID for this tool.
        """
        self.request_id = request_id

    def set_use_cache(self, use_cache: bool):
        """
        Set whether to use cache for this tool.
        """
        self.use_cache = use_cache

    def set_timeout(self, timeout: float):
        """
        Set the timeout for this tool.
        """
        self.timeout = timeout

        
    def __del__(self):
        # try:
        #     if getattr(self, "client", None):
        #         self.client.close()
        # except Exception:
        #     pass
        pass