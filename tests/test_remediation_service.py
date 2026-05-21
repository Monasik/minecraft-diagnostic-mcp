import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.services.remediation_service import apply_remediation, plan_remediation


class RemediationServiceTests(unittest.TestCase):
    def test_plan_remediation_builds_automatic_and_manual_actions(self) -> None:
        lint_result = {
            "diagnostics": [
                {"category": "rcon_configuration", "title": "RCON not enabled", "context": {"key": "enable-rcon"}},
                {"category": "rcon_configuration", "title": "RCON password missing", "context": {"key": "rcon.password"}},
                {"category": "server_properties", "title": "Invalid server-port", "context": {"key": "server-port"}},
                {"category": "missing_dependency", "source_name": "FancyPlugin", "context": {"missing_dependencies": ["PlaceholderAPI"]}},
            ]
        }

        with patch("minecraft_diagnostic_mcp.services.remediation_service.lint_server_config", return_value=lint_result), \
             patch("minecraft_diagnostic_mcp.services.remediation_service.find_existing_config_path", return_value=Path("server.properties")):
            plan = plan_remediation(default_rcon_password="secret")

        self.assertEqual(plan["automatic_action_count"], 3)
        self.assertEqual(plan["manual_action_count"], 1)

    def test_apply_remediation_updates_server_properties_and_creates_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            server_properties = Path(temp_dir) / "server.properties"
            server_properties.write_text("enable-rcon=false\nserver-port=70000\n", encoding="utf-8")
            lint_result = {
                "diagnostics": [
                    {"category": "rcon_configuration", "title": "RCON not enabled", "context": {"key": "enable-rcon"}},
                    {"category": "server_properties", "title": "Invalid server-port", "context": {"key": "server-port"}},
                ]
            }

            with patch("minecraft_diagnostic_mcp.services.remediation_service.lint_server_config", return_value=lint_result), \
                 patch("minecraft_diagnostic_mcp.services.remediation_service.find_existing_config_path", return_value=server_properties):
                result = apply_remediation()

            self.assertEqual(result["applied_count"], 2)
            updated = server_properties.read_text(encoding="utf-8")
            self.assertIn("enable-rcon=true", updated)
            self.assertIn("server-port=25565", updated)
            self.assertTrue(server_properties.with_suffix(".properties.mcp.bak").exists())


if __name__ == "__main__":
    unittest.main()
