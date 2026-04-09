import logging
import datetime
import os
import json
import time

# --------- 每个 query 日志文件统一存放 logs/yyyy_mm_dd/query_id/run.log ------------
def get_log_file_for_query(query_id: str, project_root: str, log_label:str):
    today = datetime.date.today().strftime('%Y_%m_%d')
    logs_base_dir = os.path.join(project_root, "logs", f"{today}_{log_label}", f"{query_id}")
    os.makedirs(logs_base_dir, exist_ok=True)
    filename = f"run.log"
    return os.path.join(logs_base_dir, filename)

# 创建 log 文件夹路径
def get_logs_base_dir_for_query(query_id: str, project_root:str, log_label:str):
    today = datetime.date.today().strftime('%Y_%m_%d')
    logs_base_dir = os.path.join(project_root, "logs", f"{today}_{log_label}", query_id)
    return logs_base_dir

# 设置 logger 配置
def setup_logger_for_query(query_id: str, project_root:str, log_label:str):
    log_file_path = get_log_file_for_query(query_id, project_root, log_label)
    logger = logging.getLogger(f"single_inference_{query_id}_{log_label}")
    logger.setLevel(logging.INFO)
    # Remove any previous handlers (important if rerunning in a notebook)
    if logger.hasHandlers():
        logger.handlers.clear()
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    fh = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger, log_file_path

# 当前 result 存到对应的 log 文件夹下
def save_result_to_log_dir(query_id: str, result_obj, project_root: str, log_label: str):
    logs_base_dir = get_logs_base_dir_for_query(query_id, project_root, log_label)
    os.makedirs(logs_base_dir, exist_ok=True)
    result_path = os.path.join(logs_base_dir, "result.json")
    try:
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result_obj, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # 基础的异常捕捉方便debug
        print(f"[run_single_inference.py] 保存 result.json 失败: {e}")


# --------- batch 日志文件统一存放 logs/yyyy_mm_dd_label/collect.log ------------
def get_batch_collect_log_path(project_root: str, log_label: str):
    today = datetime.date.today().strftime('%Y_%m_%d')
    logs_base_dir = os.path.join(project_root, "logs", f"{today}_{log_label}")
    os.makedirs(logs_base_dir, exist_ok=True)
    return os.path.join(logs_base_dir, "collect.log")

def setup_collect_logger(project_root, log_label):
    log_path = get_batch_collect_log_path(project_root, log_label)
    logger = logging.getLogger(f"batch_collect_logger_{log_label}")
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    fh = logging.FileHandler(log_path, mode='a', encoding='utf-8')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger, log_path
