中文 | [English](./README_en.md)

# S1-deepresearch 推理框架

## 核心特性

- **多 LLM 客户端**: 支持 vLLM、Azure OpenAI、AIHubMix 等多种 LLM 服务
- **丰富的工具集**: 提供 9 种工具，涵盖搜索、网页访问、文件解析、代码执行、多模态问答、bash 等
- **批量推理**: 支持并发批量推理，自动断点续传，定期保存结果
- **单条推理**: 支持单条查询的详细调试和测试
- **负载均衡**: 支持多 LLM 节点的负载均衡和一致性调度
- **详细日志**: 为每个查询生成独立的日志文件，便于问题追踪和分析

## 项目结构（当前）

```text
./
├── run_batch_inference_demo.sh          # 本地/vLLM 脚本模板
├── run_batch_inference_online_demo.sh   # 在线平台脚本模板
├── inference/
│   ├── run_batch_inference.py
│   └── run_single_inference.py
├── server/
├── tool_kits/
├── utils/
│   └── config/
│       ├── config.example.json
│       └── README.md
├── models/tokenizer/
└── test_all_tools.py
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置（推荐 JSON 或环境变量）

配置优先级：`自定义 JSON > 环境变量 > utils/config.py 默认值`。

常用做法：

```bash
cp utils/config/config.example.json utils/config/config.local.json
```

然后按需修改 `config.local.json`，例如：

- `TOOLS_SERVER_BASE_ENDPOINT_URL`
- `AIHUBMIX_KEY` / `AZURE_KEY` / `VOLCANO_KEY` / `ALIYUN_KEY`
- `CLIENT_TIMEOUT`

也可以通过环境变量覆盖，例如：

```bash
export S1_DR_CONFIG_JSON="utils/config/config.local.json"
```

### 3. 准备输入 JSONL

输入文件每行一个 JSON。最少建议包含 `question`，通常同时包含 `id` 与 `file_path`。

#### 3.1 jsonl 示例（涉及文件输入）

```json
{"id":"query_001","question":"阿里巴巴成立时，18位创始团队成员中，姓马、姓蔡、姓张的创始人的平均年龄，保留一位小数","file_path":[]}
{"id":"query_002","question":"阅读当前说明书，大疆发布的起飞重量最大的AIR系列无人机飞完半程马拉松，电池还剩多少毫安时的电能？（注1：假设水平无风，最低耗能的情况为最大航速的60%飞行；注2：耗电可以按最长飞行时间换算）","file_path":["/path/to/file.pdf"]}
```

#### 3.2 jsonl 示例（涉及 Skill 使用）

```json
{"id":"query_003","question":"Use pymatgen to build a simple TiO2 surface slab. Please generate a common low-index surface, report the Miller index, slab thickness, and vacuum size, and briefly describe the resulting surface structure.","skills":[{"name": "skill_name1", "description": "description1", "skill_path": "skill_path1"}, {"name": "skill_name2", "description": "description2", "skill_path": "skill_path2"}]}
```

## 推荐启动方式：复制脚本后运行

### A. 本地 / vLLM（`run_batch_inference_demo.sh`）

```bash
cp run_batch_inference_demo.sh run_batch_local.sh
mkdir -p run_logs
# 编辑 run_batch_local.sh 中的参数
bash run_batch_local.sh
```

说明：

- 脚本内部已使用 `nohup ... &` 启动 Python，会打印后台 PID。
- 常看日志：`tail -f run_logs/run.log`

### B. 在线平台（`run_batch_inference_online_demo.sh`）

```bash
cp run_batch_inference_online_demo.sh run_batch_online.sh
mkdir -p run_logs
# 编辑 run_batch_online.sh 中的参数
bash run_batch_online.sh
```

说明：

- 重点修改：`LLM_CLIENT_URLS`、`LLM_CLIENT_MODELS`、`SYSTEM_FORMAT`
- 常看日志：`tail -f run_logs/run_batch_*.log`

## 脚本参数说明

### 基础参数

- `LLM_CLIENT_URLS`：模型服务地址，多个地址用空格分隔（与模型列表一一对应）
- `LLM_CLIENT_MODELS`：模型名列表，多个模型用空格分隔
- `TEST_DATA_FILE`：输入 JSONL 路径
- `OUTPUT_FILE`：`ROLLOUT_NUM=1` 时的输出文件
- `OUTPUT_DIR`：`ROLLOUT_NUM>1` 时输出目录（生成 `rollout_01.jsonl` 等）
- `ROLLOUT_NUM`：每条样本重复推理次数
- `RESUME_FROM_FILE`：断点续跑文件（可空）
- `AVAILABLE_TOOLS`：启用工具列表（空格分隔）
- `TASK_TYPE`：是否按“输入仅文本”场景处理，默认 `input_only`

### 推理控制参数

- `MAX_ROUNDS`：单 query 最大轮次
- `CONCURRENCY_WORKERS`：并发 worker 数
- `SAVE_BATCH_SIZE`：每处理多少条就自动落盘一次
- `TEMPERATURE`：采样温度
- `TOP_P`：top-p（`run_batch_inference_demo.sh` 已包含）
- `EXTRA_PAYLOAD`：额外模型 payload（JSON 字符串，`run_batch_inference_demo.sh` 已包含）
- `TIMEOUT_FOR_ONE_QUERY`：单 query 超时时间（秒）
- `LLM_API_RETRY_TIMES`：LLM 请求失败后的重试次数（不含首次）
- `SYSTEM_PROMPT`：自定义 system prompt；留空时使用内置默认 prompt
- `SYSTEM_FORMAT`：平台格式（主要在 `run_batch_inference_online_demo.sh`）

### 上下文截断相关参数

- `DISCARD_ALL_MODE`：是否启用 discard-all（`true/false`）
- `MODEL_MAX_CONTEXT_TOKENS`：模型最大上下文长度
- `DISCARD_RATIO`：触发 discard 的比例阈值
- `TOKENIZER_PATH`：token 统计所用 tokenizer 路径

### 日志参数

- `LOG_LABEL`：日志标签，目录形如 `logs/YYYY_MM_DD_<LOG_LABEL>/`
- `LOG_FILE`：脚本启动日志文件（`run_logs/*.log`）
- `LOGGING_ROOT`：日志根路径（`run_batch_inference_demo.sh` 已包含，可空）

## `SYSTEM_FORMAT` 可选值

`SYSTEM_FORMAT` 将对应不同的平台处理逻辑，根据该关键词进入不同的处理分支。

- `deep_research`：本地 deep research 格式（vLLM 部署）
- `azure`：Azure OpenAI
- `aihubmix`：AIHubMix（OpenAI 兼容）
- `aihubmix_claude`：AIHubMix Claude 格式
- `aihubmix_glm`：AIHubMix GLM 格式
- `volcano`：火山引擎
- `aliyun`：阿里云百炼平台格式

## 当前默认可用工具（9 个）

- `wide_search`：基于 Serp 进行通用网页搜索，支持一轮提交多个 query
- `scholar_search`：基于 Google Scholar 进行学术检索  + web 结果）
- `image_search`：图片检索，支持多 query。
- `wide_visit`：访问网页并按目标 `goal` 产出摘要
- `file_wide_parse`：解析本地/在线文件（PDF、DOCX、MD、CSV等）
- `execute_code`：执行 Python 代码
- `ask_question_about_image`：图像理解与问答
- `ask_question_about_video`：视频理解与问答
- `bash`：执行 shell 脚本

各工具对应的 schema 定义详见 utils/prompts.py 下的 `DEEPRESEARCH_SYSTEM_PROMPT`

## 输出与日志

### 输出 JSONL（字段详解）

`run_batch_inference.py` 写出的每行字段如下：

- `time_stamp`：该行结果写入时的时间戳（`YYYY-MM-DD HH:MM:SS`）。
- `query_id`：批处理层生成的 query 标识（基于 `question` 哈希）。
- `query`：本条输入的 `question` 文本。
- `result`：单个 segment 的详细结果对象（来自 `run_single_inference.py`）。
- `status`：任务状态，`success` / `timeout` / `error`。
- `discard_segments`：被 `discard-all` 截断并做 summary 的段数（不含最终段）。
- `elapsed_sec`：该 query 本次 rollout 的总耗时（秒）。
- `rollout_idx`：第几次 rollout（从 1 开始）。
- `src`：原始输入行完整内容（通常含 `id`、`question`、`file_path`、skills 等）。
- `segment_idx`：当前是第几个 segment（从 1 开始）。
- `segment_total`：该 query 共拆成多少个 segment。若无有效 `result`，会写成 `0`。

其中 `result` 常见字段（`run_single_inference.py`）：

- `query_id`：单次运行实例 ID（含时间后缀）。
- `tools`：本次启用的 tools schema（字符串形式）。
- `messages`：用于模型推理与工具交互的日志消息。
- `final_answer`：当前 segment 的回答文本。
- `transcript`：更完整的对话轨迹（含工具回填）。
- `rounds`：该 segment 执行到的轮数。
- `stopped_reason`：停止原因（如 `no_tool_calls`、`discard_all_01`、`discard_all_final`、`max_rounds_exceeded`）。
- `error`：仅在异常时可能出现。

### 日志目录

默认日志结构如下（`LOGGING_ROOT` 为空时）：

```text
logs/
└── YYYY_MM_DD_<LOG_LABEL>/
    ├── collect.log
    └── <query_id>/
        ├── run.log
        └── result.json
```

## 工具测试

运行工具测试脚本：
```bash
python test_all_tools.py
```
该脚本会测试所有注册的工具，验证其基本功能是否正常。