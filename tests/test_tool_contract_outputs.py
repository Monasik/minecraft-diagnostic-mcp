import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.tools.diagnostic_tools import (
    analyze_recent_logs,
    get_server_snapshot,
    inspect_plugin,
    lint_server_config,
    list_plugins,
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


if __name__ == "__main__":
    unittest.main()
