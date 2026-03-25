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
    problem_groups = _collect_problem_groups(plugin_summary, config_diagnostics, log_diagnostics, log_summary)
    diagnostics = [group["primary_item"] for group in problem_groups]

    snapshot = ServerSnapshot(
        status=status,
        stats=stats,
        plugin_summary=plugin_summary,
        config_summary=config_summary,
        log_summary=log_summary,
        diagnostics=diagnostics,
        problem_groups=problem_groups,
        summary=_build_summary(status, problem_groups, log_summary),
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
    summary = {
        "scanned_lines": log_result.get("scanned_lines", 200),
        "item_count": log_summary.get("item_count", log_summary.get("finding_count", 0)),
        "finding_count": log_summary.get("finding_count", 0),
        "info_count": log_summary.get("info_count", 0),
        "error_count": log_summary.get("error_count", 0),
        "warning_count": log_summary.get("warning_count", 0),
        "critical_count": log_summary.get("critical_count", 0),
        "message": log_summary.get("message", ""),
    }

    try:
        compact_result = analyze_recent_logs(2000, include_archives=True, compact=True)
        summary["compact_summary"] = compact_result.get("compact_summary", {})
        summary["archives_included"] = compact_result.get("archives_included", False)
        summary["log_files_scanned"] = compact_result.get("log_files_scanned", [])
        summary["detail_mode"] = compact_result.get("detail_mode", "compact")
    except Exception as exc:
        summary["compact_summary"] = {
            "summary_text": f"Compact historical log summary was not available: {exc}",
            "active_item_count": 0,
            "resolved_item_count": 0,
            "top_active_diagnostics": [],
            "top_resolved_diagnostics": [],
            "repeated_patterns": [],
            "top_categories": [],
            "file_summary": {"scanned_count": 0, "archive_count": 0, "unreadable_count": 0, "latest_source": None, "oldest_source": None},
            "startup_summary": {"detected": False, "item_count": 0},
        }
        summary["archives_included"] = False
        summary["log_files_scanned"] = []
        summary["detail_mode"] = "full"

    return summary, log_result.get("diagnostics", [])


def _collect_problem_groups(
    plugin_summary: dict,
    config_diagnostics: list[dict],
    log_diagnostics: list[dict],
    log_summary: dict,
) -> list[dict]:
    diagnostics = []
    diagnostics.extend(plugin_summary.get("diagnostics", []))
    diagnostics.extend(log_diagnostics)
    diagnostics.extend(config_diagnostics)
    diagnostics.sort(key=diagnostic_sort_key)
    pattern_hints = _build_pattern_hints(log_summary)

    groups: dict[tuple[str, str], list[dict]] = {}
    for item in diagnostics:
        key = _group_key(item)
        groups.setdefault(key, []).append(item)

    problem_groups = []
    for key, items in groups.items():
        primary_item = sorted(items, key=diagnostic_sort_key)[0]
        related_items = [item for item in items if item is not primary_item]
        compact_pattern = _match_compact_pattern(primary_item, related_items, key[1], pattern_hints)
        recommendations = []
        for item in items:
            for recommendation in item.get("recommendations", []):
                if recommendation not in recommendations:
                    recommendations.append(recommendation)
        group_context = _build_group_context(primary_item, related_items, compact_pattern)

        problem_groups.append(
            asdict(
                DiagnosticGroup(
                    id=f"{key[0]}::{key[1]}",
                    title=_group_title(primary_item, related_items, compact_pattern, group_context),
                    severity=primary_item.get("severity", "info"),
                    suspected_component=primary_item.get("suspected_component"),
                    primary_item=_dict_to_diagnostic_item(primary_item),
                    related_items=[_dict_to_diagnostic_item(item) for item in related_items],
                    summary=_group_summary(primary_item, related_items, compact_pattern),
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


def _group_title(primary_item: dict, related_items: list[dict], compact_pattern: dict | None, context: dict) -> str:
    category = primary_item.get("category", "general")
    component = context.get("plugin_name") or primary_item.get("suspected_component")

    if compact_pattern and not _is_generic_group_title(compact_pattern):
        pattern_title = str(compact_pattern.get("title", "")).strip()
        if pattern_title:
            if related_items:
                return f"{pattern_title} (+{len(related_items)} related)"
            return pattern_title

    if category == "missing_dependency":
        missing_dependencies = context.get("missing_dependencies", [])
        if isinstance(missing_dependencies, list) and len(missing_dependencies) == 1:
            base_title = f"{component or 'Plugin'} missing {missing_dependencies[0]}"
        elif isinstance(missing_dependencies, list) and missing_dependencies:
            base_title = f"{component or 'Plugin'} missing dependencies"
        else:
            base_title = primary_item.get("title", "Diagnostic issue")
        if related_items:
            return f"{base_title} (+{len(related_items)} related)"
        return base_title

    if related_items:
        return f"{primary_item.get('title', 'Diagnostic issue')} (+{len(related_items)} related)"
    return primary_item.get("title", "Diagnostic issue")


def _group_summary(primary_item: dict, related_items: list[dict], compact_pattern: dict | None) -> str:
    base_summary = primary_item.get("summary", "")
    if compact_pattern and compact_pattern.get("issue_label"):
        pattern_label = str(compact_pattern.get("issue_label", "")).strip()
        if pattern_label and pattern_label.casefold() not in base_summary.casefold():
            base_summary = f"{base_summary} Compact log pattern: {pattern_label}."

    if not related_items:
        return base_summary.strip()
    return (
        f"{base_summary} "
        f"Detected {len(related_items)} additional related diagnostic item(s)."
    ).strip()


def _build_group_context(primary_item: dict, related_items: list[dict], compact_pattern: dict | None) -> dict:
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
                missing_target_type=context.get("missing_target_type"),
                missing_symbol=context.get("missing_symbol"),
                likely_dependency_name=context.get("likely_dependency_name"),
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

    normalized = normalize_context(primary_category, context)
    if compact_pattern:
        normalized["compact_pattern_title"] = compact_pattern.get("title")
        normalized["compact_issue_family"] = compact_pattern.get("issue_family")
        normalized["compact_issue_label"] = compact_pattern.get("issue_label")
        normalized["compact_pattern_status"] = compact_pattern.get("historical_status")

    return normalized


def _group_explanation(primary_item: dict, related_items: list[dict], theme: str, context: dict) -> str:
    component = context.get("plugin_name") or primary_item.get("suspected_component") or primary_item.get("source_name") or "This component"
    category = primary_item.get("category", "general")
    tags = {tag.lower() for tag in primary_item.get("tags", [])}
    if context.get("historical_status") == "resolved":
        last_seen_source = context.get("last_seen_source", "older logs")
        return (
            f"This issue was found in older logs for {component}, but it was not seen in the newest log data. "
            f"It may already be resolved; the last observed source was {last_seen_source}."
        )

    if category == "missing_dependency" or context.get("missing_dependencies") or "dependency" in tags:
        dependency_names = context.get("missing_dependencies", [])
        missing_target_type = str(context.get("missing_target_type", "")).casefold()
        likely_dependency_name = context.get("likely_dependency_name")
        likely_dependency_found = bool(context.get("likely_dependency_found_in_inventory"))
        missing_symbol = context.get("missing_symbol")
        dependency_suffix = f" ({', '.join(dependency_names)})" if dependency_names else ""
        if missing_target_type == "plugin_dependency" and likely_dependency_found and likely_dependency_name:
            return (
                f"Plugin {component} is failing while trying to use dependency plugin {likely_dependency_name}, but that dependency is already installed. "
                "This usually points to an incompatible dependency version, wrong platform build, or classloader mismatch rather than a truly missing plugin."
            )
        if missing_target_type == "library_or_classpath":
            subject = likely_dependency_name or missing_symbol or "a required class"
            return (
                f"Plugin {component} is failing because a required library or classpath symbol is missing ({subject}). "
                "That usually points to an incompatible build, incomplete jar, or missing shaded dependency rather than a missing plugin dependency."
            )
        if missing_target_type == "plugin_dependency" and likely_dependency_name and not dependency_names:
            dependency_suffix = f" ({likely_dependency_name})"
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

    if category == "plugin_manifest_error":
        return (
            f"Plugin {component} appears to have an invalid plugin manifest, so the server cannot load it as a valid plugin jar. "
            "This is usually a broken jar build rather than a runtime config issue."
        )

    if category == "data_integrity_error":
        return (
            f"Logs for {component} indicate SQLite or on-disk data corruption. "
            "That can break plugin persistence and may keep returning until the damaged data file is repaired or replaced."
        )

    if category == "archive_access_error":
        return (
            f"Plugin {component} hit a jar or archive access failure while running. "
            "That usually points to a corrupted plugin jar, unsafe reload behavior, or plugin-side file handling bug."
        )

    if category == "event_dispatch_failure":
        return (
            f"Plugin {component} failed while handling a server event or listener callback. "
            "That means gameplay or startup hooks are throwing inside plugin code rather than simple low-priority log noise."
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
    if context.get("historical_status") == "resolved":
        return f"Treat this as historical unless it reappears in the newest logs for {component}; verify only if players are still reporting symptoms."

    if category == "missing_dependency" or context.get("missing_dependencies") or "dependency" in tags:
        dependency_names = context.get("missing_dependencies", [])
        missing_target_type = str(context.get("missing_target_type", "")).casefold()
        likely_dependency_name = context.get("likely_dependency_name")
        likely_dependency_found = bool(context.get("likely_dependency_found_in_inventory"))
        missing_symbol = context.get("missing_symbol")
        if missing_target_type == "plugin_dependency" and likely_dependency_found and likely_dependency_name:
            return (
                f"Check that {component} and {likely_dependency_name} are on compatible versions and builds, "
                "because the dependency plugin exists but its classes are still not resolving correctly."
            )
        if missing_target_type == "library_or_classpath":
            subject = likely_dependency_name or missing_symbol or "the missing classpath symbol"
            return (
                f"Replace or update {component} with a build that includes {subject}, "
                "or switch to a version compiled for this server platform."
            )
        if dependency_names:
            return (
                f"Install the missing dependency plugin(s) {', '.join(dependency_names)} "
                f"or remove {component} from the plugins directory."
            )
        if missing_target_type == "plugin_dependency" and likely_dependency_name:
            return f"Install or update {likely_dependency_name} before loading {component}, or remove {component} until that dependency is available."
        return f"Install the missing dependency plugins required by {component} or remove {component} from the plugins directory."

    if category == "startup_security_warning":
        return "Review your authentication/proxy setup and enable online-mode unless the server is intentionally protected by a trusted external auth layer."

    if category == "plugin_compatibility_warning":
        return f"Verify that {component} officially supports this Minecraft/Paper version and update or replace it if the warning is not expected."

    if category == "plugin_manifest_error":
        return f"Replace {component} with a valid plugin build that contains a correct plugin manifest before the next restart."

    if category == "data_integrity_error":
        return f"Inspect and repair {component}'s database or data files, then restore from backup if the SQLite store is corrupted."

    if category == "archive_access_error":
        return f"Replace the affected jar for {component} and avoid reload-style workflows until the plugin can access its archive cleanly."

    if category == "event_dispatch_failure":
        return f"Inspect the stacktrace for {component}'s failing listener and update, reconfigure, or temporarily disable that plugin path."

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


def _build_pattern_hints(log_summary: dict) -> list[dict]:
    compact_summary = log_summary.get("compact_summary", {}) if isinstance(log_summary, dict) else {}
    repeated_patterns = compact_summary.get("repeated_patterns", [])
    top_active = compact_summary.get("top_active_diagnostics", [])
    top_resolved = compact_summary.get("top_resolved_diagnostics", [])

    hints: list[dict] = []
    for item in [*repeated_patterns, *top_active, *top_resolved]:
        if isinstance(item, dict):
            hints.append(item)
    return hints


def _match_compact_pattern(primary_item: dict, related_items: list[dict], theme: str, pattern_hints: list[dict]) -> dict | None:
    candidate_components = {
        str(primary_item.get("suspected_component") or "").casefold(),
        str(primary_item.get("source_name") or "").casefold(),
    }
    for item in related_items:
        candidate_components.add(str(item.get("suspected_component") or "").casefold())
        candidate_components.add(str(item.get("source_name") or "").casefold())
    candidate_components.discard("")

    resolved = str(primary_item.get("context", {}).get("historical_status", "active")).casefold()

    for pattern in pattern_hints:
        pattern_component = str(pattern.get("suspected_component") or "").casefold()
        pattern_status = str(pattern.get("historical_status", "active")).casefold()
        pattern_category = str(pattern.get("category", "general"))

        if resolved != pattern_status and pattern_status in {"active", "resolved"}:
            continue
        if pattern_component and pattern_component not in candidate_components:
            continue
        if theme == "plugin_runtime" and pattern_category in {
            "plugin_startup",
            "missing_dependency",
            "plugin_compatibility_warning",
            "plugin_manifest_error",
            "data_integrity_error",
            "archive_access_error",
            "event_dispatch_failure",
            "log_error",
            "exception",
            "exception_chain",
        }:
            return pattern
        if theme == "network_config" and pattern_category in {"startup_security_warning", "rcon_configuration", "security_configuration"}:
            return pattern
        if theme == "config_parse" and pattern_category == "parse_error":
            return pattern
        if theme == "startup_misc" and pattern_category in {"startup_warning", "plugin_compatibility_warning", "startup_security_warning"}:
            return pattern

    return None


def _is_generic_group_title(pattern: dict) -> bool:
    title = str(pattern.get("title", "")).strip().casefold()
    if not title:
        return True
    generic_titles = {
        "log issue",
        "diagnostic issue",
        "warning log entry detected",
        "error log entry detected",
        "startup error log entry detected",
        "exception reported in logs",
        "missing plugin dependency detected",
        "missing library or classpath dependency detected",
    }
    return title in generic_titles


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


def _build_summary(status: ServerStatus, problem_groups: list[dict], log_summary: dict) -> str:
    if status.execution_mode == "runtime":
        lead = f"Runtime snapshot for '{status.container_name}': {status.container_status}."
    else:
        lead = f"Backup snapshot for '{status.container_name}'."

    rcon_sentence = ""
    if not status.rcon_responsive:
        rcon_sentence = "RCON is not responding."

    if problem_groups:
        issue_titles = []
        for group in problem_groups[:2]:
            title = str(group.get("title", "")).strip()
            if title and title not in issue_titles:
                issue_titles.append(title)
        if issue_titles:
            issues_sentence = "Main issues: " + "; ".join(issue_titles) + "."
        else:
            issues_sentence = "Main issues were detected in the current snapshot."
    else:
        compact_text = str(log_summary.get("compact_summary", {}).get("summary_text", "")).strip()
        issues_sentence = compact_text or "No significant diagnostic groups were detected in the current snapshot."

    parts = [lead]
    if rcon_sentence:
        parts.append(rcon_sentence)
    if issues_sentence:
        parts.append(issues_sentence)
    return " ".join(parts[:3])
