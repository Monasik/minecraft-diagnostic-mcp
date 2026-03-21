from pathlib import Path
import zipfile

from minecraft_diagnostic_mcp.settings import settings


def get_server_root() -> Path:
    return Path(settings.server_root)


def _resolve_path(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return get_server_root() / path


def get_plugins_dir() -> Path:
    return _resolve_path(settings.plugins_dir)


def get_logs_dir() -> Path:
    return _resolve_path(settings.logs_dir)


def get_config_path(relative_path: str) -> Path:
    return _resolve_path(relative_path)


def find_existing_config_path(candidates: tuple[str, ...]) -> Path | None:
    for candidate in candidates:
        config_path = get_config_path(candidate)
        if config_path.exists() and config_path.is_file():
            return config_path
    return None


def plugins_dir_exists() -> bool:
    plugins_dir = get_plugins_dir()
    return plugins_dir.exists() and plugins_dir.is_dir()


def list_plugin_jars() -> list[Path]:
    if not plugins_dir_exists():
        return []

    return sorted(
        path for path in get_plugins_dir().iterdir()
        if path.is_file() and path.suffix.lower() == ".jar"
    )


def read_jar_entry(jar_path: Path, entry_name: str) -> bytes:
    with zipfile.ZipFile(jar_path, "r") as jar_file:
        return jar_file.read(entry_name)


def config_file_exists(relative_path: str) -> bool:
    config_path = get_config_path(relative_path)
    return config_path.exists() and config_path.is_file()


def read_text_file(path_like: str | Path) -> str:
    return _resolve_path(path_like).read_text(encoding="utf-8", errors="replace")


def get_latest_log_path() -> Path | None:
    logs_dir = get_logs_dir()
    latest_log = logs_dir / "latest.log"
    if latest_log.exists() and latest_log.is_file():
        return latest_log
    return None


def get_backup_readiness() -> dict:
    latest_log_path = get_latest_log_path()
    plugins_dir = get_plugins_dir()
    return {
        "server_root": str(get_server_root()),
        "plugins_dir": str(plugins_dir),
        "plugins_available": plugins_dir_exists(),
        "logs_available": latest_log_path is not None,
        "latest_log_path": str(latest_log_path) if latest_log_path else None,
    }
