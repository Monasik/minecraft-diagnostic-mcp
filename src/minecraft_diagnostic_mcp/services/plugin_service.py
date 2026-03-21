from dataclasses import asdict
import zipfile

from minecraft_diagnostic_mcp.collectors.filesystem_collector import (
    get_plugins_dir,
    list_plugin_jars,
    plugins_dir_exists,
    read_jar_entry,
)
from minecraft_diagnostic_mcp.models.context import (
    build_missing_dependency_context,
    normalize_context,
)
from minecraft_diagnostic_mcp.models.diagnostics import DiagnosticEvidence, DiagnosticItem
from minecraft_diagnostic_mcp.models.plugin import PluginInfo
from minecraft_diagnostic_mcp.parsers.plugin_manifest_parser import parse_plugin_manifest


def list_plugins() -> dict:
    plugins = _load_plugins()
    plugins_dir = get_plugins_dir()
    if plugins is None:
        return {
            "plugins_dir": str(plugins_dir),
            "exists": False,
            "count": 0,
            "message": "Plugins directory was not found.",
            "plugins": [],
        }

    return {
        "plugins_dir": str(plugins_dir),
        "exists": True,
        "count": len(plugins),
        "message": "Plugins directory scanned successfully.",
        "plugins": [asdict(plugin) for plugin in plugins],
    }


def get_plugin_by_name(name: str) -> dict:
    plugins_dir = get_plugins_dir()
    if not plugins_dir_exists():
        return {
            "plugins_dir": str(plugins_dir),
            "exists": False,
            "plugin_found": False,
            "query": name,
            "message": "Plugins directory was not found.",
            "plugin": None,
            "diagnostics": [],
        }

    plugins = _load_plugins()
    assert plugins is not None

    requested_name = name.strip()
    for plugin in plugins:
        if plugin.name.casefold() == requested_name.casefold():
            diagnostics = _build_plugin_diagnostics(plugin, plugins)
            return {
                "plugins_dir": str(plugins_dir),
                "exists": True,
                "plugin_found": True,
                "query": name,
                "message": "Plugin found.",
                "plugin": asdict(plugin),
                "diagnostics": [asdict(item) for item in diagnostics],
            }

    return {
        "plugins_dir": str(plugins_dir),
        "exists": True,
        "plugin_found": False,
        "query": name,
        "message": "Plugin was not found in the plugins directory.",
        "plugin": None,
        "diagnostics": [],
    }


def _load_plugins() -> list[PluginInfo] | None:
    if not plugins_dir_exists():
        return None

    plugins: list[PluginInfo] = []
    for jar_path in list_plugin_jars():
        try:
            manifest_name, plugin_manifest = _read_supported_manifest(jar_path)
            plugins.append(parse_plugin_manifest(jar_path, plugin_manifest, manifest_name=manifest_name))
        except KeyError:
            plugins.append(
                PluginInfo(
                    name=jar_path.stem,
                    path=str(jar_path),
                    manifest_found=False,
                    read_error="Neither plugin.yml nor paper-plugin.yml was found in the JAR archive.",
                )
            )
        except (OSError, zipfile.BadZipFile, RuntimeError, ValueError) as exc:
            plugins.append(
                PluginInfo(
                    name=jar_path.stem,
                    path=str(jar_path),
                    manifest_found=False,
                    read_error=f"Failed to read plugin JAR: {exc}",
                )
            )

    return plugins


def _read_supported_manifest(jar_path):
    for manifest_name in ("plugin.yml", "paper-plugin.yml"):
        try:
            return manifest_name, read_jar_entry(jar_path, manifest_name)
        except KeyError:
            continue
    raise KeyError("No supported plugin manifest found.")


def _build_plugin_diagnostics(plugin: PluginInfo, plugins: list[PluginInfo]) -> list[DiagnosticItem]:
    diagnostics: list[DiagnosticItem] = []
    installed_names = {installed_plugin.name.casefold() for installed_plugin in plugins}
    evidence = [DiagnosticEvidence(excerpt=plugin.path, source="plugin_manifest")]

    missing_dependencies = [
        dependency for dependency in plugin.depend
        if dependency.casefold() not in installed_names
    ]
    if missing_dependencies:
        diagnostics.append(
            DiagnosticItem(
                severity="warning",
                category="missing_dependency",
                source_type="plugin",
                source_name=plugin.name,
                title="Missing hard dependencies",
                summary="Some hard dependencies are not present in the current plugin inventory.",
                suspected_component=plugin.name,
                evidence=evidence,
                recommendations=["Install the missing dependency plugins or remove the dependent plugin."],
                tags=["plugin", "dependency", *missing_dependencies],
                context=build_missing_dependency_context(plugin.name, missing_dependencies, plugin.path),
            )
        )

    if not plugin.manifest_found:
        diagnostics.append(
            DiagnosticItem(
                severity="warning",
                category="manifest_missing",
                source_type="plugin",
                source_name=plugin.name,
                title="Plugin manifest missing",
                summary=plugin.read_error or "plugin.yml could not be read from the plugin JAR.",
                suspected_component=plugin.name,
                evidence=evidence,
                recommendations=["Verify that the JAR is a valid Bukkit/Paper plugin and not corrupted."],
                tags=["plugin", "manifest"],
                context=normalize_context(
                    "manifest_missing",
                    {
                        "plugin_name": plugin.name,
                        "plugin_path": plugin.path,
                        "manifest_name": plugin.manifest_name,
                        "manifest_found": plugin.manifest_found,
                        "read_error": plugin.read_error,
                    },
                ),
            )
        )

    suspicious_metadata_fields = []
    if not plugin.version:
        suspicious_metadata_fields.append("version")
    if not plugin.main:
        suspicious_metadata_fields.append("main")
    if not plugin.description:
        suspicious_metadata_fields.append("description")

    if suspicious_metadata_fields:
        diagnostics.append(
            DiagnosticItem(
                severity="warning",
                category="metadata_quality",
                source_type="plugin",
                source_name=plugin.name,
                title="Plugin metadata looks incomplete",
                summary="Some plugin metadata fields are missing or empty.",
                suspected_component=plugin.name,
                evidence=evidence,
                recommendations=["Check the plugin build or manifest metadata for missing fields."],
                tags=["plugin", "metadata", *suspicious_metadata_fields],
                context=normalize_context(
                    "metadata_quality",
                    {
                    "plugin_name": plugin.name,
                    "missing_fields": suspicious_metadata_fields,
                    "plugin_path": plugin.path,
                    "manifest_name": plugin.manifest_name,
                },
            ),
            )
        )

    if not plugin.commands:
        diagnostics.append(
            DiagnosticItem(
                severity="info",
                category="metadata_info",
                source_type="plugin",
                source_name=plugin.name,
                title="No commands declared",
                summary="This plugin does not declare any commands in plugin.yml.",
                suspected_component=plugin.name,
                evidence=evidence,
                tags=["plugin", "commands"],
                context=normalize_context(
                    "metadata_info",
                    {"plugin_name": plugin.name, "commands_declared": False, "plugin_path": plugin.path},
                ),
            )
        )

    if not plugin.permissions:
        diagnostics.append(
            DiagnosticItem(
                severity="info",
                category="metadata_info",
                source_type="plugin",
                source_name=plugin.name,
                title="No permissions declared",
                summary="This plugin does not declare any permissions in plugin.yml.",
                suspected_component=plugin.name,
                evidence=evidence,
                tags=["plugin", "permissions"],
                context=normalize_context(
                    "metadata_info",
                    {"plugin_name": plugin.name, "permissions_declared": False, "plugin_path": plugin.path},
                ),
            )
        )

    return diagnostics
