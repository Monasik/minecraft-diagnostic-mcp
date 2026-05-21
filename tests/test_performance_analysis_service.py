import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.services.performance_analysis_service import analyze_performance


class PerformanceAnalysisServiceTests(unittest.TestCase):
    def test_analyze_performance_aggregates_categories_and_runtime_stats(self) -> None:
        full_result = {
            "diagnostics": [
                {"category": "performance_warning", "suspected_component": "server", "source_name": "docker_logs"},
                {"category": "operational_movement_warning", "suspected_component": "server", "source_name": "docker_logs"},
                {"category": "monitoring_warning", "suspected_component": "spark", "source_name": "docker_logs"},
            ],
            "scanned_lines": 2000,
            "archives_included": True,
        }
        compact_result = {
            "compact_summary": {
                "repeated_patterns": [
                    {"category": "performance_warning", "title": "Server tick lag detected"},
                    {"category": "operational_movement_warning", "title": "Player movement warning"},
                ]
            }
        }

        with patch("minecraft_diagnostic_mcp.services.performance_analysis_service.analyze_recent_logs", side_effect=[full_result, compact_result]), \
             patch("minecraft_diagnostic_mcp.services.performance_analysis_service.get_server_stats", return_value="8.0%\t1.2GiB\t10kB/s / 5kB/s"), \
             patch("minecraft_diagnostic_mcp.services.performance_analysis_service.resolve_execution_mode", return_value="runtime"):
            result = analyze_performance()

        self.assertEqual(result["performance_item_count"], 3)
        self.assertEqual(result["category_counts"]["performance_warning"], 1)
        self.assertTrue(result["runtime_stats"]["available"])
        self.assertEqual(len(result["top_patterns"]), 2)


if __name__ == "__main__":
    unittest.main()
