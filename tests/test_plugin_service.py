import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.services.plugin_service import get_plugin_by_name, list_plugins


class PluginServiceTests(unittest.TestCase):
    def test_list_plugins_returns_safe_response_when_directory_missing(self) -> None:
        with patch("minecraft_diagnostic_mcp.services.plugin_service.plugins_dir_exists", return_value=False), \
             patch("minecraft_diagnostic_mcp.services.plugin_service.get_plugins_dir", return_value=Path("plugins")):
            result = list_plugins()

        self.assertFalse(result["exists"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["plugins"], [])

    def test_get_plugin_by_name_matches_case_insensitive_and_reports_missing_dependency(self) -> None:
        manifests = {
            Path("plugins/ExamplePlugin.jar"): b"""
name: ExamplePlugin
version: 1.0.0
main: com.example.Plugin
depend: [Vault, MissingLib]
""",
            Path("plugins/Vault.jar"): b"""
name: Vault
version: 2.0.0
main: net.example.Vault
""",
        }

        with patch("minecraft_diagnostic_mcp.services.plugin_service.plugins_dir_exists", return_value=True), \
             patch("minecraft_diagnostic_mcp.services.plugin_service.get_plugins_dir", return_value=Path("plugins")), \
             patch("minecraft_diagnostic_mcp.services.plugin_service.list_plugin_jars", return_value=list(manifests.keys())), \
             patch("minecraft_diagnostic_mcp.services.plugin_service.read_jar_entry", side_effect=lambda path, _: manifests[path]):
            result = get_plugin_by_name("exampleplugin")

        self.assertTrue(result["plugin_found"])
        self.assertEqual(result["plugin"]["name"], "ExamplePlugin")
        self.assertEqual(result["diagnostics"][0]["category"], "missing_dependency")
        self.assertEqual(result["diagnostics"][0]["source_type"], "plugin")
        self.assertIn("MissingLib", result["diagnostics"][0]["tags"])
        self.assertEqual(result["diagnostics"][0]["context"]["plugin_name"], "ExamplePlugin")
        self.assertEqual(result["diagnostics"][0]["context"]["missing_dependencies"], ["MissingLib"])

    def test_list_plugins_supports_paper_plugin_manifest(self) -> None:
        manifests = {
            Path("plugins/PaperOnly.jar"): b"""
name: PaperOnly
version: 2.0.0
main: com.example.PaperOnly
""",
        }

        def read_manifest(path, entry_name):
            if entry_name == "paper-plugin.yml":
                return manifests[path]
            raise KeyError(entry_name)

        with patch("minecraft_diagnostic_mcp.services.plugin_service.plugins_dir_exists", return_value=True), \
             patch("minecraft_diagnostic_mcp.services.plugin_service.get_plugins_dir", return_value=Path("plugins")), \
             patch("minecraft_diagnostic_mcp.services.plugin_service.list_plugin_jars", return_value=list(manifests.keys())), \
             patch("minecraft_diagnostic_mcp.services.plugin_service.read_jar_entry", side_effect=read_manifest):
            result = list_plugins()

        self.assertTrue(result["exists"])
        self.assertEqual(result["plugins"][0]["name"], "PaperOnly")
        self.assertEqual(result["plugins"][0]["manifest_name"], "paper-plugin.yml")
        self.assertTrue(result["plugins"][0]["manifest_found"])


if __name__ == "__main__":
    unittest.main()
