import subprocess
from pathlib import Path
from datetime import datetime, timezone

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
    checked_at = datetime.now(timezone.utc).isoformat()
    if mode == "runtime" and backend == "local":
        process_info = get_local_process_info()
        is_running = bool(process_info)
        logs_available = bool(get_latest_log_path())
        return {
            "execution_mode": mode,
            "runtime_backend": backend,
            "docker_available": False,
            "container_exists": False,
            "container_status": "running" if process_info else "stopped",
            "logs_available": logs_available,
            "local_process_running": is_running,
            "local_process_id": process_info.get("process_id") if process_info else None,
            "checked_at": checked_at,
            "readiness_reason": "process_found" if is_running else "local_process_missing",
            "ready": is_running,
            "message": (
                "Local runtime backend is ready."
                if is_running
                else "Local runtime backend is selected but no matching local Java server process was found."
            ),
        }

    docker_available = is_docker_available()
    exists = container_exists(settings.container_name) if docker_available else False
    status = None
    logs_available = bool(get_latest_log_path())

    if mode == "runtime" and docker_available and exists:
        try:
            status = _run_docker_command(
                ["docker", "inspect", "-f", "{{.State.Status}}", settings.container_name]
            ).strip()
        except Exception:
            status = None
    elif mode == "backup":
        status = "backup"

    ready = mode == "backup" or (docker_available and exists and bool(status))
    message = _runtime_readiness_message(
        mode=mode,
        backend=backend,
        docker_available=docker_available,
        container_exists=exists,
        container_status=status,
        logs_available=logs_available,
    )

    return {
        "execution_mode": mode,
        "runtime_backend": backend,
        "docker_available": docker_available,
        "container_exists": exists,
        "container_status": status,
        "logs_available": logs_available,
        "local_process_running": False,
        "local_process_id": None,
        "checked_at": checked_at,
        "readiness_reason": _runtime_readiness_reason(
            mode=mode,
            docker_available=docker_available,
            container_exists=exists,
            container_status=status,
            logs_available=logs_available,
        ),
        "ready": ready,
        "message": message,
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
    primary_script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -like 'java*' -and $_.CommandLine -like '*"
        + server_root.replace("'", "''")
        + "*"
        + jar_name.replace("'", "''")
        + "*' } | "
        "Select-Object -First 1 ProcessId,CommandLine,CreationDate,WorkingSetSize"
    )
    fallback_script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -like 'java*' -and $_.CommandLine -like '*"
        + jar_name.replace("'", "''")
        + "*' } | "
        "Select-Object -First 1 ProcessId,CommandLine,CreationDate,WorkingSetSize"
    )
    result = _run_powershell_script(primary_script)
    if not result:
        result = _run_powershell_script(fallback_script)

    process_id = _extract_process_value(result, "ProcessId")
    working_set = _extract_process_value(result, "WorkingSetSize")

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


def _run_powershell_script(script: str) -> str:
    try:
        return subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            timeout=settings.subprocess_timeout_seconds,
        ).decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _extract_process_value(result: str, field_name: str) -> int | None:
    if not result:
        return None
    for line in result.splitlines():
        if ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        if key != field_name:
            continue
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _get_local_server_stats() -> str:
    process_info = get_local_process_info()
    if not process_info:
        raise RuntimeError("Local server process was not found.")

    perf_info = _get_local_performance_info(process_info["process_id"])
    cpu_percent = _format_percent(perf_info.get("cpu_percent")) if perf_info.get("cpu_percent") is not None else "N/A"
    working_set = perf_info.get("working_set_size") or process_info.get("working_set_size")
    memory_usage = _format_bytes(working_set) if working_set else "unknown"
    net_io = _format_io_rate(
        perf_info.get("io_read_bytes_persec"),
        perf_info.get("io_write_bytes_persec"),
    )
    return f"{cpu_percent}\t{memory_usage}\t{net_io}"


def _format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024.0 or unit == "TiB":
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}B"
        size /= 1024.0
    return f"{int(value)}B"


def _format_percent(value: float | int | None) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.1f}%"


def _format_io_rate(read_bytes: int | None, write_bytes: int | None) -> str:
    if read_bytes is None and write_bytes is None:
        return "N/A"
    return f"{_format_bytes(read_bytes or 0)}/s / {_format_bytes(write_bytes or 0)}/s"


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


def _get_local_performance_info(process_id: int) -> dict:
    script = (
        f"Get-CimInstance Win32_PerfFormattedData_PerfProc_Process | "
        f"Where-Object {{ $_.IDProcess -eq {int(process_id)} }} | "
        "Select-Object -First 1 PercentProcessorTime,WorkingSetPrivate,IOReadBytesPersec,IOWriteBytesPersec"
    )
    try:
        result = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            timeout=settings.subprocess_timeout_seconds,
        ).decode("utf-8", errors="replace").strip()
    except Exception:
        return {}

    info: dict[str, int | float] = {}
    key_map = {
        "PercentProcessorTime": "cpu_percent",
        "WorkingSetPrivate": "working_set_size",
        "IOReadBytesPersec": "io_read_bytes_persec",
        "IOWriteBytesPersec": "io_write_bytes_persec",
    }
    for line in result.splitlines():
        if ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        mapped_key = key_map.get(key)
        if not mapped_key:
            continue
        try:
            info[mapped_key] = float(value) if mapped_key == "cpu_percent" else int(value)
        except ValueError:
            continue
    return info


def _runtime_readiness_message(
    mode: str,
    backend: str,
    docker_available: bool,
    container_exists: bool,
    container_status: str | None,
    logs_available: bool,
) -> str:
    if mode == "backup":
        if logs_available:
            return "Runtime mode is not active; backup analysis mode is using filesystem inputs."
        return "Runtime mode is not active; backup analysis mode is selected but no log inputs were found."

    if backend != "docker":
        return "Runtime backend status is managed by the local runtime branch."

    if not docker_available:
        return "Docker runtime backend is selected but Docker CLI is not available."
    if not container_exists:
        return f"Docker runtime backend is selected but container '{settings.container_name}' was not found."
    if not container_status:
        return f"Docker runtime backend found container '{settings.container_name}', but its status could not be determined."
    if container_status != "running":
        return f"Docker container '{settings.container_name}' is present but currently '{container_status}'."
    return f"Docker runtime backend is ready and container '{settings.container_name}' is running."


def _runtime_readiness_reason(
    mode: str,
    docker_available: bool,
    container_exists: bool,
    container_status: str | None,
    logs_available: bool,
) -> str:
    if mode == "backup":
        return "backup_inputs_found" if logs_available else "backup_inputs_missing"
    if not docker_available:
        return "docker_cli_missing"
    if not container_exists:
        return "container_missing"
    if not container_status:
        return "container_status_unknown"
    if container_status != "running":
        return "container_not_running"
    return "runtime_ready"
