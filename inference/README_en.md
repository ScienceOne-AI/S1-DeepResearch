# Inference Platform

## ✨ Key Features

- **Multiple LLM Clients:** Supports vLLM, Azure OpenAI, AIHubMix, and more
- **Rich Tooling:** Five Dockerized tools for search, file parsing, code execution, web browsing, and academic search. Search tools accept both list and string parameters.
- **Batch Inference:** Concurrent, resumable batch inference with periodic checkpointing
- **Single Query Inference:** Detailed debugging and testing for individual queries
- **Load Balancing:** Requests are distributed across multiple LLM nodes for optimal load and consistency
- **Detailed Logging:** Per-query log files enable convenient debugging and traceability

## 🏗️ Project Structure

```
inference/
├── server/                    
│   ├── llm_api.py             # LLM client wrappers (vLLM, Azure, AIHubMix, etc.)
│   ├── tool_api.py            # Tool registry and management
│   └── tool_execution.py      # Tool execution logic
├── inference/                 
│   ├── run_batch_inference.py # Batch inference script
│   └── run_single_inference.py# Single inference script
├── tool_kits/                 
│   ├── base.py                # Toolkit base class
│   ├── wide_search_toolkit.py      
│   ├── scholar_search_toolkit.py   
│   ├── wide_visit_toolkit.py       
│   ├── execute_code_toolkit.py     
│   ├── file_wide_parse_toolkit.py  
├── utils/                     
│   ├── configs.py             # Configurations
│   ├── build_prompt.py        # Prompt construction
│   ├── prompts.py             # System prompt templates
│   ├── logger.py              # Logging
│   ├── common.py              # Common utilities
│   └── extract_schemas*.py    # Tool call schema extractors
├── docker/                    
├── results/                   # Inference output storage
├── logs/                      # Logs directory
├── test_files/                # Test cases
└── test_all_tools.py          # Tool test script
```

## 🛠️ Tool List

- **wide_search:** General web search (multiple queries supported)
- **scholar_search:** Academic search (Google Scholar)
- **wide_visit:** Batch visiting of multiple web pages
- **file_wide_parse:** Batch parsing of various file formats (PDF, DOCX, CSV, MP4, MP3, etc.)
- **execute_code:** Secure Python code execution in a sandbox


## ⚙️ Configuration Guide

### `system_format` Parameter

Different LLM backends/platforms have varying requirements for function calling, tool results, and prompt concatenation. Use `--system_format` to specify the appropriate logic:

Options include: `tongyi_deepresearch`, `azure`, `aihubmix`, `aihubmix_claude`, `volcano`.

**Usage:**

From CLI:
```bash
python inference/run_batch_inference.py --system_format aihubmix ...
```

Or in code:
```python
result = await run_one_query(
    ...
    system_format="azure",
    ...
)
```

### LLM Client Configuration

Supports multi-path inference. The system automatically balances queries to the node with the lightest load, ensuring consistent handling for repeated queries.

#### vLLM Example
```python
llm_client_urls = ["http://node1:10777/vllm_generate", "http://node2:10778/vllm_generate"]
llm_client_models = ["<inference_model_name>", "<inference_model_name>"]
```

#### Azure OpenAI Example
```python
llm_client_urls = ["https://<your_special_id>.openai.azure.com/openai/v1/"]
llm_client_models = ["gpt-5"]
system_format = "azure"
```

#### AIHubMix (OpenAI Format)
```python
llm_client_urls = ["https://aihubmix.com/v1"]
llm_client_models = ["gpt-5"]
system_format = "aihubmix"
```

#### AIHubMix (Claude Format)
```python
llm_client_urls = ["https://aihubmix.com/v1"]
llm_client_models = ["claude-3.5-sonnet"]
system_format = "aihubmix_claude"
```

#### Volcano Engine Example
```python
llm_client_urls = ["https://ark.cn-beijing.volces.com/api/v3"]
llm_client_models = ["ep-xxx"]
system_format = "volcano"
```

### Tool Configurations

See `utils/configs.py`:
- `TOOLS_SERVER_BASE_ENDPOINT_URL`: List of tool server addresses (supports load balancing)
- `WEB_BASED_TOOLS_USE_CACHE`: Use cache for web-based tools
- `USE_TONGYI_FORMAT_RETURN`: Return format (JSON or plain text)
- `CLIENTTIMEOUT`: LLM client timeout in seconds

### Inference Parameters

- `--concurrency_workers`: Number of concurrent workers (default: 10)
- `--save_batch_size`: Number of results per checkpoint save (default: 1)
- `--max_rounds`: Max conversation turns (default: 100)
- `--temperature`: Sampling temperature (default: 0.7)
- `--timeout_for_one_query`: Max duration per query in seconds (default: 7200)
- `--resume_from_file`: Resume from file (skips finished items)

## 📝 Input Data Format

The input file must be in JSONL format. Each line should be a JSON object (**must contain `id`, `question`, and `file_path` fields**):

```json
{"id": "query_001", "question": "What was the average age of Alibaba's 18 founding members surnamed Ma, Cai, and Zhang at the time of its founding? Round to one decimal.", "file_path": ""}
{"id": "query_002", "question": "After reading the current instruction manual, how much milliamp-hour power remains in the DJI AIR series drone with the largest takeoff weight after flying half a marathon (with minimal energy consumption at 60% of maximum speed)?", "file_path": "/path/to/file.pdf"}
```

Field reference:
- `id`: Unique query identifier
- `question`: User query
- `file_path`: Optional file path (for multimodal tasks)
- Other custom fields are allowed. Original input fields will be available under the `src` key of the output.

## 📤 Output Data Format

Each inference output is a JSON line containing the complete result:

```json
{
  "time_stamp": "2025-12-05 10:30:00",
  "query_id": "uuid_hash",
  "query": "user query",
  "result": {
    "query_id": "uuid_hash",
    "tools": "[tool list JSON]",
    "messages": [conversation messages],
    "final_answer": "final answer",
    "transcript": [full dialog history],
    "rounds": 5,
    "stopped_reason": "no_tool_calls"
  },
  "status": "success",
  "elapsed_sec": 123.456,
  "src": {original input data}
}
```

## 🔍 Logging System

### Log Directory Structure

```
logs/
├── {log_label}/                    
│   ├── collect.log                # Batch summary log
│   └── {query_id}/                # Per-query logs
│       ├── run.log                # Runtime log
│       └── result.json            # Result JSON
```

## 🧪 Tool Testing

Run the tool test script to verify all registered tools:

```bash
python test_all_tools.py
```

This script checks the basic functionality of all tools.

## 🔧 Advanced Features

### Load Balancing

Run with multiple LLM endpoints:
```bash
--llm_client_urls "http://node1:10777/vllm_generate" "http://node2:10777/vllm_generate"
```
The system distributes queries to less-loaded nodes and guarantees consistent node assignment for repeated queries.

### Resumable Inference

By specifying `--resume_from_file`, the system will:
1. Load finished results
2. Extract completed query IDs
3. Skip these and only process unfinished queries

### Custom System Prompts

```bash
--system_prompt "You are a helpful assistant."
# Or load from file:
--system_prompt "./custom_system_prompt.txt"
```

### Custom Tool Sets

Specify available tools with:
```bash
--available_tools wide_search scholar_search file_wide_parse execute_code wide_visit
```

