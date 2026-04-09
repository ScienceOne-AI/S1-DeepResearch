import os
from pathlib import Path
from typing import Any, Dict, Iterable, List


SKILL_USAGE_GUIDE_TEXT = """# Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. Below is the list of skills that can be used. Each entry includes a name, description, and file path so you can open the source for full instructions when using a specific skill.

## Available Skills
{available_skills}

## How to Use Skills

* Discovery: Skills are listed with their name, description, and file path. You can open the source for full instructions.
* Triggering: If the user names a skill OR the task clearly matches a skill's description shown above, you must use that skill for that turn. Multiple mentions mean use them all. Do not carry skills across turns unless re-mentioned.
* Missing/Blocked Skills: If a named skill isn't in the list or the path can't be read, say so briefly and continue with the best fallback.
* Using a Skill (progressive disclosure):
    1. After deciding to use a skill, open its `SKILL.md`. Read only enough to follow the workflow.
    2. If `SKILL.md` points to extra folders such as `references/`, load only the specific files needed for the request; don't bulk-load everything.
    3. If `scripts/` exist, prefer running or patching them instead of retyping large code blocks.
    4. If `assets/` or templates exist, reuse them instead of recreating from scratch.
* Coordination and Sequencing:
  * For multiple applicable skills, choose the minimal set and state the order.
  * Announce which skill(s) you're using and why (one short line).If you skip an obvious skill, say why.
* Context Hygiene:
  * Summarize long sections instead of pasting them; load extra files only when needed.
  * Avoid deep reference-chasing: prefer opening only files directly linked from `SKILL.md` unless you're blocked.
  * For variants (frameworks, providers, domains), pick the relevant reference files and note the choice.
* Fallback: If a skill can’t be applied due to missing files or unclear instructions, state the issue, pick the next-best approach, and proceed."""


def _has_non_empty_value(value: Any) -> bool:
    """
    判定值非空
    """
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def normalize_skill_path(skill_path: str) -> str:
    """
    把 skill path 整理成 skills/name/... 的形式
    """
    if not isinstance(skill_path, str):
        return ""
    normalized = skill_path.replace("\\", "/").strip()
    if not normalized:
        return ""
    normalized = normalized.rstrip("/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized.startswith("skills/"):
        return normalized
    marker = "/skills/"
    idx = normalized.rfind(marker)
    if idx >= 0:
        return normalized[idx + 1 :]
    idx = normalized.find("skills/")
    if idx >= 0:
        return normalized[idx:]
    return normalized


def normalize_skill_dir_path(skill_path: str) -> str:
    """
    只返回 skill_path 中的 skill 对应的文件夹 skills/name
    """
    normalized = normalize_skill_path(skill_path)
    if normalized.endswith("/SKILL.md"):
        return normalized[: -len("/SKILL.md")]
    if normalized == "SKILL.md":
        return "skills"
    return normalized


def to_skill_file_path(skill_path: str) -> str:
    """
    返回 f"{normalized}/SKILL.md"
    """
    normalized = normalize_skill_dir_path(skill_path)
    if not normalized:
        return ""
    if normalized.endswith("SKILL.md"):
        return normalized
    return f"{normalized}/SKILL.md"


def _normalize_single_skill(skill_obj: Dict[str, Any]) -> Dict[str, str]:
    """
    获取 name，description，skill_path 字段返回
    """
    name = str(skill_obj.get("name", "") or "").strip()
    description = str(skill_obj.get("description", "") or "").strip()
    skill_path = str(skill_obj.get("skill_path", "") or "").strip()
    if "raw_skill_path" in skill_obj:
        raw_skill_path = str(skill_obj.get("raw_skill_path", "") or "").strip()
    else:
        # 只有第一次从数据集中读取的时候，是读取正式的路径结果，后续的 skill_path 都已经被处理成相对路径了
        raw_skill_path = str(skill_obj.get("skill_path", "") or "").strip()
    if skill_path: 
        skill_path = normalize_skill_dir_path(skill_path)
    return {
        "name": name,
        "description": description,
        "skill_path": skill_path,
        "raw_skill_path": raw_skill_path
    }


def deduplicate_skills(skills: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    去重重复的 skill（按照 skill path + name 同时作为一致性索引）
    """
    deduped: List[Dict[str, str]] = []
    seen = set()
    for skill in skills:
        normalized = _normalize_single_skill(skill if isinstance(skill, dict) else {})
        name = normalized.get("name", "")
        description = normalized.get("description", "")
        skill_path = normalized.get("skill_path", "")
        if not (name or skill_path):
            continue
        key = (skill_path.lower(), name.lower()) if skill_path else ("", name.lower())
        if key in seen:
            continue
        seen.add(key)
        if not skill_path and name:
            skill_path = f"skills/{name}"
            normalized["skill_path"] = skill_path
        deduped.append(normalized)
    return deduped


def extract_skills_from_row(row: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    找到 row 中的所有 skill
    """
    if not isinstance(row, dict):
        return []

    collected: List[Dict[str, Any]] = []

    other_skills = row.get("skills")
    if _has_non_empty_value(other_skills):
        if isinstance(other_skills, dict):
            collected.append(other_skills)
        elif isinstance(other_skills, list):
            for item in other_skills:
                if isinstance(item, dict) and _has_non_empty_value(item):
                    collected.append(item)

    return deduplicate_skills(collected)


def build_skills_system_text(skills: List[Dict[str, Any]]) -> str:
    """
    构建 system prompt 的 skill 部分完整文本，包括
     
    ##Available Skills 文本 动态拼接 和该部分内容的前后的所有 skill 相关的提示词
    需要注意的是，如果 skill 对应的 SKILL.md 文件不存在，这个 skill 会被判定为无效且跳过
    """
    normalized_skills = deduplicate_skills(skills)
    if not normalized_skills:
        return ""
    lines = []
    for skill in normalized_skills:
        name = skill.get("name", "").strip() or "unknown-skill"
        description = skill.get("description", "").strip() or "No description provided."
        file_path = to_skill_file_path(skill.get("skill_path", "").strip())
        if not file_path:
            # 跳过所有无效的 skill
            continue
        lines.append(f"- {name}: {description} (file: {file_path})")
    available_skills = "\n".join(lines)
    return SKILL_USAGE_GUIDE_TEXT.format(available_skills=available_skills).strip()


def resolve_skill_source_dirs(skills: List[Dict[str, Any]], project_root: str) -> List[str]:
    """
    返回所有不重复的 skill 的文件夹的绝对路径(读取 raw_skill_path 拿到真实 skill 所在的路径)
    """
    dirs: List[str] = []
    seen = set()
    for skill in deduplicate_skills(skills):
        skill_path = skill.get("raw_skill_path", "").strip()
        print("skill_path: ", skill_path)
        if not skill_path:
            continue
        abs_path = skill_path if os.path.isabs(skill_path) else os.path.join(project_root, skill_path)
        p = Path(abs_path)
        if p.is_file() and p.name == "SKILL.md":
            p = p.parent
        p_str = str(p.resolve()) if p.exists() else str(p)
        if p_str in seen:
            continue
        seen.add(p_str)
        dirs.append(p_str)
    return dirs
