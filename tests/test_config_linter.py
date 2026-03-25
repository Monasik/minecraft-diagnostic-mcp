import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.analyzers.config_linter import lint_configs
from minecraft_diagnostic_mcp.models.config import ConfigFileInfo


class ConfigLinterTests(unittest.TestCase):
    def test_lint_configs_reports_missing_files_and_server_properties_issues(self) -> None:
        config_files = [
            ConfigFileInfo(path="server.properties", exists=True, parsed=True, kind="properties"),
            ConfigFileInfo(path="paper.yml", exists=False, parsed=False, kind="yaml"),
        ]
        parsed_configs = {
            "server.properties": {
                "server-port": "70000",
                "enable-rcon": "true",
                "rcon.password": "",
                "online-mode": "false",
                "motd": "",
            }
        }

        issues = lint_configs(config_files, parsed_configs)
        titles = {issue.title for issue in issues}
        severities = {issue.severity for issue in issues}

        self.assertIn("Invalid server-port", titles)
        self.assertIn("RCON password missing", titles)
        self.assertIn("Online mode disabled", titles)
        self.assertIn("Empty MOTD", titles)
        self.assertIn("Config file missing", titles)
        self.assertTrue(severities.issubset({"info", "warning", "error", "critical"}))
        invalid_port = next(issue for issue in issues if issue.title == "Invalid server-port")
        self.assertEqual(invalid_port.context["config_file"], "server.properties")
        self.assertEqual(invalid_port.context["key"], "server-port")
        self.assertEqual(invalid_port.context["current_value"], "70000")

    def test_lint_configs_skips_paper_yml_when_modern_paper_configs_exist(self) -> None:
        config_files = [
            ConfigFileInfo(path="paper.yml", exists=False, parsed=False, kind="yaml"),
            ConfigFileInfo(path="paper-global.yml", exists=True, parsed=True, kind="yaml"),
            ConfigFileInfo(path="purpur.yml", exists=True, parsed=True, kind="yaml"),
        ]

        issues = lint_configs(config_files, {"paper-global.yml": {"dummy": True}, "purpur.yml": {"dummy": True}})

        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
