import json
import tempfile
import unittest
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.integrations.manager import _post_json, dispatch_alerts, get_enabled_integrations


class IntegrationsManagerTests(unittest.TestCase):
    def test_get_enabled_integrations_lists_configured_sinks(self) -> None:
        fake_settings = SimpleNamespace(
            discord_alerts_enabled=True,
            discord_webhook_url="https://discord.test/webhook",
            generic_webhook_enabled=True,
            generic_webhook_url="https://webhook.test/alerts",
            alert_file_sink_enabled=True,
            alert_file_sink_path="alerts.ndjson",
        )

        with patch("minecraft_diagnostic_mcp.integrations.manager.settings", fake_settings):
            integrations = get_enabled_integrations()

        self.assertEqual(len(integrations), 3)
        self.assertEqual(integrations[0]["target"], "https://discord.test/...")
        self.assertEqual(integrations[1]["target"], "https://webhook.test/...")

    def test_dispatch_alerts_writes_file_sink(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sink_path = Path(temp_dir) / "alerts.ndjson"
            fake_settings = SimpleNamespace(
                discord_alerts_enabled=False,
                discord_webhook_url="",
                generic_webhook_enabled=False,
                generic_webhook_url="",
                generic_webhook_headers_json="",
                alert_file_sink_enabled=True,
                alert_file_sink_path=str(sink_path),
            )
            payload = {"event_type": "test", "alerts": [{"title": "A"}]}

            with patch("minecraft_diagnostic_mcp.integrations.manager.settings", fake_settings):
                result = dispatch_alerts({"embeds": []}, payload)

            self.assertEqual(result["delivery_count"], 1)
            stored = [json.loads(line) for line in sink_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(stored[0]["event_type"], "test")

    def test_post_json_sets_user_agent_for_discord_compatibility(self) -> None:
        captured = {}

        class FakeResponse:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def fake_urlopen(req, timeout):
            captured["headers"] = dict(req.header_items())
            captured["timeout"] = timeout
            return FakeResponse()

        with patch("minecraft_diagnostic_mcp.integrations.manager.request.urlopen", side_effect=fake_urlopen):
            _post_json("https://discord.test/webhook", {"content": "hello"})

        self.assertIn("User-agent", captured["headers"])
        self.assertTrue(captured["headers"]["User-agent"].startswith("minecraft-diagnostic-mcp/"))
        self.assertEqual(captured["timeout"], 15)


if __name__ == "__main__":
    unittest.main()
