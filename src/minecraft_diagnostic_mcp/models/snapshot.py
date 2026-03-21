from dataclasses import dataclass
from typing import Optional

from minecraft_diagnostic_mcp.models.diagnostics import DiagnosticGroup, DiagnosticItem


@dataclass
class ContainerStats:
    cpu_percent: Optional[str] = None
    memory_usage: Optional[str] = None
    net_io: Optional[str] = None


@dataclass
class ServerStatus:
    execution_mode: str
    container_name: str
    container_status: str
    rcon_responsive: bool
    players_online_raw: Optional[str] = None
    runtime_readiness: dict | None = None
    backup_readiness: dict | None = None


@dataclass
class ServerSnapshot:
    status: ServerStatus
    stats: ContainerStats
    plugin_summary: dict
    config_summary: dict
    log_summary: dict
    diagnostics: list[DiagnosticItem]
    problem_groups: list[DiagnosticGroup]
    summary: str
