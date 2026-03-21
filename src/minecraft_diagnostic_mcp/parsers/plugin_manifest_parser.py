from pathlib import Path

from minecraft_diagnostic_mcp.models.plugin import PluginCommandInfo, PluginInfo

try:
    import yaml
except ImportError:  # pragma: no cover - fallback for environments without PyYAML
    yaml = None


def parse_plugin_manifest(jar_path: Path, plugin_yml_bytes: bytes, manifest_name: str = "plugin.yml") -> PluginInfo:
    raw_manifest = _load_manifest(plugin_yml_bytes)
    manifest = raw_manifest if isinstance(raw_manifest, dict) else {}

    return PluginInfo(
        name=_coerce_string(manifest.get("name")) or jar_path.stem,
        path=str(jar_path),
        manifest_name=manifest_name,
        version=_coerce_string(manifest.get("version")),
        main=_coerce_string(manifest.get("main")),
        depend=_coerce_list(manifest.get("depend")),
        softdepend=_coerce_list(manifest.get("softdepend")),
        loadbefore=_coerce_list(manifest.get("loadbefore")),
        commands=_parse_commands(manifest.get("commands")),
        permissions=_parse_permissions(manifest.get("permissions")),
        description=_coerce_string(manifest.get("description")),
        website=_coerce_string(manifest.get("website")),
        authors=_coerce_authors(manifest),
        manifest_found=True,
    )


def _load_manifest(plugin_yml_bytes: bytes) -> dict:
    text = plugin_yml_bytes.decode("utf-8", errors="replace")
    if yaml is not None:
        loaded = yaml.safe_load(text)
        return loaded if isinstance(loaded, dict) else {}
    return _fallback_parse_manifest(text)


def _fallback_parse_manifest(text: str) -> dict:
    manifest: dict = {}
    current_section: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if not line.startswith((" ", "\t")) and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()

            if value:
                manifest[key] = _fallback_parse_value(value)
                current_section = None
            else:
                manifest[key] = {}
                current_section = key
            continue

        if current_section and line.startswith((" ", "\t")):
            nested = stripped
            if ":" in nested:
                nested_key, _nested_value = nested.split(":", 1)
                section = manifest.setdefault(current_section, {})
                if isinstance(section, dict):
                    section[nested_key.strip()] = {}

    return manifest


def _fallback_parse_value(value: str):
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("'\"") for item in inner.split(",")]

    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]

    return value


def _coerce_string(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _coerce_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_coerce_string(item) for item in value if _coerce_string(item)]
    if isinstance(value, str):
        return [value]
    return [str(value)]


def _coerce_authors(manifest: dict) -> list[str]:
    authors = _coerce_list(manifest.get("authors"))
    if authors:
        return authors

    author = _coerce_string(manifest.get("author"))
    return [author] if author else []


def _parse_commands(value) -> list[PluginCommandInfo]:
    if not isinstance(value, dict):
        return []

    commands: list[PluginCommandInfo] = []
    for command_name, command_data in value.items():
        command_name_str = _coerce_string(command_name)
        if not command_name_str:
            continue

        data = command_data if isinstance(command_data, dict) else {}
        aliases = _coerce_list(data.get("aliases"))
        commands.append(
            PluginCommandInfo(
                name=command_name_str,
                description=_coerce_string(data.get("description")),
                usage=_coerce_string(data.get("usage")),
                permission=_coerce_string(data.get("permission")),
                aliases=aliases,
            )
        )

    return commands


def _parse_permissions(value) -> list[str]:
    if not isinstance(value, dict):
        return []

    permissions: list[str] = []
    for permission_name in value.keys():
        permission_name_str = _coerce_string(permission_name)
        if permission_name_str:
            permissions.append(permission_name_str)
    return permissions
