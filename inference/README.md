# 推理平台

## ✨ 核心特性

- **多 LLM 客户端**: 支持 vLLM、Azure OpenAI、AIHubMix 等多种 LLM 服务
- **工具支持**: 提供封装在 Docker 中的 5 种工具，包括搜索、文件解析、代码执行、网页浏览、学术搜索和代码执行。搜索类工具均支持 List 和 String 形式的参数传递
- **批量推理**: 支持并发批量推理，自动断点续传，定期保存结果
- **单条推理**: 支持单条查询的详细调试和测试
- **负载均衡**: 支持多 LLM 节点的负载均衡和一致性调度
- **详细日志**: 为每个查询生成独立的日志文件，便于问题追踪和分析

## 🏗️ 项目结构

```
inference/
├── server/                    # 服务端核心模块
│   ├── llm_api.py             # LLM 客户端封装（支持 vLLM、Azure、AIHubMix）
│   ├── tool_api.py            # 工具注册与管理
│   └── tool_execution.py      # 工具执行逻辑
├── inference/                    # 推理模块
│   ├── run_batch_inference.py    # 批量推理脚本
│   └── run_single_inference.py   # 单条推理脚本
├── tool_kits/                 # 工具实现
│   ├── base.py                # 工具基类
│   ├── wide_search_toolkit.py      # 搜索
│   ├── scholar_search_toolkit.py   # 学术搜索
│   ├── wide_visit_toolkit.py       # 网页访问
│   ├── execute_code_toolkit.py     # 代码执行
│   ├── file_wide_parse_toolkit.py  # 文件解析
├── utils/                   # 工具函数
│   ├── configs.py             # 配置文件
│   ├── build_prompt.py        # 提示词构建
│   ├── prompts.py             # 系统提示词模板
│   ├── logger.py              # 日志管理
│   ├── common.py              # 通用工具函数
│   └── extract_schemas*.py    # 工具调用解析
├── docker/                  # 工具docker
├── results/                 # 推理结果存储
├── logs/                    # 日志文件
├── test_files/              # 测试文件
└── test_all_tools.py        # 工具测试脚本
```

## 🛠️ 工具列表

- **wide_search**: 广泛搜索（支持多查询）
- **scholar_search**: 学术搜索（Google Scholar）

- **wide_visit**: 批量访问多个网页

- **file_wide_parse**: 批量解析多种格式文件（PDF、DOCX、CSV、MP4、MP3 等）

- **execute_code**: 在沙箱环境中执行 Python 代码



## ⚙️ 配置说明

### system_format 参数说明

考虑到各平台的 Function calling、Tool Result 等字段传参和拼接逻辑不同，使用 `--system_format` 来指定不同的模型/平台的拼接逻辑。支持的 system_format 选项：`tongyi_deepresearch` 、`azure`、`aihubmix`、`aihubmix_claude` 以及`volcano`。

**使用方式：**

在运行推理时通过命令行参数指定：
```bash
python inference/run_batch_inference.py --system_format aihubmix ...
```

或在代码中直接指定：
```python
result = await run_one_query(
    ...
    system_format="azure",
    ...
)
```

### LLM 客户端配置

LLM 客户端配置支持多路推理，系统会自动将查询分配到负载最小的节点，并保持同一查询的一致性（同一查询始终使用同一节点）。

#### vLLM 客户端
```python
llm_client_urls = ["http://node1:10777/vllm_generate", "http://node2:10778/vllm_generate"]
llm_client_models = ["<inference_model_name>", "<inference_model_name>"]
```

#### Azure OpenAI 客户端
```python
llm_client_urls = ["https://<your_special_id>.openai.azure.com/openai/v1/"]
llm_client_models = ["gpt-5"]
system_format = "azure"
```

#### AIHubMix 客户端（OpenAI 格式）
```python
llm_client_urls = ["https://aihubmix.com/v1"]
llm_client_models = ["gpt-5"]
system_format = "aihubmix"
```

#### AIHubMix 客户端（Claude 格式）
```python
llm_client_urls = ["https://aihubmix.com/v1"]
llm_client_models = ["claude-3.5-sonnet"]
system_format = "aihubmix_claude"
```

#### 火山引擎客户端
```python
llm_client_urls = ["https://ark.cn-beijing.volces.com/api/v3"]
llm_client_models = ["ep-xxx"]
system_format = "volcano"
```

### 工具配置

在 `utils/configs.py` 中可以配置：
- `TOOLS_SERVER_BASE_ENDPOINT_URL`: 工具服务器地址列表（支持负载均衡）
- `WEB_BASED_TOOLS_USE_CACHE`: 是否对基于网页的工具使用缓存
- `USE_TONGYI_FORMAT_RETURN`: 返回格式（JSON 或自然语言）
- `CLIENTTIMEOUT`: LLM 客户端超时时间（秒）

### 推理参数

- `--concurrency_workers`: 并发工作线程数（默认 10）
- `--save_batch_size`: 每处理多少条结果保存一次（默认 1）
- `--max_rounds`: 最大对话轮数（默认 100）
- `--temperature`: 采样温度（默认 0.7）
- `--timeout_for_one_query`: 单个查询的最大执行时长（秒，默认 7200）
- `--resume_from_file`: 断点续传文件路径（自动跳过已完成样本）

## 📝 输入数据格式

输入文件应为 JSONL 格式，每行一个 JSON 对象（**务必包含 `id`、`question` 以及 `file_path` 字段**）：

```json
{"id": "query_001", "question": "阿里巴巴成立时，18位创始团队成员中，姓马、姓蔡、姓张的创始人的平均年龄，保留一位小数", "file_path": ""}
{"id": "query_002", "question": "阅读当前说明书，大疆发布的起飞重量最大的AIR系列无人机飞完半程马拉松，电池还剩多少毫安时的电能？（注1：假设水平无风，最低耗能的情况为最大航速的60%飞行；注2：耗电可以按最长飞行时间换算）", "file_path": "/path/to/file.pdf"}
```

字段说明：
- `id`: 查询唯一标识符
- `question`: 用户查询问题
- `file_path`: 可选的文件路径（用于多模态任务）
- 其他字段可自行设置，在最终的数据输出格式中，可以在 `src` 字段看到原来的所有字段信息

## 📤 输出数据格式

输出文件为 JSONL 格式，每行包含完整的推理结果：

```json
{
  "time_stamp": "2025-12-05 10:30:00",
  "query_id": "uuid_hash",
  "query": "用户查询",
  "result": {
    "query_id": "uuid_hash",
    "tools": "[工具列表JSON]",
    "messages": [对话消息列表],
    "final_answer": "最终答案",
    "transcript": [完整对话记录],
    "rounds": 5,
    "stopped_reason": "no_tool_calls"
  },
  "status": "success",
  "elapsed_sec": 123.456,
  "src": {原始输入数据}
}
```

## 🔍 日志系统

### 日志结构

```
logs/
├── {log_label}/                    # 按 log_label 分组
│   ├── collect.log                # 批量推理汇总日志
│   └── {query_id}/                # 每个查询的独立目录
│       ├── run.log                # 运行日志
│       └── result.json            # 结果 JSON
```

## 🧪 工具测试

运行工具测试脚本：

```bash
python test_all_tools.py
```

该脚本会测试所有注册的工具，验证其基本功能是否正常。

## 🔧 高级功能

### 负载均衡

支持多个 LLM 节点的负载均衡：
```bash
--llm_client_urls "http://node1:10777/vllm_generate" "http://node2:10777/vllm_generate"
```

系统会自动将查询分配到负载最小的节点，并保持同一查询的一致性（同一查询始终使用同一节点）。

### 断点续传

通过 `--resume_from_file` 参数指定已完成结果文件，系统会自动：
1. 加载已完成的结果
2. 提取已完成查询的 ID
3. 跳过这些查询，只处理未完成的查询

### 自定义系统提示词

```bash
--system_prompt "You are a helpful assistant."
# 或从文件读取
--system_prompt "./custom_system_prompt.txt"
```

### 自定义工具集

通过 `--available_tools` 参数指定可用的工具：
```bash
--available_tools wide_search scholar_search file_wide_parse execute_code wide_visit
```

