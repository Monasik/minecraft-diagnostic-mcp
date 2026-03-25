from dataclasses import asdict
import re

from minecraft_diagnostic_mcp.models.context import build_missing_dependency_context, build_plugin_startup_context, normalize_context
from minecraft_diagnostic_mcp.models.diagnostics import DiagnosticEvidence, DiagnosticItem, diagnostic_sort_key


PLUGIN_NAME_RE = re.compile(r"plugin\s+([A-Za-z0-9_.-]+)", re.IGNORECASE)
BRACKET_PLUGIN_RE = re.compile(r"\[([A-Za-z0-9_.-]+)\]")
ENABLE_RE = re.compile(r"while enabling\s+([A-Za-z0-9_.-]+)", re.IGNORECASE)
LOAD_RE = re.compile(r"could not load\s+plugin\s+([A-Za-z0-9_.-]+)", re.IGNORECASE)
VERSION_OF_RE = re.compile(r"version of\s+([A-Za-z0-9_.-]+)", re.IGNORECASE)
MISSING_CLASS_RE = re.compile(r"(?:NoClassDefFoundError|ClassNotFoundException):?\s+([A-Za-z0-9_/$\.]+)", re.IGNORECASE)

KNOWN_DEPENDENCY_SYMBOLS = {
    "placeholderapi": ("plugin_dependency", "PlaceholderAPI"),
    "me.clip.placeholderapi": ("plugin_dependency", "PlaceholderAPI"),
    "vault": ("plugin_dependency", "Vault"),
    "net.milkbowl.vault": ("plugin_dependency", "Vault"),
    "worldedit": ("plugin_dependency", "WorldEdit"),
    "com.sk89q.worldedit": ("plugin_dependency", "WorldEdit"),
    "worldguard": ("plugin_dependency", "WorldGuard"),
    "com.sk89q.worldguard": ("plugin_dependency", "WorldGuard"),
    "luckperms": ("plugin_dependency", "LuckPerms"),
    "net.luckperms": ("plugin_dependency", "LuckPerms"),
    "protocollib": ("plugin_dependency", "ProtocolLib"),
    "com.comphenix.protocol": ("plugin_dependency", "ProtocolLib"),
    "packetevents": ("plugin_dependency", "PacketEvents"),
    "com.github.retrooper.packetevents": ("plugin_dependency", "PacketEvents"),
    "floodgate": ("plugin_dependency", "Floodgate"),
    "org.geysermc.floodgate": ("plugin_dependency", "Floodgate"),
    "geyser": ("plugin_dependency", "Geyser"),
    "org.geysermc.geyser": ("plugin_dependency", "Geyser"),
    "citizens": ("plugin_dependency", "Citizens"),
    "net.citizensnpcs": ("plugin_dependency", "Citizens"),
    "oraxen": ("plugin_dependency", "Oraxen"),
    "io.th0rgal.oraxen": ("plugin_dependency", "Oraxen"),
    "itemsadder": ("plugin_dependency", "ItemsAdder"),
    "dev.lone.itemsadder": ("plugin_dependency", "ItemsAdder"),
    "nexo": ("plugin_dependency", "Nexo"),
    "com.nexomc.nexo": ("plugin_dependency", "Nexo"),
    "nexoitems": ("plugin_dependency", "Nexo"),
}


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

        specific_error = _build_specific_error_finding(
            text=text,
            text_lower=text_lower,
            level=level,
            component=component,
            evidence=evidence,
            log_context=log_context,
            startup_phase=startup_phase,
        )
        if specific_error is not None:
            findings.append(specific_error)

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
            missing_symbol = _extract_missing_symbol(text)
            missing_target_type, likely_dependency_name = _classify_missing_symbol(missing_symbol)
            if missing_target_type == "plugin_dependency":
                title = "Missing plugin dependency detected"
                summary = "A required plugin API or dependency class could not be found, which usually means a missing plugin dependency."
                tags = ["log", "dependency", "plugin", *(_startup_tags(startup_phase))]
                recommendations = [
                    "Install or update the missing dependency plugin before restarting the affected plugin.",
                    "Confirm the dependent plugin matches the server platform and version.",
                ]
            else:
                title = "Missing library or classpath dependency detected"
                summary = "A required class could not be found, which usually points to a missing bundled library, shaded dependency, or incompatible plugin build."
                tags = ["log", "dependency", "classpath", *(_startup_tags(startup_phase))]
                recommendations = [
                    "Verify that the plugin build includes its required libraries and matches the server platform and version.",
                    "Check whether the plugin jar is incomplete or built for a different environment.",
                ]
            findings.append(
                DiagnosticItem(
                    severity="error",
                    category="missing_dependency",
                    source_type="log",
                    source_name="docker_logs",
                    title=title,
                    summary=summary,
                    suspected_component=component,
                    evidence=evidence,
                    tags=tags,
                    context=build_missing_dependency_context(
                        component,
                        [likely_dependency_name] if missing_target_type == "plugin_dependency" and likely_dependency_name else [],
                        None,
                        missing_target_type=missing_target_type,
                        missing_symbol=missing_symbol,
                        likely_dependency_name=likely_dependency_name,
                    )
                    | log_context,
                    recommendations=recommendations,
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
    if level != "WARN":
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

    if not startup_phase:
        return None

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


def _build_specific_error_finding(level, text, text_lower, component, evidence, log_context, startup_phase):
    if level not in {"ERROR", "WARN"}:
        return None

    if "database disk image is malformed" in text_lower or "sqlite_corrupt" in text_lower:
        return DiagnosticItem(
            severity="error",
            category="data_integrity_error",
            source_type="log",
            source_name="docker_logs",
            title="SQLite data corruption detected",
            summary="The logs indicate SQLite database corruption, which can break plugin data reads or writes until the affected data store is repaired or restored.",
            suspected_component=component,
            evidence=evidence,
            tags=["log", "database", "sqlite", "integrity", *(_startup_tags(startup_phase))],
            context=log_context,
            recommendations=[
                "Check the affected plugin database file, restore from backup if needed, and verify disk or shutdown stability before restarting the plugin.",
            ],
        )

    if "zip file closed" in text_lower:
        return DiagnosticItem(
            severity="error" if level == "ERROR" else "warning",
            category="archive_access_error",
            source_type="log",
            source_name="docker_logs",
            title="Plugin archive access failed",
            summary="The logs show a closed zip/jar access failure, which often points to a corrupted plugin archive, unexpected reload behavior, or plugin I/O bug.",
            suspected_component=component,
            evidence=evidence,
            tags=["log", "archive", "jar", "io", *(_startup_tags(startup_phase))],
            context=log_context,
            recommendations=[
                "Reinstall or replace the affected plugin jar and avoid live-reload workflows if the plugin is not designed for them.",
            ],
        )

    if "plugin description" in text_lower and "no name field found in plugin.yml" in text_lower:
        return DiagnosticItem(
            severity="error",
            category="plugin_manifest_error",
            source_type="log",
            source_name="docker_logs",
            title="Plugin manifest is invalid",
            summary="A plugin jar contains an invalid plugin manifest, so the server cannot load it as a valid Bukkit/Paper plugin.",
            suspected_component=component,
            evidence=evidence,
            tags=["log", "plugin", "manifest", *(_startup_tags(startup_phase))],
            context=log_context,
            recommendations=[
                "Replace the plugin jar with a valid build that contains a correct plugin.yml or paper-plugin.yml manifest.",
            ],
        )

    if "could not pass event" in text_lower or ("caught unhandled exception" in text_lower and "calling event" in text_lower):
        return DiagnosticItem(
            severity="error" if level == "ERROR" else "warning",
            category="event_dispatch_failure",
            source_type="log",
            source_name="docker_logs",
            title="Plugin event dispatch failed",
            summary="The logs show an event listener or event dispatch failure, which usually means a plugin threw inside a listener during gameplay or startup hooks.",
            suspected_component=component,
            evidence=evidence,
            tags=["log", "plugin", "event", *(_startup_tags(startup_phase))],
            context=log_context,
            recommendations=[
                "Inspect the related stacktrace and update or reconfigure the plugin that owns the failing listener.",
            ],
        )

    return None


def _startup_tags(startup_phase: bool) -> list[str]:
    return ["startup"] if startup_phase else []


def _extract_missing_symbol(text: str) -> str | None:
    match = MISSING_CLASS_RE.search(text)
    if not match:
        return None
    return _clean_symbol_name(match.group(1))


def _classify_missing_symbol(symbol: str | None) -> tuple[str, str | None]:
    if not symbol:
        return "library_or_classpath", None

    normalized = str(symbol).strip().replace("/", ".").replace("$", ".").strip(".")
    normalized_lower = normalized.casefold()

    for key, value in KNOWN_DEPENDENCY_SYMBOLS.items():
        if normalized_lower == key or normalized_lower.startswith(f"{key}."):
            return value

    tail = normalized_lower.split(".")[-1]
    for key, value in KNOWN_DEPENDENCY_SYMBOLS.items():
        if tail == key.split(".")[-1]:
            return value

    return "library_or_classpath", _clean_symbol_name(normalized)


def _clean_symbol_name(raw: str) -> str:
    text = str(raw).strip().strip(":;,.)]}")
    text = text.replace("/", ".").replace("$", ".")
    text = re.sub(r"\.+", ".", text)
    text = text.strip(".")
    if not text:
        return ""
    parts = [part for part in text.split(".") if part]
    if not parts:
        return text
    return parts[-1]
