import ast
import json
import re
from typing import Any, Dict, List
from tqdm import tqdm
import os
from datetime import datetime
from urllib.parse import urlparse
import uuid
import hashlib
from transformers import AutoTokenizer


_TOKENIZER_CACHE = {}


# 读取测试文件
def load_jsonl(file_path):
    """加载 JSONL 文件"""
    print("reading file: ", file_path)
    data = []
    with open(file_path, 'r') as file:
        for line in tqdm(file, desc="Loading JSONL data"):
            data.append(json.loads(line))
    return data

# 存储文件
def save_jsonl(data, file_path):
    """保存数据为 JSONL 文件"""
    with open(file_path, 'w') as file:
        for item in tqdm(data, desc="Saving JSONL data"):
            file.write(json.dumps(item, ensure_ascii=False) + '\n')

# 获取目录下的多模态文件
def get_images_under_dir(dir_path):
    """获取目录下所有图片文件的路径"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
    image_files = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            if os.path.splitext(file)[1].lower() in image_extensions:
                image_files.append(os.path.join(root, file))
    return image_files

def today_date():
    return datetime.now().strftime("%Y-%m-%d")

def contains_chinese_basic(text: str) -> bool:
    # 判定是否有中文
    return any('\u4E00' <= char <= '\u9FFF' for char in text)

def switch_language(quesiton:str, zh_des:str, en_des:str):
    if contains_chinese_basic(quesiton):
        return zh_des
    else:
        return en_des

def get_query_uuid(query: str) -> str:
    """
    Generate a UUID based on the query content.
    对于同一个 query，总是返回一致的 UUID（确定性；结果唯一）。
    """
    # 用 query 的内容的 sha256 做为 deterministic namespace，确保同内容唯一
    sha = hashlib.sha256(query.encode("utf-8")).hexdigest()
    # 用 uuid5 根据 sha 结果生成 uuid（uuid5 是 deterministic 的，只要 name 一样就一样）
    return str(uuid.uuid5(uuid.NAMESPACE_URL, sha))

def reorder_keys(d) -> dict:
    """
    为了让 openai 返回的字段顺序更符合阅读习惯（如 role、content、type 排在前面），提升可读性
    """
    # 只对 dict 类型进行重排
    if not isinstance(d, dict):
        return d
    new_dict = {}
    keys = list(d.keys())
    if 'id' in keys:
        new_dict['id'] = d['id']
    if 'role' in keys:
        new_dict['role'] = d['role']
    if 'content' in keys:
        new_dict['content'] = d['content']
    if 'type' in keys:
        new_dict['type'] = d['type']
    # 其余字段按原有顺序添加，避免重复
    for k in keys:
        if k not in new_dict:
            new_dict[k] = d[k]
    return new_dict


def extract_candidate_object(cand):
    """
    尝试用多种方式解析 cand（字典/列表的字符串表达）为 Python 对象。
    优先使用 ast.literal_eval 和 json.loads，最后才用 eval。
    若都失败，返回空字典。
    """
    for loader in (ast.literal_eval, json.loads, eval):
        try:
            obj = loader(cand)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return {}


def _join_if_relative(base_dirs: List| None, value: str) -> str:
    if base_dirs:
        for base_dir in base_dirs:
            if value in base_dir:
                # 返回真正的存储路径 /app/literature_seed/...
                return base_dir
    # 没找到这个文件 
    return value

def _prefix_files(base_dirs: List | None, files: Any, file_prefix, prefix_mode) -> Any:
    if prefix_mode == "inference":
        # 换成对应的 docker 中的路径
        if isinstance(files, list):
            return [_join_if_relative(base_dirs, item) for item in files]
        if isinstance(files, str):
            return _join_if_relative(base_dirs, files)
    else:
        # 用于评测时，直接把前缀加上形成 docker 中的路径
        if file_prefix:
            if isinstance(files, list):
                return [_add_prefix(file_prefix, item) for item in files]
            elif isinstance(files, str):
                return _add_prefix(file_prefix, files)
    return files

def _is_url(path: str) -> bool:
    parsed = urlparse(path)
    return bool(parsed.scheme)

def _add_prefix(file_prefix, file_path:str)  -> str:
    if file_prefix is None or file_prefix in file_path:
        return file_path
    # url 也不需要拼接
    if _is_url(file_path):
        return file_path
    return os.path.join(file_prefix, file_path)

def _to_bool(v, default = False) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

def count_tokens(text: str, tokenizer_path) -> int:
    cache_key = str(tokenizer_path)
    tokenizer = _TOKENIZER_CACHE.get(cache_key)
    if tokenizer is None:
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, trust_remote_code=True)
        _TOKENIZER_CACHE[cache_key] = tokenizer
    tokens = tokenizer(
        text,
        return_attention_mask=False,
        add_special_tokens=False,
        return_tensors=None
    )["input_ids"]
    num_tokens = len(tokens)
    return num_tokens


def _extract_total_tokens(usage) -> int:
    if not isinstance(usage, dict):
        return -1
    try:
        return int(usage.get("total_tokens", -1))
    except (TypeError, ValueError):
        return -1

def _estimate_message_tokens(log_messages: List[Dict[str, Any]], tokenizer_path: str) -> int:
    last_usage_idx = -1
    last_usage_tokens = 0
    for idx in range(len(log_messages) - 1, -1, -1):
        token_val = _extract_total_tokens(log_messages[idx].get("usage"))
        if token_val >= 0:
            last_usage_idx = idx
            last_usage_tokens = token_val
            break
    untracked_messages = log_messages[last_usage_idx + 1 :] if last_usage_idx >= 0 else log_messages
    if not untracked_messages:
        return last_usage_tokens
    untracked_messages_text = "\n".join(json.dumps(msg, ensure_ascii=False) for msg in untracked_messages)
    return last_usage_tokens + count_tokens(untracked_messages_text, tokenizer_path)
