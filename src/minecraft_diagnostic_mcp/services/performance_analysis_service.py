from __future__ import annotations

from collections import Counter
from typing import Any

from minecraft_diagnostic_mcp.collectors.docker_collector import get_server_stats, resolve_execution_mode
from minecraft_diagnostic_mcp.services.log_analysis_service import analyze_recent_logs


PERFORMANCE_CATEGORIES = {
    "performance_warning",
    "operational_movement_warning",
    "monitoring_warning",
}


def analyze_performance(include_archives: bool = True, lines: int = 2000) -> dict[str, Any]:
    log_result = analyze_recent_logs(lines, include_archives=include_archives, compact=False)
    diagnostics = log_result.get("diagnostics", [])
    performance_items = [item for item in diagnostics if str(item.get("category", "")) in PERFORMANCE_CATEGORIES]
    category_counts = Counter(str(item.get("category", "general")) for item in performance_items)
    component_counts = Counter(
        str(item.get("suspected_component") or item.get("source_name") or "server")
        for item in performance_items
    )
    lag_sources = [
        item for item in performance_items
        if str(item.get("category", "")) == "performance_warning"
    ]
    top_patterns = _extract_top_patterns(log_result)
    runtime_stats = _collect_runtime_stats()

    recommendations = []
    if category_counts.get("performance_warning", 0):
        recommendations.append("Inspect lag spikes, chunk loading, and heavy plugin tasks if performance warnings keep repeating.")
    if category_counts.get("operational_movement_warning", 0) > 10:
        recommendations.append("Repeated movement warnings can indicate rubber-banding, lag, or strict movement checks.")
    if category_counts.get("monitoring_warning", 0):
        recommendations.append("Review profiler or monitoring tool output only if it was not intentionally triggered.")

    summary = (
        f"Analyzed {len(diagnostics)} log diagnostic item(s) and found "
        f"{category_counts.get('performance_warning', 0)} lag warning(s), "
        f"{category_counts.get('operational_movement_warning', 0)} movement warning(s), and "
        f"{category_counts.get('monitoring_warning', 0)} monitoring warning(s)."
    )

    return {
        "execution_mode": resolve_execution_mode(),
        "runtime_stats": runtime_stats,
        "total_diagnostics": len(diagnostics),
        "performance_item_count": len(performance_items),
        "category_counts": dict(category_counts),
        "top_components": [{"component": name, "count": count} for name, count in component_counts.most_common(10)],
        "lag_signals": lag_sources[:20],
        "top_patterns": top_patterns,
        "recommendations": recommendations,
        "summary": summary,
    }


def _collect_runtime_stats() -> dict[str, Any]:
    try:
        raw_stats = get_server_stats()
    except Exception as exc:
        return {"available": False, "message": str(exc)}

    parts = raw_stats.split("\t")
    return {
        "available": True,
        "cpu_percent": parts[0].strip() if len(parts) > 0 else None,
        "memory_usage": parts[1].strip() if len(parts) > 1 else None,
        "net_io": parts[2].strip() if len(parts) > 2 else None,
    }


def _extract_top_patterns(log_result: dict[str, Any]) -> list[dict[str, Any]]:
    compact = analyze_recent_logs(
        int(log_result.get("scanned_lines", 2000)),
        include_archives=bool(log_result.get("archives_included", False)),
        compact=True,
    )
    compact_summary = compact.get("compact_summary", {})
    repeated_patterns = compact_summary.get("repeated_patterns", [])
    return [
        item for item in repeated_patterns
        if str(item.get("category", "")) in PERFORMANCE_CATEGORIES
    ][:10]
