from __future__ import annotations

from collections import defaultdict
from typing import Any

from minecraft_diagnostic_mcp.services.log_analysis_service import analyze_recent_logs
from minecraft_diagnostic_mcp.services.plugin_service import list_plugins


def analyze_dependency_graph(include_log_signals: bool = True) -> dict[str, Any]:
    plugin_result = list_plugins()
    plugins = plugin_result.get("plugins", [])
    installed_names = {str(plugin.get("name", "")).casefold() for plugin in plugins}

    nodes = []
    edges = []
    blocked_plugins = []
    reverse_edges: dict[str, list[str]] = defaultdict(list)

    for plugin in plugins:
        name = str(plugin.get("name", "unknown"))
        hard_dependencies = [str(item) for item in plugin.get("depend", [])]
        soft_dependencies = [str(item) for item in plugin.get("softdepend", [])]
        loadbefore = [str(item) for item in plugin.get("loadbefore", [])]
        missing_hard = [item for item in hard_dependencies if item.casefold() not in installed_names]

        for dependency in hard_dependencies:
            edges.append(
                {
                    "source": name,
                    "target": dependency,
                    "type": "hard",
                    "status": "installed" if dependency.casefold() in installed_names else "missing",
                }
            )
            reverse_edges[dependency.casefold()].append(name)
        for dependency in soft_dependencies:
            edges.append(
                {
                    "source": name,
                    "target": dependency,
                    "type": "soft",
                    "status": "installed" if dependency.casefold() in installed_names else "missing",
                }
            )
            reverse_edges[dependency.casefold()].append(name)
        for dependency in loadbefore:
            edges.append(
                {
                    "source": name,
                    "target": dependency,
                    "type": "loadbefore",
                    "status": "hint",
                }
            )

        if missing_hard:
            blocked_plugins.append(
                {
                    "plugin": name,
                    "missing_dependencies": missing_hard,
                }
            )

        nodes.append(
            {
                "name": name,
                "version": plugin.get("version"),
                "manifest_name": plugin.get("manifest_name"),
                "hard_dependencies": hard_dependencies,
                "soft_dependencies": soft_dependencies,
                "loadbefore": loadbefore,
                "missing_hard_dependencies": missing_hard,
                "dependent_count": len(reverse_edges.get(name.casefold(), [])),
            }
        )

    cycles = _detect_cycles(edges, installed_names)
    log_signals = _collect_log_signals() if include_log_signals else []
    node_map = {node["name"].casefold(): node for node in nodes}
    for signal in log_signals:
        component = str(signal.get("suspected_component") or signal.get("source_name") or "").casefold()
        if component and component in node_map:
            node_map[component].setdefault("active_log_signals", []).append(signal.get("title"))

    summary = _build_summary(len(nodes), blocked_plugins, cycles, log_signals)

    return {
        "plugin_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "blocked_plugins": blocked_plugins,
        "cycles": cycles,
        "log_signals": log_signals[:20],
        "summary": summary,
    }


def _detect_cycles(edges: list[dict[str, Any]], installed_names: set[str]) -> list[list[str]]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    canonical_names: dict[str, str] = {}
    for edge in edges:
        if edge.get("type") not in {"hard", "soft"}:
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        source_key = source.casefold()
        target_key = target.casefold()
        if source_key in installed_names and target_key in installed_names:
            adjacency[source_key].append(target_key)
            canonical_names.setdefault(source_key, source)
            canonical_names.setdefault(target_key, target)

    cycles: list[list[str]] = []
    visited: set[str] = set()
    stack: list[str] = []
    stack_set: set[str] = set()

    def dfs(node: str) -> None:
        visited.add(node)
        stack.append(node)
        stack_set.add(node)
        for neighbor in adjacency.get(node, []):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in stack_set:
                cycle = stack[stack.index(neighbor):] + [neighbor]
                resolved = [canonical_names.get(item, item) for item in cycle]
                if resolved not in cycles:
                    cycles.append(resolved)
        stack.pop()
        stack_set.discard(node)

    for node in adjacency:
        if node not in visited:
            dfs(node)

    return cycles


def _collect_log_signals() -> list[dict[str, Any]]:
    result = analyze_recent_logs(800, include_archives=False, compact=False)
    diagnostics = result.get("diagnostics", [])
    return [
        item for item in diagnostics
        if str(item.get("category", "")) in {"plugin_startup", "missing_dependency", "plugin_compatibility_warning"}
    ]


def _build_summary(
    node_count: int,
    blocked_plugins: list[dict[str, Any]],
    cycles: list[list[str]],
    log_signals: list[dict[str, Any]],
) -> str:
    parts = [f"Dependency graph contains {node_count} plugin node(s)."]
    if blocked_plugins:
        parts.append(f"{len(blocked_plugins)} plugin(s) are blocked by missing hard dependencies.")
    if cycles:
        parts.append(f"{len(cycles)} dependency cycle(s) were detected.")
    if log_signals:
        parts.append(f"{len(log_signals)} plugin-related log signal(s) were correlated into the graph.")
    return " ".join(parts)
