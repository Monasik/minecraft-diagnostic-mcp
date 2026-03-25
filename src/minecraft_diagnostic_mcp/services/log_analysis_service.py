import re

from minecraft_diagnostic_mcp.collectors.filesystem_collector import (
    get_latest_log_path,
    list_log_files,
    read_log_text,
    read_text_file,
)
from minecraft_diagnostic_mcp.models.diagnostics import DiagnosticSummary, diagnostic_sort_key
from minecraft_diagnostic_mcp.analyzers.log_analyzer import analyze_log_records, serialize_findings
from minecraft_diagnostic_mcp.collectors.docker_collector import get_recent_logs
from minecraft_diagnostic_mcp.parsers.log_parser import parse_log_records
from minecraft_diagnostic_mcp.services.plugin_service import list_plugins
from minecraft_diagnostic_mcp.settings import settings


STARTUP_DONE_RE = re.compile(r'for help,\s*type\s+"help"', re.IGNORECASE)
COMPACT_ACTIVE_LIMIT = 8
COMPACT_RESOLVED_LIMIT = 5
COMPACT_PATTERN_LIMIT = 8
GENERIC_PATTERN_CATEGORIES = {"log_warning", "log_error", "exception", "exception_chain"}
PATTERN_LABEL_CATEGORIES = GENERIC_PATTERN_CATEGORIES | {
    "data_integrity_error",
    "archive_access_error",
    "plugin_manifest_error",
    "event_dispatch_failure",
    "plugin_compatibility_warning",
    "startup_security_warning",
    "startup_warning",
}


def analyze_recent_logs(lines: int = 200, include_archives: bool = False, compact: bool = False) -> dict:
    safe_lines = max(1, int(lines))
    archives_enabled = bool(include_archives)
    latest_log_path = get_latest_log_path()
    latest_log_path_str = str(latest_log_path) if latest_log_path else None

    try:
        raw_logs = get_recent_logs(safe_lines)
    except Exception as exc:
        result = {
            "scanned_lines": safe_lines,
            "archives_included": archives_enabled,
            "detail_mode": "compact" if compact else "full",
            "log_files_scanned": [],
            "diagnostics": [],
            "summary": {
                "record_count": 0,
                "item_count": 0,
                "finding_count": 0,
                "info_count": 0,
                "error_count": 0,
                "warning_count": 0,
                "critical_count": 0,
                "message": f"Failed to fetch logs: {exc}",
            },
        }
        return _compactify_result(result) if compact else result

    if not raw_logs.strip():
        result = {
            "scanned_lines": safe_lines,
            "archives_included": archives_enabled,
            "detail_mode": "compact" if compact else "full",
            "log_files_scanned": [],
            "diagnostics": [],
            "summary": {
                "record_count": 0,
                "item_count": 0,
                "finding_count": 0,
                "info_count": 0,
                "error_count": 0,
                "warning_count": 0,
                "critical_count": 0,
                "message": "No recent log lines were returned.",
            },
        }
        return _compactify_result(result) if compact else result

    records = parse_log_records(raw_logs)
    if latest_log_path_str:
        for record in records:
            record["log_source_file"] = latest_log_path_str

    latest_log_records, startup_records, startup_window = _load_latest_log_records()
    scanned_files: list[dict] = []

    if archives_enabled:
        archive_result = _load_archive_records()
        records = archive_result["records"] + records
        scanned_files = archive_result["log_files_scanned"]
    else:
        latest_log_path = get_latest_log_path()
        if latest_log_path:
            scanned_files = [{
                "path": str(latest_log_path),
                "file_type": "log",
                "readable": True,
            }]

    findings = analyze_log_records(records)
    startup_findings = analyze_log_records(startup_records)
    startup_window["item_count"] = len(startup_findings)
    findings = _merge_findings(findings, startup_findings)
    findings = _correlate_findings_with_plugins(findings)
    findings = _annotate_historical_status(findings, archives_enabled, latest_log_records, latest_log_path_str)
    summary = DiagnosticSummary(
        item_count=len(findings),
        info_count=sum(1 for finding in findings if finding.severity == "info"),
        warning_count=sum(1 for finding in findings if finding.severity == "warning"),
        error_count=sum(1 for finding in findings if finding.severity == "error"),
        critical_count=sum(1 for finding in findings if finding.severity == "critical"),
        message="Recent log analysis completed successfully.",
    )

    result = {
        "scanned_lines": safe_lines,
        "archives_included": archives_enabled,
        "detail_mode": "compact" if compact else "full",
        "log_files_scanned": scanned_files,
        "diagnostics": serialize_findings(findings),
        "startup_window": startup_window,
        "log_category_counts": _count_categories(findings),
        "summary": {
            "record_count": len(records),
            "item_count": summary.item_count,
            "finding_count": summary.item_count,
            "info_count": summary.info_count,
            "warning_count": summary.warning_count,
            "error_count": summary.error_count,
            "critical_count": summary.critical_count,
            "message": summary.message,
        },
    }
    return _compactify_result(result) if compact else result


def _compactify_result(result: dict) -> dict:
    diagnostics = result.get("diagnostics", [])
    summary = result.get("summary", {})
    compact_summary = _build_compact_log_summary(
        diagnostics=diagnostics,
        log_files_scanned=result.get("log_files_scanned", []),
        log_category_counts=result.get("log_category_counts", {}),
        startup_window=result.get("startup_window", {}),
        summary=summary,
    )

    compact_result = {
        "scanned_lines": result.get("scanned_lines", 0),
        "archives_included": result.get("archives_included", False),
        "detail_mode": "compact",
        "log_files_scanned": result.get("log_files_scanned", []),
        "startup_window": result.get("startup_window", {}),
        "log_category_counts": result.get("log_category_counts", {}),
        "compact_summary": compact_summary,
        "summary": summary,
    }

    compact_result["diagnostics"] = compact_summary.get("top_active_diagnostics", [])
    return compact_result


def _build_compact_log_summary(
    diagnostics: list[dict],
    log_files_scanned: list[dict],
    log_category_counts: dict[str, int],
    startup_window: dict,
    summary: dict,
) -> dict:
    active_diagnostics = [item for item in diagnostics if item.get("context", {}).get("historical_status") != "resolved"]
    resolved_diagnostics = [item for item in diagnostics if item.get("context", {}).get("historical_status") == "resolved"]

    top_active = sorted(active_diagnostics, key=diagnostic_sort_key)[:COMPACT_ACTIVE_LIMIT]
    top_resolved = sorted(resolved_diagnostics, key=diagnostic_sort_key)[:COMPACT_RESOLVED_LIMIT]
    repeated_patterns = _build_repeated_patterns(diagnostics)[:COMPACT_PATTERN_LIMIT]
    file_summary = _build_file_summary(log_files_scanned)

    return {
        "active_item_count": len(active_diagnostics),
        "resolved_item_count": len(resolved_diagnostics),
        "top_active_diagnostics": top_active,
        "top_resolved_diagnostics": top_resolved,
        "repeated_patterns": repeated_patterns,
        "top_categories": _top_category_counts(log_category_counts),
        "file_summary": file_summary,
        "startup_summary": _build_startup_compact_summary(startup_window),
        "summary_text": _build_compact_summary_text(top_active, top_resolved, repeated_patterns, summary, file_summary),
    }


def _build_repeated_patterns(diagnostics: list[dict]) -> list[dict]:
    grouped_patterns: dict[tuple[str, str, str, str], dict] = {}
    for item in diagnostics:
        occurrence_count = int(item.get("context", {}).get("occurrence_count", 1))
        component = str(item.get("suspected_component") or item.get("source_name") or "").casefold()
        status = str(item.get("context", {}).get("historical_status", "active")).casefold()
        issue_family, issue_label = _compact_issue_family(item)
        title_signature = f"{str(item.get('title', '')).casefold()}::{issue_family}"
        key = (
            str(item.get("category", "general")).casefold(),
            component,
            status,
            title_signature,
        )
        source_files = item.get("context", {}).get("source_files", [])
        existing = grouped_patterns.get(key)
        if existing is None:
            grouped_patterns[key] = {
                "category": item.get("category", "general"),
                "title": _compact_pattern_title(item, issue_label),
                "suspected_component": item.get("suspected_component"),
                "severity": item.get("severity", "info"),
                "priority": item.get("priority", 0),
                "occurrence_count": occurrence_count,
                "source_file_count": len(source_files),
                "historical_status": item.get("context", {}).get("historical_status", "active"),
                "issue_family": issue_family,
                "issue_label": issue_label,
            }
            continue

        existing["occurrence_count"] += occurrence_count
        existing["source_file_count"] = max(existing["source_file_count"], len(source_files))
        existing["priority"] = max(existing["priority"], item.get("priority", 0))

    patterns = [item for item in grouped_patterns.values() if item.get("occurrence_count", 1) >= 2]
    for pattern in patterns:
        pattern["pattern_score"] = _pattern_score(pattern)
    patterns = _suppress_generic_patterns(patterns)
    patterns.sort(
        key=lambda item: (
            -int(item.get("pattern_score", 0)),
            -int(item.get("priority", 0)),
            -int(item.get("occurrence_count", 1)),
            str(item.get("title", "")),
        )
    )
    return patterns


def _compact_issue_family(item: dict) -> tuple[str, str]:
    category = str(item.get("category", "general"))
    evidence = item.get("evidence", [])
    excerpt = evidence[0].get("excerpt", "") if evidence else ""
    normalized = _normalize_excerpt_signature(excerpt)
    component = str(item.get("suspected_component") or "").casefold()

    category_overrides = {
        "data_integrity_error": ("sqlite_corruption", "SQLite corruption"),
        "archive_access_error": ("zip_file_closed", "Zip file closed"),
        "plugin_manifest_error": ("plugin_manifest_invalid", "Invalid plugin manifest"),
        "event_dispatch_failure": ("packet_handling_failure", "Packet handling failure")
        if "packetevents" in normalized or "packetevents" in component
        else ("event_dispatch_failure", "Event dispatch failure"),
    }
    if category in category_overrides:
        return category_overrides[category]

    startup_family = _startup_issue_family(category, normalized)
    if startup_family is not None:
        return startup_family

    if category == "missing_dependency":
        issue_info = _missing_dependency_issue_info(item, excerpt, normalized)
        if issue_info:
            return issue_info

    if category not in GENERIC_PATTERN_CATEGORIES:
        return category, _humanize_category_label(category)

    known_patterns = (
        ("database disk image is malformed", ("sqlite_corruption", "SQLite corruption")),
        ("sqlite_corrupt", ("sqlite_corruption", "SQLite corruption")),
        ("zip file closed", ("zip_file_closed", "Zip file closed")),
        ("no name field found in plugin.yml", ("plugin_manifest_invalid", "Invalid plugin manifest")),
        ("could not pass event", ("event_dispatch_failure", "Event dispatch failure")),
        ("nullpointerexception", ("null_pointer", "Null pointer exception")),
        ("illegalstateexception", ("illegal_state", "Illegal state exception")),
        ("ioexception", ("io_failure", "I/O failure")),
        ("could not load", ("plugin_load_failure", "Plugin load failure")),
        ("had an error while loading user data", ("player_data_lookup_failure", "Player data lookup failure")),
        ("while loading user data", ("player_data_lookup_failure", "Player data lookup failure")),
        ("packet handling error", ("packet_handling_failure", "Packet handling failure")),
    )
    for needle, family_info in known_patterns:
        if needle in normalized:
            return family_info

    if "caught unhandled exception" in normalized and ("packetevents" in normalized or "packetevents" in component):
        return ("packet_handling_failure", "Packet handling failure")
    if "caught an unhandled exception" in normalized and ("packetevents" in normalized or "packetevents" in component):
        return ("packet_handling_failure", "Packet handling failure")
    if "calling your listener" in normalized and ("packetevents" in normalized or "packetevents" in component):
        return ("packet_handling_failure", "Packet handling failure")
    exception_family = _exception_issue_family(normalized)
    if exception_family is not None:
        return exception_family
    if "caught unhandled exception" in normalized:
        return ("unhandled_exception", "Unhandled exception")
    if "calling event" in normalized or "event exception" in normalized:
        return ("event_dispatch_failure", "Event dispatch failure")
    if "plugin description" in normalized and "no name field" in normalized:
        return ("plugin_manifest_invalid", "Invalid plugin manifest")

    if "saving" in normalized and ("player" in normalized or "user data" in normalized):
        return ("player_save_failure", "Player save failure")
    if ("loading user data" in normalized) or ("loading" in normalized and "player" in normalized):
        return ("player_data_load_failure", "Player data load failure")
    if "saving data" in normalized or ("saving" in normalized and "data" in normalized):
        return ("data_save_failure", "Data save failure")
    if "loading data" in normalized:
        return ("data_load_failure", "Data load failure")

    fallback_family = _fallback_issue_family(normalized, category)
    fallback_label = _fallback_issue_label(normalized, category)
    return fallback_family, fallback_label


def _missing_dependency_issue_info(item: dict, excerpt: str, normalized: str) -> tuple[str, str] | None:
    context = item.get("context", {}) if isinstance(item, dict) else {}
    missing_dependencies = context.get("missing_dependencies", [])
    target_type = str(context.get("missing_target_type", "")).casefold()
    likely_dependency_name = _clean_symbol_name(str(context.get("likely_dependency_name", ""))) if context.get("likely_dependency_name") else None
    missing_symbol = _clean_symbol_name(str(context.get("missing_symbol", ""))) if context.get("missing_symbol") else None

    if target_type == "plugin_dependency" and likely_dependency_name:
        dependency_slug = _slugify_issue_part(likely_dependency_name) or "dependency"
        return (f"missing_plugin_dependency_{dependency_slug}", f"Missing plugin dependency {likely_dependency_name}")

    if target_type == "library_or_classpath" and missing_symbol:
        symbol_slug = _slugify_issue_part(missing_symbol) or "class"
        return (f"missing_library_symbol_{symbol_slug}", f"Missing class {missing_symbol}")

    if isinstance(missing_dependencies, list) and len(missing_dependencies) == 1:
        dependency_name = _clean_symbol_name(str(missing_dependencies[0]))
        dependency_slug = _slugify_issue_part(dependency_name) or "dependency"
        return (f"missing_dependency_{dependency_slug}", f"Missing dependency {dependency_name}")
    if isinstance(missing_dependencies, list) and len(missing_dependencies) > 1:
        return ("missing_dependencies", "Missing dependencies")

    missing_class = _extract_missing_class_name(excerpt, normalized)
    if missing_class:
        class_slug = _slugify_issue_part(missing_class) or "class"
        return (f"missing_class_{class_slug}", f"Missing class {missing_class}")

    return None


def _extract_missing_class_name(excerpt: str, normalized: str) -> str | None:
    patterns = (
        r"NoClassDefFoundError:?\s+([A-Za-z0-9_/$\.]+)",
        r"ClassNotFoundException:?\s+([A-Za-z0-9_/$\.]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, excerpt, re.IGNORECASE)
        if match:
            return _clean_symbol_name(match.group(1))

    if "noclassdeffounderror" in normalized or "classnotfoundexception" in normalized:
        tail_match = re.search(r"(?:noclassdeffounderror|classnotfoundexception)\s*([a-z0-9_/$\.]+)", normalized)
        if tail_match:
            return _clean_symbol_name(tail_match.group(1))
    return None


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
    if len(parts[-1]) <= 2 and len(parts) > 1:
        return parts[-2]
    return parts[-1]


def _slugify_issue_part(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(text).casefold())
    slug = slug.strip("_")
    return slug


def _compact_pattern_title(item: dict, issue_label: str) -> str:
    category = str(item.get("category", "general"))
    component = item.get("suspected_component")
    component_display = _display_component_name(component)
    component_prefix = f"{component_display}: " if component_display else ""

    if category == "missing_dependency" and issue_label:
        return f"{component_prefix}{issue_label}".strip()

    if category not in PATTERN_LABEL_CATEGORIES:
        return str(item.get("title", "Repeated issue"))

    if issue_label:
        normalized_label = issue_label
        if component and issue_label.casefold().startswith(str(component).casefold()):
            normalized_label = issue_label[len(str(component)):].strip(" :-")
        return f"{component_prefix}{normalized_label} pattern".strip()

    fallback = str(item.get("title", "Repeated issue"))
    if component_display:
        return f"{component_display}: {fallback}"
    return fallback


def _display_component_name(component: str | None) -> str:
    if not component:
        return ""

    raw = str(component).strip()
    if not raw:
        return ""

    if "." in raw:
        tail = raw.split(".")[-1].strip()
        if tail:
            return tail

    return raw


def _preferred_summary_pattern(repeated_patterns: list[dict]) -> dict:
    ranked = sorted(
        repeated_patterns,
        key=lambda item: (
            0 if str(item.get("historical_status", "active")).casefold() == "active" else 1,
            -int(item.get("pattern_score", 0)),
            -int(item.get("occurrence_count", 1)),
            str(item.get("title", "")),
        ),
    )
    return ranked[0]


def _humanize_category_label(category: str) -> str:
    return category.replace("_", " ").strip().title()


def _fallback_issue_family(normalized_excerpt: str, category: str) -> str:
    words = [word for word in normalized_excerpt.split(" ") if word]
    if not words:
        return category

    family_words = []
    for word in words:
        cleaned = re.sub(r"[^a-z0-9_]+", "", word)
        if cleaned in {"uuid", "id"}:
            continue
        if not cleaned or cleaned in {"the", "and", "with", "from", "while", "when", "for", "of", "to", "server", "thread", "warn", "error", "had", "an"}:
            continue
        family_words.append(cleaned)
        if len(family_words) >= 6:
            break

    return "_".join(family_words) or category


def _fallback_issue_label(normalized_excerpt: str, category: str) -> str:
    phrase_patterns = (
        (("saving", "player"), "Player save failure"),
        (("saving", "user data"), "Player save failure"),
        (("loading", "player"), "Player data load failure"),
        (("loading", "user data"), "Player data load failure"),
        (("caught unhandled exception", "packetevents"), "Packet handling failure"),
        (("caught an unhandled exception", "packetevents"), "Packet handling failure"),
        (("calling your listener", "packetevents"), "Packet handling failure"),
        (("caught unhandled exception",), "Unhandled exception"),
        (("calling event",), "Event dispatch failure"),
        (("event exception",), "Event dispatch failure"),
        (("plugin description", "no name field"), "Invalid plugin manifest"),
        (("database disk image is malformed",), "SQLite corruption"),
        (("zip file closed",), "Zip file closed"),
    )
    for needles, label in phrase_patterns:
        if all(needle in normalized_excerpt for needle in needles):
            return label

    words = [word for word in normalized_excerpt.split(" ") if word]
    if not words:
        return _humanize_category_label(category)

    label_words = []
    for word in words:
        cleaned = re.sub(r"[^a-z0-9]+", "", word)
        if cleaned in {"uuid", "id"}:
            continue
        if not cleaned or cleaned in {"the", "and", "with", "from", "while", "when", "for", "of", "to", "server", "thread", "warn", "error", "had", "an", "caught", "calling", "exception", "unhandled", "your", "listener"}:
            continue
        label_words.append(cleaned.capitalize())
        if len(label_words) >= 4:
            break

    if not label_words:
        return _humanize_category_label(category)
    return " ".join(label_words)


def _startup_issue_family(category: str, normalized_excerpt: str) -> tuple[str, str] | None:
    if category == "startup_security_warning":
        if "offline/insecure mode" in normalized_excerpt or "online-mode" in normalized_excerpt:
            return ("offline_mode_enabled", "Offline mode enabled")
        return ("startup_security_warning", "Startup security warning")

    if category == "plugin_compatibility_warning":
        if "nms hook" in normalized_excerpt:
            return ("server_hook_unavailable", "Server version hook unavailable")
        if "not been tested with the current minecraft version" in normalized_excerpt:
            return ("untested_minecraft_version", "Untested Minecraft version")
        if "paper-plugins" in normalized_excerpt:
            return ("paper_plugin_compatibility_limit", "Paper plugin compatibility limitation")
        return ("plugin_compatibility_warning", "Plugin compatibility warning")

    if category == "startup_warning":
        if "deprecated" in normalized_excerpt:
            return ("deprecated_startup_config", "Deprecated startup config")
        if "lang file" in normalized_excerpt or "locale" in normalized_excerpt:
            return ("missing_locale_resource", "Missing locale resource")
        if "mineskinclient without api key" in normalized_excerpt or "without api key" in normalized_excerpt:
            return ("missing_api_key", "Missing API key")
        if "legacy material support" in normalized_excerpt:
            return ("legacy_material_support", "Legacy material support")
        return ("startup_warning", "Startup warning")

    return None


def _exception_issue_family(normalized_excerpt: str) -> tuple[str, str] | None:
    exception_patterns = (
        ("illegalargumentexception", ("illegal_argument", "Illegal argument error")),
        ("illegalstateexception", ("illegal_state", "Illegal state error")),
        ("numberformatexception", ("number_format", "Number format error")),
        ("classcastexception", ("class_cast", "Class cast error")),
        ("unsupportedclassversionerror", ("unsupported_java_version", "Unsupported Java version")),
        ("verifyerror", ("bytecode_verification", "Bytecode verification error")),
        ("sqlexception", ("sql_failure", "SQL failure")),
        ("ioexception", ("io_failure", "I/O failure")),
        ("nullpointerexception", ("null_pointer", "Null pointer exception")),
    )
    for needle, result in exception_patterns:
        if needle in normalized_excerpt:
            return result
    return None


def _pattern_score(pattern: dict) -> int:
    score = int(pattern.get("priority", 0)) + min(int(pattern.get("occurrence_count", 1)), 50)

    category = str(pattern.get("category", "general"))
    if category in {"missing_dependency", "plugin_startup", "plugin_compatibility_warning", "startup_security_warning"}:
        score += 25
    elif category in {"performance_warning", "monitoring_warning", "operational_movement_warning"}:
        score += 10
    elif category in GENERIC_PATTERN_CATEGORIES:
        score -= 15

    if pattern.get("suspected_component"):
        score += 8

    if str(pattern.get("historical_status", "active")).casefold() == "active":
        score += 12
    else:
        score -= 8

    return max(score, 0)


def _suppress_generic_patterns(patterns: list[dict]) -> list[dict]:
    has_specific_patterns = any(
        pattern.get("category") not in GENERIC_PATTERN_CATEGORIES
        for pattern in patterns
    )
    if not has_specific_patterns:
        return patterns

    filtered = []
    generic_with_component = []
    for pattern in patterns:
        category = str(pattern.get("category", "general"))
        component = pattern.get("suspected_component")
        if category in GENERIC_PATTERN_CATEGORIES and not component:
            continue
        if category in GENERIC_PATTERN_CATEGORIES:
            generic_with_component.append(pattern)
            continue
        filtered.append(pattern)

    if generic_with_component:
        generic_with_component.sort(
            key=lambda item: (
                -int(item.get("pattern_score", 0)),
                -int(item.get("occurrence_count", 1)),
                str(item.get("title", "")),
            )
        )
        filtered.extend(generic_with_component[:2])

    return filtered


def _build_file_summary(log_files_scanned: list[dict]) -> dict:
    scanned_count = len(log_files_scanned)
    archive_count = sum(1 for item in log_files_scanned if item.get("file_type") == "log.gz")
    unreadable_count = sum(1 for item in log_files_scanned if not item.get("readable", True))
    readable_files = [item for item in log_files_scanned if item.get("readable", True)]

    first_source = readable_files[-1]["path"] if readable_files else None
    latest_source = readable_files[0]["path"] if readable_files else None

    return {
        "scanned_count": scanned_count,
        "archive_count": archive_count,
        "unreadable_count": unreadable_count,
        "latest_source": latest_source,
        "oldest_source": first_source,
    }


def _build_startup_compact_summary(startup_window: dict) -> dict:
    if not startup_window:
        return {"detected": False, "item_count": 0}

    return {
        "detected": bool(startup_window.get("detected", False)),
        "completed": bool(startup_window.get("completed", False)),
        "record_count": int(startup_window.get("record_count", 0)),
        "item_count": int(startup_window.get("item_count", 0)),
        "source": startup_window.get("source"),
    }


def _top_category_counts(log_category_counts: dict[str, int]) -> list[dict]:
    return [
        {"category": category, "count": count}
        for category, count in list(log_category_counts.items())[:8]
    ]


def _build_compact_summary_text(
    top_active: list[dict],
    top_resolved: list[dict],
    repeated_patterns: list[dict],
    summary: dict,
    file_summary: dict,
) -> str:
    file_count = int(file_summary.get("scanned_count", 0))
    archive_count = int(file_summary.get("archive_count", 0))
    item_count = int(summary.get("item_count", 0))
    error_count = int(summary.get("error_count", 0))
    warning_count = int(summary.get("warning_count", 0))
    intro = (
        f"Scanned {file_count} log file(s)"
        + (f" including {archive_count} archive(s)" if archive_count else "")
        + f" and condensed {item_count} diagnostic item(s)."
    )

    if top_active:
        lead = top_active[0]
        lead_title = str(lead.get("title", "Diagnostic issue")).strip()
        active_sentence = f"Active now: {lead_title}."
    elif item_count:
        active_sentence = "No high-priority active issue remains after comparing historical and latest logs."
    else:
        active_sentence = "No significant diagnostics were produced from the scanned logs."

    detail_sentence = ""
    resolved_patterns = [
        pattern for pattern in repeated_patterns
        if str(pattern.get("historical_status", "active")).casefold() == "resolved"
    ]
    if resolved_patterns:
        resolved_titles = []
        for item in resolved_patterns[:2]:
            title = str(item.get("title", "")).strip()
            if title and title not in resolved_titles:
                resolved_titles.append(title)
        if resolved_titles:
            detail_sentence = "Historical issues now resolved include " + ", ".join(resolved_titles) + "."
    elif top_resolved:
        resolved_titles = []
        for item in top_resolved[:2]:
            title = str(item.get("title", "")).strip()
            if title and title not in resolved_titles:
                resolved_titles.append(title)
        if resolved_titles:
            detail_sentence = "Historical issues now resolved include " + ", ".join(resolved_titles) + "."

    if not detail_sentence and repeated_patterns:
        strongest = _preferred_summary_pattern(repeated_patterns)
        detail_sentence = (
            f"Most repeated pattern: {strongest.get('title', 'Repeated issue')} "
            f"({strongest.get('occurrence_count', 1)} occurrence(s))."
        )

    totals_sentence = ""
    if error_count or warning_count:
        totals_sentence = f"Totals across scanned logs: {error_count} error(s), {warning_count} warning(s)."

    parts = [intro, active_sentence]
    if detail_sentence:
        parts.append(detail_sentence)
    if totals_sentence:
        parts.append(totals_sentence)
    return " ".join(parts[:4])


def _annotate_historical_status(findings, archives_enabled: bool, latest_log_records: list[dict], latest_log_path: str | None):
    latest_signature_set = _build_signature_set(analyze_log_records(latest_log_records)) if latest_log_records else set()

    for finding in findings:
        source_files = list(finding.context.get("source_files", []))
        single_source = finding.context.get("source_file")
        if single_source and single_source not in source_files:
            source_files.append(single_source)
        if source_files:
            finding.context["source_files"] = source_files

        signature = _historical_signature(finding)
        seen_in_latest = signature in latest_signature_set or (latest_log_path is not None and latest_log_path in source_files)
        finding.context["seen_in_latest_log"] = seen_in_latest
        if latest_log_path:
            finding.context["latest_log_path"] = latest_log_path

        if source_files:
            finding.context["last_seen_source"] = source_files[0]

        if archives_enabled and source_files and not seen_in_latest and any(path != latest_log_path for path in source_files):
            finding.context["historical_status"] = "resolved"
            if "resolved" not in finding.tags:
                finding.tags.append("resolved")
            if "historical" not in finding.tags:
                finding.tags.append("historical")
            if "This issue appears in older logs but was not seen in the latest log, so it may already be resolved." not in finding.recommendations:
                finding.recommendations.append(
                    "This issue appears in older logs but was not seen in the latest log, so it may already be resolved."
                )
            finding.priority = max(5, finding.priority - 35)
        else:
            finding.context["historical_status"] = "active"

    return sorted(findings, key=lambda finding: (-finding.priority, finding.severity, finding.title))


def _load_archive_records() -> dict:
    records: list[dict] = []
    scanned_files: list[dict] = []
    total_lines = 0

    log_files = list_log_files()[: max(1, settings.max_log_files)]
    latest_log = get_latest_log_path()
    latest_log_str = str(latest_log) if latest_log else None

    for log_file in log_files:
        if latest_log_str and log_file.path == latest_log_str:
            continue

        file_entry = {
            "path": log_file.path,
            "file_type": log_file.file_type,
            "readable": True,
            "read_error": None,
            "line_count": 0,
        }

        try:
            raw_text = read_log_text(log_file.path)
        except Exception as exc:
            file_entry["readable"] = False
            file_entry["read_error"] = str(exc)
            scanned_files.append(file_entry)
            continue

        if not raw_text.strip():
            scanned_files.append(file_entry)
            continue

        lines = raw_text.splitlines()
        if total_lines >= settings.max_log_lines_total:
            break

        remaining = settings.max_log_lines_total - total_lines
        if len(lines) > remaining:
            lines = lines[-remaining:]

        file_entry["line_count"] = len(lines)
        total_lines += len(lines)
        file_records = parse_log_records("\n".join(lines))
        for record in file_records:
            record["log_source_file"] = log_file.path
        records.extend(file_records)
        scanned_files.append(file_entry)

        if total_lines >= settings.max_log_lines_total:
            break

    return {
        "records": records,
        "log_files_scanned": scanned_files,
    }


def _correlate_findings_with_plugins(findings):
    try:
        plugin_result = list_plugins()
        plugin_name_map = {
            plugin.get("name", "").casefold(): plugin.get("name", "")
            for plugin in plugin_result.get("plugins", [])
            if plugin.get("name")
        }
    except Exception:
        plugin_name_map = {}

    plugin_names = set(plugin_name_map.keys())

    for finding in findings:
        component = (finding.suspected_component or "").casefold()
        if component and component in plugin_names:
            if "correlated" not in finding.tags:
                finding.tags.append("correlated")
            if "plugin_inventory" not in finding.tags:
                finding.tags.append("plugin_inventory")
            finding.context["plugin_found_in_inventory"] = True
            if "Plugin is present in current inventory." not in finding.recommendations:
                finding.recommendations.append("Plugin is present in current inventory.")

        if finding.category == "missing_dependency":
            likely_dependency_name = str(finding.context.get("likely_dependency_name", "")).strip()
            likely_dependency_key = likely_dependency_name.casefold()
            likely_dependency_found = bool(likely_dependency_key and likely_dependency_key in plugin_names)
            finding.context["likely_dependency_found_in_inventory"] = likely_dependency_found
            if likely_dependency_found:
                if "dependency_present" not in finding.tags:
                    finding.tags.append("dependency_present")
                inventory_name = plugin_name_map.get(likely_dependency_key, likely_dependency_name)
                if (
                    f"Dependency plugin {inventory_name} is already present in inventory, so this may be a version or compatibility issue."
                    not in finding.recommendations
                ):
                    finding.recommendations.append(
                        f"Dependency plugin {inventory_name} is already present in inventory, so this may be a version or compatibility issue."
                    )

    return findings


def _load_latest_log_records() -> tuple[list[dict], list[dict], dict]:
    latest_log_path = get_latest_log_path()
    if not latest_log_path:
        return [], [], {
            "detected": False,
            "source": None,
            "record_count": 0,
            "item_count": 0,
            "completed": False,
            "message": "No latest.log file was found for startup analysis.",
        }

    try:
        raw_log = read_text_file(latest_log_path)
    except Exception as exc:
        return [], [], {
            "detected": False,
            "source": str(latest_log_path),
            "record_count": 0,
            "item_count": 0,
            "completed": False,
            "message": f"Failed to read latest.log for startup analysis: {exc}",
        }

    if not raw_log.strip():
        return [], [], {
            "detected": False,
            "source": str(latest_log_path),
            "record_count": 0,
            "item_count": 0,
            "completed": False,
            "message": "latest.log was empty.",
        }

    all_records = parse_log_records(raw_log)
    if not all_records:
        return [], [], {
            "detected": False,
            "source": str(latest_log_path),
            "record_count": 0,
            "item_count": 0,
            "completed": False,
            "message": "No log records were parsed from latest.log.",
        }

    done_index = next(
        (index for index, record in enumerate(all_records) if STARTUP_DONE_RE.search(record.get("text", ""))),
        None,
    )

    if done_index is not None:
        selected_records = all_records[: done_index + 1]
        completed = True
        message = "Startup window detected from log start until server reported readiness."
    else:
        selected_records = all_records[: min(len(all_records), 250)]
        completed = False
        message = "Startup completion marker was not found, so startup analysis used the first parsed log records."

    full_records = []
    startup_records = []
    startup_cutoff = len(selected_records)
    for index, record in enumerate(all_records):
        tagged_record = dict(record)
        tagged_record["startup_phase"] = index < startup_cutoff
        tagged_record["log_source_file"] = str(latest_log_path)
        full_records.append(tagged_record)
        if index < startup_cutoff:
            startup_records.append(dict(tagged_record))

    return full_records, startup_records, {
        "detected": True,
        "source": str(latest_log_path),
        "record_count": len(startup_records),
        "item_count": 0,
        "completed": completed,
        "message": message,
    }


def _merge_findings(*finding_lists):
    aggregated: dict[tuple[str, str, str | None, str, int | None], object] = {}

    for finding_list in finding_lists:
        for finding in finding_list:
            first_evidence = finding.evidence[0] if finding.evidence else None
            key = (
                finding.category,
                finding.title,
                finding.suspected_component,
                first_evidence.excerpt if first_evidence else "",
                first_evidence.line_number if first_evidence else None,
            )
            existing = aggregated.get(key)
            if existing is None:
                source_files = []
                source_file = finding.context.get("source_file")
                if source_file:
                    source_files.append(source_file)
                finding.context["occurrence_count"] = 1
                if source_files:
                    finding.context["source_files"] = source_files
                aggregated[key] = finding
                continue

            existing.context["occurrence_count"] = int(existing.context.get("occurrence_count", 1)) + 1
            source_files = list(existing.context.get("source_files", []))
            source_file = finding.context.get("source_file")
            if source_file and source_file not in source_files:
                source_files.append(source_file)
            if source_files:
                existing.context["source_files"] = source_files
            for evidence in finding.evidence:
                if len(existing.evidence) >= 3:
                    break
                if not any(
                    current.excerpt == evidence.excerpt and current.line_number == evidence.line_number
                    for current in existing.evidence
                ):
                    existing.evidence.append(evidence)

    merged = list(aggregated.values())
    return sorted(merged, key=lambda finding: (-finding.priority, finding.severity, finding.title))


def _count_categories(findings) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.category] = counts.get(finding.category, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _historical_signature(finding) -> tuple[str, str, str, str]:
    component = (
        finding.context.get("plugin_name")
        or finding.suspected_component
        or finding.source_name
        or ""
    )
    config_file = finding.context.get("config_file", "")
    key = finding.context.get("key", "")
    first_excerpt = finding.evidence[0].excerpt if finding.evidence else ""
    excerpt_signature = _normalize_excerpt_signature(first_excerpt)
    signature_tail = str(key).casefold() or excerpt_signature or finding.title.casefold()
    return (
        finding.category,
        str(component).casefold(),
        str(config_file).casefold(),
        signature_tail,
    )


def _build_signature_set(findings) -> set[tuple[str, str, str, str]]:
    return {_historical_signature(finding) for finding in findings}


def _normalize_excerpt_signature(text: str) -> str:
    normalized = text.strip().lower()
    normalized = re.sub(r"^\[[^\]]+\]\s+\[[^\]]+\]:\s*", "", normalized)
    normalized = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "uuid", normalized)
    normalized = re.sub(r"\b[0-9a-f]{16,}\b", "id", normalized)
    normalized = re.sub(r"\b\d+\b", "#", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized[:180]
