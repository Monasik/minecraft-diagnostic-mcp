import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.services.alert_service import _build_discord_payload, poll_alerts_once


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


if __name__ == "__main__":
    unittest.main()
