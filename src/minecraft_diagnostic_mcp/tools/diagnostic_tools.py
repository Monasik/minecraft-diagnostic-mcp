from minecraft_diagnostic_mcp.integrations.manager import get_enabled_integrations
from minecraft_diagnostic_mcp.services.config_lint_service import lint_server_config as lint_server_config_service
from minecraft_diagnostic_mcp.services.dependency_graph_service import analyze_dependency_graph as analyze_dependency_graph_service
from minecraft_diagnostic_mcp.services.log_analysis_service import analyze_recent_logs as analyze_recent_logs_service
from minecraft_diagnostic_mcp.services.log_forensics_service import (
    extract_raw_logs as extract_raw_logs_service,
    incident_timeline as incident_timeline_service,
    list_cant_keep_up_events as list_cant_keep_up_events_service,
    list_log_sources as list_log_sources_service,
    list_player_commands as list_player_commands_service,
    list_stacktrace_plugins as list_stacktrace_plugins_service,
    list_watchdog_dumps as list_watchdog_dumps_service,
    search_logs as search_logs_service,
)
from minecraft_diagnostic_mcp.services.performance_analysis_service import analyze_performance as analyze_performance_service
from minecraft_diagnostic_mcp.services.plugin_service import (
    get_plugin_by_name,
    list_plugins as list_plugins_service,
)
from minecraft_diagnostic_mcp.services.remediation_service import (
    apply_remediation as apply_remediation_service,
    plan_remediation as plan_remediation_service,
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


def analyze_recent_logs(lines: int = 200, include_archives: bool = False, compact: bool = False) -> dict:
    """Analyze recent Docker log lines for startup and plugin issues."""
    return analyze_recent_logs_service(lines, include_archives, compact)


def get_server_snapshot() -> dict:
    """Get an aggregated read-only snapshot of server health and diagnostics."""
    return get_server_snapshot_service()


def list_log_sources(source: str = "all", date_value: str = "") -> dict:
    """List available log sources and their inferred time ranges without mixing files implicitly."""
    return list_log_sources_service(source=source or "all", date_value=date_value or None)


def extract_raw_logs(
    source: str = "all",
    date_value: str = "",
    time_from: str = "",
    time_to: str = "",
    around: str = "",
    window_seconds: int = 120,
    contains: str = "",
    regex: str = "",
    case_sensitive: bool = False,
    before_lines: int = 0,
    after_lines: int = 0,
    max_lines: int = 400,
    mode: str = "full_raw",
) -> dict:
    """Return raw log records for precise forensic analysis with source and time filters."""
    return extract_raw_logs_service(
        source=source or "all",
        date_value=date_value or None,
        time_from=time_from or None,
        time_to=time_to or None,
        around=around or None,
        window_seconds=window_seconds,
        contains=contains or None,
        regex=regex or None,
        case_sensitive=case_sensitive,
        before_lines=before_lines,
        after_lines=after_lines,
        max_lines=max_lines,
        mode=mode,
    )


def search_logs(
    source: str = "all",
    date_value: str = "",
    time_from: str = "",
    time_to: str = "",
    contains: str = "",
    regex: str = "",
    case_sensitive: bool = False,
    before_lines: int = 0,
    after_lines: int = 0,
    max_lines: int = 300,
    mode: str = "full",
) -> dict:
    """Search logs by text or regex across latest.log, archives, or one explicit file."""
    return search_logs_service(
        source=source or "all",
        date_value=date_value or None,
        time_from=time_from or None,
        time_to=time_to or None,
        contains=contains or None,
        regex=regex or None,
        case_sensitive=case_sensitive,
        before_lines=before_lines,
        after_lines=after_lines,
        max_lines=max_lines,
        mode=mode,
    )


def incident_timeline(
    source: str = "all",
    date_value: str = "",
    around: str = "",
    window_seconds: int = 120,
    before_minutes: int = 10,
    after_minutes: int = 5,
    max_lines: int = 600,
    mode: str = "full",
) -> dict:
    """Group relevant records around an incident timestamp, including player commands and recovery events."""
    return incident_timeline_service(
        source=source or "all",
        date_value=date_value or None,
        around=around or None,
        window_seconds=window_seconds,
        before_minutes=before_minutes,
        after_minutes=after_minutes,
        max_lines=max_lines,
        mode=mode,
    )


def list_cant_keep_up_events(source: str = "archives", date_value: str = "", max_lines: int = 200) -> dict:
    """List all 'Can't keep up!' lag events for a selected source and date."""
    return list_cant_keep_up_events_service(source=source or "archives", date_value=date_value or None, max_lines=max_lines)


def list_watchdog_dumps(source: str = "archives", date_value: str = "", max_lines: int = 600, mode: str = "full_raw") -> dict:
    """List watchdog-related dumps and keep long stacktraces available when requested."""
    return list_watchdog_dumps_service(
        source=source or "archives",
        date_value=date_value or None,
        max_lines=max_lines,
        mode=mode,
    )


def list_stacktrace_plugins(source: str = "all", date_value: str = "") -> dict:
    """List plugin names that appear in stacktraces for the selected logs."""
    return list_stacktrace_plugins_service(source=source or "all", date_value=date_value or None)


def list_player_commands(
    source: str = "all",
    date_value: str = "",
    time_from: str = "",
    time_to: str = "",
    around: str = "",
    before_minutes: int = 10,
    max_lines: int = 200,
) -> dict:
    """List player commands in an explicit interval or in the minutes before an incident timestamp."""
    return list_player_commands_service(
        source=source or "all",
        date_value=date_value or None,
        time_from=time_from or None,
        time_to=time_to or None,
        around=around or None,
        before_minutes=before_minutes,
        max_lines=max_lines,
    )


def analyze_dependency_graph(include_log_signals: bool = True) -> dict:
    """Analyze plugin dependency relationships and missing dependency paths."""
    return analyze_dependency_graph_service(include_log_signals=include_log_signals)


def analyze_performance(include_archives: bool = True, lines: int = 2000) -> dict:
    """Analyze runtime and historical performance-related signals."""
    return analyze_performance_service(include_archives=include_archives, lines=lines)


def plan_remediation(default_rcon_password: str = "") -> dict:
    """Build a remediation plan for safe automatic fixes and manual follow-ups."""
    return plan_remediation_service(default_rcon_password=default_rcon_password or None)


def apply_remediation(action_ids: list[str] | None = None, default_rcon_password: str = "") -> dict:
    """Apply allowlisted safe remediation actions to server configuration files."""
    return apply_remediation_service(action_ids=action_ids, default_rcon_password=default_rcon_password or None)


def list_integrations() -> dict:
    """List currently enabled alerting and integration sinks."""
    integrations = get_enabled_integrations()
    return {
        "enabled_count": len(integrations),
        "integrations": integrations,
    }


def register_diagnostic_tools(mcp) -> None:
    mcp.tool()(list_plugins)
    mcp.tool()(inspect_plugin)
    mcp.tool()(lint_server_config)
    mcp.tool()(analyze_recent_logs)
    mcp.tool()(get_server_snapshot)
    mcp.tool()(list_log_sources)
    mcp.tool()(extract_raw_logs)
    mcp.tool()(search_logs)
    mcp.tool()(incident_timeline)
    mcp.tool()(list_cant_keep_up_events)
    mcp.tool()(list_watchdog_dumps)
    mcp.tool()(list_stacktrace_plugins)
    mcp.tool()(list_player_commands)
    mcp.tool()(analyze_dependency_graph)
    mcp.tool()(analyze_performance)
    mcp.tool()(plan_remediation)
    mcp.tool()(apply_remediation)
    mcp.tool()(list_integrations)
