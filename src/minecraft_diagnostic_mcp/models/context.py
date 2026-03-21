from typing import Any


CONTEXT_SCHEMAS: dict[str, tuple[str, ...]] = {
    "missing_dependency": ("plugin_name", "missing_dependencies", "plugin_path"),
    "plugin_startup": ("plugin_name", "line_number", "source", "plugin_found_in_inventory"),
    "rcon_configuration": ("config_file", "key", "current_value"),
    "security_configuration": ("config_file", "key", "current_value"),
    "parse_error": ("config_file", "parse_error"),
}


def build_missing_dependency_context(
    plugin_name: str | None,
    missing_dependencies: list[str] | None,
    plugin_path: str | None = None,
) -> dict[str, Any]:
    return normalize_context(
        "missing_dependency",
        {
            "plugin_name": plugin_name,
            "missing_dependencies": missing_dependencies or [],
            "plugin_path": plugin_path,
        },
    )


def build_plugin_startup_context(
    plugin_name: str | None,
    line_number: int | None = None,
    source: str | None = None,
    plugin_found_in_inventory: bool | None = None,
) -> dict[str, Any]:
    return normalize_context(
        "plugin_startup",
        {
            "plugin_name": plugin_name,
            "line_number": line_number,
            "source": source,
            "plugin_found_in_inventory": plugin_found_in_inventory,
        },
    )


def build_config_context(
    category: str,
    config_file: str | None,
    key: str | None = None,
    current_value: Any = None,
) -> dict[str, Any]:
    return normalize_context(
        category,
        {
            "config_file": config_file,
            "key": key,
            "current_value": current_value,
        },
    )


def build_parse_error_context(config_file: str | None, parse_error: str | None) -> dict[str, Any]:
    return normalize_context(
        "parse_error",
        {
            "config_file": config_file,
            "parse_error": parse_error,
        },
    )


def normalize_context(category: str, context: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(context) if isinstance(context, dict) else {}
    normalized = raw.copy()

    if category == "missing_dependency":
        normalized["plugin_name"] = _normalize_optional_string(normalized.get("plugin_name"))
        normalized["missing_dependencies"] = _normalize_string_list(normalized.get("missing_dependencies"))
        normalized["plugin_path"] = _normalize_optional_string(normalized.get("plugin_path"))
    elif category == "plugin_startup":
        normalized["plugin_name"] = _normalize_optional_string(normalized.get("plugin_name"))
        normalized["line_number"] = _normalize_optional_int(normalized.get("line_number"))
        normalized["source"] = _normalize_optional_string(normalized.get("source"))
        normalized["plugin_found_in_inventory"] = _normalize_optional_bool(normalized.get("plugin_found_in_inventory"))
    elif category in {"rcon_configuration", "security_configuration"}:
        normalized["config_file"] = _normalize_optional_string(normalized.get("config_file"))
        normalized["key"] = _normalize_optional_string(normalized.get("key"))
        normalized["current_value"] = _normalize_scalar(normalized.get("current_value"))
    elif category == "parse_error":
        normalized["config_file"] = _normalize_optional_string(normalized.get("config_file"))
        normalized["parse_error"] = _normalize_optional_string(normalized.get("parse_error"))
    else:
        normalized = {
            key: _normalize_generic_value(value)
            for key, value in normalized.items()
        }

    return {
        key: value
        for key, value in normalized.items()
        if value is not None and value != []
    }


def merge_contexts(category: str, *contexts: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for context in contexts:
        if not isinstance(context, dict):
            continue
        for key, value in context.items():
            if value is None:
                continue
            existing = merged.get(key)
            if isinstance(existing, list) and isinstance(value, list):
                for item in value:
                    if item not in existing:
                        existing.append(item)
                merged[key] = existing
            elif existing in (None, "", []):
                merged[key] = value
    return normalize_context(category, merged)


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = [value]

    normalized: list[str] = []
    for item in items:
        text = _normalize_optional_string(item)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _normalize_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _normalize_generic_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_generic_value(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_generic_value(item) for item in value]
    return _normalize_scalar(value)
