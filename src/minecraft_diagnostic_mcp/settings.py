import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    transport: str
    http_host: str
    http_port: int
    http_path: str
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
    max_log_files: int
    max_log_lines_total: int
    discord_alerts_enabled: bool
    discord_webhook_url: str
    discord_alert_username: str
    discord_alert_poll_seconds: int
    discord_alert_scan_lines: int
    discord_alert_min_priority: int
    discord_alert_state_file: str
    config_targets: tuple[tuple[str, tuple[str, ...]], ...]

    def iter_config_targets(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        return self.config_targets


def _read_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _read_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


settings = Settings(
    transport=os.getenv("MCP_TRANSPORT", "stdio").strip().lower() or "stdio",
    http_host=os.getenv("MCP_HTTP_HOST", "127.0.0.1"),
    http_port=_read_int_env("MCP_HTTP_PORT", 8000),
    http_path=os.getenv("MCP_HTTP_PATH", "/mcp").strip() or "/mcp",
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
    max_log_files=_read_int_env("MCP_MAX_LOG_FILES", 20),
    max_log_lines_total=_read_int_env("MCP_MAX_LOG_LINES_TOTAL", 50000),
    discord_alerts_enabled=_read_bool_env("MCP_DISCORD_ALERTS_ENABLED", False),
    discord_webhook_url=os.getenv("MCP_DISCORD_WEBHOOK_URL", "").strip(),
    discord_alert_username=os.getenv("MCP_DISCORD_ALERT_USERNAME", "Minecraft Diagnostic MCP").strip() or "Minecraft Diagnostic MCP",
    discord_alert_poll_seconds=_read_int_env("MCP_DISCORD_ALERT_POLL_SECONDS", 30),
    discord_alert_scan_lines=_read_int_env("MCP_DISCORD_ALERT_SCAN_LINES", 400),
    discord_alert_min_priority=_read_int_env("MCP_DISCORD_ALERT_MIN_PRIORITY", 50),
    discord_alert_state_file=os.getenv("MCP_DISCORD_ALERT_STATE_FILE", "").strip(),
    config_targets=(
        ("server.properties", ("server.properties",)),
        ("bukkit.yml", ("bukkit.yml",)),
        ("spigot.yml", ("spigot.yml",)),
        ("paper.yml", ("paper.yml",)),
        ("paper-global.yml", ("paper-global.yml", "config/paper-global.yml")),
        ("purpur.yml", ("purpur.yml", "config/purpur.yml")),
    ),
)
