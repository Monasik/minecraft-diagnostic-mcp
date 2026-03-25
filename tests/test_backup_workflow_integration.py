import gzip
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.services.config_lint_service import lint_server_config
from minecraft_diagnostic_mcp.services.log_analysis_service import analyze_recent_logs
from minecraft_diagnostic_mcp.services.plugin_service import get_plugin_by_name, list_plugins
from minecraft_diagnostic_mcp.services.snapshot_service import get_server_snapshot


class BackupWorkflowIntegrationTests(unittest.TestCase):
    def test_backup_workflow_handles_realistic_temp_server_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            server_root = Path(temp_dir)
            plugins_dir = server_root / "plugins"
            logs_dir = server_root / "logs"
            plugins_dir.mkdir()
            logs_dir.mkdir()

            self._write_plugin_jar(
                plugins_dir / "FancyPlugin.jar",
                """
name: FancyPlugin
version: 1.0.0
main: com.example.fancy.FancyPlugin
depend:
  - PlaceholderAPI
commands:
  fancy: {}
""".strip(),
            )

            (server_root / "server.properties").write_text(
                "enable-rcon=false\nonline-mode=false\nmotd=Integration Test\n",
                encoding="utf-8",
            )
            (server_root / "bukkit.yml").write_text("settings:\n  allow-end: true\n", encoding="utf-8")
            (server_root / "spigot.yml").write_text("settings:\n  debug: false\n", encoding="utf-8")
            (server_root / "purpur.yml").write_text("settings:\n  use-alternate-keepalive: true\n", encoding="utf-8")

            latest_log = """\
[10:00:00 INFO]: Starting minecraft server version 1.21.8
[10:00:01 WARN]: **** SERVER IS RUNNING IN OFFLINE/INSECURE MODE!
[10:00:02 ERROR]: Could not load plugin FancyPlugin v1.0.0
[10:00:03 ERROR]: java.lang.NoClassDefFoundError: me/clip/placeholderapi/PlaceholderAPIPlugin
[10:00:04 INFO]: Done (2.345s)! For help, type "help"
[10:05:00 WARN]: Can't keep up! Is the server overloaded?
"""
            (logs_dir / "latest.log").write_text(latest_log, encoding="utf-8")

            archived_log = """\
[09:00:00 INFO]: Starting minecraft server version 1.21.8
[09:00:01 ERROR]: Could not load plugin Vulcan v2.9.0
[09:00:02 ERROR]: java.lang.IllegalStateException: zip file closed
[09:00:03 INFO]: Done (1.222s)! For help, type "help"
"""
            with gzip.open(logs_dir / "2026-03-24-1.log.gz", "wt", encoding="utf-8") as handle:
                handle.write(archived_log)

            fake_settings = SimpleNamespace(
                server_root=str(server_root),
                plugins_dir="plugins",
                logs_dir="logs",
                max_log_files=10,
                max_log_lines_total=20000,
                iter_config_targets=lambda: (
                    ("server.properties", ("server.properties",)),
                    ("bukkit.yml", ("bukkit.yml",)),
                    ("spigot.yml", ("spigot.yml",)),
                    ("paper.yml", ("paper.yml",)),
                    ("paper-global.yml", ("paper-global.yml", "config/paper-global.yml")),
                    ("purpur.yml", ("purpur.yml", "config/purpur.yml")),
                ),
            )

            with patch("minecraft_diagnostic_mcp.collectors.filesystem_collector.settings", fake_settings), \
                 patch("minecraft_diagnostic_mcp.services.config_lint_service.settings", fake_settings), \
                 patch("minecraft_diagnostic_mcp.services.log_analysis_service.settings", fake_settings), \
                 patch("minecraft_diagnostic_mcp.collectors.docker_collector.resolve_execution_mode", return_value="backup"), \
                 patch("minecraft_diagnostic_mcp.services.snapshot_service.resolve_execution_mode", return_value="backup"), \
                 patch("minecraft_diagnostic_mcp.services.snapshot_service.get_container_status", return_value="backup"), \
                 patch("minecraft_diagnostic_mcp.services.snapshot_service.get_runtime_readiness", return_value={"execution_mode": "backup", "ready": False, "readiness_reason": "backup_mode", "message": "Runtime backend is inactive in backup mode.", "docker_available": False, "container_exists": False, "container_status": "backup", "logs_available": True, "local_process_running": False, "local_process_id": None}), \
                 patch("minecraft_diagnostic_mcp.services.snapshot_service.get_rcon_readiness", return_value={"execution_mode": "backup", "rcon_available": False, "rcon_responsive": False, "auth_configured": False, "ready": False, "readiness_reason": "backup_mode", "message": "RCON is unavailable in backup analysis mode."}), \
                 patch("minecraft_diagnostic_mcp.services.snapshot_service.run_rcon_command", side_effect=RuntimeError("backup mode")), \
                 patch("minecraft_diagnostic_mcp.services.snapshot_service.get_server_stats", side_effect=RuntimeError("backup mode")):
                plugins_result = list_plugins()
                plugin_result = get_plugin_by_name("FancyPlugin")
                config_result = lint_server_config()
                logs_result = analyze_recent_logs(500, include_archives=True, compact=True)
                snapshot = get_server_snapshot()

            self.assertTrue(plugins_result["exists"])
            self.assertEqual(plugins_result["count"], 1)
            self.assertTrue(plugin_result["plugin_found"])
            self.assertEqual(plugin_result["plugin"]["name"], "FancyPlugin")
            dependency_diagnostic = next(item for item in plugin_result["diagnostics"] if item["category"] == "missing_dependency")
            self.assertEqual(dependency_diagnostic["context"]["missing_dependencies"], ["PlaceholderAPI"])

            categories = {item["category"] for item in config_result["diagnostics"]}
            self.assertIn("rcon_configuration", categories)
            self.assertIn("security_configuration", categories)

            active_categories = {item["category"] for item in logs_result["compact_summary"]["top_active_diagnostics"]}
            self.assertTrue({"missing_dependency", "plugin_startup"} & active_categories)
            self.assertGreaterEqual(logs_result["compact_summary"]["resolved_item_count"], 1)
            self.assertEqual(logs_result["compact_summary"]["file_summary"]["archive_count"], 1)
            self.assertIn("Active now:", logs_result["compact_summary"]["summary_text"])

            self.assertEqual(snapshot["status"]["execution_mode"], "backup")
            self.assertEqual(snapshot["plugin_summary"]["count"], 1)
            self.assertGreaterEqual(len(snapshot["problem_groups"]), 1)
            self.assertIn("Main issues:", snapshot["summary"])

    def _write_plugin_jar(self, jar_path: Path, plugin_manifest: str) -> None:
        with zipfile.ZipFile(jar_path, "w") as jar_file:
            jar_file.writestr("plugin.yml", plugin_manifest)


if __name__ == "__main__":
    unittest.main()
