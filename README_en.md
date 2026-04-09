
<div align="center">

# S1-DeepResearch: End-to-End Models for Long-Horizon Deep Research

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=for-the-badge)](./LICENSE)
[![HuggingFace](https://img.shields.io/badge/🤗%20HuggingFace-S1--DeepResearch--15k-0040A1?style=for-the-badge)](https://huggingface.co/datasets/ScienceOne-AI/S1-DeepResearch-15k)
[![HuggingFace](https://img.shields.io/badge/🤗%20HuggingFace-S1--DeepResearch--32B-ffd21e?style=for-the-badge)](https://huggingface.co/ScienceOne-AI/S1-DeepResearch-32B)
[![ModelScope](https://img.shields.io/badge/🤖%20ModelScope-S1--DeepResearch--32B-mediumpurple?style=for-the-badge)](https://modelscope.cn/models/ScienceOne-AI/S1-DeepResearch-32B)

English | [中文](./README.md)

</div>

<hr>

## 🔥 News & Updates

- **[2026/04/04]** 🎉 We release [**S1-DeepResearch-32B**](https://huggingface.co/ScienceOne-AI/S1-DeepResearch-32B), an end-to-end agentic model for long-horizon deep research, with stronger emphasis on **real-world deployment**—beyond **long-chain complex reasoning**, it focuses on **deep-research instruction following**, **deep research report writing**, **file understanding and generation**, and **skills using**. On **20 agentic capability benchmarks**, it **outperforms the base model Qwen3-32B by a clear margin across the board**, and overall performance is close to mainstream closed-source flagship models (**GPT 5.2**, **Claude 4.6**, **GLM-5**). Inference code and the [**15K agent training trajectory dataset**](https://huggingface.co/datasets/ScienceOne-AI/S1-DeepResearch-15k) (a subset of the full training data) are released together.
- **[2025/12/31]** We open-sourced [**S1-DeepResearch-8B-Preview**](https://huggingface.co/ScienceOne-AI/S1-DeepResearch-8B-Preview), focusing on **general long-chain complex reasoning** and exploring what is feasible in deep research at a smaller parameter scale.

## 📝 Overview

**S1-DeepResearch-32B** is an end-to-end model developed by the ScienceOne AI for **long-horizon deep research**. Its core capabilities span **five dimensions**:

- **Long-chain complex reasoning**: Supports sustained reasoning and action across multi-stage, multi-hop tasks, going beyond single-step Q&A. Through cross-document retrieval, evidence aggregation, state memory, and policy iteration, it plans paths, integrates information, and converges results in complex settings, keeping the reasoning process stable and conclusions reliable.

- **Deep research instruction following**: Parses multi-constraint instructions in deep research scenarios and builds an instruction-understanding paradigm along the full research chain—**task definition → mechanisms → tool execution → result presentation**—with coordinated constraints across cognition, artifacts, execution, and environment so complex tasks stay controllable, processes predictable, and outputs aligned with intent.

- **Deep research report writing**: Produces arguable, citable report-style outputs on top of information integration; organizes multi-source material and evidence checks while balancing structure, readability, and traceability—suited for scientific writing and decision support.

- **File understanding and generation**: Covers PDFs, tables, web pages, and other modalities for input understanding, plus structured, deliverable outputs. In multi-turn tool-augmented interaction, it keeps semantics and execution aligned, closing the loop **parse → process → generate** and reducing repetitive manual work in research and data-heavy workflows.

- **Skills Using**: Organizes literature search, data analysis, experiment design, computational modeling, visualization, report generation, and more as callable modules, dynamically assembled and progressively loaded toward task goals, supporting continuous workflows from data acquisition to presentation.

### ✨ Key Features

- **Ultra-long context modeling**: A **128K** context window lets a single session hold longer evidence chains and multi-turn interaction history, suited to long-horizon research tasks.
- **Long-horizon tool calling**: Stably runs **150+** consecutive tool-call rounds, building reasoning-driven tool orchestration and a decision closed loop—enabling continuous planning, execution, and self-correction across multi-stage tasks.
- **Native tool ecosystem**: **9** built-in common tools (e.g., search, web browsing, code execution, command line) ready to use out of the box.

## 🚀 Model Download

<div align="center">

| Model | Parameters | Context length | Download |
| :---: | :---: | :---: | :---: |
| **S1-DeepResearch-32B** | 32B | 128k | [🤗 HuggingFace](https://huggingface.co/ScienceOne-AI/S1-DeepResearch-32B) \| [🤖 ModelScope](https://modelscope.cn/models/ScienceOne-AI/S1-DeepResearch-32B) |
| **S1-DeepResearch-8B-Preview** | 8B | 128k | [🤗 HuggingFace](https://huggingface.co/ScienceOne-AI/S1-DeepResearch-8B-Preview) \| [🤖 ModelScope](https://modelscope.cn/models/ScienceOne-AI/S1-DeepResearch-8B-Preview) |

</div>

## 📊 Evaluation

We systematically evaluated **S1-DeepResearch-32B** on **20 agentic capability benchmarks** grouped into **5 dimensions** aligned with the five capability areas:

- **Long-chain complex reasoning**: Text—GAIA (text), BrowseComp, BrowseComp-ZH, XBench-DeepSearch, HLE (text); vision-language—LiveVQA, MM-Search, BrowseComp-VL, RealX-Bench, HLE-VL, MM-BrowseComp.
- **Deep research instruction following**: ComplexBench, DeepResearchIF (in-house).
- **Deep research report writing**: DeepResearch Bench, DeepResearch Bench II, Research Rubrics.
- **File understanding and generation**: GAIA (file), GTA, FileSys (in-house).
- **Skills Using**: SkillsUse (in-house).

<div align="center">

<img src="./assets/benchmark_performance.png" alt="S1-DeepResearch-32B vs. base and closed-source flagships on 20 agentic benchmarks" width="800" />

</div>

**S1-DeepResearch-32B** gains a **clear advantage** over the base **Qwen3-32B** and the larger **Qwen3-235B** on all listed benchmarks; on in-house leaderboards for deep-research instruction following, file understanding and generation, and skill invocation, it also **surpasses Qwen3.5-397B**. Overall performance is close to mainstream closed-source flagships (**GPT 5.2**, **Claude 4.6**, **GLM-5**, **Kimi-K2.5**). Public benchmarks and internal tasks are mutually consistent, indicating that S1-DeepResearch-32B is **ready for real business deployment**.

## 📂 Example Cases

Below is an example of **S1-DeepResearch-32B** using skills: during materials modeling, the model first invokes the scientific skill `scientific-skills/pymatgen` for domain knowledge, then follows the skill guidance to run modeling with `pymatgen` and outputs a CIF file.

<div align="center">

<img src="./cases/case_skills_science_en_01.png" alt="English scientific skills collaboration example" width="600" />

</div>

More cases will be added under the `cases/` directory.

## 🚀 Quick Start

### Environment setup

1. **Install dependencies**:

```bash
pip install -r requirements.txt
```

2. **Docker setup**

The project provides official pre-built Docker images for fast deployment. There are two core images:

- **toolkits-api**: Main tool-service container (exposes API capabilities)
- **code-sandbox**: Code-execution sandbox image (created on demand by the service for isolated runs)

Execution-oriented tools (`execute_code`, `bash`) use **Docker-outside-of-Docker (DooD)**: by mounting the host Docker socket, the tool container talks to the host Docker daemon and creates isolated sandbox containers as needed.

**Image tags:**

```text
ghcr.io/wenge-research/toolkits-api:v2.0.260403
ghcr.io/wenge-research/code-sandbox:v1.0.260403
```

**Pull images:**

```text
docker pull ghcr.io/wenge-research/toolkits-api:v2.0.260403
docker pull ghcr.io/wenge-research/code-sandbox:v1.0.260403
```

**Run the container**

Mount `src/config.yaml`, the Docker socket (for sandbox execution), and optionally log and cache directories:

```bash
docker run -d \
  --name toolkits-api \
  --network host \
  -e API_PORT=8080 \
  -e API_WORKERS=4 \
  -e HOST_LOG_DIR=$(pwd)/logs \
  -e SANDBOX_MODE=docker \
  -e HTTP_PROXY=http://your-proxy:port \
  -e HTTPS_PROXY=http://your-proxy:port \
  -e PROXY_URL=http://your-proxy:port \
  -v /etc/localtime:/etc/localtime:ro \
  -v /etc/timezone:/etc/timezone:ro \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/src/config.yaml:/app/src/config.yaml \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/cache:/app/cache \
  ghcr.io/wenge-research/toolkits-api:v2.0.260403
```

**Parameter reference**

| Flag / env | Description |
|------|------|
| `-e API_PORT` | Listen port, default 8080 |
| `-e API_WORKERS` | Number of worker processes; tune for concurrency, default 1 |
| `-e SANDBOX_MODE=docker` | Enable Docker sandbox mode (otherwise subprocess) |
| `-e HOST_LOG_DIR` | Host log directory for sandbox mounts when Docker sandbox is enabled |
| `-e HTTP_PROXY / HTTPS_PROXY / PROXY_URL` | Proxy settings (optional) |
| `--network host` | Use if you rely on a proxy bound on the host (optional) |
| `-v /etc/localtime:/etc/localtime:ro` | Sync host timezone (read-only) |
| `-v /etc/timezone:/etc/timezone:ro` | Sync host timezone file (read-only) |
| `-v /var/run/docker.sock` | Required for Docker sandbox mode to schedule sandbox containers |
| `-v config.yaml` | Mount config (API keys, model and sandbox settings) |
| `-v logs` | Mount log directory (optional) |
| `-v cache` | Mount cache directory; structure mirrors `/app/cache` inside the container (optional) |


3. **Configure the tool service URL**

Prefer JSON config or environment variables to override defaults. Avoid editing `utils/configs.py` directly.

**Option A (recommended): local JSON**

Copy from the example and edit locally:

```bash
cp utils/config/config.example.json utils/config/config.local.json
```

Set the tool service base URL in `utils/config/config.local.json`, for example:

```json
{
  "TOOLS_SERVER_BASE_ENDPOINT_URL": [
    "http://127.0.0.1:8080"
  ]
}
```

**Option B: environment variables**

Point to a config file or override individual keys:

```bash
export S1_DR_CONFIG_JSON="utils/config/config.local.json"
# or override TOOLS_SERVER_BASE_ENDPOINT_URL only
export TOOLS_SERVER_BASE_ENDPOINT_URL='["http://127.0.0.1:8080"]'
```

4. **API keys**

Prefer `utils/config/config.local.json` for provider keys, or mirror the same names with environment variables:

```json
{
  "AIHUBMIX_KEY": "<your_aihubmix_key>",
  "AZURE_KEY": "<your_azure_key>",
  "VOLCANO_KEY": "<your_volcano_key>",
  "ALIYUN_KEY": "<your_aliyun_key>"
}
```

Environment variables:

```bash
export AIHUBMIX_KEY="<your_aihubmix_key>"
export AZURE_KEY="<your_azure_key>"
export VOLCANO_KEY="<your_volcano_key>"
export ALIYUN_KEY="<your_aliyun_key>"
```

### Single-query inference

```python
import asyncio

from server.llm_api import LLMClient
from server.tool_api import return_all_tools
from inference.run_single_inference import run_one_query
from utils.prompts import DEEPRESEARCH_SYSTEM_PROMPT


async def main():
    llm_client_urls = ["http://127.0.0.1:10777/v1/chat/completions"]
    llm_client_models = ["S1-DeepResearch-32B"]
    llm_client = LLMClient(llm_client_urls, llm_client_models)

    all_tools = return_all_tools()

    result = await run_one_query(
        llm=llm_client,
        user_query="阿里巴巴成立时，18位创始团队成员中，姓马、姓蔡、姓张的创始人的平均年龄，保留一位小数",
        file_path=[],
        system=DEEPRESEARCH_SYSTEM_PROMPT,
        max_rounds=15,
        temperature=0.4,
        top_p=0.95,
        extra_payload={},
        debug=True,
        all_tools=all_tools,
        system_format="deep_research",
        log_label="quick_start_single",
    )

    final_answer = result[-1]["final_answer"] if result else ""
    print(final_answer)


if __name__ == "__main__":
    asyncio.run(main())
```

Notes:

- `file_path` must be a `list` in the current implementation (e.g. `[]` or `['/path/a.pdf']`).
- `system_format` options: `deep_research`, `azure`, `aihubmix`, `aihubmix_claude`, `aihubmix_glm`, `volcano`, `aliyun`.

### Batch inference

Local / vLLM:

```bash
cd inference
cp run_batch_inference_demo.sh run_batch_local.sh
# Edit run_batch_local.sh (LLM_CLIENT_URLS, LLM_CLIENT_MODELS, TEST_DATA_FILE, etc.)
bash run_batch_local.sh
```

Hosted APIs:

```bash
cd inference
cp run_batch_inference_online_demo.sh run_batch_online.sh
# Edit run_batch_online.sh (LLM_CLIENT_URLS, LLM_CLIENT_MODELS, SYSTEM_FORMAT, etc.)
bash run_batch_online.sh
```

Logs:

```bash
tail -f run_logs/*.log
```

📖 **[Advanced usage](./inference/README.md)**.

## 🔭 Future Work

- **S1-DeepResearch Paper:** We expect to release the paper within about two weeks, covering data synthesis for the five capability areas, training and inference design, test-time scaling, and key evaluation takeaways.
- **S1-DeepResearch-VL:** In the first half of 2026, we plan to release **S1-DeepResearch-VL** with vision understanding and cross-modal reasoning for richer research-style tasks.

## 📜 License

This project is licensed under the **[Apache License 2.0](./LICENSE)**.

## Citation

If S1-DeepResearch is useful to your work, please consider citing:

```bibtex
@software{s1deepresearch2026,
    title={S1-DeepResearch: End-to-End Deep Research Models},
    author={ScienceOne Team},
    year={2026},
    url={https://github.com/ScienceOne-AI/S1-DeepResearch},
}
```
