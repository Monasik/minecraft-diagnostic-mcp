try:
    import yaml
except ImportError:  # pragma: no cover - fallback for environments without PyYAML
    yaml = None


def parse_yaml(text: str) -> dict:
    if yaml is None:
        return {
            "parsed": False,
            "data": {},
            "parse_error": "PyYAML is not installed, so YAML files cannot be parsed.",
        }

    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return {
            "parsed": False,
            "data": {},
            "parse_error": str(exc),
        }

    if loaded is None:
        return {
            "parsed": True,
            "data": {},
            "parse_error": None,
        }

    if not isinstance(loaded, dict):
        return {
            "parsed": False,
            "data": {},
            "parse_error": "Expected a top-level mapping in YAML config.",
        }

    return {
        "parsed": True,
        "data": loaded,
        "parse_error": None,
    }
