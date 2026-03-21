import subprocess
from pathlib import Path

from minecraft_diagnostic_mcp.collectors.filesystem_collector import get_latest_log_path, read_text_file
from minecraft_diagnostic_mcp.settings import settings


def resolve_execution_mode() -> str:
    configured_mode = settings.analysis_mode
    if configured_mode in {"backup", "runtime"}:
        return configured_mode

    if is_docker_available() and container_exists(settings.container_name):
        return "runtime"

    if get_latest_log_path():
        return "backup"

    return "runtime"


def get_runtime_backend() -> str:
    backend = settings.runtime_backend
    return backend if backend in {"docker", "local"} else "docker"


def is_docker_available() -> bool:
    try:
        _run_docker_command(["docker", "version", "--format", "{{.Server.Version}}"])
        return True
    except Exception:
        return False


def container_exists(container_name: str | None = None) -> bool:
    if not is_docker_available():
        return False

    target = container_name or settings.container_name
    try:
        _run_docker_command(["docker", "inspect", target])
        return True
    except Exception:
        return False


def get_runtime_readiness() -> dict:
    mode = resolve_execution_mode()
    backend = get_runtime_backend()
    if mode == "runtime" and backend == "local":
        process_info = get_local_process_info()
        return {
            "execution_mode": mode,
            "runtime_backend": backend,
            "docker_available": False,
            "container_exists": False,
            "container_status": "running" if process_info else "stopped",
            "logs_available": bool(get_latest_log_path()),
            "local_process_running": bool(process_info),
            "local_process_id": process_info.get("process_id") if process_info else None,
        }

    docker_available = is_docker_available()
    exists = container_exists(settings.container_name) if docker_available else False
    status = None

    if mode == "runtime" and docker_available and exists:
        try:
            status = _run_docker_command(
                ["docker", "inspect", "-f", "{{.State.Status}}", settings.container_name]
            ).strip()
        except Exception:
            status = None
    elif mode == "backup":
        status = "backup"

    return {
        "execution_mode": mode,
        "runtime_backend": backend,
        "docker_available": docker_available,
        "container_exists": exists,
        "container_status": status,
        "logs_available": bool(get_latest_log_path()),
    }


def get_server_stats() -> str:
    mode = resolve_execution_mode()
    if mode == "backup":
        return ""

    if get_runtime_backend() == "local":
        return _get_local_server_stats()

    if not is_docker_available():
        raise RuntimeError("Docker CLI is not available.")

    if not container_exists(settings.container_name):
        raise RuntimeError(f"Docker container '{settings.container_name}' was not found.")

    return _run_docker_command(
        [
            "docker",
            "stats",
            settings.container_name,
            "--no-stream",
            "--format",
            "{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}",
        ]
    ).strip()


def get_recent_logs(lines: int, since: str | None = None) -> str:
    mode = resolve_execution_mode()
    if mode == "backup" or get_runtime_backend() == "local":
        return _read_recent_log_file(lines)

    command = ["docker", "logs", "--tail", str(lines)]
    if since:
        command.extend(["--since", since])
    command.append(settings.container_name)

    try:
        if not is_docker_available():
            raise RuntimeError("Docker CLI is not available.")
        if not container_exists(settings.container_name):
            raise RuntimeError(f"Docker container '{settings.container_name}' was not found.")
        return _run_docker_command(command)
    except Exception:
        if settings.analysis_mode == "auto" and get_latest_log_path():
            return _read_recent_log_file(lines)
        raise


def get_container_status() -> str:
    mode = resolve_execution_mode()
    if mode == "backup":
        return "backup"

    if get_runtime_backend() == "local":
        return "running" if get_local_process_info() else "stopped"

    if not is_docker_available():
        raise RuntimeError("Docker CLI is not available.")
    if not container_exists(settings.container_name):
        raise RuntimeError(f"Docker container '{settings.container_name}' was not found.")

    try:
        return _run_docker_command(
            ["docker", "inspect", "-f", "{{.State.Status}}", settings.container_name]
        ).strip()
    except Exception:
        if settings.analysis_mode == "auto" and get_latest_log_path():
            return "backup"
        raise


def _read_recent_log_file(lines: int) -> str:
    latest_log_path = get_latest_log_path()
    if not latest_log_path:
        raise FileNotFoundError("No latest.log file was found for backup log analysis.")

    content = read_text_file(latest_log_path)
    log_lines = content.splitlines()
    return "\n".join(log_lines[-max(1, int(lines)):])


def _run_docker_command(command: list[str]) -> str:
    return subprocess.check_output(
        command,
        timeout=settings.subprocess_timeout_seconds,
    ).decode("utf-8", errors="replace")


def get_local_process_info() -> dict | None:
    server_root = str(Path(settings.server_root).resolve())
    jar_name = settings.local_server_jar
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -like 'java*' -and $_.CommandLine -like '*"
        + server_root.replace("'", "''")
        + "*"
        + jar_name.replace("'", "''")
        + "*' } | "
        "Select-Object -First 1 ProcessId,CommandLine,CreationDate,WorkingSetSize"
    )
    try:
        result = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            timeout=settings.subprocess_timeout_seconds,
        ).decode("utf-8", errors="replace").strip()
    except Exception:
        return None

    process_id = None
    working_set = None
    if result:
        for line in result.splitlines():
            if ":" not in line:
                continue
            key, value = [part.strip() for part in line.split(":", 1)]
            if key == "ProcessId":
                try:
                    process_id = int(value)
                except ValueError:
                    process_id = None
            elif key == "WorkingSetSize":
                try:
                    working_set = int(value)
                except ValueError:
                    working_set = None

    if not process_id:
        process_id = _get_listener_process_id(settings.local_rcon_port)
        if not process_id:
            return None
        working_set = _get_process_working_set(process_id)

    return {
        "process_id": process_id,
        "working_set_size": working_set,
        "raw": result,
    }


def _get_local_server_stats() -> str:
    process_info = get_local_process_info()
    if not process_info:
        raise RuntimeError("Local server process was not found.")

    working_set = process_info.get("working_set_size")
    memory_usage = _format_bytes(working_set) if working_set else "unknown"
    return f"N/A\t{memory_usage}\tN/A"


def _format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024.0 or unit == "TiB":
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}B"
        size /= 1024.0
    return f"{int(value)}B"


def _get_listener_process_id(port: int) -> int | None:
    script = (
        f"Get-NetTCPConnection -State Listen -LocalPort {int(port)} -ErrorAction SilentlyContinue | "
        "Select-Object -First 1 OwningProcess"
    )
    try:
        result = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            timeout=settings.subprocess_timeout_seconds,
        ).decode("utf-8", errors="replace").strip()
    except Exception:
        return None

    for line in result.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
        if ":" in line:
            _, value = [part.strip() for part in line.split(":", 1)]
            if value.isdigit():
                return int(value)
    return None


def _get_process_working_set(process_id: int) -> int | None:
    script = f"Get-Process -Id {int(process_id)} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty WorkingSet64"
    try:
        result = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            timeout=settings.subprocess_timeout_seconds,
        ).decode("utf-8", errors="replace").strip()
    except Exception:
        return None

    try:
        return int(result)
    except ValueError:
        return None
