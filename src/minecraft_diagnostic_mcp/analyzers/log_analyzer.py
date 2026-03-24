from dataclasses import asdict
import re

from minecraft_diagnostic_mcp.models.context import build_missing_dependency_context, build_plugin_startup_context, normalize_context
from minecraft_diagnostic_mcp.models.diagnostics import DiagnosticEvidence, DiagnosticItem, diagnostic_sort_key


PLUGIN_NAME_RE = re.compile(r"plugin\s+([A-Za-z0-9_.-]+)", re.IGNORECASE)
BRACKET_PLUGIN_RE = re.compile(r"\[([A-Za-z0-9_.-]+)\]")
ENABLE_RE = re.compile(r"while enabling\s+([A-Za-z0-9_.-]+)", re.IGNORECASE)
LOAD_RE = re.compile(r"could not load\s+plugin\s+([A-Za-z0-9_.-]+)", re.IGNORECASE)
VERSION_OF_RE = re.compile(r"version of\s+([A-Za-z0-9_.-]+)", re.IGNORECASE)


def analyze_log_records(records: list[dict]) -> list[DiagnosticItem]:
    findings: list[DiagnosticItem] = []

    for record in records:
        text = record.get("text", "")
        text_lower = text.lower()
        level = record.get("level", "INFO")
        startup_phase = bool(record.get("startup_phase"))
        evidence = [DiagnosticEvidence(excerpt=text[:1200], line_number=record.get("start_line"), source="docker_logs")]
        component = _suspect_component(text)
        startup_context = build_plugin_startup_context(component, record.get("start_line"), "docker_logs")
        if record.get("log_source_file"):
            startup_context["source_file"] = record.get("log_source_file")
        log_context = normalize_context(
            "log_entry",
            {
                "plugin_name": component,
                "line_number": record.get("start_line"),
                "source": "docker_logs",
                "startup_phase": startup_phase,
                "source_file": record.get("log_source_file"),
            },
        )

        if "could not load" in text_lower:
            findings.append(
                DiagnosticItem(
                    severity="error",
                    category="plugin_startup",
                    source_type="log",
                    source_name="docker_logs",
                    title="Plugin could not load",
                    summary="A plugin failed during load, which often indicates a startup or dependency problem.",
                    suspected_component=component,
                    evidence=evidence,
                    tags=["log", "plugin", "startup"],
                    context=startup_context,
                    recommendations=[
                        "Check the plugin version and server compatibility.",
                        "Review missing dependencies or follow-up exception details in the same stacktrace.",
                    ],
                )
            )

        if "error occurred while enabling" in text_lower:
            findings.append(
                DiagnosticItem(
                    severity="error",
                    category="plugin_startup",
                    source_type="log",
                    source_name="docker_logs",
                    title="Plugin failed while enabling",
                    summary="A plugin threw an error during enable, which usually prevents it from starting correctly.",
                    suspected_component=component,
                    evidence=evidence,
                    tags=["log", "plugin", "startup"],
                    context=startup_context,
                    recommendations=[
                        "Inspect the stacktrace for the root cause.",
                        "Verify the plugin's dependencies and config files.",
                    ],
                )
            )

        if "noclassdeffounderror" in text_lower or "classnotfoundexception" in text_lower:
            findings.append(
                DiagnosticItem(
                    severity="error",
                    category="missing_dependency",
                    source_type="log",
                    source_name="docker_logs",
                    title="Missing class or dependency detected",
                    summary="A required class could not be found, which often means a missing plugin, library, or incompatible server build.",
                    suspected_component=component,
                    evidence=evidence,
                    tags=["log", "dependency", "classpath", *(_startup_tags(startup_phase))],
                    context=build_missing_dependency_context(component, [], None) | log_context,
                    recommendations=[
                        "Check hard dependencies for the affected plugin.",
                        "Confirm the plugin build matches the server platform and version.",
                    ],
                )
            )

        if "caused by:" in text_lower:
            findings.append(
                DiagnosticItem(
                    severity="warning",
                    category="exception_chain",
                    source_type="log",
                    source_name="docker_logs",
                    title="Nested exception cause detected",
                    summary="The log contains a nested exception cause that may point to the real root problem.",
                    suspected_component=component,
                    evidence=evidence,
                    tags=["log", "exception", *(_startup_tags(startup_phase))],
                    context=log_context,
                    recommendations=[
                        "Read the deepest 'Caused by' line in the stacktrace first.",
                    ],
                )
            )

        if "exception" in text_lower and "caused by:" not in text_lower:
            findings.append(
                DiagnosticItem(
                    severity="warning" if level != "ERROR" else "error",
                    category="exception",
                    source_type="log",
                    source_name="docker_logs",
                    title="Exception reported in logs",
                    summary="The logs contain an exception that may indicate startup, plugin, or runtime instability.",
                    suspected_component=component,
                    evidence=evidence,
                    tags=["log", "exception", *(_startup_tags(startup_phase))],
                    context=log_context,
                    recommendations=[
                        "Inspect the exception class and surrounding lines for the failing component.",
                    ],
                )
            )

        startup_warning = _build_startup_warning(
            level,
            text,
            text_lower,
            component,
            evidence,
            log_context,
            startup_phase,
        )
        if startup_warning is not None:
            findings.append(startup_warning)
            continue

        operational_warning = _build_operational_warning(level, text, text_lower, component, evidence, log_context)
        if operational_warning is not None:
            findings.append(operational_warning)
            continue

        if level == "ERROR":
            findings.append(
                DiagnosticItem(
                    severity="error",
                    category="log_error",
                    source_type="log",
                    source_name="docker_logs",
                    title="Startup error log entry detected" if startup_phase else "Error log entry detected",
                    summary="The server emitted an ERROR-level log entry during startup." if startup_phase else "The server emitted an ERROR-level log entry.",
                    suspected_component=component,
                    evidence=evidence,
                    tags=["log", "error", *(_startup_tags(startup_phase))],
                    context=log_context,
                    recommendations=[
                        "Review the error context and any related stacktrace lines.",
                    ],
                )
            )
        elif level == "WARN":
            if startup_phase:
                continue
            findings.append(
                DiagnosticItem(
                    severity="warning",
                    category="log_warning",
                    source_type="log",
                    source_name="docker_logs",
                    title="Startup warning log entry detected" if startup_phase else "Warning log entry detected",
                    summary="The server emitted a WARN-level log entry during startup that may indicate a configuration or plugin issue." if startup_phase else "The server emitted a WARN-level log entry that may indicate a configuration or plugin issue.",
                    suspected_component=component,
                    evidence=evidence,
                    tags=["log", "warning", *(_startup_tags(startup_phase))],
                    context=log_context,
                    recommendations=[
                        "Review whether the warning is expected or indicates a missing dependency or misconfiguration.",
                    ],
                )
            )

    deduped = _deduplicate_findings(findings)
    return sorted(deduped, key=diagnostic_sort_key)


def serialize_findings(findings: list[DiagnosticItem]) -> list[dict]:
    return [asdict(finding) for finding in findings]


def _suspect_component(text: str) -> str | None:
    enable_match = ENABLE_RE.search(text)
    if enable_match:
        return enable_match.group(1)

    load_match = LOAD_RE.search(text)
    if load_match:
        return load_match.group(1)

    plugin_match = PLUGIN_NAME_RE.search(text)
    if plugin_match:
        candidate = plugin_match.group(1)
        if candidate.casefold() not in {"description", "version"}:
            return candidate

    version_match = VERSION_OF_RE.search(text)
    if version_match:
        return version_match.group(1)

    bracket_matches = BRACKET_PLUGIN_RE.findall(text)
    for match in bracket_matches:
        upper = match.upper()
        if upper not in {"INFO", "WARN", "ERROR", "SERVER", "MAIN"}:
            return match
    return None


def _deduplicate_findings(findings: list[DiagnosticItem]) -> list[DiagnosticItem]:
    seen: set[tuple[str, str, str | None, str]] = set()
    deduped: list[DiagnosticItem] = []

    for finding in findings:
        first_excerpt = finding.evidence[0].excerpt if finding.evidence else ""
        dedupe_by_category = finding.category in {"startup_security_warning"}
        key = (
            finding.category,
            finding.title,
            finding.suspected_component,
            "" if dedupe_by_category else first_excerpt,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)

    return deduped


def _build_operational_warning(level, text, text_lower, component, evidence, log_context):
    if level != "WARN":
        return None

    if "moved too quickly" in text_lower or "moved wrongly" in text_lower:
        return DiagnosticItem(
            severity="info",
            category="operational_movement_warning",
            source_type="log",
            source_name="docker_logs",
            title="Player movement warning",
            summary="The server logged a movement-related warning. These messages are common during lag spikes, teleportation, or aggressive movement checks.",
            suspected_component=component,
            evidence=evidence,
            tags=["log", "operational", "movement"],
            context=log_context,
            recommendations=[
                "Treat this as low-priority noise unless it appears very frequently or players report rubber-banding.",
            ],
            priority=14,
        )

    if "can't keep up!" in text_lower:
        return DiagnosticItem(
            severity="warning",
            category="performance_warning",
            source_type="log",
            source_name="docker_logs",
            title="Server tick lag detected",
            summary="The server reported that it was running behind, which suggests a temporary performance spike or sustained lag.",
            suspected_component=component,
            evidence=evidence,
            tags=["log", "performance", "lag"],
            context=log_context,
            recommendations=[
                "Check whether lag spikes are recurring before treating this as a major issue.",
            ],
            priority=28,
        )

    if component and component.casefold() == "spark":
        return DiagnosticItem(
            severity="info",
            category="monitoring_warning",
            source_type="log",
            source_name="docker_logs",
            title="Monitoring plugin warning",
            summary="The spark monitoring plugin reported a warning while profiling or collecting diagnostics.",
            suspected_component=component,
            evidence=evidence,
            tags=["log", "monitoring", "spark"],
            context=log_context,
            recommendations=[
                "Review this only if the profiler output was unexpected or the warning repeats outside manual profiling.",
            ],
            priority=16,
        )

    return None


def _build_startup_warning(level, text, text_lower, component, evidence, log_context, startup_phase):
    if not startup_phase or level != "WARN":
        return None

    if "offline/insecure mode" in text_lower or ('online-mode' in text_lower and '"true"' in text_lower):
        return DiagnosticItem(
            severity="warning",
            category="startup_security_warning",
            source_type="log",
            source_name="docker_logs",
            title="Server started in insecure mode",
            summary="The startup logs indicate that the server is running in offline or insecure mode.",
            suspected_component=component,
            evidence=evidence,
            tags=["log", "startup", "security", "network"],
            context=log_context,
            recommendations=[
                "Enable online-mode in server.properties unless this server is intentionally behind a trusted proxy or auth layer.",
            ],
        )

    compatibility_patterns = (
        "could not setup a nms hook",
        "has not been tested with the current minecraft version",
        "cannot interact with paper-plugins",
        "it seems like you're running on paper",
    )
    if any(pattern in text_lower for pattern in compatibility_patterns):
        return DiagnosticItem(
            severity="warning",
            category="plugin_compatibility_warning",
            source_type="log",
            source_name="docker_logs",
            title="Plugin compatibility warning",
            summary="A plugin reported a startup-time compatibility limitation with the current server platform or version.",
            suspected_component=component,
            evidence=evidence,
            tags=["log", "startup", "plugin", "compatibility"],
            context=log_context,
            recommendations=[
                "Verify that the plugin officially supports this Minecraft or Paper version before treating this as harmless.",
            ],
        )

    startup_info_patterns = (
        "deprecated",
        "lang file",
        "no migrations found",
        "creating mineskinclient without api key",
        "legacy material support",
    )
    if any(pattern in text_lower for pattern in startup_info_patterns):
        return DiagnosticItem(
            severity="info",
            category="startup_warning",
            source_type="log",
            source_name="docker_logs",
            title="Startup warning",
            summary="A plugin emitted a startup-time warning that may not block boot but is worth reviewing.",
            suspected_component=component,
            evidence=evidence,
            tags=["log", "startup", "warning"],
            context=log_context,
            recommendations=[
                "Review the plugin's startup warning and update its config or version if needed.",
            ],
        )

    return None


def _startup_tags(startup_phase: bool) -> list[str]:
    return ["startup"] if startup_phase else []
