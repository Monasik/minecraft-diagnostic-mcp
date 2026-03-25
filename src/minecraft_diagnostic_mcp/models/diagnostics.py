from dataclasses import dataclass, field
from typing import Any, Optional

from minecraft_diagnostic_mcp.models.context import normalize_context


VALID_SEVERITIES = {"info", "warning", "error", "critical"}
SEVERITY_WEIGHTS = {"info": 10, "warning": 40, "error": 70, "critical": 90}
CATEGORY_BONUS = {
    "plugin_startup": 12,
    "missing_dependency": 12,
    "startup_security_warning": 12,
    "plugin_compatibility_warning": 8,
    "startup_warning": 4,
    "rcon_configuration": 10,
    "security_configuration": 8,
    "parse_error": 8,
    "performance_warning": 2,
    "manifest_missing": 8,
    "plugin_manifest_error": 10,
    "data_integrity_error": 11,
    "archive_access_error": 8,
    "event_dispatch_failure": 7,
    "invalid_config": 6,
    "monitoring_warning": 1,
    "operational_movement_warning": 0,
    "exception": 6,
    "exception_chain": 4,
    "log_error": 3,
    "log_warning": 1,
}


@dataclass
class DiagnosticEvidence:
    excerpt: str
    source: str
    line_number: Optional[int] = None


@dataclass
class DiagnosticItem:
    severity: str
    category: str
    source_type: str
    source_name: str
    title: str
    summary: str
    suspected_component: Optional[str] = None
    evidence: list[DiagnosticEvidence] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 0

    def __post_init__(self) -> None:
        self.severity = normalize_severity(self.severity)
        self.context = normalize_context(self.category, self.context)
        self.priority = compute_priority(self.severity, self.category, self.tags, self.priority)


@dataclass
class DiagnosticSummary:
    item_count: int = 0
    info_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    critical_count: int = 0
    message: str = ""


@dataclass
class DiagnosticGroup:
    id: str
    title: str
    severity: str
    suspected_component: Optional[str]
    primary_item: DiagnosticItem
    related_items: list[DiagnosticItem] = field(default_factory=list)
    summary: str = ""
    explanation: str = ""
    recommended_action: str = ""
    recommendations: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        category = self.primary_item.category if self.primary_item else "general"
        self.context = normalize_context(category, self.context)


def normalize_severity(value: str) -> str:
    normalized = (value or "info").strip().lower()
    if normalized not in VALID_SEVERITIES:
        return "info"
    return normalized


def compute_priority(severity: str, category: str, tags: list[str], explicit_priority: int = 0) -> int:
    if explicit_priority:
        return explicit_priority

    priority = SEVERITY_WEIGHTS.get(normalize_severity(severity), 10)
    priority += CATEGORY_BONUS.get(category, 0)

    lowered_tags = {tag.lower() for tag in tags}
    if "startup" in lowered_tags:
        priority += 4
    if "dependency" in lowered_tags:
        priority += 4
    if "rcon" in lowered_tags or "network" in lowered_tags:
        priority += 3

    return min(priority, 100)


def diagnostic_sort_key(item: dict | DiagnosticItem) -> tuple[int, str, str]:
    if isinstance(item, DiagnosticItem):
        return (-item.priority, item.severity, item.title)

    priority = int(item.get("priority", 0))
    severity = str(item.get("severity", "info"))
    title = str(item.get("title", ""))
    return (-priority, severity, title)


def group_sort_key(group: dict | DiagnosticGroup) -> tuple[int, str, str]:
    if isinstance(group, DiagnosticGroup):
        return (-group.primary_item.priority, group.severity, group.title)

    primary_item = group.get("primary_item", {})
    priority = int(primary_item.get("priority", group.get("priority", 0)))
    severity = str(group.get("severity", "info"))
    title = str(group.get("title", ""))
    return (-priority, severity, title)
