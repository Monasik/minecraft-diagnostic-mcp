from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any
from urllib import error, request

from minecraft_diagnostic_mcp import __version__
from minecraft_diagnostic_mcp.settings import settings


def get_enabled_integrations() -> list[dict[str, Any]]:
    integrations: list[dict[str, Any]] = []

    if settings.discord_alerts_enabled and settings.discord_webhook_url:
        integrations.append(
            {
                "name": "discord_webhook",
                "type": "webhook",
                "enabled": True,
                "target": _redact_url(settings.discord_webhook_url),
            }
        )

    if settings.generic_webhook_enabled and settings.generic_webhook_url:
        integrations.append(
            {
                "name": "generic_webhook",
                "type": "webhook",
                "enabled": True,
                "target": _redact_url(settings.generic_webhook_url),
            }
        )

    if settings.alert_file_sink_enabled and settings.alert_file_sink_path:
        integrations.append(
            {
                "name": "file_sink",
                "type": "file",
                "enabled": True,
                "target": settings.alert_file_sink_path,
            }
        )

    return integrations


def dispatch_alerts(discord_payload: dict[str, Any], generic_payload: dict[str, Any]) -> dict[str, Any]:
    deliveries: list[dict[str, Any]] = []

    if settings.discord_alerts_enabled and settings.discord_webhook_url:
        _post_json(settings.discord_webhook_url, discord_payload)
        deliveries.append({"integration": "discord_webhook", "status": "sent"})

    if settings.generic_webhook_enabled and settings.generic_webhook_url:
        headers = _parse_headers_json(settings.generic_webhook_headers_json)
        _post_json(settings.generic_webhook_url, generic_payload, headers=headers)
        deliveries.append({"integration": "generic_webhook", "status": "sent"})

    if settings.alert_file_sink_enabled and settings.alert_file_sink_path:
        _append_json_line(settings.alert_file_sink_path, generic_payload)
        deliveries.append({"integration": "file_sink", "status": "written"})

    return {
        "delivery_count": len(deliveries),
        "deliveries": deliveries,
    }


def _parse_headers_json(value: str) -> dict[str, str]:
    if not value.strip():
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(loaded, dict):
        return {}
    return {str(key): str(item) for key, item in loaded.items()}


def _redact_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return "<redacted>"
    if not parsed.scheme or not parsed.netloc:
        return "<redacted>"
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) <= 2:
        redacted_path = "/..."
    else:
        redacted_path = "/" + "/".join(path_parts[:2]) + "/..."
    return f"{parsed.scheme}://{parsed.netloc}{redacted_path}"


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> None:
    request_headers = {
        "Content-Type": "application/json",
        "User-Agent": f"minecraft-diagnostic-mcp/{__version__}",
    }
    if headers:
        request_headers.update(headers)
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            if response.status >= 400:
                raise RuntimeError(f"Webhook returned status {response.status}")
    except error.HTTPError as exc:
        raise RuntimeError(f"Webhook returned status {exc.code}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Webhook request failed: {exc.reason}") from exc


def _append_json_line(path_like: str, payload: dict[str, Any]) -> None:
    path = Path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
