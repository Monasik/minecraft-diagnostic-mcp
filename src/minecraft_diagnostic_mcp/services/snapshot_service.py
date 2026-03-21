from dataclasses import asdict

from minecraft_diagnostic_mcp.collectors.docker_collector import (
    get_container_status,
    get_runtime_readiness,
    get_server_stats,
    resolve_execution_mode,
)
from minecraft_diagnostic_mcp.collectors.filesystem_collector import get_backup_readiness
from minecraft_diagnostic_mcp.collectors.rcon_collector import get_rcon_readiness, run_rcon_command
from minecraft_diagnostic_mcp.models.context import (
    build_config_context,
    build_missing_dependency_context,
    merge_contexts,
    normalize_context,
)
from minecraft_diagnostic_mcp.models.diagnostics import (
    DiagnosticGroup,
    DiagnosticItem,
    diagnostic_sort_key,
    group_sort_key,
)
from minecraft_diagnostic_mcp.models.snapshot import ContainerStats, ServerSnapshot, ServerStatus
from minecraft_diagnostic_mcp.services.config_lint_service import lint_server_config
from minecraft_diagnostic_mcp.services.log_analysis_service import analyze_recent_logs
from minecraft_diagnostic_mcp.services.plugin_service import list_plugins
from minecraft_diagnostic_mcp.settings import settings


def get_server_snapshot() -> dict:
    status = _collect_status()
    stats = _collect_stats()
    plugin_summary = _collect_plugin_summary()
    config_summary, config_diagnostics = _collect_config_summary()
    log_summary, log_diagnostics = _collect_log_summary()
    problem_groups = _collect_problem_groups(plugin_summary, config_diagnostics, log_diagnostics)
    diagnostics = [group["primary_item"] for group in problem_groups]

    snapshot = ServerSnapshot(
        status=status,
        stats=stats,
        plugin_summary=plugin_summary,
        config_summary=config_summary,
        log_summary=log_summary,
        diagnostics=diagnostics,
        problem_groups=problem_groups,
        summary=_build_summary(status, problem_groups),
    )
    return asdict(snapshot)


def _collect_status() -> ServerStatus:
    execution_mode = resolve_execution_mode()
    runtime_readiness = get_runtime_readiness()
    backup_readiness = get_backup_readiness()
    rcon_readiness = get_rcon_readiness()

    container_status = "unknown"
    try:
        container_status = get_container_status()
    except Exception as exc:
        container_status = f"error: {exc}"

    players_online_raw = None
    rcon_responsive = bool(rcon_readiness.get("rcon_responsive", False))
    if execution_mode == "runtime" and rcon_responsive:
        try:
            players_online_raw = run_rcon_command("list").strip()
        except Exception:
            rcon_responsive = False

    return ServerStatus(
        execution_mode=execution_mode,
        container_name=settings.container_name,
        container_status=container_status,
        rcon_responsive=rcon_responsive,
        players_online_raw=players_online_raw,
        runtime_readiness={
            **runtime_readiness,
            "rcon_available": rcon_readiness.get("rcon_available", False),
            "rcon_responsive": rcon_readiness.get("rcon_responsive", False),
            "rcon_message": rcon_readiness.get("message", ""),
        },
        backup_readiness=backup_readiness,
    )


def _collect_stats() -> ContainerStats:
    try:
        raw_stats = get_server_stats()
    except Exception:
        return ContainerStats()

    parts = raw_stats.split("\t")
    return ContainerStats(
        cpu_percent=parts[0].strip() if len(parts) > 0 else None,
        memory_usage=parts[1].strip() if len(parts) > 1 else None,
        net_io=parts[2].strip() if len(parts) > 2 else None,
    )


def _collect_plugin_summary() -> dict:
    try:
        plugins_result = list_plugins()
    except Exception as exc:
        return {
            "exists": False,
            "count": 0,
            "message": f"Failed to inspect plugins: {exc}",
            "diagnostics": [],
        }

    summary = {
        "exists": plugins_result.get("exists", False),
        "count": plugins_result.get("count", 0),
        "message": plugins_result.get("message", ""),
    }
    if not summary["exists"]:
        summary["diagnostics"] = [
            asdict(
                DiagnosticItem(
                    severity="warning",
                    category="missing_directory",
                    source_type="plugin_inventory",
                    source_name=plugins_result.get("plugins_dir", "plugins"),
                    title="Plugins directory missing",
                    summary=plugins_result.get("message", "Plugins directory was not found."),
                    tags=["plugin", "inventory"],
                    recommendations=["Verify the configured plugins directory path before running plugin diagnostics."],
                    context=normalize_context("missing_directory", {"plugins_dir": plugins_result.get("plugins_dir", "plugins")}),
                )
            )
        ]
    else:
        summary["diagnostics"] = []
    return summary


def _collect_config_summary() -> tuple[dict, list[dict]]:
    try:
        config_result = lint_server_config()
    except Exception as exc:
        return {
            "config_count": 0,
            "item_count": 0,
            "issue_count": 0,
            "warning_count": 0,
            "error_count": 0,
            "critical_count": 0,
            "info_count": 0,
            "message": f"Failed to lint config files: {exc}",
        }, []

    summary = dict(config_result.get("summary", {}))
    summary.setdefault("config_count", 0)
    summary.setdefault("item_count", summary.get("issue_count", 0))
    summary.setdefault("issue_count", 0)
    summary.setdefault("warning_count", 0)
    summary.setdefault("error_count", 0)
    summary.setdefault("critical_count", 0)
    summary.setdefault("info_count", 0)
    summary.setdefault("message", "Config lint completed.")
    return summary, config_result.get("diagnostics", [])


def _collect_log_summary() -> tuple[dict, list[dict]]:
    try:
        log_result = analyze_recent_logs(200)
    except Exception as exc:
        return {
            "scanned_lines": 200,
            "item_count": 0,
            "finding_count": 0,
            "info_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "critical_count": 0,
            "message": f"Failed to analyze recent logs: {exc}",
        }, []

    log_summary = dict(log_result.get("summary", {}))
    return {
        "scanned_lines": log_result.get("scanned_lines", 200),
        "item_count": log_summary.get("item_count", log_summary.get("finding_count", 0)),
        "finding_count": log_summary.get("finding_count", 0),
        "info_count": log_summary.get("info_count", 0),
        "error_count": log_summary.get("error_count", 0),
        "warning_count": log_summary.get("warning_count", 0),
        "critical_count": log_summary.get("critical_count", 0),
        "message": log_summary.get("message", ""),
    }, log_result.get("diagnostics", [])


def _collect_problem_groups(
    plugin_summary: dict,
    config_diagnostics: list[dict],
    log_diagnostics: list[dict],
) -> list[dict]:
    diagnostics = []
    diagnostics.extend(plugin_summary.get("diagnostics", []))
    diagnostics.extend(log_diagnostics)
    diagnostics.extend(config_diagnostics)
    diagnostics.sort(key=diagnostic_sort_key)

    groups: dict[tuple[str, str], list[dict]] = {}
    for item in diagnostics:
        key = _group_key(item)
        groups.setdefault(key, []).append(item)

    problem_groups = []
    for key, items in groups.items():
        primary_item = sorted(items, key=diagnostic_sort_key)[0]
        related_items = [item for item in items if item is not primary_item]
        recommendations = []
        for item in items:
            for recommendation in item.get("recommendations", []):
                if recommendation not in recommendations:
                    recommendations.append(recommendation)
        group_context = _build_group_context(primary_item, related_items)

        problem_groups.append(
            asdict(
                DiagnosticGroup(
                    id=f"{key[0]}::{key[1]}",
                    title=_group_title(primary_item, related_items),
                    severity=primary_item.get("severity", "info"),
                    suspected_component=primary_item.get("suspected_component"),
                    primary_item=_dict_to_diagnostic_item(primary_item),
                    related_items=[_dict_to_diagnostic_item(item) for item in related_items],
                    summary=_group_summary(primary_item, related_items),
                    explanation=_group_explanation(primary_item, related_items, key[1], group_context),
                    recommended_action=_group_action(primary_item, recommendations, key[1], group_context),
                    recommendations=recommendations[:4],
                    context=group_context,
                )
            )
        )

    problem_groups.sort(key=group_sort_key)
    return problem_groups[:5]


def _group_key(item: dict) -> tuple[str, str]:
    component = (
        item.get("suspected_component")
        or item.get("source_name")
        or "global"
    )
    tags = {tag.lower() for tag in item.get("tags", [])}
    category = item.get("category", "general")

    if category in {"startup_security_warning", "rcon_configuration", "security_configuration"}:
        theme = "network_config"
    elif category == "parse_error":
        theme = "config_parse"
    elif category in {"plugin_compatibility_warning", "plugin_startup", "missing_dependency"}:
        theme = "plugin_runtime"
    elif category == "startup_warning":
        theme = "startup_misc"
    elif {"dependency", "startup"} & tags:
        theme = "plugin_runtime"
    elif {"rcon", "network", "security"} & tags:
        theme = "network_config"
    else:
        theme = category

    return (str(component).casefold(), theme)


def _group_title(primary_item: dict, related_items: list[dict]) -> str:
    if related_items:
        return f"{primary_item.get('title', 'Diagnostic issue')} (+{len(related_items)} related)"
    return primary_item.get("title", "Diagnostic issue")


def _group_summary(primary_item: dict, related_items: list[dict]) -> str:
    if not related_items:
        return primary_item.get("summary", "")
    return (
        f"{primary_item.get('summary', '')} "
        f"Detected {len(related_items)} additional related diagnostic item(s)."
    ).strip()


def _build_group_context(primary_item: dict, related_items: list[dict]) -> dict:
    merged_items = [primary_item, *related_items]
    primary_category = primary_item.get("category", "general")
    contexts = [item.get("context", {}) for item in merged_items]
    context = merge_contexts(primary_category, *contexts)

    if primary_category == "missing_dependency":
        context = merge_contexts(
            "missing_dependency",
            build_missing_dependency_context(
                primary_item.get("suspected_component") or primary_item.get("source_name"),
                context.get("missing_dependencies", []),
                context.get("plugin_path"),
            ),
            context,
        )
    elif primary_category in {"rcon_configuration", "security_configuration"}:
        context = merge_contexts(
            primary_category,
            build_config_context(
                primary_category,
                context.get("config_file") or primary_item.get("source_name"),
                context.get("key"),
                context.get("current_value"),
            ),
            context,
        )

    related_sources: list[str] = []
    for item in merged_items:
        source_name = item.get("source_name")
        if source_name and source_name not in related_sources:
            related_sources.append(source_name)
    if related_sources:
        context["related_sources"] = related_sources

    return normalize_context(primary_category, context)


def _group_explanation(primary_item: dict, related_items: list[dict], theme: str, context: dict) -> str:
    component = context.get("plugin_name") or primary_item.get("suspected_component") or primary_item.get("source_name") or "This component"
    category = primary_item.get("category", "general")
    tags = {tag.lower() for tag in primary_item.get("tags", [])}

    if category == "missing_dependency" or context.get("missing_dependencies") or "dependency" in tags:
        dependency_names = context.get("missing_dependencies", [])
        dependency_suffix = f" ({', '.join(dependency_names)})" if dependency_names else ""
        return (
            f"Plugin {component} depends on another plugin that is not currently installed{dependency_suffix}. "
            f"That missing dependency can prevent the plugin from loading correctly."
        )

    if category == "startup_security_warning":
        return (
            "The startup logs show that the server is running in offline or insecure mode. "
            "That can be intentional behind a trusted auth/proxy setup, but it is still a high-value startup warning."
        )

    if category == "plugin_compatibility_warning":
        return (
            f"Plugin {component} reported a startup-time compatibility limitation with the current server version or platform. "
            "That may not break startup immediately, but it can disable features or cause later instability."
        )

    if category == "startup_warning":
        return (
            f"Plugin or server startup emitted a warning for {component}. "
            "It does not necessarily block boot, but it is more important than routine runtime noise."
        )

    if category == "plugin_startup" or theme == "plugin_runtime":
        return (
            f"Plugin {component} is failing during startup or load. "
            f"This usually means a missing dependency, incompatible plugin build, or another startup-time error."
        )

    if category == "rcon_configuration":
        config_file = context.get("config_file", "server.properties")
        key = context.get("key", "enable-rcon")
        return (
            f"RCON is disabled or not configured as expected in {config_file} ({key}). "
            "That limits remote diagnostics and admin commands that rely on the Minecraft RCON interface."
        )

    if category == "security_configuration":
        return (
            "The current server security or networking configuration looks risky. "
            "This can affect authentication, connectivity, or safe remote access."
        )

    if category == "performance_warning":
        return (
            "The server reported a lag or tick-delay warning. "
            "This is usually a performance hint rather than a startup or configuration failure."
        )

    if category == "monitoring_warning":
        return (
            f"Monitoring output from {component} reported a warning during diagnostics or profiling. "
            "This is usually informational unless it keeps repeating unexpectedly."
        )

    if category == "operational_movement_warning":
        return (
            "The logs contain movement-related warnings such as players moving too quickly or wrongly. "
            "These are common gameplay/runtime warnings and are usually lower-priority noise."
        )

    if category == "parse_error" or theme == "config_parse":
        config_file = context.get("config_file") or component
        parse_error = context.get("parse_error")
        suffix = f" Parser reported: {parse_error}" if parse_error else ""
        return (
            f"Configuration file {config_file} could not be parsed cleanly. "
            f"Invalid syntax can cause server settings to be ignored or misapplied.{suffix}"
        )

    return primary_item.get("summary", "")


def _group_action(primary_item: dict, recommendations: list[str], theme: str, context: dict) -> str:
    component = context.get("plugin_name") or primary_item.get("suspected_component") or primary_item.get("source_name") or "this component"
    category = primary_item.get("category", "general")
    tags = {tag.lower() for tag in primary_item.get("tags", [])}

    if category == "missing_dependency" or context.get("missing_dependencies") or "dependency" in tags:
        dependency_names = context.get("missing_dependencies", [])
        if dependency_names:
            return (
                f"Install the missing dependency plugin(s) {', '.join(dependency_names)} "
                f"or remove {component} from the plugins directory."
            )
        return f"Install the missing dependency plugins required by {component} or remove {component} from the plugins directory."

    if category == "startup_security_warning":
        return "Review your authentication/proxy setup and enable online-mode unless the server is intentionally protected by a trusted external auth layer."

    if category == "plugin_compatibility_warning":
        return f"Verify that {component} officially supports this Minecraft/Paper version and update or replace it if the warning is not expected."

    if category == "startup_warning":
        return f"Review the startup warning for {component} and decide whether it needs a config cleanup, plugin update, or can be safely ignored."

    if category == "plugin_startup" or theme == "plugin_runtime":
        return f"Check {component}'s version compatibility, dependencies, and the related startup stacktrace before restarting the server."

    if category == "rcon_configuration":
        config_file = context.get("config_file", "server.properties")
        key = context.get("key", "enable-rcon")
        current_value = context.get("current_value")
        value_suffix = f" The current value is {current_value!r}." if current_value is not None else ""
        return f"Enable RCON in {config_file} by setting {key}=true and verify the RCON port and password so MCP diagnostics can use the remote console safely.{value_suffix}"

    if category == "security_configuration":
        return "Review the relevant network and authentication settings, then align them with your intended server access model."

    if category == "parse_error" or theme == "config_parse":
        config_file = context.get("config_file") or component
        return f"Fix the syntax errors in {config_file} and reload or restart the server so the corrected configuration is applied."

    if category == "performance_warning":
        return "Watch for repeated lag warnings and only escalate if players report sustained lag or the warnings become frequent."

    if category == "monitoring_warning":
        return "Treat this as monitoring noise unless the related profiler or diagnostic action was not intentional."

    if category == "operational_movement_warning":
        return "Ignore isolated movement warnings unless they become frequent enough to suggest rubber-banding or anticheat issues."

    if recommendations:
        return recommendations[0]

    return "Review the related diagnostic items and address the highest-priority issue first."


def _dict_to_diagnostic_item(item: dict) -> DiagnosticItem:
    return DiagnosticItem(
        severity=item.get("severity", "info"),
        category=item.get("category", "general"),
        source_type=item.get("source_type", "unknown"),
        source_name=item.get("source_name", "unknown"),
        title=item.get("title", ""),
        summary=item.get("summary", ""),
        suspected_component=item.get("suspected_component"),
        evidence=[],
        recommendations=item.get("recommendations", []),
        tags=item.get("tags", []),
        context=item.get("context", {}),
        priority=item.get("priority", 0),
    )


def _build_summary(status: ServerStatus, problem_groups: list[dict]) -> str:
    sentences = [f"Server is running in {status.execution_mode} mode."]
    if status.execution_mode == "runtime":
        sentences.append(f"Container '{status.container_name}' is {status.container_status}.")
    else:
        sentences.append(f"Container '{status.container_name}' is represented by backup data.")

    if not status.rcon_responsive:
        sentences.append("RCON is not responding right now.")

    top_groups = problem_groups[:2]
    if top_groups:
        explanations = [group.get("explanation") or group.get("summary", "") for group in top_groups]
        condensed = " ".join(text.strip() for text in explanations if text.strip())
        if condensed:
            sentences.append(condensed)
    else:
        sentences.append("No significant diagnostic groups were detected in the current snapshot.")

    return " ".join(sentences[:3])
