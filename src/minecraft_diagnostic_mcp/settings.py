import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    container_name: str
    default_log_lines: int
    subprocess_timeout_seconds: int
    analysis_mode: str
    runtime_backend: str
    server_root: str
    plugins_dir: str
    logs_dir: str
    local_server_jar: str
    local_rcon_host: str
    local_rcon_port: int
    local_rcon_password: str
    config_targets: tuple[tuple[str, tuple[str, ...]], ...]

    def iter_config_targets(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        return self.config_targets


def _read_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


settings = Settings(
    container_name=os.getenv("MCP_CONTAINER_NAME", "mc"),
    default_log_lines=_read_int_env("MCP_DEFAULT_LOG_LINES", 10),
    subprocess_timeout_seconds=_read_int_env("MCP_SUBPROCESS_TIMEOUT_SECONDS", 30),
    analysis_mode=os.getenv("MCP_ANALYSIS_MODE", "runtime").strip().lower() or "runtime",
    runtime_backend=os.getenv("MCP_RUNTIME_BACKEND", "docker").strip().lower() or "docker",
    server_root=os.getenv("MCP_SERVER_ROOT", "."),
    plugins_dir=os.getenv("MCP_PLUGINS_DIR", "plugins"),
    logs_dir=os.getenv("MCP_LOGS_DIR", "logs"),
    local_server_jar=os.getenv("MCP_LOCAL_SERVER_JAR", "purpur.jar"),
    local_rcon_host=os.getenv("MCP_LOCAL_RCON_HOST", "127.0.0.1"),
    local_rcon_port=_read_int_env("MCP_LOCAL_RCON_PORT", 25575),
    local_rcon_password=os.getenv("MCP_LOCAL_RCON_PASSWORD", ""),
    config_targets=(
        ("server.properties", ("server.properties",)),
        ("bukkit.yml", ("bukkit.yml",)),
        ("spigot.yml", ("spigot.yml",)),
        ("paper.yml", ("paper.yml",)),
        ("paper-global.yml", ("paper-global.yml", "config/paper-global.yml")),
        ("purpur.yml", ("purpur.yml", "config/purpur.yml")),
    ),
)
