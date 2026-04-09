[中文](./README.md) | English

# S1-DeepResearch Inference Framework

## Key Features

- **Multiple LLM clients**: Supports vLLM, Azure OpenAI, AIHubMix, and other LLM services
- **Rich toolset**: Nine tools covering search, web browsing, file parsing, code execution, multimodal Q&A, bash, and more
- **Batch inference**: Concurrent batch inference with resume-from-checkpoint and periodic result saving
- **Single-query inference**: Detailed debugging and testing for individual queries
- **Load balancing**: Multi-node LLM load balancing and consistent scheduling
- **Detailed logging**: Per-query log files for easier troubleshooting and analysis

## Project Layout (current)

```text
./
├── run_batch_inference_demo.sh          # Local / vLLM script template
├── run_batch_inference_online_demo.sh   # Online platform script template
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

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configuration (JSON or environment variables recommended)

Precedence: **custom JSON > environment variables > defaults in `utils/config.py`**.

Typical workflow:

```bash
cp utils/config/config.example.json utils/config/config.local.json
```

Edit `config.local.json` as needed, for example:

- `TOOLS_SERVER_BASE_ENDPOINT_URL`
- `AIHUBMIX_KEY` / `AZURE_KEY` / `VOLCANO_KEY` / `ALIYUN_KEY`
- `CLIENT_TIMEOUT`

You can also override via environment variables, for example:

```bash
export S1_DR_CONFIG_JSON="utils/config/config.local.json"
```

### 3. Prepare input JSONL

Each line is one JSON object. At minimum include `question`; usually also `id` and `file_path`.

#### 3.1 JSONL example (file inputs)

```json
{"id":"query_001","question":"When Alibaba was founded, what was the average age of the founders whose surnames are Ma, Cai, or Zhang among the 18 co-founders? Round to one decimal place.","file_path":[]}
{"id":"query_002","question":"According to the manual, for DJI's heaviest AIR-series drone by takeoff weight, how many mAh of battery energy remain after flying half a marathon? (Note 1: assume calm air; minimum energy use is flying at 60% of max speed. Note 2: power draw can be converted from max flight time.)","file_path":["/path/to/file.pdf"]}
```

#### 3.2 JSONL example (using Skills)

```json
{"id":"query_003","question":"Use pymatgen to build a simple TiO2 surface slab. Please generate a common low-index surface, report the Miller index, slab thickness, and vacuum size, and briefly describe the resulting surface structure.","skills":[{"name": "skill_name1", "description": "description1", "skill_path": "skill_path1"}, {"name": "skill_name2", "description": "description2", "skill_path": "skill_path2"}]}
```

## Recommended workflow: copy a script, then run

### A. Local / vLLM (`run_batch_inference_demo.sh`)

```bash
cp run_batch_inference_demo.sh run_batch_local.sh
mkdir -p run_logs
# Edit parameters inside run_batch_local.sh
bash run_batch_local.sh
```

Notes:

- The script starts Python with `nohup ... &` and prints the background PID.
- Tail logs: `tail -f run_logs/run.log`

### B. Online platform (`run_batch_inference_online_demo.sh`)

```bash
cp run_batch_inference_online_demo.sh run_batch_online.sh
mkdir -p run_logs
# Edit parameters inside run_batch_online.sh
bash run_batch_online.sh
```

Notes:

- Focus on: `LLM_CLIENT_URLS`, `LLM_CLIENT_MODELS`, `SYSTEM_FORMAT`
- Tail logs: `tail -f run_logs/run_batch_*.log`

## Script parameters

### Basic

- `LLM_CLIENT_URLS`: Model service URLs, space-separated (paired with the model list)
- `LLM_CLIENT_MODELS`: Model names, space-separated
- `TEST_DATA_FILE`: Input JSONL path
- `OUTPUT_FILE`: Output file when `ROLLOUT_NUM=1`
- `OUTPUT_DIR`: Output directory when `ROLLOUT_NUM>1` (e.g. `rollout_01.jsonl`, …)
- `ROLLOUT_NUM`: Number of rollouts per sample
- `RESUME_FROM_FILE`: Resume checkpoint file (may be empty)
- `AVAILABLE_TOOLS`: Enabled tools, space-separated
- `TASK_TYPE`: Whether to treat input as text-only; default `input_only`

### Inference control

- `MAX_ROUNDS`: Max rounds per query
- `CONCURRENCY_WORKERS`: Number of concurrent workers
- `SAVE_BATCH_SIZE`: Flush results to disk every N samples
- `TEMPERATURE`: Sampling temperature
- `TOP_P`: Top-p (included in `run_batch_inference_demo.sh`)
- `EXTRA_PAYLOAD`: Extra model payload (JSON string; included in `run_batch_inference_demo.sh`)
- `TIMEOUT_FOR_ONE_QUERY`: Per-query timeout (seconds)
- `LLM_API_RETRY_TIMES`: Retries after LLM failure (not counting the first attempt)
- `SYSTEM_PROMPT`: Custom system prompt; empty uses the built-in default
- `SYSTEM_FORMAT`: Platform format (mainly in `run_batch_inference_online_demo.sh`)

### Context truncation

- `DISCARD_ALL_MODE`: Enable discard-all (`true`/`false`)
- `MODEL_MAX_CONTEXT_TOKENS`: Model max context length
- `DISCARD_RATIO`: Threshold ratio to trigger discard
- `TOKENIZER_PATH`: Path to tokenizer used for token counting

### Logging

- `LOG_LABEL`: Log label; directory shape `logs/YYYY_MM_DD_<LOG_LABEL>/`
- `LOG_FILE`: Script log file under `run_logs/*.log`
- `LOGGING_ROOT`: Log root (set in `run_batch_inference_demo.sh`; may be empty)

## `SYSTEM_FORMAT` values

`SYSTEM_FORMAT` selects platform-specific handling via keyword branches.

- `deep_research`: Local deep-research format (vLLM deployment)
- `azure`: Azure OpenAI
- `aihubmix`: AIHubMix (OpenAI-compatible)
- `aihubmix_claude`: AIHubMix Claude format
- `aihubmix_glm`: AIHubMix GLM format
- `volcano`: Volcano Engine
- `aliyun`: Alibaba Cloud Bailian format

## Currently available tools (9)

- `wide_search`: General web search via Serp; multiple queries in one round
- `scholar_search`: Google Scholar academic search (+ web results)
- `image_search`: Image search; multiple queries supported
- `wide_visit`: Visit pages and summarize toward a `goal`
- `file_wide_parse`: Parse local/remote files (PDF, DOCX, MD, CSV, etc.)
- `execute_code`: Run Python code
- `ask_question_about_image`: Image understanding and Q&A
- `ask_question_about_video`: Video understanding and Q&A
- `bash`: Run shell commands

Tool schemas are defined in `DEEPRESEARCH_SYSTEM_PROMPT` in `utils/prompts.py`.

## Outputs and logs

### Output JSONL fields

Each line written by `run_batch_inference.py` contains:

- `time_stamp`: Write time for that row (`YYYY-MM-DD HH:MM:SS`).
- `query_id`: Batch-level query id (hash of `question`).
- `query`: This row’s `question` text.
- `result`: Detailed result object for one segment (from `run_single_inference.py`).
- `status`: `success` / `timeout` / `error`.
- `discard_segments`: Segments truncated by discard-all and summarized (excluding the final segment).
- `elapsed_sec`: Total seconds for this rollout of the query.
- `rollout_idx`: Rollout index (1-based).
- `src`: Full original input line (often includes `id`, `question`, `file_path`, skills, etc.).
- `segment_idx`: Current segment index (1-based).
- `segment_total`: Total segments for this query; `0` if there is no valid `result`.

Common fields inside `result` (`run_single_inference.py`):

- `query_id`: Single-run instance id (includes a time suffix).
- `tools`: Enabled tool schemas (string form).
- `messages`: Messages for model reasoning and tool interaction.
- `final_answer`: Answer text for this segment.
- `transcript`: Fuller trajectory (including tool returns).
- `rounds`: Rounds executed in this segment.
- `stopped_reason`: Why it stopped (e.g. `no_tool_calls`, `discard_all_01`, `discard_all_final`, `max_rounds_exceeded`).
- `error`: Present only on failure.

### Log directories

Default layout when `LOGGING_ROOT` is empty:

```text
logs/
└── YYYY_MM_DD_<LOG_LABEL>/
    ├── collect.log
    └── <query_id>/
        ├── run.log
        └── result.json
```

## Tool tests

Run the tool test script:

```bash
python test_all_tools.py
```

This exercises all registered tools and checks that basic behavior works.
