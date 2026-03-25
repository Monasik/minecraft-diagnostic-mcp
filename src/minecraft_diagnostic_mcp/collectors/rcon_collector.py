import socket
import struct
import subprocess
from datetime import datetime, timezone

from minecraft_diagnostic_mcp.collectors.docker_collector import (
    container_exists,
    get_runtime_backend,
    is_docker_available,
    resolve_execution_mode,
)
from minecraft_diagnostic_mcp.settings import settings


def run_rcon_command(command: str) -> str:
    if resolve_execution_mode() == "backup":
        raise RuntimeError("RCON is unavailable in backup analysis mode.")

    if get_runtime_backend() == "local":
        return _run_local_rcon_command(command)

    if not is_docker_available():
        raise RuntimeError("Docker CLI is not available.")
    if not container_exists(settings.container_name):
        raise RuntimeError(f"Docker container '{settings.container_name}' was not found.")

    return subprocess.check_output(
        ["docker", "exec", settings.container_name, "rcon-cli", command],
        timeout=settings.subprocess_timeout_seconds,
    ).decode("utf-8")


def get_rcon_readiness() -> dict:
    mode = resolve_execution_mode()
    checked_at = datetime.now(timezone.utc).isoformat()
    if mode == "backup":
        return {
            "execution_mode": mode,
            "runtime_backend": get_runtime_backend(),
            "rcon_available": False,
            "rcon_responsive": False,
            "auth_configured": False,
            "ready": False,
            "checked_at": checked_at,
            "readiness_reason": "backup_mode",
            "message": "RCON is unavailable in backup analysis mode.",
        }

    if get_runtime_backend() == "local":
        auth_configured = bool(settings.local_rcon_password)
        try:
            run_rcon_command("list")
            return {
                "execution_mode": mode,
                "runtime_backend": "local",
                "rcon_available": True,
                "rcon_responsive": True,
                "auth_configured": auth_configured,
                "ready": True,
                "checked_at": checked_at,
                "readiness_reason": "rcon_ready",
                "message": "Local RCON responded successfully.",
            }
        except Exception as exc:
            return {
                "execution_mode": mode,
                "runtime_backend": "local",
                "rcon_available": auth_configured,
                "rcon_responsive": False,
                "auth_configured": auth_configured,
                "ready": False,
                "checked_at": checked_at,
                "readiness_reason": "local_rcon_auth_missing" if not auth_configured else "local_rcon_unresponsive",
                "message": f"Local RCON did not respond cleanly: {exc}",
            }

    if not is_docker_available():
        return {
            "execution_mode": mode,
            "runtime_backend": "docker",
            "rcon_available": False,
            "rcon_responsive": False,
            "auth_configured": None,
            "ready": False,
            "checked_at": checked_at,
            "readiness_reason": "docker_cli_missing",
            "message": "Docker CLI is not available.",
        }

    if not container_exists(settings.container_name):
        return {
            "execution_mode": mode,
            "runtime_backend": "docker",
            "rcon_available": False,
            "rcon_responsive": False,
            "auth_configured": None,
            "ready": False,
            "checked_at": checked_at,
            "readiness_reason": "container_missing",
            "message": f"Docker container '{settings.container_name}' was not found.",
        }

    try:
        run_rcon_command("list")
        return {
            "execution_mode": mode,
            "runtime_backend": "docker",
            "rcon_available": True,
            "rcon_responsive": True,
            "auth_configured": None,
            "ready": True,
            "checked_at": checked_at,
            "readiness_reason": "rcon_ready",
            "message": "RCON responded successfully.",
        }
    except Exception as exc:
        return {
            "execution_mode": mode,
            "runtime_backend": "docker",
            "rcon_available": True,
            "rcon_responsive": False,
            "auth_configured": None,
            "ready": False,
            "checked_at": checked_at,
            "readiness_reason": "rcon_unresponsive",
            "message": f"RCON did not respond cleanly: {exc}",
        }


def _run_local_rcon_command(command: str) -> str:
    password = settings.local_rcon_password
    if not password:
        raise RuntimeError("Local RCON password is not configured.")

    host = settings.local_rcon_host
    port = settings.local_rcon_port
    request_id = 1

    with socket.create_connection((host, port), timeout=settings.subprocess_timeout_seconds) as sock:
        sock.settimeout(settings.subprocess_timeout_seconds)
        _send_rcon_packet(sock, request_id, 3, password)
        auth_id, _, _ = _receive_rcon_packet(sock)
        if auth_id == -1:
            raise RuntimeError("Local RCON authentication failed.")

        _send_rcon_packet(sock, request_id, 2, command)
        response_id, _, payload = _receive_rcon_packet(sock)
        if response_id == -1:
            raise RuntimeError("Local RCON command failed.")
        return payload


def _send_rcon_packet(sock: socket.socket, request_id: int, packet_type: int, payload: str) -> None:
    body = struct.pack("<ii", request_id, packet_type) + payload.encode("utf-8") + b"\x00\x00"
    packet = struct.pack("<i", len(body)) + body
    sock.sendall(packet)


def _receive_rcon_packet(sock: socket.socket) -> tuple[int, int, str]:
    raw_length = _recv_exact(sock, 4)
    length = struct.unpack("<i", raw_length)[0]
    body = _recv_exact(sock, length)
    request_id, packet_type = struct.unpack("<ii", body[:8])
    payload = body[8:-2].decode("utf-8", errors="replace")
    return request_id, packet_type, payload


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    buffer = b""
    while len(buffer) < size:
        chunk = sock.recv(size - len(buffer))
        if not chunk:
            raise RuntimeError("Socket closed while reading RCON response.")
        buffer += chunk
    return buffer
