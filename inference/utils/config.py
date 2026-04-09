# 默认配置（最低优先级）
# 1. 自定义 JSON 文件：
#    - 设置环境变量 `S1_DR_CONFIG_JSON=/path/to/config.json`
#    - 或在仓库中放置 `config.local.json` / `config.json`
#    - 或在 `utils/config/` 下放置同名文件
# 2. 环境变量：支持 `KEY`、`S1_DR_KEY`、`DR_SKILLS_KEY`
# 3. 本文件对应的 `utils/config.py`
#
# `utils/configs.py` 会按以上优先级统一读取配置。
# 建议把真实私有配置写到 JSON 或环境变量中，把 `utils/config.py` 保持为默认值。

LITERATURE_SEED_DATA_DIR = "/app/logs"

TOOLS_SERVER_BASE_ENDPOINT_URL = [
    "http://url:port",
]

LLM_SERVER_BASE_ENDPOINT_URL = [
    "http://url/v1/chat/completions",
]

LLM_SERVER_MODEL_NAME = [
    "demo_model",
]

WEB_BASED_TOOLS_USE_CACHE = True
USE_NLP_FORMAT_RETURN = True
CLIENT_TIMEOUT = 1800

AIHUBMIX_KEY = "<your_api_key>"
AZURE_KEY = "<your_api_key>"
VOLCANO_KEY = "<your_api_key>"
ALIYUN_KEY = "<your_api_key>"

ONLINE_PLATFORM = ["aihubmix", "aihubmix_claude", "aihubmix_glm", "azure", "volcano", "aliyun"]
