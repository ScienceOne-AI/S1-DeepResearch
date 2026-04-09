#!/bin/bash

# 可选：通过 JSON / 环境变量覆盖 `utils.config` 中的配置
# 示例 1：指定 JSON 配置文件（优先级最高）
# export S1_DR_CONFIG_JSON="utils/config/config.example.json"
#
# 示例 2：直接用环境变量覆盖
# export CLIENT_TIMEOUT=7200
# export USE_NLP_FORMAT_RETURN=true
# export MY_NEW_FLAG="demo_value"

# system prompt 参数
SYSTEM_PROMPT="" # 标准的 9 个工具 system prompt

LLM_CLIENT_URLS="http://url:port/v1/chat/completions http://url:port/v1/chat/completions"
LLM_CLIENT_MODELS="model_name1 model_name1"

TEST_DATA_FILE="test.jsonl"
OUTPUT_FILE="test_results.jsonl"

# OUTPUT_DIR 仅在 Pass@K（多次 rollout）场景下生效。
# 当 ROLLOUT_NUM=1 时，忽略 OUTPUT_DIR；单次推理结果写入 OUTPUT_FILE 所指定的 jsonl 路径。
# 当 ROLLOUT_NUM≠1 时，忽略 OUTPUT_FILE；在 OUTPUT_DIR 下按 xxx_01.jsonl、xxx_02.jsonl、… 命名保存各次 rollout 结果。
OUTPUT_DIR=""
# 启动所有的 9 个工具
AVAILABLE_TOOLS="wide_search scholar_search file_wide_parse execute_code wide_visit ask_question_about_image ask_question_about_video image_search bash"
ROLLOUT_NUM=1
RESUME_FROM_FILE=""

# LOGGING_ROOT：日志根路径；在其下创建 `logs` 子目录。例如设为 "/app" 时，日志目录为 "/app/logs"。
LOGGING_ROOT=""
# LOG_LABEL：日志标签；运行日志写入 `logs/YYYY_MM_DD_<LOG_LABEL>/` 子目录（与 LOGGING_ROOT 组合使用时，位于上述 logs 路径之下）。
LOG_LABEL="test"
LOG_FILE="run_logs/run.log"

# 仅在与附件相关的任务中需调整 TASK_TYPE；其余推理任务可沿用默认值，无需修改该参数。
TASK_TYPE="input_only" 
MAX_ROUNDS=100
CONCURRENCY_WORKERS=16
SAVE_BATCH_SIZE=10
TEMPERATURE=0.7
TOP_P=0.95
# 额外的 payload 参数（JSON 字符串），透传给模型 API，可按需增减字段
# 不需要额外参数时设为空 JSON：EXTRA_PAYLOAD='{}'
EXTRA_PAYLOAD='{"presence_penalty": 0.0}'
TIMEOUT_FOR_ONE_QUERY=3600
LLM_API_RETRY_TIMES=2
# discard-all：此处为 false，表示不启用该模式
DISCARD_ALL_MODE="false"
MODEL_MAX_CONTEXT_TOKENS=128000
DISCARD_RATIO=0.8
TOKENIZER_PATH="models/tokenizer"

PARAM_INFO=$(
cat <<EOF
========== Run Parameters ==========
Start Time: $(date)
LLM_CLIENT_URLS: $LLM_CLIENT_URLS
LLM_CLIENT_MODELS: $LLM_CLIENT_MODELS
TEST_DATA_FILE: $TEST_DATA_FILE
OUTPUT_FILE: $OUTPUT_FILE
OUTPUT_DIR: $OUTPUT_DIR
AVAILABLE_TOOLS: $AVAILABLE_TOOLS
CONCURRENCY_WORKERS: $CONCURRENCY_WORKERS
SAVE_BATCH_SIZE: $SAVE_BATCH_SIZE
ROLLOUT_NUM: $ROLLOUT_NUM
MAX_ROUNDS: $MAX_ROUNDS
TEMPERATURE: $TEMPERATURE
TOP_P: $TOP_P
EXTRA_PAYLOAD: $EXTRA_PAYLOAD
TIMEOUT_FOR_ONE_QUERY: $TIMEOUT_FOR_ONE_QUERY
LLM_API_RETRY_TIMES: $LLM_API_RETRY_TIMES
DISCARD_ALL_MODE: $DISCARD_ALL_MODE
MODEL_MAX_CONTEXT_TOKENS: $MODEL_MAX_CONTEXT_TOKENS
DISCARD_RATIO: $DISCARD_RATIO
TOKENIZER_PATH: $TOKENIZER_PATH
RESUME_FROM_FILE: $RESUME_FROM_FILE
LOG_LABEL: $LOG_LABEL
TASK_TYPE: $TASK_TYPE
LOGGING_ROOT: $LOGGING_ROOT
SYSTEM_PROMPT: $SYSTEM_PROMPT
Shell PID: $$
====================================
EOF
)
echo "$PARAM_INFO"
echo "$PARAM_INFO" > "$LOG_FILE"

# 使用 nohup 在后台启动 Python：标准输出与标准错误追加写入 LOG_FILE；随后将进程 PID 输出至终端，并同步追加至 LOG_FILE。
# 当 TASK_TYPE 为 input_only 时，须在命令行中加入 --clean_files_copy_dir。
if [ "$TASK_TYPE" = "input_only" ]; then
  nohup python inference/run_batch_inference.py \
    --llm_client_urls $LLM_CLIENT_URLS \
    --llm_client_models $LLM_CLIENT_MODELS \
    --test_data_file "$TEST_DATA_FILE" \
    --output_file "$OUTPUT_FILE" \
    --output_dir "$OUTPUT_DIR" \
    --available_tools $AVAILABLE_TOOLS \
    --concurrency_workers $CONCURRENCY_WORKERS \
    --save_batch_size $SAVE_BATCH_SIZE \
    --rollout_num $ROLLOUT_NUM \
    --max_rounds $MAX_ROUNDS \
    --temperature $TEMPERATURE \
    --top_p $TOP_P \
    --extra_payload "$EXTRA_PAYLOAD" \
    --timeout_for_one_query $TIMEOUT_FOR_ONE_QUERY \
    --llm_api_retry_times $LLM_API_RETRY_TIMES \
    --discard_all_mode "$DISCARD_ALL_MODE" \
    --model_max_context_tokens $MODEL_MAX_CONTEXT_TOKENS \
    --discard_ratio $DISCARD_RATIO \
    --tokenizer_path "$TOKENIZER_PATH" \
    --resume_from_file "$RESUME_FROM_FILE" \
    --log_label "$LOG_LABEL" \
    --logging_root "$LOGGING_ROOT" \
    --system_prompt "$SYSTEM_PROMPT" \
    --verbose \
    --clean_files_copy_dir \
    >> "$LOG_FILE" 2>&1 &
else
  nohup python inference/run_batch_inference.py \
    --llm_client_urls $LLM_CLIENT_URLS \
    --llm_client_models $LLM_CLIENT_MODELS \
    --test_data_file "$TEST_DATA_FILE" \
    --output_file "$OUTPUT_FILE" \
    --output_dir "$OUTPUT_DIR" \
    --available_tools $AVAILABLE_TOOLS \
    --concurrency_workers $CONCURRENCY_WORKERS \
    --save_batch_size $SAVE_BATCH_SIZE \
    --rollout_num $ROLLOUT_NUM \
    --max_rounds $MAX_ROUNDS \
    --temperature $TEMPERATURE \
    --top_p $TOP_P \
    --extra_payload "$EXTRA_PAYLOAD" \
    --timeout_for_one_query $TIMEOUT_FOR_ONE_QUERY \
    --llm_api_retry_times $LLM_API_RETRY_TIMES \
    --discard_all_mode "$DISCARD_ALL_MODE" \
    --model_max_context_tokens $MODEL_MAX_CONTEXT_TOKENS \
    --discard_ratio $DISCARD_RATIO \
    --tokenizer_path "$TOKENIZER_PATH" \
    --resume_from_file "$RESUME_FROM_FILE" \
    --log_label "$LOG_LABEL" \
    --logging_root "$LOGGING_ROOT" \
    --system_prompt "$SYSTEM_PROMPT" \
    --verbose \
    >> "$LOG_FILE" 2>&1 &
fi

PY_PID=$!
echo "Python running as PID: $PY_PID"
echo "Python running as PID: $PY_PID" >> "$LOG_FILE"
