import ast
import json
import re
from tqdm import tqdm
import os
from datetime import datetime
import uuid
import hashlib


def load_jsonl(file_path):
    """Load a JSONL file."""
    print("reading file: ", file_path)
    data = []
    with open(file_path, 'r') as file:
        for line in tqdm(file, desc="Loading JSONL data"):
            data.append(json.loads(line))
    return data

def save_jsonl(data, file_path):
    """Save data to a JSONL file."""
    with open(file_path, 'w') as file:
        for item in tqdm(data, desc="Saving JSONL data"):
            file.write(json.dumps(item, ensure_ascii=False) + '\n')

def get_images_under_dir(dir_path):
    """Get the paths of all image files under the directory."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
    image_files = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            if os.path.splitext(file)[1].lower() in image_extensions:
                image_files.append(os.path.join(root, file))
    return image_files

def today_date():
    return datetime.now().strftime("%Y-%m-%d")

def get_query_uuid(query: str) -> str:
    """
    Generate a UUID based on the query content.
    Always returns a consistent UUID (deterministic; unique per content) for the same query.
    """
    # Use the SHA256 hash of query content as a deterministic namespace to ensure uniqueness per content
    sha = hashlib.sha256(query.encode("utf-8")).hexdigest()
    # Use uuid5 to generate a deterministic uuid according to the sha result (uuid5 is deterministic, same name -> same uuid)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, sha))

def extract_json_from_answer(answer):
    """
    Extract a ```json ... ``` code block from an answer string and parse it as a list/object.
    """
    if not isinstance(answer, str):
        return {}
    pattern = r"```json(.*?)```"
    match = re.search(pattern, answer, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
        # print(json_str)
        try:
            # Try to parse with ast.literal_eval first
            return ast.literal_eval(json_str)
        except Exception:
            try:
                # Then try to parse with json.loads
                return json.loads(json_str)
            except Exception:
                try:
                    return eval(json_str)
                except Exception:
                    if "```json" in answer:
                        lines = answer.split("\n")
                        if lines[0].strip() == "```json" and lines[-1].strip() == "```":
                            content = "\n".join(lines[1:-1])
                            try:
                                return eval(content)
                            except Exception:
                                print("Eval failed after removing first and last lines")
                                return {}
                        return lines

                    print("Parse failed")
    return eval(answer)

def reorder_keys(d) -> dict:
    """
    Reorder the fields so that fields like 'role', 'content', 'type' appear at the front for better readability.
    """
    # Only reorder dicts
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
    # Add the remaining fields in original order, avoiding duplicates
    for k in keys:
        if k not in new_dict:
            new_dict[k] = d[k]
    return new_dict