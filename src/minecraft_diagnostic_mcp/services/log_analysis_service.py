import re

from minecraft_diagnostic_mcp.collectors.filesystem_collector import get_latest_log_path, read_text_file
from minecraft_diagnostic_mcp.models.diagnostics import DiagnosticSummary
from minecraft_diagnostic_mcp.analyzers.log_analyzer import analyze_log_records, serialize_findings
from minecraft_diagnostic_mcp.collectors.docker_collector import get_recent_logs
from minecraft_diagnostic_mcp.parsers.log_parser import parse_log_records
from minecraft_diagnostic_mcp.services.plugin_service import list_plugins


STARTUP_DONE_RE = re.compile(r'for help,\s*type\s+"help"', re.IGNORECASE)


def analyze_recent_logs(lines: int = 200) -> dict:
    safe_lines = max(1, int(lines))

    try:
        raw_logs = get_recent_logs(safe_lines)
    except Exception as exc:
        return {
            "scanned_lines": safe_lines,
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

    if not raw_logs.strip():
        return {
            "scanned_lines": safe_lines,
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

    records = parse_log_records(raw_logs)
    startup_records, startup_window = _load_startup_records()

    findings = analyze_log_records(records)
    startup_findings = analyze_log_records(startup_records)
    startup_window["item_count"] = len(startup_findings)
    findings = _merge_findings(findings, startup_findings)
    findings = _correlate_findings_with_plugins(findings)
    summary = DiagnosticSummary(
        item_count=len(findings),
        info_count=sum(1 for finding in findings if finding.severity == "info"),
        warning_count=sum(1 for finding in findings if finding.severity == "warning"),
        error_count=sum(1 for finding in findings if finding.severity == "error"),
        critical_count=sum(1 for finding in findings if finding.severity == "critical"),
        message="Recent log analysis completed successfully.",
    )

    return {
        "scanned_lines": safe_lines,
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


def _correlate_findings_with_plugins(findings):
    try:
        plugin_result = list_plugins()
        plugin_names = {
            plugin.get("name", "").casefold()
            for plugin in plugin_result.get("plugins", [])
            if plugin.get("name")
        }
    except Exception:
        plugin_names = set()

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

    return findings


def _load_startup_records() -> tuple[list[dict], dict]:
    latest_log_path = get_latest_log_path()
    if not latest_log_path:
        return [], {
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
        return [], {
            "detected": False,
            "source": str(latest_log_path),
            "record_count": 0,
            "item_count": 0,
            "completed": False,
            "message": f"Failed to read latest.log for startup analysis: {exc}",
        }

    if not raw_log.strip():
        return [], {
            "detected": False,
            "source": str(latest_log_path),
            "record_count": 0,
            "item_count": 0,
            "completed": False,
            "message": "latest.log was empty.",
        }

    all_records = parse_log_records(raw_log)
    if not all_records:
        return [], {
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

    startup_records = []
    for record in selected_records:
        startup_record = dict(record)
        startup_record["startup_phase"] = True
        startup_records.append(startup_record)

    return startup_records, {
        "detected": True,
        "source": str(latest_log_path),
        "record_count": len(startup_records),
        "item_count": 0,
        "completed": completed,
        "message": message,
    }


def _merge_findings(*finding_lists):
    merged = []
    seen: set[tuple[str, str, str | None, str, int | None]] = set()

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
            if key in seen:
                continue
            seen.add(key)
            merged.append(finding)

    return sorted(merged, key=lambda finding: (-finding.priority, finding.severity, finding.title))


def _count_categories(findings) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.category] = counts.get(finding.category, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
