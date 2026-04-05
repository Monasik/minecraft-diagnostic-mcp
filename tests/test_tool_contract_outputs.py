import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.tools.diagnostic_tools import (
    analyze_recent_logs,
    extract_raw_logs,
    get_server_snapshot,
    incident_timeline,
    inspect_plugin,
    lint_server_config,
    list_cant_keep_up_events,
    list_log_sources,
    list_player_commands,
    list_plugins,
    list_stacktrace_plugins,
    list_watchdog_dumps,
    search_logs,
)


class ToolContractOutputTests(unittest.TestCase):
    def test_list_plugins_output_keeps_expected_top_level_fields(self) -> None:
        with patch(
            "minecraft_diagnostic_mcp.tools.diagnostic_tools.list_plugins_service",
            return_value={"plugins_dir": "plugins", "exists": True, "count": 1, "message": "ok", "plugins": [{"name": "FancyPlugin"}]},
        ):
            result = list_plugins()

        self.assertTrue({"plugins_dir", "exists", "count", "message", "plugins"} <= set(result))

    def test_inspect_plugin_output_keeps_expected_top_level_fields(self) -> None:
        with patch(
            "minecraft_diagnostic_mcp.tools.diagnostic_tools.get_plugin_by_name",
            return_value={
                "plugins_dir": "plugins",
                "exists": True,
                "plugin_found": True,
                "query": "FancyPlugin",
                "message": "Plugin found.",
                "plugin": {"name": "FancyPlugin"},
                "diagnostics": [],
            },
        ):
            result = inspect_plugin("FancyPlugin")

        self.assertTrue({"plugins_dir", "exists", "plugin_found", "query", "message", "plugin", "diagnostics"} <= set(result))

    def test_lint_server_config_output_keeps_expected_top_level_fields(self) -> None:
        with patch(
            "minecraft_diagnostic_mcp.tools.diagnostic_tools.lint_server_config_service",
            return_value={
                "config_files": [],
                "diagnostics": [],
                "summary": {
                    "config_count": 1,
                    "item_count": 0,
                    "issue_count": 0,
                    "info_count": 0,
                    "warning_count": 0,
                    "error_count": 0,
                    "critical_count": 0,
                    "message": "ok",
                },
            },
        ):
            result = lint_server_config()

        self.assertTrue({"config_files", "diagnostics", "summary"} <= set(result))
        self.assertTrue({"config_count", "item_count", "issue_count", "info_count", "warning_count", "error_count", "critical_count", "message"} <= set(result["summary"]))

    def test_analyze_recent_logs_output_keeps_expected_top_level_fields(self) -> None:
        with patch(
            "minecraft_diagnostic_mcp.tools.diagnostic_tools.analyze_recent_logs_service",
            return_value={
                "scanned_lines": 200,
                "archives_included": True,
                "detail_mode": "compact",
                "log_files_scanned": [],
                "startup_window": {"detected": True},
                "log_category_counts": {"plugin_startup": 1},
                "compact_summary": {"summary_text": "ok"},
                "summary": {
                    "record_count": 10,
                    "item_count": 1,
                    "finding_count": 1,
                    "info_count": 0,
                    "warning_count": 0,
                    "error_count": 1,
                    "critical_count": 0,
                    "message": "ok",
                },
                "diagnostics": [],
            },
        ):
            result = analyze_recent_logs(lines=200, include_archives=True, compact=True)

        self.assertTrue({"scanned_lines", "archives_included", "detail_mode", "log_files_scanned", "summary", "diagnostics"} <= set(result))
        self.assertIn("compact_summary", result)
        self.assertIn("startup_window", result)
        self.assertIn("log_category_counts", result)
        self.assertTrue({"record_count", "item_count", "finding_count", "info_count", "warning_count", "error_count", "critical_count", "message"} <= set(result["summary"]))

    def test_get_server_snapshot_output_keeps_expected_top_level_fields(self) -> None:
        with patch(
            "minecraft_diagnostic_mcp.tools.diagnostic_tools.get_server_snapshot_service",
            return_value={
                "status": {"execution_mode": "backup"},
                "stats": {"cpu_percent": None, "memory_usage": None, "net_io": None},
                "plugin_summary": {"exists": True, "count": 1},
                "config_summary": {"config_count": 1, "item_count": 0},
                "log_summary": {"scanned_lines": 200, "item_count": 0},
                "diagnostics": [],
                "problem_groups": [],
                "summary": "ok",
            },
        ):
            result = get_server_snapshot()

        self.assertTrue({"status", "stats", "plugin_summary", "config_summary", "log_summary", "diagnostics", "problem_groups", "summary"} <= set(result))

    def test_list_log_sources_output_keeps_expected_top_level_fields(self) -> None:
        with patch(
            "minecraft_diagnostic_mcp.tools.diagnostic_tools.list_log_sources_service",
            return_value={
                "source": "archives",
                "date": "2026-04-03",
                "source_count": 1,
                "sources": [],
                "precision": {"guaranteed": True, "notices": []},
            },
        ):
            result = list_log_sources()

        self.assertTrue({"source", "date", "source_count", "sources", "precision"} <= set(result))

    def test_extract_raw_logs_output_keeps_expected_top_level_fields(self) -> None:
        with patch(
            "minecraft_diagnostic_mcp.tools.diagnostic_tools.extract_raw_logs_service",
            return_value={
                "source": "file:2026-04-03-1.log.gz",
                "mode": "full_raw",
                "filters": {},
                "matched_record_count": 1,
                "matched_line_count": 10,
                "truncated": False,
                "files_scanned": [],
                "records": [],
                "precision": {"guaranteed": True, "notices": []},
            },
        ):
            result = extract_raw_logs()

        self.assertTrue({"source", "mode", "filters", "matched_record_count", "matched_line_count", "truncated", "files_scanned", "records", "precision"} <= set(result))

    def test_search_logs_output_keeps_expected_top_level_fields(self) -> None:
        with patch(
            "minecraft_diagnostic_mcp.tools.diagnostic_tools.search_logs_service",
            return_value={
                "source": "archives",
                "mode": "full",
                "filters": {},
                "matched_record_count": 1,
                "matched_line_count": 3,
                "truncated": False,
                "files_scanned": [],
                "records": [],
                "precision": {"guaranteed": True, "notices": []},
            },
        ):
            result = search_logs()

        self.assertTrue({"source", "mode", "filters", "matched_record_count", "matched_line_count", "truncated", "files_scanned", "records", "precision"} <= set(result))

    def test_incident_timeline_output_keeps_expected_top_level_fields(self) -> None:
        with patch(
            "minecraft_diagnostic_mcp.tools.diagnostic_tools.incident_timeline_service",
            return_value={
                "source": "archives",
                "incident_found": True,
                "incident_timestamp": "2026-04-03 22:35:29",
                "filters": {},
                "anchor_record": {},
                "preceding_player_actions": [],
                "relevant_plugin_stacktraces": [],
                "following_recovery_events": [],
                "records": [],
                "precision": {"guaranteed": True, "notices": []},
            },
        ):
            result = incident_timeline()

        self.assertTrue({"source", "incident_found", "incident_timestamp", "filters", "anchor_record", "preceding_player_actions", "relevant_plugin_stacktraces", "following_recovery_events", "records", "precision"} <= set(result))

    def test_helper_tool_outputs_keep_expected_top_level_fields(self) -> None:
        with patch(
            "minecraft_diagnostic_mcp.tools.diagnostic_tools.list_cant_keep_up_events_service",
            return_value={"matched_record_count": 1, "records": [], "precision": {"guaranteed": True, "notices": []}},
        ), patch(
            "minecraft_diagnostic_mcp.tools.diagnostic_tools.list_watchdog_dumps_service",
            return_value={"matched_record_count": 1, "records": [], "precision": {"guaranteed": True, "notices": []}},
        ), patch(
            "minecraft_diagnostic_mcp.tools.diagnostic_tools.list_stacktrace_plugins_service",
            return_value={"plugin_count": 1, "plugins": [], "files_scanned": [], "precision": {"guaranteed": True, "notices": []}},
        ), patch(
            "minecraft_diagnostic_mcp.tools.diagnostic_tools.list_player_commands_service",
            return_value={"command_count": 1, "commands": [], "precision": {"guaranteed": True, "notices": []}},
        ):
            lag_result = list_cant_keep_up_events()
            watchdog_result = list_watchdog_dumps()
            plugins_result = list_stacktrace_plugins()
            commands_result = list_player_commands()

        self.assertTrue({"matched_record_count", "records", "precision"} <= set(lag_result))
        self.assertTrue({"matched_record_count", "records", "precision"} <= set(watchdog_result))
        self.assertTrue({"plugin_count", "plugins", "files_scanned", "precision"} <= set(plugins_result))
        self.assertTrue({"command_count", "commands", "precision"} <= set(commands_result))


if __name__ == "__main__":
    unittest.main()
