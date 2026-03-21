from dataclasses import dataclass
from typing import Optional

from minecraft_diagnostic_mcp.models.diagnostics import DiagnosticItem


@dataclass
class ConfigFileInfo:
    path: str
    exists: bool
    parsed: bool
    kind: str
    parse_error: Optional[str] = None


ConfigIssue = DiagnosticItem
