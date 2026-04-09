from utils.config_loader import (
    CONFIG_KEYS,
    get_config_dict,
    get_config_keys,
    get_config_value,
    reload_config as _reload_config,
)


__all__ = [*CONFIG_KEYS, "get_config_dict", "get_config_keys", "get_config_value", "reload_config"]


def _refresh_module_globals() -> None:
    previous_keys = tuple(globals().get("CONFIG_KEYS", ()))
    current_keys = get_config_keys()

    for name in previous_keys:
        if name not in current_keys:
            globals().pop(name, None)

    globals().update(get_config_dict())
    globals()["CONFIG_KEYS"] = current_keys
    globals()["__all__"] = [
        *current_keys,
        "get_config_dict",
        "get_config_keys",
        "get_config_value",
        "reload_config",
    ]


_refresh_module_globals()


def __getattr__(name: str):
    if name in get_config_keys():
        return get_config_value(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def reload_config():
    data = _reload_config()
    _refresh_module_globals()
    return data
