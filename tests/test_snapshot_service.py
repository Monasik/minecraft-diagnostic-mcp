import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.services.snapshot_service import get_server_snapshot


class SnapshotServiceTests(unittest.TestCase):
    def test_get_server_snapshot_aggregates_subsystem_summaries(self) -> None:
        def analyze_logs_stub(lines, include_archives=False, compact=False):
            if compact:
                return {
                    "scanned_lines": lines,
                    "archives_included": include_archives,
                    "detail_mode": "compact",
                    "log_files_scanned": [{"path": "logs/latest.log", "file_type": "log", "readable": True}],
                    "compact_summary": {
                        "summary_text": "Compact log summary for snapshot.",
                        "active_item_count": 1,
                        "resolved_item_count": 1,
                        "top_active_diagnostics": [{"category": "plugin_startup", "title": "Log issue"}],
                        "top_resolved_diagnostics": [{"category": "missing_dependency", "title": "Resolved dependency issue"}],
                        "repeated_patterns": [{"category": "plugin_startup", "title": "Log issue", "occurrence_count": 3}],
                        "top_categories": [{"category": "plugin_startup", "count": 1}],
                        "file_summary": {"scanned_count": 1, "archive_count": 0, "unreadable_count": 0, "latest_source": "logs/latest.log", "oldest_source": "logs/latest.log"},
                        "startup_summary": {"detected": True, "item_count": 1},
                    },
                    "summary": {"finding_count": 2, "item_count": 2, "error_count": 2, "warning_count": 0, "info_count": 0, "critical_count": 0, "message": "done"},
                    "diagnostics": [{"severity": "error", "priority": 82, "title": "Log issue", "category": "plugin_startup", "source_type": "log", "source_name": "docker_logs", "summary": "Plugin startup failed", "suspected_component": "FancyPlugin", "tags": ["log", "plugin", "startup"], "context": {"plugin_name": "FancyPlugin", "line_number": 12, "source": "docker_logs"}}],
                }
            return {
                "scanned_lines": 200,
                "diagnostics": [
                    {"severity": "error", "priority": 82, "title": "Log issue", "category": "plugin_startup", "source_type": "log", "source_name": "docker_logs", "summary": "Plugin startup failed", "suspected_component": "FancyPlugin", "tags": ["log", "plugin", "startup"], "context": {"plugin_name": "FancyPlugin", "line_number": 12, "source": "docker_logs"}},
                    {"severity": "error", "priority": 84, "title": "Dependency issue", "category": "missing_dependency", "source_type": "plugin", "source_name": "FancyPlugin", "summary": "Dependency missing", "suspected_component": "FancyPlugin", "tags": ["plugin", "dependency"], "context": {"plugin_name": "FancyPlugin", "missing_dependencies": ["MissingLib"]}},
                ],
                "summary": {"finding_count": 2, "item_count": 2, "error_count": 2, "warning_count": 0, "info_count": 0, "critical_count": 0, "message": "done"},
            }

        with patch("minecraft_diagnostic_mcp.services.snapshot_service.get_container_status", return_value="running"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.resolve_execution_mode", return_value="runtime"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_runtime_readiness", return_value={"execution_mode": "runtime", "docker_available": True, "container_exists": True, "container_status": "running", "logs_available": True}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_backup_readiness", return_value={"server_root": ".", "plugins_dir": "plugins", "plugins_available": True, "logs_available": True, "latest_log_path": "logs/latest.log"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_rcon_readiness", return_value={"execution_mode": "runtime", "rcon_available": True, "rcon_responsive": True, "message": "ok"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.run_rcon_command", return_value="There are 0 of a max of 20 players online:"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_server_stats", return_value="1.00%\t256MiB / 1GiB\t1kB / 2kB"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.list_plugins", return_value={"exists": True, "count": 4, "message": "ok"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.lint_server_config", return_value={"diagnostics": [{"severity": "warning", "priority": 46, "title": "Config issue", "category": "rcon_configuration", "source_type": "config", "source_name": "server.properties", "summary": "RCON disabled", "tags": ["config", "rcon"], "context": {"config_file": "server.properties", "key": "enable-rcon", "current_value": "false"}}], "summary": {"config_count": 5, "issue_count": 1, "item_count": 1, "warning_count": 1, "info_count": 0, "error_count": 0, "critical_count": 0}}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.analyze_recent_logs", side_effect=analyze_logs_stub):
            snapshot = get_server_snapshot()

        self.assertEqual(snapshot["status"]["container_status"], "running")
        self.assertEqual(snapshot["status"]["execution_mode"], "runtime")
        self.assertTrue(snapshot["status"]["rcon_responsive"])
        self.assertEqual(snapshot["stats"]["cpu_percent"], "1.00%")
        self.assertEqual(snapshot["plugin_summary"]["count"], 4)
        self.assertEqual(snapshot["config_summary"]["issue_count"], 1)
        self.assertEqual(snapshot["log_summary"]["finding_count"], 2)
        self.assertEqual(snapshot["log_summary"]["compact_summary"]["summary_text"], "Compact log summary for snapshot.")
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
        self.assertIn("Runtime snapshot", snapshot["summary"])
        self.assertIn("FancyPlugin", snapshot["summary"])
        self.assertIn("Main issues:", snapshot["summary"])

    def test_get_server_snapshot_uses_compact_log_summary_when_no_problem_groups_exist(self) -> None:
        def analyze_logs_stub(lines, include_archives=False, compact=False):
            if compact:
                return {
                    "scanned_lines": lines,
                    "archives_included": include_archives,
                    "detail_mode": "compact",
                    "log_files_scanned": [{"path": "logs/latest.log", "file_type": "log", "readable": True}],
                    "compact_summary": {
                        "summary_text": "Compact historical logs show no active issues and one resolved archive problem.",
                        "active_item_count": 0,
                        "resolved_item_count": 1,
                        "top_active_diagnostics": [],
                        "top_resolved_diagnostics": [{"category": "plugin_startup", "title": "Resolved plugin failure"}],
                        "repeated_patterns": [],
                        "top_categories": [],
                        "file_summary": {"scanned_count": 1, "archive_count": 0, "unreadable_count": 0, "latest_source": "logs/latest.log", "oldest_source": "logs/latest.log"},
                        "startup_summary": {"detected": True, "item_count": 0},
                    },
                    "summary": {"finding_count": 0, "item_count": 0, "error_count": 0, "warning_count": 0, "info_count": 0, "critical_count": 0, "message": "done"},
                    "diagnostics": [],
                }
            return {
                "scanned_lines": 200,
                "diagnostics": [],
                "summary": {"finding_count": 0, "item_count": 0, "error_count": 0, "warning_count": 0, "info_count": 0, "critical_count": 0, "message": "done"},
            }

        with patch("minecraft_diagnostic_mcp.services.snapshot_service.get_container_status", return_value="backup"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.resolve_execution_mode", return_value="backup"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_runtime_readiness", return_value={"execution_mode": "backup", "docker_available": False, "container_exists": False, "container_status": "backup", "logs_available": True}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_backup_readiness", return_value={"server_root": ".", "plugins_dir": "plugins", "plugins_available": True, "logs_available": True, "latest_log_path": "logs/latest.log"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_rcon_readiness", return_value={"execution_mode": "backup", "rcon_available": False, "rcon_responsive": False, "message": "backup mode"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.run_rcon_command", side_effect=RuntimeError("rcon failed")), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_server_stats", return_value=""), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.list_plugins", return_value={"exists": True, "count": 4, "message": "ok"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.lint_server_config", return_value={"diagnostics": [], "summary": {"config_count": 5, "issue_count": 0, "item_count": 0, "warning_count": 0, "info_count": 0, "error_count": 0, "critical_count": 0}}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.analyze_recent_logs", side_effect=analyze_logs_stub):
            snapshot = get_server_snapshot()

        self.assertEqual(snapshot["diagnostics"], [])
        self.assertEqual(snapshot["problem_groups"], [])
        self.assertIn("Backup snapshot", snapshot["summary"])
        self.assertIn("Compact historical logs show no active issues", snapshot["summary"])

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

    def test_get_server_snapshot_treats_resolved_historical_log_issue_as_lower_priority(self) -> None:
        with patch("minecraft_diagnostic_mcp.services.snapshot_service.get_container_status", return_value="backup"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.resolve_execution_mode", return_value="backup"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_runtime_readiness", return_value={"execution_mode": "backup", "docker_available": False, "container_exists": False, "container_status": "backup", "logs_available": True}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_backup_readiness", return_value={"server_root": ".", "plugins_dir": "plugins", "plugins_available": True, "logs_available": True, "latest_log_path": "logs/latest.log"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_rcon_readiness", return_value={"execution_mode": "backup", "rcon_available": False, "rcon_responsive": False, "message": "backup mode"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.run_rcon_command", side_effect=RuntimeError("rcon failed")), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_server_stats", return_value=""), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.list_plugins", return_value={"exists": True, "count": 4, "message": "ok"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.lint_server_config", return_value={"diagnostics": [{"severity": "warning", "priority": 53, "title": "RCON not enabled", "category": "rcon_configuration", "source_type": "config", "source_name": "server.properties", "summary": "RCON disabled", "tags": ["config", "rcon"], "context": {"config_file": "server.properties", "key": "enable-rcon", "current_value": "false"}}], "summary": {"config_count": 5, "issue_count": 1, "item_count": 1, "warning_count": 1, "info_count": 0, "error_count": 0, "critical_count": 0}}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.analyze_recent_logs", return_value={"scanned_lines": 200, "diagnostics": [{"severity": "error", "priority": 20, "title": "Plugin failed while enabling", "category": "plugin_startup", "source_type": "log", "source_name": "docker_logs", "summary": "Historical startup failure", "suspected_component": "Vulcan", "tags": ["log", "plugin", "startup", "historical", "resolved"], "context": {"plugin_name": "Vulcan", "historical_status": "resolved", "seen_in_latest_log": False, "last_seen_source": "logs/2026-03-18-1.log.gz"}}, {"severity": "warning", "priority": 53, "title": "RCON not enabled", "category": "rcon_configuration", "source_type": "config", "source_name": "server.properties", "summary": "RCON disabled", "tags": ["config", "rcon"], "context": {"config_file": "server.properties", "key": "enable-rcon", "current_value": "false"}}], "summary": {"finding_count": 2, "item_count": 2, "error_count": 1, "warning_count": 1, "info_count": 0, "critical_count": 0, "message": "done"}}):
            snapshot = get_server_snapshot()

        self.assertEqual(snapshot["diagnostics"][0]["category"], "rcon_configuration")
        resolved_group = next(group for group in snapshot["problem_groups"] if group["suspected_component"] == "Vulcan")
        self.assertIn("not seen in the newest log data", resolved_group["explanation"])
        self.assertIn("historical", resolved_group["primary_item"]["tags"])

    def test_get_server_snapshot_reuses_compact_pattern_naming_inside_problem_groups(self) -> None:
        def analyze_logs_stub(lines, include_archives=False, compact=False):
            if compact:
                return {
                    "scanned_lines": lines,
                    "archives_included": True,
                    "detail_mode": "compact",
                    "log_files_scanned": [{"path": "logs/latest.log", "file_type": "log", "readable": True}],
                    "compact_summary": {
                        "summary_text": "Compact log summary for snapshot.",
                        "active_item_count": 1,
                        "resolved_item_count": 0,
                        "top_active_diagnostics": [{"category": "missing_dependency", "title": "FancyPlugin missing PlaceholderAPI", "suspected_component": "FancyPlugin", "historical_status": "active", "issue_family": "missing_plugin_dependency_placeholderapi", "issue_label": "Missing plugin dependency PlaceholderAPI"}],
                        "top_resolved_diagnostics": [],
                        "repeated_patterns": [{"category": "missing_dependency", "title": "FancyPlugin missing PlaceholderAPI", "suspected_component": "FancyPlugin", "historical_status": "active", "issue_family": "missing_plugin_dependency_placeholderapi", "issue_label": "Missing plugin dependency PlaceholderAPI", "occurrence_count": 3}],
                        "top_categories": [{"category": "missing_dependency", "count": 1}],
                        "file_summary": {"scanned_count": 1, "archive_count": 0, "unreadable_count": 0, "latest_source": "logs/latest.log", "oldest_source": "logs/latest.log"},
                        "startup_summary": {"detected": True, "item_count": 1},
                    },
                    "summary": {"finding_count": 1, "item_count": 1, "error_count": 1, "warning_count": 0, "info_count": 0, "critical_count": 0, "message": "done"},
                    "diagnostics": [{"severity": "error", "priority": 82, "title": "Missing plugin dependency detected", "category": "missing_dependency", "source_type": "log", "source_name": "docker_logs", "summary": "Dependency missing", "suspected_component": "FancyPlugin", "tags": ["log", "dependency", "plugin"], "context": {"plugin_name": "FancyPlugin", "missing_target_type": "plugin_dependency", "missing_dependencies": ["PlaceholderAPI"], "likely_dependency_name": "PlaceholderAPI"}}],
                }
            return {
                "scanned_lines": 200,
                "diagnostics": [
                    {"severity": "error", "priority": 82, "title": "Missing plugin dependency detected", "category": "missing_dependency", "source_type": "log", "source_name": "docker_logs", "summary": "Dependency missing", "suspected_component": "FancyPlugin", "tags": ["log", "dependency", "plugin"], "context": {"plugin_name": "FancyPlugin", "missing_target_type": "plugin_dependency", "missing_dependencies": ["PlaceholderAPI"], "likely_dependency_name": "PlaceholderAPI"}}
                ],
                "summary": {"finding_count": 1, "item_count": 1, "error_count": 1, "warning_count": 0, "info_count": 0, "critical_count": 0, "message": "done"},
            }

        with patch("minecraft_diagnostic_mcp.services.snapshot_service.get_container_status", return_value="backup"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.resolve_execution_mode", return_value="backup"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_runtime_readiness", return_value={"execution_mode": "backup", "docker_available": False, "container_exists": False, "container_status": "backup", "logs_available": True}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_backup_readiness", return_value={"server_root": ".", "plugins_dir": "plugins", "plugins_available": True, "logs_available": True, "latest_log_path": "logs/latest.log"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_rcon_readiness", return_value={"execution_mode": "backup", "rcon_available": False, "rcon_responsive": False, "message": "backup mode"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.run_rcon_command", side_effect=RuntimeError("rcon failed")), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_server_stats", return_value=""), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.list_plugins", return_value={"exists": True, "count": 4, "message": "ok"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.lint_server_config", return_value={"diagnostics": [], "summary": {"config_count": 5, "issue_count": 0, "item_count": 0, "warning_count": 0, "info_count": 0, "error_count": 0, "critical_count": 0}}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.analyze_recent_logs", side_effect=analyze_logs_stub):
            snapshot = get_server_snapshot()

        group = snapshot["problem_groups"][0]
        self.assertEqual(group["title"], "FancyPlugin missing PlaceholderAPI")
        self.assertEqual(group["context"]["compact_issue_label"], "Missing plugin dependency PlaceholderAPI")
        self.assertIn("Compact log pattern", group["summary"])

    def test_get_server_snapshot_explains_dependency_present_but_unusable(self) -> None:
        with patch("minecraft_diagnostic_mcp.services.snapshot_service.get_container_status", return_value="backup"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.resolve_execution_mode", return_value="backup"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_runtime_readiness", return_value={"execution_mode": "backup", "docker_available": False, "container_exists": False, "container_status": "backup", "logs_available": True}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_backup_readiness", return_value={"server_root": ".", "plugins_dir": "plugins", "plugins_available": True, "logs_available": True, "latest_log_path": "logs/latest.log"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_rcon_readiness", return_value={"execution_mode": "backup", "rcon_available": False, "rcon_responsive": False, "message": "backup mode"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.run_rcon_command", side_effect=RuntimeError("rcon failed")), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_server_stats", return_value=""), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.list_plugins", return_value={"exists": True, "count": 4, "message": "ok"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.lint_server_config", return_value={"diagnostics": [], "summary": {"config_count": 5, "issue_count": 0, "item_count": 0, "warning_count": 0, "info_count": 0, "error_count": 0, "critical_count": 0}}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.analyze_recent_logs", return_value={"scanned_lines": 200, "diagnostics": [{"severity": "error", "priority": 82, "title": "Missing plugin dependency detected", "category": "missing_dependency", "source_type": "log", "source_name": "docker_logs", "summary": "Dependency missing", "suspected_component": "FancyPlugin", "tags": ["log", "dependency", "plugin", "dependency_present"], "context": {"plugin_name": "FancyPlugin", "missing_target_type": "plugin_dependency", "likely_dependency_name": "PlaceholderAPI", "likely_dependency_found_in_inventory": True, "missing_dependencies": ["PlaceholderAPI"]}}], "summary": {"finding_count": 1, "item_count": 1, "error_count": 1, "warning_count": 0, "info_count": 0, "critical_count": 0, "message": "done"}}):
            snapshot = get_server_snapshot()

        group = snapshot["problem_groups"][0]
        self.assertIn("already installed", group["explanation"])
        self.assertIn("compatible versions", group["recommended_action"])

    def test_get_server_snapshot_explains_high_signal_log_categories(self) -> None:
        with patch("minecraft_diagnostic_mcp.services.snapshot_service.get_container_status", return_value="backup"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.resolve_execution_mode", return_value="backup"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_runtime_readiness", return_value={"execution_mode": "backup", "docker_available": False, "container_exists": False, "container_status": "backup", "logs_available": True}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_backup_readiness", return_value={"server_root": ".", "plugins_dir": "plugins", "plugins_available": True, "logs_available": True, "latest_log_path": "logs/latest.log"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_rcon_readiness", return_value={"execution_mode": "backup", "rcon_available": False, "rcon_responsive": False, "message": "backup mode"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.run_rcon_command", side_effect=RuntimeError("rcon failed")), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_server_stats", return_value=""), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.list_plugins", return_value={"exists": True, "count": 4, "message": "ok"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.lint_server_config", return_value={"diagnostics": [], "summary": {"config_count": 5, "issue_count": 0, "item_count": 0, "warning_count": 0, "info_count": 0, "error_count": 0, "critical_count": 0}}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.analyze_recent_logs", return_value={"scanned_lines": 200, "diagnostics": [{"severity": "error", "priority": 81, "title": "SQLite data corruption detected", "category": "data_integrity_error", "source_type": "log", "source_name": "docker_logs", "summary": "SQLite corruption", "suspected_component": "PyroFishingPro", "tags": ["log", "database", "sqlite", "integrity"], "context": {"plugin_name": "PyroFishingPro"}}, {"severity": "error", "priority": 80, "title": "Plugin manifest is invalid", "category": "plugin_manifest_error", "source_type": "log", "source_name": "docker_logs", "summary": "Bad manifest", "suspected_component": "PlugManX", "tags": ["log", "plugin", "manifest"], "context": {"plugin_name": "PlugManX"}}], "summary": {"finding_count": 2, "item_count": 2, "error_count": 2, "warning_count": 0, "info_count": 0, "critical_count": 0, "message": "done"}}):
            snapshot = get_server_snapshot()

        integrity_group = next(group for group in snapshot["problem_groups"] if group["primary_item"]["category"] == "data_integrity_error")
        manifest_group = next(group for group in snapshot["problem_groups"] if group["primary_item"]["category"] == "plugin_manifest_error")
        self.assertIn("SQLite or on-disk data corruption", integrity_group["explanation"])
        self.assertIn("repair", integrity_group["recommended_action"])
        self.assertIn("invalid plugin manifest", manifest_group["explanation"])
        self.assertIn("valid plugin build", manifest_group["recommended_action"])

    def test_get_server_snapshot_reuses_compact_startup_pattern_label_when_specific(self) -> None:
        def analyze_logs_stub(lines, include_archives=False, compact=False):
            if compact:
                return {
                    "scanned_lines": lines,
                    "archives_included": True,
                    "detail_mode": "compact",
                    "log_files_scanned": [{"path": "logs/latest.log", "file_type": "log", "readable": True}],
                    "compact_summary": {
                        "summary_text": "Compact startup warning summary.",
                        "active_item_count": 1,
                        "resolved_item_count": 0,
                        "top_active_diagnostics": [{"category": "plugin_compatibility_warning", "title": "DeluxeMenus: Server version hook unavailable pattern", "suspected_component": "DeluxeMenus", "historical_status": "active", "issue_family": "server_hook_unavailable", "issue_label": "Server version hook unavailable"}],
                        "top_resolved_diagnostics": [],
                        "repeated_patterns": [{"category": "plugin_compatibility_warning", "title": "DeluxeMenus: Server version hook unavailable pattern", "suspected_component": "DeluxeMenus", "historical_status": "active", "issue_family": "server_hook_unavailable", "issue_label": "Server version hook unavailable", "occurrence_count": 2}],
                        "top_categories": [{"category": "plugin_compatibility_warning", "count": 1}],
                        "file_summary": {"scanned_count": 1, "archive_count": 0, "unreadable_count": 0, "latest_source": "logs/latest.log", "oldest_source": "logs/latest.log"},
                        "startup_summary": {"detected": True, "item_count": 1},
                    },
                    "summary": {"finding_count": 1, "item_count": 1, "error_count": 0, "warning_count": 1, "info_count": 0, "critical_count": 0, "message": "done"},
                    "diagnostics": [{"severity": "warning", "priority": 52, "title": "Plugin compatibility warning", "category": "plugin_compatibility_warning", "source_type": "log", "source_name": "docker_logs", "summary": "Compatibility limit", "suspected_component": "DeluxeMenus", "tags": ["log", "startup", "plugin", "compatibility"], "context": {"plugin_name": "DeluxeMenus"}}],
                }
            return {
                "scanned_lines": 200,
                "diagnostics": [
                    {"severity": "warning", "priority": 52, "title": "Plugin compatibility warning", "category": "plugin_compatibility_warning", "source_type": "log", "source_name": "docker_logs", "summary": "Compatibility limit", "suspected_component": "DeluxeMenus", "tags": ["log", "startup", "plugin", "compatibility"], "context": {"plugin_name": "DeluxeMenus"}}
                ],
                "summary": {"finding_count": 1, "item_count": 1, "error_count": 0, "warning_count": 1, "info_count": 0, "critical_count": 0, "message": "done"},
            }

        with patch("minecraft_diagnostic_mcp.services.snapshot_service.get_container_status", return_value="backup"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.resolve_execution_mode", return_value="backup"), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_runtime_readiness", return_value={"execution_mode": "backup", "docker_available": False, "container_exists": False, "container_status": "backup", "logs_available": True}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_backup_readiness", return_value={"server_root": ".", "plugins_dir": "plugins", "plugins_available": True, "logs_available": True, "latest_log_path": "logs/latest.log"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_rcon_readiness", return_value={"execution_mode": "backup", "rcon_available": False, "rcon_responsive": False, "message": "backup mode"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.run_rcon_command", side_effect=RuntimeError("rcon failed")), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.get_server_stats", return_value=""), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.list_plugins", return_value={"exists": True, "count": 4, "message": "ok"}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.lint_server_config", return_value={"diagnostics": [], "summary": {"config_count": 5, "issue_count": 0, "item_count": 0, "warning_count": 0, "info_count": 0, "error_count": 0, "critical_count": 0}}), \
             patch("minecraft_diagnostic_mcp.services.snapshot_service.analyze_recent_logs", side_effect=analyze_logs_stub):
            snapshot = get_server_snapshot()

        group = snapshot["problem_groups"][0]
        self.assertEqual(group["title"], "DeluxeMenus: Server version hook unavailable pattern")
        self.assertEqual(group["context"]["compact_issue_family"], "server_hook_unavailable")


if __name__ == "__main__":
    unittest.main()
