import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any
from urllib import error, request

from minecraft_diagnostic_mcp.services.log_analysis_service import analyze_recent_logs
from minecraft_diagnostic_mcp.settings import settings


LOGGER = logging.getLogger(__name__)
NOISE_CATEGORIES = {"operational_movement_warning", "monitoring_warning", "performance_warning", "log_warning"}
ALERT_CATEGORIES = {
    "plugin_startup",
    "missing_dependency",
    "startup_security_warning",
    "rcon_configuration",
    "security_configuration",
    "parse_error",
    "plugin_compatibility_warning",
    "log_error",
    "exception",
    "exception_chain",
}


def alerts_enabled() -> bool:
    return settings.discord_alerts_enabled and bool(settings.discord_webhook_url)


def start_background_alert_loop() -> threading.Thread | None:
    if not alerts_enabled():
        return None

    thread = threading.Thread(
        target=run_alert_loop,
        name="minecraft-diagnostic-discord-alerts",
        daemon=True,
    )
    thread.start()
    return thread


def run_alert_loop() -> None:
    LOGGER.info("Discord alert loop enabled.")
    poll_seconds = max(10, settings.discord_alert_poll_seconds)
    while True:
        try:
            poll_alerts_once()
        except Exception as exc:
            LOGGER.warning("Discord alert poll failed: %s", exc)
        time.sleep(poll_seconds)


def poll_alerts_once() -> dict[str, Any]:
    analysis = analyze_recent_logs(settings.discord_alert_scan_lines, include_archives=False, compact=False)
    diagnostics = analysis.get("diagnostics", [])
    state = _load_alert_state()

    sent_items = []
    now = int(time.time())
    updated = False

    for item in diagnostics:
        if not _is_alert_candidate(item):
            continue

        fingerprint = _alert_fingerprint(item)
        if fingerprint in state.get("sent_alerts", {}):
            continue

        payload = _build_discord_payload(item)
        _send_discord_webhook(payload)
        state.setdefault("sent_alerts", {})[fingerprint] = {
            "sent_at": now,
            "title": item.get("title", ""),
            "category": item.get("category", ""),
        }
        sent_items.append(item)
        updated = True

    if updated:
        _save_alert_state(state)

    return {
        "scanned_count": len(diagnostics),
        "sent_count": len(sent_items),
        "sent_titles": [item.get("title", "") for item in sent_items],
    }


def _is_alert_candidate(item: dict[str, Any]) -> bool:
    category = str(item.get("category", "general"))
    severity = str(item.get("severity", "info")).lower()
    priority = int(item.get("priority", 0))
    context = item.get("context", {}) if isinstance(item.get("context", {}), dict) else {}

    if str(context.get("historical_status", "active")).lower() == "resolved":
        return False
    if category in NOISE_CATEGORIES:
        return False
    if category in ALERT_CATEGORIES:
        return True
    if severity in {"error", "critical"} and priority >= settings.discord_alert_min_priority:
        return True
    return False


def _alert_fingerprint(item: dict[str, Any]) -> str:
    context = item.get("context", {}) if isinstance(item.get("context", {}), dict) else {}
    evidence = item.get("evidence", []) if isinstance(item.get("evidence", []), list) else []
    excerpt = ""
    if evidence and isinstance(evidence[0], dict):
        excerpt = str(evidence[0].get("excerpt", ""))

    signature = {
        "category": item.get("category", ""),
        "title": item.get("title", ""),
        "component": item.get("suspected_component") or item.get("source_name", ""),
        "key": context.get("key"),
        "missing_dependencies": context.get("missing_dependencies", []),
        "issue_family": context.get("issue_family"),
        "excerpt": excerpt[:240],
    }
    return hashlib.sha256(json.dumps(signature, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _build_discord_payload(item: dict[str, Any]) -> dict[str, Any]:
    severity = str(item.get("severity", "info")).upper()
    title = str(item.get("title", "Minecraft diagnostic alert")).strip()
    summary = str(item.get("summary", "")).strip()
    category = str(item.get("category", "general")).strip()
    component = str(item.get("suspected_component") or item.get("source_name") or "server").strip()
    context = item.get("context", {}) if isinstance(item.get("context", {}), dict) else {}
    recommendations = item.get("recommendations", []) if isinstance(item.get("recommendations", []), list) else []
    evidence = item.get("evidence", []) if isinstance(item.get("evidence", []), list) else []
    excerpt = ""
    if evidence and isinstance(evidence[0], dict):
        excerpt = str(evidence[0].get("excerpt", "")).strip()

    description_lines = [
        f"**Severity:** {severity}",
        f"**Category:** {category}",
        f"**Component:** {component}",
    ]
    if summary:
        description_lines.append(f"**Summary:** {summary}")
    if recommendations:
        description_lines.append(f"**Action:** {recommendations[0]}")
    if excerpt:
        compact_excerpt = excerpt[:500]
        description_lines.append(f"**Evidence:** `{compact_excerpt}`")

    fields = []
    if context.get("missing_dependencies"):
        fields.append({
            "name": "Missing dependencies",
            "value": ", ".join(str(item) for item in context.get("missing_dependencies", []))[:1024] or "-",
            "inline": False,
        })
    if context.get("config_file"):
        key_name = context.get("key") or "-"
        current_value = context.get("current_value")
        value_text = f"{context.get('config_file')} ({key_name})"
        if current_value is not None:
            value_text += f"\nCurrent value: {current_value}"
        fields.append({"name": "Config context", "value": value_text[:1024], "inline": False})
    if context.get("source_file"):
        fields.append({"name": "Log source", "value": str(context.get("source_file"))[:1024], "inline": False})

    return {
        "username": settings.discord_alert_username,
        "embeds": [
            {
                "title": title[:256],
                "description": "\n".join(description_lines)[:4000],
                "color": _discord_color_for_severity(severity.lower()),
                "fields": fields[:5],
            }
        ],
    }


def _discord_color_for_severity(severity: str) -> int:
    if severity == "critical":
        return 0xB71C1C
    if severity == "error":
        return 0xD32F2F
    if severity == "warning":
        return 0xF9A825
    return 0x1976D2


def _send_discord_webhook(payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        settings.discord_webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            if response.status >= 400:
                raise RuntimeError(f"Discord webhook returned status {response.status}")
    except error.HTTPError as exc:
        raise RuntimeError(f"Discord webhook returned status {exc.code}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Discord webhook request failed: {exc.reason}") from exc


def _state_file_path() -> Path:
    if settings.discord_alert_state_file:
        return Path(settings.discord_alert_state_file)
    base = Path(settings.server_root).resolve()
    return base / ".mcp_discord_alert_state.json"


def _load_alert_state() -> dict[str, Any]:
    path = _state_file_path()
    if not path.exists():
        return {"sent_alerts": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"sent_alerts": {}}


def _save_alert_state(state: dict[str, Any]) -> None:
    path = _state_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
