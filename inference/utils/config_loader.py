import importlib
import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH_ENV_NAMES = (
    "S1_DR_CONFIG_JSON",
    "DR_SKILLS_CONFIG_JSON",
    "CONFIG_JSON_PATH",
)


class ConfigSource:
    def get(self, key: str, default: Any = None) -> Any:
        raise NotImplementedError


class JsonConfigSource(ConfigSource):
    def __init__(self, paths: list[Path]):
        self.paths = paths
        self._loaded = False
        self._data: dict[str, Any] = {}
        self.loaded_path: Path | None = None

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        for path in self.paths:
            if not path or not path.is_file():
                continue
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError(f"JSON config must be an object: {path}")
            self._data = data
            self.loaded_path = path
            return

    def get(self, key: str, default: Any = None) -> Any:
        self._load()
        return self._data.get(key, default)


class EnvConfigSource(ConfigSource):
    def __init__(self, defaults: dict[str, Any]):
        self.defaults = defaults

    def get(self, key: str, default: Any = None) -> Any:
        for env_name in _env_names_for_key(key):
            raw_value = os.environ.get(env_name)
            if raw_value is None:
                continue
            expected = self.defaults.get(key, default)
            return _coerce_value(raw_value, expected)
        return default


class PythonConfigSource(ConfigSource):
    def __init__(self, module_name: str):
        self.module_name = module_name
        self._module = None

    def _load_module(self, force_reload: bool = False):
        if self._module is None:
            self._module = importlib.import_module(self.module_name)
        elif force_reload:
            self._module = importlib.reload(self._module)
        return self._module

    def reload_module(self):
        module = self._load_module()
        stale_keys = [
            name
            for name, value in module.__dict__.items()
            if name.isupper() and not name.startswith("_") and not callable(value)
        ]
        for name in stale_keys:
            module.__dict__.pop(name, None)
        self._module = importlib.reload(module)
        return self._module

    def get(self, key: str, default: Any = None) -> Any:
        module = self._load_module()
        return getattr(module, key, default)

    def keys(self) -> tuple[str, ...]:
        module = self._load_module()
        return tuple(
            name
            for name, value in module.__dict__.items()
            if name.isupper() and not name.startswith("_") and not callable(value)
        )


class ConfigManager:
    def __init__(self) -> None:
        self._defaults_source = PythonConfigSource("utils.config")
        self._defaults_source.reload_module()
        self._keys = self._defaults_source.keys()
        self._defaults = self._load_defaults()
        self._sources = [
            JsonConfigSource(_discover_json_paths()),
            EnvConfigSource(self._defaults),
            self._defaults_source,
        ]

    @property
    def keys(self) -> tuple[str, ...]:
        return self._keys

    def _load_defaults(self) -> dict[str, Any]:
        defaults: dict[str, Any] = {}
        for key in self._keys:
            defaults[key] = self._defaults_source.get(key)
        return defaults

    def get(self, key: str) -> Any:
        fallback = self._defaults.get(key)
        for source in self._sources:
            value = source.get(key, None)
            if value is not None:
                return value
        return fallback

    def as_dict(self) -> dict[str, Any]:
        return {key: self.get(key) for key in self._keys}


def _discover_json_paths() -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()

    for env_name in CONFIG_PATH_ENV_NAMES:
        raw_path = os.environ.get(env_name)
        if raw_path:
            candidate = Path(raw_path).expanduser()
            if not candidate.is_absolute():
                candidate = PROJECT_ROOT / candidate
            candidate = candidate.resolve(strict=False)
            if candidate not in seen:
                paths.append(candidate)
                seen.add(candidate)

    for candidate in (
        PROJECT_ROOT / "config.local.json",
        PROJECT_ROOT / "config.json",
        PROJECT_ROOT / "utils" / "config" / "config.local.json",
        PROJECT_ROOT / "utils" / "config" / "config.json",
    ):
        candidate = candidate.resolve(strict=False)
        if candidate not in seen:
            paths.append(candidate)
            seen.add(candidate)

    return paths


def _env_names_for_key(key: str) -> tuple[str, ...]:
    return (
        key,
        f"S1_DR_{key}",
        f"DR_SKILLS_{key}",
    )


def _coerce_value(raw_value: str, expected: Any) -> Any:
    if expected is None:
        return _parse_json_like(raw_value)

    if isinstance(expected, bool):
        lowered = raw_value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        return bool(raw_value)

    if isinstance(expected, int) and not isinstance(expected, bool):
        return int(raw_value)

    if isinstance(expected, float):
        return float(raw_value)

    if isinstance(expected, list):
        parsed = _parse_json_like(raw_value)
        if isinstance(parsed, list):
            return parsed
        return [item.strip() for item in raw_value.split(",") if item.strip()]

    if isinstance(expected, dict):
        parsed = _parse_json_like(raw_value)
        if not isinstance(parsed, dict):
            raise ValueError("Expected a JSON object for config override")
        return parsed

    return raw_value


def _parse_json_like(raw_value: str) -> Any:
    value = raw_value.strip()
    if not value:
        return raw_value

    if value[0] in "[{\"" or value in {"true", "false", "null"}:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return raw_value

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return raw_value


_CONFIG_MANAGER = ConfigManager()
CONFIG_KEYS = _CONFIG_MANAGER.keys


def get_config_keys() -> tuple[str, ...]:
    return _CONFIG_MANAGER.keys


def get_config_value(key: str) -> Any:
    return _CONFIG_MANAGER.get(key)


def get_config_dict() -> dict[str, Any]:
    return _CONFIG_MANAGER.as_dict()


def reload_config() -> dict[str, Any]:
    global _CONFIG_MANAGER, CONFIG_KEYS
    _CONFIG_MANAGER = ConfigManager()
    CONFIG_KEYS = _CONFIG_MANAGER.keys
    return get_config_dict()
