from tool_kits import (
    AskQuestionAboutImageToolkit,
    AskQuestionAboutVideoToolkit,
    ExecuteCodeToolkit,
    WideSearchToolkit,
    ImageSearchToolkit,
    ScholarSearchToolkit,
    FileWideParseToolkit,
    WideVisitToolkit,
    BashToolkit
)

from urllib.parse import urljoin
from typing import Callable, Dict, Any

# initialize all tools (alphabetically sorted)
tools = {
    "ask_question_about_image": AskQuestionAboutImageToolkit(),
    "ask_question_about_video": AskQuestionAboutVideoToolkit(),
    "execute_code": ExecuteCodeToolkit(),
    "wide_search": WideSearchToolkit(),
    "image_search": ImageSearchToolkit(),
    "scholar_search": ScholarSearchToolkit(),
    "file_wide_parse": FileWideParseToolkit(),
    "wide_visit": WideVisitToolkit(),
    "bash": BashToolkit(),
}

# register all tools

ALL_TOOLS: Dict[str, Dict[str, Any]] = {}

def register_tool(name: str, description: str, parameters: Dict[str, Any]):
    """
    装饰器：注册工具到 TOOLS
    """
    def decorator(func: Callable):
        ALL_TOOLS[name] = {
            "name": name,
            "description": description,
            "strict": True,
            "parameters": parameters,
            "function": func,
        }
        return func
    return decorator

# for competibility with the old code
for tool_name, tool in tools.items():
    ALL_TOOLS[tool_name] = {
        "name": tool.name,
        "description": tool.description,
        "strict": True,
        "parameters": tool.params,
        "function": tool.forward, # 工具执行函数
        "schema_json": tool.json
    }

def test_tools():
    """
    测试所有注册的工具，参考xxl_wrapped_camel_tools.py中的测试用例
    """
    results = {}
    # 测试用例定义（每个工具一个简单用例）
    test_cases = {
        "ask_question_about_image": {"image_path": [
            "http://img.daimg.com/uploads/allimg/240712/3-240G2112F6.jpg"
            ], "question": "What is in this image?"},
        "ask_question_about_video": {"video_path": "https://www.bilibili.com/video/BV11p81zFEJT/?spm_id_from=333.337.search-card.all.click", "question": "描述这个视频的内容和主要场景。"},
        "bash": {"command": "echo 'hello world'"},
        "execute_code": {"code": "print('Hello World')"},
        "execute_code": {"code": "import math\nimport matplotlib.pyplot as plt\n"},
        "wide_search": {"query": ['伊莎贝尔·于佩尔 包法利夫人 苦的砒霜', 'Isabelle Huppert insisted poison taste bitter']},
        "image_search": {"query": ["咖喱", "肉骨茶", "印尼九层塔"]},
        "scholar_search": {"query": ["spa", "烟花", "attention"]},
        "file_wide_parse": {
                "files": [
                    "http://img.daimg.com/uploads/allimg/240712/3-240G2112F6.jpg"
                    ], 
            },
        "wide_visit": {"url": "https://www.sohu.com/a/960662276_163491", "goal": "疯狂动物城有哪些周边"},
    }

    for tool_name, test_case in test_cases.items():
        if tool_name not in ALL_TOOLS:
            print(f"Tool {tool_name} not found in registered tools.")
            continue
        tool_info = ALL_TOOLS[tool_name]
        print(f"\nTool: {tool_name}")
        print(f"Description: {tool_info['description']}")
        print(f"Parameters: {tool_info['parameters']}")
        params = test_case
        import time
        params['conversation_id'] = f"test_{time.strftime('%Y%m%d%H%M%S', time.localtime())}"
        print(f"Testing with parameters: {params}")

        try:
            # 支持异步工具（如browse_url）
            if tool_name == "browse_url":
                import asyncio
                result = asyncio.run(tool_info["function"](**params))
            else:
                result = tool_info["function"](**params)
            print(f"\n✅ Test result: {str(result)}")
            results[tool_name] = {"success": True, "result": result}
        except Exception as e:
            print(f"\n❌ Test failed: {str(e)}")
            results[tool_name] = {"success": False, "error": str(e)}
        print("\n" +  "🏃..🎈 " * 20 + "\n")

    print("\n" +  "==" * 20 + "END" + "==" * 20 + "\n")


if __name__ == "__main__":

    for key in ALL_TOOLS.keys():
        print(ALL_TOOLS[key]['schema_json'])

    print("=" * 100)

    test_tools()
    

