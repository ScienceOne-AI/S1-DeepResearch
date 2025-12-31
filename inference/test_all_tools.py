from tool_kits import (
    AskQuestionAboutImageToolkit,
    AskQuestionAboutVideoToolkit,
    BrowserToolkit,
    ExecuteCodeToolkit,
    ExtractCSVContentToolkit,
    ExtractDocumentContentToolkit,
    ExtractPDFContentToolkit,
    FetchWebPageToolkit,
    ImageToTextToolkit,
    VisitToolkit,
    WebSearchToolkit,
    WriteToFileToolkit,
    WideSearchToolkit,
    ImageSearchToolkit,
    ScholarSearchToolkit,
    FileWideParseToolkit,
    WideVisitToolkit
)

from urllib.parse import urljoin
from typing import Callable, Dict, Any

# initialize all tools (alphabetically sorted)
tools = {
    "ask_question_about_image": AskQuestionAboutImageToolkit(),
    "ask_question_about_video": AskQuestionAboutVideoToolkit(),
    "browse_url": BrowserToolkit(),
    "execute_code": ExecuteCodeToolkit(),
    "extract_csv_content": ExtractCSVContentToolkit(),
    "extract_document_content": ExtractDocumentContentToolkit(),
    "extract_pdf_content": ExtractPDFContentToolkit(),
    "fetch_web_page": FetchWebPageToolkit(),
    "image_to_text": ImageToTextToolkit(),
    "visit_url": VisitToolkit(),
    "web_search": WebSearchToolkit(),
    "write_to_file": WriteToFileToolkit(),
    "wide_search": WideSearchToolkit(),
    "image_search": ImageSearchToolkit(),
    "scholar_search": ScholarSearchToolkit(),
    "file_wide_parse": FileWideParseToolkit(),
    "wide_visit": WideVisitToolkit(),
}

# register all tools

ALL_TOOLS: Dict[str, Dict[str, Any]] = {}

def register_tool(name: str, description: str, parameters: Dict[str, Any]):

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
        "function": tool.forward,
    }

def test_tools():

    results = {}
    test_cases = {
        "ask_question_about_image": {"image_path": "https://ts1.tc.mm.bing.net/th/id/R-C.264a8a0ae5dd97e67b21938ed84c71f7?rik=3lEZxaxx16%2fWog&riu=http%3a%2f%2fpuui.qpic.cn%2fvpic_cover%2fe3351dhdrb4%2fe3351dhdrb4_hz.jpg%2f1280&ehk=boOom6rWfByEXfMQ%2bMkeJWOa3XH8il1uvyakDaFSBkQ%3d&risl=&pid=ImgRaw&r=0", "question": "What is in this image?"},
        "ask_question_about_video": {"video_path": "https://www.bilibili.com/video/BV11p81zFEJT/?spm_id_from=333.337.search-card.all.click", "question": "描述这个视频的内容和主要场景。"},
        "browse_url": {"task_prompt": "总结这个网页", "start_url": "https://baike.baidu.com/item/%E9%B2%81%E8%BF%85/36231"},
        "execute_code": {"code": "print('Hello World')"},
        "extract_csv_content": {"csv_path": "./test_files/测试.csv"},
        "extract_local_document_content": {"document_path": "./test_files/测试.docx"},
        "extract_pdf_content": {"pdf_document_path_or_url": "https://source.wengegroup.com/mam2/66aaf921e4b05f58e12cd2d8.pdf"},
        "fetch_web_page": {"url": "https://www.baidu.com"},
        "image_to_text": {"image_path": "http://img.daimg.com/uploads/allimg/240712/3-240G2112F6.jpg"},
        "visit_url": {"task_prompt": "詹姆斯哪年出生的", "start_url": "https://baike.baidu.com/item/%e5%8b%92%e5%b8%83%e6%9c%97%c2%b7%e8%a9%b9%e5%a7%86%e6%96%af/1989503"},
        "web_search": {"query": "中科院自动化所"},
        "write_to_file": {"content": "Hello Markdown", "filename": "test.md"},
        "wide_search": {"query": ['伊莎贝尔·于佩尔 包法利夫人 苦的砒霜', 'Isabelle Huppert insisted poison taste bitter']},
        "image_search": {"query": ["咖喱", "肉骨茶", "印尼九层塔"]},
        "scholar_search": {"query": ["spa", "烟花", "attention"]},
        "file_wide_parse": {
                "files": [
                    "/app/literature_seed/test_files/测试.docx",
                    "/app/literature_seed/test_files/测试.csv",
                    "https://www.bilibili.com/video/BV11p81zFEJT/?spm_id_from=333.337.search-card.all.click",
                    "https://www.youtube.com/watch?v=pbSji_3prUc&list=RDpbSji_3prUc&start_radio=1",
                    ], 
            },
        "wide_visit": {"url": [
            "https://baijiahao.baidu.com/s?id=1846237877083219477&wfr=spider&for=pc", 
            "https://kan.china.com/article/5071502.html",
            "https://www.seattleschools.org/news/school-calendar/"
            ], "goal": "2026年中小学和大学寒假时间差异"},
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

        print(f"Testing with parameters: {params}")

        try:
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
    test_tools()

    

