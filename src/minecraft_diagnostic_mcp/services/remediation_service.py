from __future__ import annotations

from pathlib import Path
from typing import Any

from minecraft_diagnostic_mcp.collectors.filesystem_collector import find_existing_config_path, read_text_file
from minecraft_diagnostic_mcp.parsers.properties_parser import parse_properties
from minecraft_diagnostic_mcp.services.config_lint_service import lint_server_config
from minecraft_diagnostic_mcp.settings import settings


SAFE_AUTOMATIC_ACTIONS = {
    "server-properties-enable-rcon",
    "server-properties-reset-server-port",
    "server-properties-set-rcon-password",
}


def plan_remediation(default_rcon_password: str | None = None) -> dict[str, Any]:
    lint_result = lint_server_config()
    diagnostics = lint_result.get("diagnostics", [])
    properties_path = find_existing_config_path(("server.properties",))
    actions = []

    has_rcon_enable_issue = False
    has_rcon_password_issue = False
    has_port_issue = False

    for item in diagnostics:
        category = str(item.get("category", "general"))
        title = str(item.get("title", ""))
        context = item.get("context", {}) if isinstance(item.get("context"), dict) else {}

        if category == "rcon_configuration" and context.get("key") == "enable-rcon":
            has_rcon_enable_issue = True
        if category == "rcon_configuration" and "password" in str(context.get("key", "")):
            has_rcon_password_issue = True
        if category == "server_properties" and "server-port" in title.casefold():
            has_port_issue = True

    if properties_path and has_rcon_enable_issue:
        actions.append(
            _build_action(
                "server-properties-enable-rcon",
                "Enable RCON in server.properties",
                "Set enable-rcon=true so MCP and remote tooling can use the server RCON interface.",
                str(properties_path),
                {"enable-rcon": "true"},
                safe_to_apply=True,
            )
        )

    if properties_path and has_port_issue:
        actions.append(
            _build_action(
                "server-properties-reset-server-port",
                "Reset invalid server-port",
                "Set server-port back to 25565 if the configured port is missing, invalid, or out of range.",
                str(properties_path),
                {"server-port": "25565"},
                safe_to_apply=True,
            )
        )

    if properties_path and has_rcon_password_issue:
        safe_to_apply = bool(default_rcon_password)
        actions.append(
            _build_action(
                "server-properties-set-rcon-password",
                "Set RCON password",
                "Write a non-empty rcon.password so RCON can be used safely after restart.",
                str(properties_path),
                {"rcon.password": default_rcon_password or "<required>"},
                safe_to_apply=safe_to_apply,
                manual_reason=None if safe_to_apply else "Provide a default_rcon_password when applying this action.",
            )
        )

    for item in diagnostics:
        if item.get("category") == "missing_dependency":
            context = item.get("context", {}) if isinstance(item.get("context"), dict) else {}
            actions.append(
                _build_action(
                    f"manual-missing-dependency-{str(item.get('source_name', 'plugin')).casefold()}",
                    f"Install missing dependency for {item.get('source_name', 'plugin')}",
                    "Install the missing plugin dependency before the next restart.",
                    None,
                    {"missing_dependencies": context.get("missing_dependencies", [])},
                    safe_to_apply=False,
                    manual_reason="Requires downloading or restoring the dependency plugin manually.",
                )
            )

    return {
        "action_count": len(actions),
        "automatic_action_count": sum(1 for action in actions if action["safe_to_apply"]),
        "manual_action_count": sum(1 for action in actions if not action["safe_to_apply"]),
        "actions": actions,
        "summary": _build_remediation_summary(actions),
    }


def apply_remediation(action_ids: list[str] | None = None, default_rcon_password: str | None = None) -> dict[str, Any]:
    plan = plan_remediation(default_rcon_password=default_rcon_password)
    actions = plan["actions"]
    selected_ids = set(action_ids or [])
    if selected_ids:
        actions = [action for action in actions if action["id"] in selected_ids]

    applied = []
    skipped = []

    for action in actions:
        if not action["safe_to_apply"]:
            skipped.append({"id": action["id"], "reason": action.get("manual_reason", "Action is manual-only.")})
            continue
        if action["id"] not in SAFE_AUTOMATIC_ACTIONS:
            skipped.append({"id": action["id"], "reason": "Action is outside the automatic remediation allowlist."})
            continue

        file_path = action.get("file_path")
        if not file_path:
            skipped.append({"id": action["id"], "reason": "Action does not target a writable file."})
            continue

        updates = action.get("updates", {})
        if action["id"] == "server-properties-set-rcon-password" and updates.get("rcon.password") == "<required>":
            skipped.append({"id": action["id"], "reason": "A real RCON password must be provided before applying this action."})
            continue

        original_text = read_text_file(file_path)
        updated_text = _apply_properties_updates(original_text, updates)
        path = Path(file_path)
        backup_path = path.with_suffix(path.suffix + ".mcp.bak")
        backup_path.write_text(original_text, encoding="utf-8")
        path.write_text(updated_text, encoding="utf-8")
        applied.append({"id": action["id"], "file_path": file_path, "backup_path": str(backup_path)})

    return {
        "requested_action_count": len(actions),
        "applied_count": len(applied),
        "skipped_count": len(skipped),
        "applied": applied,
        "skipped": skipped,
        "summary": f"Applied {len(applied)} remediation action(s); skipped {len(skipped)} action(s).",
    }


def _build_action(
    action_id: str,
    title: str,
    summary: str,
    file_path: str | None,
    updates: dict[str, str],
    safe_to_apply: bool,
    manual_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "id": action_id,
        "title": title,
        "summary": summary,
        "file_path": file_path,
        "updates": updates,
        "safe_to_apply": safe_to_apply,
        "manual_reason": manual_reason,
        "requires_restart": True,
    }


def _build_remediation_summary(actions: list[dict[str, Any]]) -> str:
    automatic_count = sum(1 for action in actions if action["safe_to_apply"])
    manual_count = sum(1 for action in actions if not action["safe_to_apply"])
    return f"Prepared {len(actions)} remediation action(s): {automatic_count} automatic and {manual_count} manual."


def _apply_properties_updates(original_text: str, updates: dict[str, str]) -> str:
    lines = original_text.splitlines()
    updated_keys = set()
    new_lines = []

    for line in lines:
        separator_index = -1
        for separator in ("=", ":"):
            separator_index = line.find(separator)
            if separator_index != -1:
                break
        if separator_index == -1 or line.strip().startswith(("#", "!")):
            new_lines.append(line)
            continue

        key = line[:separator_index].strip()
        if key in updates:
            separator = line[separator_index]
            new_lines.append(f"{key}{separator}{updates[key]}")
            updated_keys.add(key)
        else:
            new_lines.append(line)

    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")

    return "\n".join(new_lines) + ("\n" if original_text.endswith("\n") or new_lines else "")
