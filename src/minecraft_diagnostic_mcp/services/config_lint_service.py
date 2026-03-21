from dataclasses import asdict

from minecraft_diagnostic_mcp.analyzers.config_linter import lint_configs
from minecraft_diagnostic_mcp.collectors.filesystem_collector import find_existing_config_path, read_text_file
from minecraft_diagnostic_mcp.models.config import ConfigFileInfo
from minecraft_diagnostic_mcp.models.diagnostics import DiagnosticSummary
from minecraft_diagnostic_mcp.parsers.properties_parser import parse_properties
from minecraft_diagnostic_mcp.parsers.yaml_parser import parse_yaml
from minecraft_diagnostic_mcp.settings import settings


def lint_server_config() -> dict:
    config_files: list[ConfigFileInfo] = []
    parsed_configs: dict[str, dict] = {}

    for logical_name, candidates in settings.iter_config_targets():
        kind = "properties" if logical_name.endswith(".properties") else "yaml"
        resolved_path = find_existing_config_path(candidates)
        exists = resolved_path is not None

        if not exists:
            config_files.append(
                ConfigFileInfo(
                    path=logical_name,
                    exists=False,
                    parsed=False,
                    kind=kind,
                )
            )
            continue

        try:
            content = read_text_file(resolved_path)
        except OSError as exc:
            config_files.append(
                ConfigFileInfo(
                    path=str(resolved_path),
                    exists=True,
                    parsed=False,
                    kind=kind,
                    parse_error=f"Failed to read file: {exc}",
                )
            )
            continue

        parse_result = parse_properties(content) if kind == "properties" else parse_yaml(content)
        config_files.append(
            ConfigFileInfo(
                path=str(resolved_path),
                exists=True,
                parsed=parse_result["parsed"],
                kind=kind,
                parse_error=parse_result["parse_error"],
            )
        )
        parsed_configs[logical_name] = parse_result["data"]

    diagnostics = lint_configs(config_files, parsed_configs)
    summary = DiagnosticSummary(
        item_count=len(diagnostics),
        info_count=sum(1 for item in diagnostics if item.severity == "info"),
        warning_count=sum(1 for item in diagnostics if item.severity == "warning"),
        error_count=sum(1 for item in diagnostics if item.severity == "error"),
        critical_count=sum(1 for item in diagnostics if item.severity == "critical"),
        message="Config lint completed.",
    )

    return {
        "config_files": [asdict(config_file) for config_file in config_files],
        "diagnostics": [asdict(item) for item in diagnostics],
        "summary": {
            "config_count": len(config_files),
            "item_count": summary.item_count,
            "issue_count": summary.item_count,
            "info_count": summary.info_count,
            "warning_count": summary.warning_count,
            "error_count": summary.error_count,
            "critical_count": summary.critical_count,
            "message": summary.message,
        },
    }
