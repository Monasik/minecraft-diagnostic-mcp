import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.services.dependency_graph_service import analyze_dependency_graph


class DependencyGraphServiceTests(unittest.TestCase):
    def test_analyze_dependency_graph_builds_nodes_edges_and_cycles(self) -> None:
        plugin_result = {
            "plugins": [
                {"name": "PluginA", "version": "1.0", "manifest_name": "plugin.yml", "depend": ["PluginB"], "softdepend": [], "loadbefore": []},
                {"name": "PluginB", "version": "1.0", "manifest_name": "plugin.yml", "depend": ["PluginA"], "softdepend": ["PluginC"], "loadbefore": []},
                {"name": "PluginC", "version": "1.0", "manifest_name": "plugin.yml", "depend": ["MissingLib"], "softdepend": [], "loadbefore": []},
            ]
        }
        log_result = {
            "diagnostics": [
                {
                    "category": "plugin_startup",
                    "title": "Plugin failed during startup",
                    "suspected_component": "PluginC",
                    "source_name": "docker_logs",
                }
            ]
        }

        with patch("minecraft_diagnostic_mcp.services.dependency_graph_service.list_plugins", return_value=plugin_result), \
             patch("minecraft_diagnostic_mcp.services.dependency_graph_service.analyze_recent_logs", return_value=log_result):
            result = analyze_dependency_graph()

        self.assertEqual(result["plugin_count"], 3)
        self.assertTrue(result["cycles"])
        self.assertEqual(result["blocked_plugins"][0]["plugin"], "PluginC")
        node_c = next(node for node in result["nodes"] if node["name"] == "PluginC")
        self.assertIn("Plugin failed during startup", node_c["active_log_signals"])


if __name__ == "__main__":
    unittest.main()
