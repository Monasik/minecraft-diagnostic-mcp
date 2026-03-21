from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PluginCommandInfo:
    name: str
    description: Optional[str] = None
    usage: Optional[str] = None
    permission: Optional[str] = None
    aliases: list[str] = field(default_factory=list)


@dataclass
class PluginInfo:
    name: str
    path: str
    manifest_name: Optional[str] = None
    version: Optional[str] = None
    main: Optional[str] = None
    depend: list[str] = field(default_factory=list)
    softdepend: list[str] = field(default_factory=list)
    loadbefore: list[str] = field(default_factory=list)
    commands: list[PluginCommandInfo] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    description: Optional[str] = None
    website: Optional[str] = None
    authors: list[str] = field(default_factory=list)
    manifest_found: bool = False
    read_error: Optional[str] = None
