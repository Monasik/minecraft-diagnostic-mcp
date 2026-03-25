import json
import tempfile
import unittest
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.services.alert_service import _build_discord_payload, poll_alerts_once, preview_alert_candidates


class AlertServiceTests(unittest.TestCase):
    def test_poll_alerts_once_sends_only_active_serious_items_and_deduplicates(self) -> None:
        diagnostics = [
            {
                "severity": "error",
                "priority": 82,
                "title": "Plugin failed while enabling",
                "category": "plugin_startup",
                "source_type": "log",
                "source_name": "docker_logs",
                "summary": "Plugin startup failed",
                "suspected_component": "FancyPlugin",
                "recommendations": ["Check compatibility."],
                "context": {"plugin_name": "FancyPlugin", "historical_status": "active", "source_file": "logs/latest.log"},
                "evidence": [{"excerpt": "Error occurred while enabling FancyPlugin", "source": "docker_logs", "line_number": 12}],
            },
            {
                "severity": "warning",
                "priority": 28,
                "title": "Server tick lag detected",
                "category": "performance_warning",
                "source_type": "log",
                "source_name": "docker_logs",
                "summary": "Lag warning",
                "context": {"historical_status": "active"},
                "recommendations": ["Watch performance."],
                "evidence": [],
            },
            {
                "severity": "error",
                "priority": 70,
                "title": "Old plugin error",
                "category": "plugin_startup",
                "source_type": "log",
                "source_name": "docker_logs",
                "summary": "Historical issue",
                "context": {"historical_status": "resolved"},
                "recommendations": ["Ignore if resolved."],
                "evidence": [],
            },
        ]

        analysis = {"diagnostics": diagnostics}
        sent_payloads = []

        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "alerts.json"
            with patch("minecraft_diagnostic_mcp.services.alert_service.analyze_recent_logs", return_value=analysis), \
                 patch("minecraft_diagnostic_mcp.services.alert_service._send_discord_webhook", side_effect=lambda payload: sent_payloads.append(payload)), \
                 patch("minecraft_diagnostic_mcp.services.alert_service._state_file_path", return_value=state_file):
                first = poll_alerts_once()
                second = poll_alerts_once()

        self.assertEqual(first["sent_count"], 1)
        self.assertEqual(second["sent_count"], 0)
        self.assertEqual(len(sent_payloads), 1)
        self.assertIn("Plugin failed while enabling", json.dumps(sent_payloads[0], ensure_ascii=False))

    def test_poll_alerts_once_respects_cooldown_and_batches_alerts(self) -> None:
        diagnostics = [
            {
                "severity": "error",
                "priority": 82,
                "title": "Plugin failed while enabling",
                "category": "plugin_startup",
                "source_type": "log",
                "source_name": "docker_logs",
                "summary": "Plugin startup failed",
                "suspected_component": "FancyPlugin",
                "recommendations": ["Check compatibility."],
                "context": {"plugin_name": "FancyPlugin", "historical_status": "active", "source_file": "logs/latest.log"},
                "evidence": [{"excerpt": "Error occurred while enabling FancyPlugin", "source": "docker_logs", "line_number": 12}],
            },
            {
                "severity": "error",
                "priority": 80,
                "title": "Dependency missing",
                "category": "missing_dependency",
                "source_type": "log",
                "source_name": "docker_logs",
                "summary": "Missing PlaceholderAPI",
                "suspected_component": "FancyPlugin",
                "recommendations": ["Install PlaceholderAPI."],
                "context": {"plugin_name": "FancyPlugin", "historical_status": "active", "source_file": "logs/latest.log"},
                "evidence": [{"excerpt": "NoClassDefFoundError", "source": "docker_logs", "line_number": 13}],
            },
        ]
        analysis = {"diagnostics": diagnostics}
        sent_payloads = []

        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "alerts.json"
            fake_settings = SimpleNamespace(
                discord_alert_scan_lines=400,
                discord_alert_min_priority=50,
                discord_alert_cooldown_seconds=60,
                discord_alert_max_batch_items=3,
                discord_alert_username="Minecraft Diagnostic MCP",
                discord_webhook_url="https://example.test/webhook",
                server_root=temp_dir,
                discord_alert_state_file=str(state_file),
            )
            with patch("minecraft_diagnostic_mcp.services.alert_service.settings", fake_settings), \
                 patch("minecraft_diagnostic_mcp.services.alert_service.analyze_recent_logs", return_value=analysis), \
                 patch("minecraft_diagnostic_mcp.services.alert_service._send_discord_webhook", side_effect=lambda payload: sent_payloads.append(payload)), \
                 patch("minecraft_diagnostic_mcp.services.alert_service._state_file_path", return_value=state_file), \
                 patch("minecraft_diagnostic_mcp.services.alert_service.time.time", side_effect=[1000, 1020, 1085]):
                first = poll_alerts_once()
                second = poll_alerts_once()
                third = poll_alerts_once()

        self.assertEqual(first["sent_count"], 2)
        self.assertEqual(second["sent_count"], 0)
        self.assertEqual(third["sent_count"], 2)
        self.assertEqual(len(sent_payloads), 2)
        self.assertEqual(len(sent_payloads[0]["embeds"]), 2)

    def test_build_discord_payload_includes_context_fields(self) -> None:
        item = {
            "severity": "error",
            "title": "Missing dependency detected",
            "category": "missing_dependency",
            "source_type": "log",
            "source_name": "docker_logs",
            "summary": "Plugin dependency missing.",
            "suspected_component": "FancyPlugin",
            "recommendations": ["Install MissingLib."],
            "context": {
                "missing_dependencies": ["MissingLib"],
                "source_file": "logs/latest.log",
            },
            "evidence": [{"excerpt": "NoClassDefFoundError: MissingLib", "source": "docker_logs", "line_number": 44}],
        }

        payload = _build_discord_payload(item)

        self.assertEqual(payload["username"], "Minecraft Diagnostic MCP")
        embed = payload["embeds"][0]
        self.assertEqual(embed["title"], "Missing dependency detected")
        fields = {field["name"]: field["value"] for field in embed["fields"]}
        self.assertIn("Missing dependencies", fields)
        self.assertIn("MissingLib", fields["Missing dependencies"])
        self.assertIn("Log source", fields)

    def test_build_discord_payload_batches_multiple_items(self) -> None:
        items = [
            {
                "severity": "error",
                "title": "First issue",
                "category": "plugin_startup",
                "source_type": "log",
                "source_name": "docker_logs",
                "summary": "First summary",
                "suspected_component": "PluginA",
                "recommendations": ["Action A"],
                "context": {"source_file": "logs/latest.log"},
                "evidence": [],
            },
            {
                "severity": "warning",
                "title": "Second issue",
                "category": "security_configuration",
                "source_type": "config",
                "source_name": "server.properties",
                "summary": "Second summary",
                "suspected_component": "server.properties",
                "recommendations": ["Action B"],
                "context": {"config_file": "server.properties", "key": "online-mode", "current_value": "false"},
                "evidence": [],
            },
        ]

        with patch("minecraft_diagnostic_mcp.services.alert_service.settings", SimpleNamespace(discord_alert_username="Minecraft Diagnostic MCP", discord_alert_max_batch_items=3)):
            payload = _build_discord_payload(items)

        self.assertEqual(len(payload["embeds"]), 2)

    def test_preview_alert_candidates_returns_filtered_preview_without_sending(self) -> None:
        analysis = {
            "diagnostics": [
                {
                    "severity": "error",
                    "priority": 82,
                    "title": "Plugin failed while enabling",
                    "category": "plugin_startup",
                    "source_type": "log",
                    "source_name": "docker_logs",
                    "summary": "Plugin startup failed",
                    "suspected_component": "FancyPlugin",
                    "recommendations": ["Check compatibility."],
                    "context": {"historical_status": "active"},
                    "evidence": [],
                },
                {
                    "severity": "warning",
                    "priority": 10,
                    "title": "Movement warning",
                    "category": "operational_movement_warning",
                    "source_type": "log",
                    "source_name": "docker_logs",
                    "summary": "noise",
                    "context": {"historical_status": "active"},
                    "evidence": [],
                },
            ]
        }
        fake_settings = SimpleNamespace(discord_alert_scan_lines=400, discord_alert_max_batch_items=2, discord_alert_min_priority=50)

        with patch("minecraft_diagnostic_mcp.services.alert_service.settings", fake_settings), \
             patch("minecraft_diagnostic_mcp.services.alert_service.analyze_recent_logs", return_value=analysis):
            preview = preview_alert_candidates()

        self.assertEqual(preview["scanned_count"], 2)
        self.assertEqual(preview["candidate_count"], 1)
        self.assertEqual(preview["candidate_titles"], ["Plugin failed while enabling"])


if __name__ == "__main__":
    unittest.main()
