from minecraft_diagnostic_mcp.models.config import ConfigFileInfo
from minecraft_diagnostic_mcp.models.context import build_config_context, build_parse_error_context, normalize_context
from minecraft_diagnostic_mcp.models.diagnostics import DiagnosticItem


def lint_configs(config_files: list[ConfigFileInfo], parsed_configs: dict[str, dict]) -> list[DiagnosticItem]:
    issues: list[DiagnosticItem] = []

    for config_file in config_files:
        if not config_file.exists:
            if _is_optional_missing_config(config_file.path, parsed_configs):
                continue
            issues.append(
                DiagnosticItem(
                    severity=_missing_file_severity(config_file.path),
                    category="missing_file",
                    source_type="config",
                    source_name=config_file.path,
                    title="Config file missing",
                    summary=f"Expected config file '{config_file.path}' was not found.",
                    tags=["config", "missing_file"],
                    recommendations=["Verify the server distribution and confirm whether this file should exist."],
                    context=normalize_context("missing_file", {"config_file": config_file.path, "exists": False}),
                )
            )
            continue

        if config_file.parse_error:
            issues.append(
                DiagnosticItem(
                    severity="warning",
                    category="parse_error",
                    source_type="config",
                    source_name=config_file.path,
                    title="Config parse issue",
                    summary=config_file.parse_error,
                    tags=["config", "parse_error"],
                    recommendations=["Fix invalid syntax before relying on this config in diagnostics."],
                    context=build_parse_error_context(config_file.path, config_file.parse_error),
                )
            )

    server_properties = parsed_configs.get("server.properties", {})
    _lint_server_properties(server_properties, issues)
    return issues


def _lint_server_properties(server_properties: dict, issues: list[DiagnosticItem]) -> None:
    if not server_properties:
        return

    port_value = server_properties.get("server-port")
    if port_value is None or str(port_value).strip() == "":
        issues.append(
            DiagnosticItem(
                severity="warning",
                category="invalid_config",
                source_type="config",
                source_name="server.properties",
                title="Missing server-port",
                summary="The server-port setting is missing or empty.",
                tags=["config", "server.properties", "server-port"],
                recommendations=["Set server-port to a valid TCP port number."],
                context=build_config_context("invalid_config", "server.properties", "server-port", port_value),
            )
        )
    else:
        try:
            int(str(port_value))
        except ValueError:
            issues.append(
                DiagnosticItem(
                    severity="warning",
                    category="invalid_config",
                    source_type="config",
                    source_name="server.properties",
                    title="Invalid server-port",
                    summary="The server-port value is not numeric.",
                    tags=["config", "server.properties", "server-port"],
                    recommendations=["Change server-port to a valid integer."],
                    context=build_config_context("invalid_config", "server.properties", "server-port", port_value),
                )
            )

    enable_rcon = server_properties.get("enable-rcon")
    if enable_rcon is None or str(enable_rcon).strip().lower() != "true":
        issues.append(
            DiagnosticItem(
                severity="warning",
                category="rcon_configuration",
                source_type="config",
                source_name="server.properties",
                title="RCON not enabled",
                summary="RCON is disabled or missing, which limits this MCP server's capabilities.",
                tags=["config", "server.properties", "enable-rcon", "rcon"],
                recommendations=["Set enable-rcon=true if this MCP server should interact with the server over RCON."],
                context=build_config_context("rcon_configuration", "server.properties", "enable-rcon", enable_rcon),
            )
        )

    online_mode = server_properties.get("online-mode")
    if online_mode is not None and str(online_mode).strip().lower() == "false":
        issues.append(
            DiagnosticItem(
                severity="warning",
                category="security_configuration",
                source_type="config",
                source_name="server.properties",
                title="Online mode disabled",
                summary="online-mode=false can be valid, but it is a common source of authentication and security risk.",
                tags=["config", "server.properties", "online-mode", "security"],
                recommendations=["Confirm this is intentional and that any proxy or auth setup is configured safely."],
                context=build_config_context("security_configuration", "server.properties", "online-mode", online_mode),
            )
        )

    motd_value = server_properties.get("motd")
    if motd_value is not None and str(motd_value).strip() == "":
        issues.append(
            DiagnosticItem(
                severity="info",
                category="metadata",
                source_type="config",
                source_name="server.properties",
                title="Empty MOTD",
                summary="motd is present but empty.",
                tags=["config", "server.properties", "motd"],
                recommendations=["Set a non-empty MOTD if you want the server list entry to be descriptive."],
                context=build_config_context("metadata", "server.properties", "motd", motd_value),
            )
        )


def _missing_file_severity(path: str) -> str:
    if path == "server.properties":
        return "warning"
    return "info"


def _is_optional_missing_config(path: str, parsed_configs: dict[str, dict]) -> bool:
    if path == "paper.yml" and (parsed_configs.get("paper-global.yml") or parsed_configs.get("purpur.yml")):
        return True
    if path == "paper-global.yml" and parsed_configs.get("paper.yml"):
        return True
    return False
