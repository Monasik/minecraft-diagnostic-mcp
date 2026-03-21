import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.services.snapshot_service import get_server_snapshot


class SnapshotServiceTests(unittest.TestCase):
    def test_get_server_snapshot_aggregates_subsystem_summaries(self) -> None:
        with patch("minecraft_diagnostic_mcp.services.snapshot_service.get_container_status", return_value="running"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.resolve_execution_mode", return_value="runtime"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_runtime_readiness", return_value={"execution_mode": "runtime", "docker_available": True, "container_exists": True, "container_status": "running", "logs_available": True}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_backup_readiness", return_value={"server_root": ".", "plugins_dir": "plugins", "plugins_available": True, "logs_available": True, "latest_log_path": "logs/latest.log"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_rcon_readiness", return_value={"execution_mode": "runtime", "rcon_available": True, "rcon_responsive": True, "message": "ok"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.run_rcon_command", return_value="There are 0 of a max of 20 players online:"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_server_stats", return_value="1.00%\t256MiB / 1GiB\t1kB / 2kB"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.list_plugins", return_value={"exists": True, "count": 4, "message": "ok"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.lint_server_config", return_value={"diagnostics": [{"severity": "warning", "priority": 46, "title": "Config issue", "category": "rcon_configuration", "source_type": "config", "source_name": "server.properties", "summary": "RCON disabled", "tags": ["config", "rcon"], "context": {"config_file": "server.properties", "key": "enable-rcon", "current_value": "false"}}], "summary": {"config_count": 5, "issue_count": 1, "item_count": 1, "warning_count": 1, "info_count": 0, "error_count": 0, "critical_count": 0}}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.analyze_recent_logs", return_value={"scanned_lines": 200, "diagnostics": [{"severity": "error", "priority": 82, "title": "Log issue", "category": "plugin_startup", "source_type": "log", "source_name": "docker_logs", "summary": "Plugin startup failed", "suspected_component": "FancyPlugin", "tags": ["log", "plugin", "startup"], "context": {"plugin_name": "FancyPlugin", "line_number": 12, "source": "docker_logs"}}, {"severity": "error", "priority": 84, "title": "Dependency issue", "category": "missing_dependency", "source_type": "plugin", "source_name": "FancyPlugin", "summary": "Dependency missing", "suspected_component": "FancyPlugin", "tags": ["plugin", "dependency"], "context": {"plugin_name": "FancyPlugin", "missing_dependencies": ["MissingLib"]}}], "summary": {"finding_count": 2, "item_count": 2, "error_count": 2, "warning_count": 0, "info_count": 0, "critical_count": 0, "message": "done"}}):
            snapshot = get_server_snapshot()

        self.assertEqual(snapshot["status"]["container_status"], "running")
        self.assertEqual(snapshot["status"]["execution_mode"], "runtime")
        self.assertTrue(snapshot["status"]["rcon_responsive"])
        self.assertEqual(snapshot["stats"]["cpu_percent"], "1.00%")
        self.assertEqual(snapshot["plugin_summary"]["count"], 4)
        self.assertEqual(snapshot["config_summary"]["issue_count"], 1)
        self.assertEqual(snapshot["log_summary"]["finding_count"], 2)
        self.assertTrue(snapshot["status"]["runtime_readiness"]["docker_available"])
        self.assertGreaterEqual(len(snapshot["diagnostics"]), 2)
        self.assertEqual(snapshot["diagnostics"][0]["title"], "Dependency issue")
        self.assertGreaterEqual(len(snapshot["problem_groups"]), 2)
        self.assertIn("fancyplugin", snapshot["problem_groups"][0]["id"])
        self.assertGreaterEqual(len(snapshot["problem_groups"][0]["related_items"]), 1)
        self.assertIn("depends on another plugin", snapshot["problem_groups"][0]["explanation"])
        self.assertIn("MissingLib", snapshot["problem_groups"][0]["explanation"])
        self.assertIn("Install the missing dependency", snapshot["problem_groups"][0]["recommended_action"])
        self.assertEqual(snapshot["problem_groups"][0]["context"]["plugin_name"], "FancyPlugin")
        self.assertEqual(snapshot["problem_groups"][0]["context"]["missing_dependencies"], ["MissingLib"])
        self.assertIn("FancyPlugin", snapshot["summary"])

    def test_get_server_snapshot_handles_partial_failures(self) -> None:
        with patch("minecraft_diagnostic_mcp.services.snapshot_service.get_container_status", side_effect=RuntimeError("inspect failed")), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.resolve_execution_mode", return_value="runtime"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_runtime_readiness", return_value={"execution_mode": "runtime", "docker_available": False, "container_exists": False, "container_status": None, "logs_available": False}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_backup_readiness", return_value={"server_root": ".", "plugins_dir": "plugins", "plugins_available": False, "logs_available": False, "latest_log_path": None}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_rcon_readiness", return_value={"execution_mode": "runtime", "rcon_available": False, "rcon_responsive": False, "message": "docker unavailable"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.run_rcon_command", side_effect=RuntimeError("rcon failed")), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_server_stats", side_effect=RuntimeError("stats failed")), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.list_plugins", return_value={"exists": False, "count": 0, "message": "missing"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.lint_server_config", side_effect=RuntimeError("config failed")), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.analyze_recent_logs", side_effect=RuntimeError("logs failed")):
            snapshot = get_server_snapshot()

        self.assertFalse(snapshot["status"]["rcon_responsive"])
        self.assertEqual(snapshot["status"]["execution_mode"], "runtime")
        self.assertIsNone(snapshot["stats"]["cpu_percent"])
        self.assertIn("Failed to lint config files", snapshot["config_summary"]["message"])
        self.assertIn("Failed to analyze recent logs", snapshot["log_summary"]["message"])
        self.assertGreaterEqual(len(snapshot["diagnostics"]), 1)
        self.assertGreaterEqual(len(snapshot["problem_groups"]), 1)
        self.assertTrue(snapshot["summary"])

    def test_get_server_snapshot_prefers_config_issues_over_operational_log_noise(self) -> None:
        with patch("minecraft_diagnostic_mcp.services.snapshot_service.get_container_status", return_value="backup"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.resolve_execution_mode", return_value="backup"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_runtime_readiness", return_value={"execution_mode": "backup", "docker_available": False, "container_exists": False, "container_status": "backup", "logs_available": True}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_backup_readiness", return_value={"server_root": ".", "plugins_dir": "plugins", "plugins_available": True, "logs_available": True, "latest_log_path": "logs/latest.log"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_rcon_readiness", return_value={"execution_mode": "backup", "rcon_available": False, "rcon_responsive": False, "message": "backup mode"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.run_rcon_command", side_effect=RuntimeError("rcon failed")), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_server_stats", return_value=""), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.list_plugins", return_value={"exists": True, "count": 4, "message": "ok"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.lint_server_config", return_value={"diagnostics": [{"severity": "warning", "priority": 53, "title": "RCON not enabled", "category": "rcon_configuration", "source_type": "config", "source_name": "server.properties", "summary": "RCON disabled", "tags": ["config", "rcon"], "context": {"config_file": "server.properties", "key": "enable-rcon", "current_value": "false"}}], "summary": {"config_count": 5, "issue_count": 1, "item_count": 1, "warning_count": 1, "info_count": 0, "error_count": 0, "critical_count": 0}}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.analyze_recent_logs", return_value={"scanned_lines": 200, "diagnostics": [{"severity": "warning", "priority": 56, "title": "Server started in insecure mode", "category": "startup_security_warning", "source_type": "log", "source_name": "docker_logs", "summary": "Offline mode warning", "tags": ["log", "startup", "security"], "context": {"line_number": 10, "source": "docker_logs"}}, {"severity": "info", "priority": 14, "title": "Player movement warning", "category": "operational_movement_warning", "source_type": "log", "source_name": "docker_logs", "summary": "Movement warning", "tags": ["log", "operational", "movement"], "context": {"line_number": 11, "source": "docker_logs"}}, {"severity": "warning", "priority": 28, "title": "Server tick lag detected", "category": "performance_warning", "source_type": "log", "source_name": "docker_logs", "summary": "Lag warning", "tags": ["log", "performance", "lag"], "context": {"line_number": 12, "source": "docker_logs"}}], "summary": {"finding_count": 3, "item_count": 3, "error_count": 0, "warning_count": 2, "info_count": 1, "critical_count": 0, "message": "done"}}):
            snapshot = get_server_snapshot()

        top_categories = [item["category"] for item in snapshot["diagnostics"][:3]]
        self.assertIn("rcon_configuration", top_categories[:2])
        self.assertIn("startup_security_warning", top_categories[:2])
        self.assertNotEqual(snapshot["diagnostics"][-1]["category"], "rcon_configuration")


if __name__ == "__main__":
    unittest.main()
