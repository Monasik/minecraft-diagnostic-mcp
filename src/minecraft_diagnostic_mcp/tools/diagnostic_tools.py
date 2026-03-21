from minecraft_diagnostic_mcp.services.config_lint_service import lint_server_config as lint_server_config_service
from minecraft_diagnostic_mcp.services.log_analysis_service import analyze_recent_logs as analyze_recent_logs_service
from minecraft_diagnostic_mcp.services.plugin_service import (
    get_plugin_by_name,
    list_plugins as list_plugins_service,
)
from minecraft_diagnostic_mcp.services.snapshot_service import get_server_snapshot as get_server_snapshot_service


def list_plugins() -> dict:
    """List plugins found in the configured plugins directory."""
    return list_plugins_service()


def inspect_plugin(name: str) -> dict:
    """Inspect a single plugin by name."""
    return get_plugin_by_name(name)


def lint_server_config() -> dict:
    """Lint the server's core configuration files."""
    return lint_server_config_service()


def analyze_recent_logs(lines: int = 200) -> dict:
    """Analyze recent Docker log lines for startup and plugin issues."""
    return analyze_recent_logs_service(lines)


def get_server_snapshot() -> dict:
    """Get an aggregated read-only snapshot of server health and diagnostics."""
    return get_server_snapshot_service()


def register_diagnostic_tools(mcp) -> None:
    mcp.tool()(list_plugins)
    mcp.tool()(inspect_plugin)
    mcp.tool()(lint_server_config)
    mcp.tool()(analyze_recent_logs)
    mcp.tool()(get_server_snapshot)
