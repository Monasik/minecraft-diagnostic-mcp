from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from minecraft_diagnostic_mcp.models.diagnostics import DiagnosticEvidence, DiagnosticItem


@dataclass
class LogFileInfo:
    path: str
    file_type: str
    readable: bool
    read_error: Optional[str] = None
    line_count: int = 0
    modified_time: Optional[datetime] = None


Evidence = DiagnosticEvidence
Finding = DiagnosticItem
