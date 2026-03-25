import unittest
from pathlib import Path
import gzip
import tempfile
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.services.log_analysis_service import analyze_recent_logs


class LogAnalysisServiceTests(unittest.TestCase):
    def test_analyze_recent_logs_includes_startup_findings_from_latest_log(self) -> None:
        recent_log = "\n".join(
            [
                "[22:28:48] [Server thread/WARN]: Brumiiczekk moved too quickly! -1,2,3",
                "[22:36:06] [Server thread/WARN]: Can't keep up! Is the server overloaded? Running 2638ms or 52 ticks behind",
            ]
        )
        full_log = "\n".join(
            [
                "[21:33:19] [Server thread/INFO]: Starting minecraft server version 1.21.8",
                "[21:33:30] [Server thread/WARN]: [DeluxeMenus] Could not setup a NMS hook for your server version!",
                '[21:33:41] [Server thread/WARN]: **** SERVER IS RUNNING IN OFFLINE/INSECURE MODE!',
                '[21:34:33] [Server thread/INFO]: Done (98.510s)! For help, type "help"',
                "[22:28:48] [Server thread/WARN]: Brumiiczekk moved too quickly! -1,2,3",
            ]
        )

        with patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_recent_logs", return_value=recent_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_latest_log_path", return_value=Path("latest.log")), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.read_text_file", return_value=full_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_plugins", return_value={"plugins": []}):
            result = analyze_recent_logs(50)

        categories = [item["category"] for item in result["diagnostics"]]
        self.assertIn("startup_security_warning", categories)
        self.assertIn("plugin_compatibility_warning", categories)
        self.assertIn("operational_movement_warning", categories)
        self.assertTrue(result["startup_window"]["detected"])
        self.assertTrue(result["startup_window"]["completed"])
        self.assertGreaterEqual(result["startup_window"]["item_count"], 2)

    def test_analyze_recent_logs_can_include_archives(self) -> None:
        recent_log = "[22:36:06] [Server thread/WARN]: Can't keep up! Is the server overloaded? Running 2638ms or 52 ticks behind\n"
        full_log = "\n".join(
            [
                "[21:33:19] [Server thread/INFO]: Starting minecraft server version 1.21.8",
                '[21:34:33] [Server thread/INFO]: Done (98.510s)! For help, type "help"',
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "2026-03-10-1.log.gz"
            with gzip.open(archive_path, "wt", encoding="utf-8") as handle:
                handle.write("[20:00:00] [Server thread/ERROR]: [PlugManX] Error reading plugin description: No name field found in plugin.yml\n")

            with patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_recent_logs", return_value=recent_log), \
                 patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_latest_log_path", return_value=Path("latest.log")), \
                 patch("minecraft_diagnostic_mcp.services.log_analysis_service.read_text_file", return_value=full_log), \
                 patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_plugins", return_value={"plugins": [{"name": "PlugManX"}]}), \
                 patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_log_files", return_value=[]):
                with patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_log_files", return_value=[
                    type("LogFileInfo", (), {"path": str(archive_path), "file_type": "log.gz", "readable": True, "modified_time": None})()
                ]):
                    result = analyze_recent_logs(50, include_archives=True)

        categories = [item["category"] for item in result["diagnostics"]]
        self.assertIn("log_error", categories)
        self.assertTrue(result["archives_included"])
        self.assertEqual(len(result["log_files_scanned"]), 1)
        self.assertEqual(result["log_files_scanned"][0]["file_type"], "log.gz")

    def test_analyze_recent_logs_marks_old_error_as_resolved_when_absent_from_latest(self) -> None:
        recent_log = "[22:36:06] [Server thread/INFO]: Regular runtime line\n"
        full_log = "\n".join(
            [
                "[21:33:19] [Server thread/INFO]: Starting minecraft server version 1.21.8",
                '[21:34:33] [Server thread/INFO]: Done (98.510s)! For help, type "help"',
                "[22:36:06] [Server thread/INFO]: Server still running cleanly",
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "2026-03-10-1.log.gz"
            with gzip.open(archive_path, "wt", encoding="utf-8") as handle:
                handle.write("[20:00:00] [Server thread/ERROR]: Error occurred while enabling Vulcan v2.9.7.16 (Is it up to date?)\n")

            with patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_recent_logs", return_value=recent_log), \
                 patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_latest_log_path", return_value=Path("latest.log")), \
                 patch("minecraft_diagnostic_mcp.services.log_analysis_service.read_text_file", return_value=full_log), \
                 patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_plugins", return_value={"plugins": [{"name": "Vulcan"}]}), \
                 patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_log_files", return_value=[
                     type("LogFileInfo", (), {"path": str(archive_path), "file_type": "log.gz", "readable": True, "modified_time": None})()
                 ]):
                result = analyze_recent_logs(50, include_archives=True)

        vulcan_item = next(item for item in result["diagnostics"] if item["suspected_component"] == "Vulcan")
        self.assertEqual(vulcan_item["context"]["historical_status"], "resolved")
        self.assertFalse(vulcan_item["context"]["seen_in_latest_log"])
        self.assertIn("resolved", vulcan_item["tags"])

    def test_analyze_recent_logs_compact_mode_returns_condensed_payload(self) -> None:
        recent_log = "\n".join(
            [
                "[22:36:06] [Server thread/WARN]: Can't keep up! Is the server overloaded? Running 2638ms or 52 ticks behind",
                "[22:36:10] [Server thread/WARN]: Can't keep up! Is the server overloaded? Running 2100ms or 42 ticks behind",
                "[22:36:12] [Server thread/WARN]: Brumiiczekk moved too quickly! -1,2,3",
            ]
        )
        full_log = "\n".join(
            [
                "[21:33:19] [Server thread/INFO]: Starting minecraft server version 1.21.8",
                '[21:34:33] [Server thread/INFO]: Done (98.510s)! For help, type "help"',
            ]
        )

        with patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_recent_logs", return_value=recent_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_latest_log_path", return_value=Path("latest.log")), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.read_text_file", return_value=full_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_plugins", return_value={"plugins": []}):
            result = analyze_recent_logs(50, compact=True)

        self.assertEqual(result["detail_mode"], "compact")
        self.assertIn("compact_summary", result)
        self.assertIn("summary_text", result["compact_summary"])
        self.assertLessEqual(len(result["diagnostics"]), 8)
        self.assertEqual(
            result["diagnostics"][0]["category"],
            "performance_warning",
        )
        self.assertGreaterEqual(len(result["compact_summary"]["repeated_patterns"]), 1)
        self.assertIn("Scanned", result["compact_summary"]["summary_text"])
        self.assertIn("Active now:", result["compact_summary"]["summary_text"])

    def test_analyze_recent_logs_compact_mode_keeps_resolved_items_out_of_top_active(self) -> None:
        recent_log = "[22:36:06] [Server thread/INFO]: Runtime line\n"
        full_log = "\n".join(
            [
                "[21:33:19] [Server thread/INFO]: Starting minecraft server version 1.21.8",
                '[21:34:33] [Server thread/INFO]: Done (98.510s)! For help, type "help"',
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "2026-03-10-1.log.gz"
            with gzip.open(archive_path, "wt", encoding="utf-8") as handle:
                handle.write("[20:00:00] [Server thread/ERROR]: Error occurred while enabling Vulcan v2.9.7.16 (Is it up to date?)\n")

            with patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_recent_logs", return_value=recent_log), \
                 patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_latest_log_path", return_value=Path("latest.log")), \
                 patch("minecraft_diagnostic_mcp.services.log_analysis_service.read_text_file", return_value=full_log), \
                 patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_plugins", return_value={"plugins": [{"name": "Vulcan"}]}), \
                 patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_log_files", return_value=[
                     type("LogFileInfo", (), {"path": str(archive_path), "file_type": "log.gz", "readable": True, "modified_time": None})()
                 ]):
                result = analyze_recent_logs(50, include_archives=True, compact=True)

        self.assertEqual(result["detail_mode"], "compact")
        self.assertEqual(result["compact_summary"]["active_item_count"], 0)
        self.assertGreaterEqual(result["compact_summary"]["resolved_item_count"], 1)
        self.assertEqual(result["compact_summary"]["top_active_diagnostics"], [])
        self.assertEqual(result["compact_summary"]["top_resolved_diagnostics"][0]["context"]["historical_status"], "resolved")

    def test_compact_repeated_patterns_prefers_specific_problem_over_generic_warning(self) -> None:
        recent_log = "\n".join(
            [
                "[22:36:01] [Server thread/WARN]: Generic warning text one",
                "[22:36:02] [Server thread/WARN]: Generic warning text two",
                "[22:36:03] [Server thread/WARN]: Generic warning text three",
                "[22:36:04] [Server thread/ERROR]: Error occurred while enabling Vulcan v2.9.7.16 (Is it up to date?)",
                "[22:36:05] [Server thread/ERROR]: Error occurred while enabling Vulcan v2.9.7.16 (Is it up to date?)",
            ]
        )
        full_log = "\n".join(
            [
                "[21:33:19] [Server thread/INFO]: Starting minecraft server version 1.21.8",
                '[21:34:33] [Server thread/INFO]: Done (98.510s)! For help, type "help"',
            ]
        )

        with patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_recent_logs", return_value=recent_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_latest_log_path", return_value=Path("latest.log")), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.read_text_file", return_value=full_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_plugins", return_value={"plugins": [{"name": "Vulcan"}]}):
            result = analyze_recent_logs(50, compact=True)

        repeated = result["compact_summary"]["repeated_patterns"]
        self.assertGreaterEqual(len(repeated), 1)
        self.assertEqual(repeated[0]["category"], "plugin_startup")
        self.assertEqual(repeated[0]["suspected_component"], "Vulcan")

    def test_compact_repeated_patterns_suppresses_generic_global_patterns_when_specific_ones_exist(self) -> None:
        recent_log = "\n".join(
            [
                "[22:36:01] [Server thread/WARN]: Generic warning text one",
                "[22:36:02] [Server thread/WARN]: Generic warning text two",
                "[22:36:03] [Server thread/ERROR]: Error occurred while enabling Vulcan v2.9.7.16 (Is it up to date?)",
                "[22:36:04] [Server thread/ERROR]: Error occurred while enabling Vulcan v2.9.7.16 (Is it up to date?)",
                "[22:36:05] [Server thread/ERROR]: [PyroFishingPro] Something bad happened",
                "[22:36:06] [Server thread/ERROR]: [PyroFishingPro] Something bad happened",
            ]
        )
        full_log = "\n".join(
            [
                "[21:33:19] [Server thread/INFO]: Starting minecraft server version 1.21.8",
                '[21:34:33] [Server thread/INFO]: Done (98.510s)! For help, type "help"',
            ]
        )

        with patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_recent_logs", return_value=recent_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_latest_log_path", return_value=Path("latest.log")), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.read_text_file", return_value=full_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_plugins", return_value={"plugins": [{"name": "Vulcan"}, {"name": "PyroFishingPro"}]}):
            result = analyze_recent_logs(50, compact=True)

        repeated = result["compact_summary"]["repeated_patterns"]
        self.assertTrue(all(not (item["category"] == "log_warning" and item["suspected_component"] is None) for item in repeated))

    def test_compact_repeated_patterns_promotes_generic_error_to_incident_like_title(self) -> None:
        recent_log = "\n".join(
            [
                "[22:36:05] [Server thread/ERROR]: [PyroFishingPro] org.sqlite.SQLiteException: [SQLITE_CORRUPT] The database disk image is malformed",
                "[22:36:06] [Server thread/ERROR]: [PyroFishingPro] org.sqlite.SQLiteException: [SQLITE_CORRUPT] The database disk image is malformed",
            ]
        )
        full_log = "\n".join(
            [
                "[21:33:19] [Server thread/INFO]: Starting minecraft server version 1.21.8",
                '[21:34:33] [Server thread/INFO]: Done (98.510s)! For help, type "help"',
            ]
        )

        with patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_recent_logs", return_value=recent_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_latest_log_path", return_value=Path("latest.log")), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.read_text_file", return_value=full_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_plugins", return_value={"plugins": [{"name": "PyroFishingPro"}]}):
            result = analyze_recent_logs(50, compact=True)

        repeated = result["compact_summary"]["repeated_patterns"]
        self.assertGreaterEqual(len(repeated), 1)
        self.assertEqual(repeated[0]["issue_family"], "sqlite_corruption")
        self.assertEqual(repeated[0]["issue_label"], "SQLite corruption")
        self.assertIn("PyroFishingPro", repeated[0]["title"])
        self.assertIn("SQLite corruption pattern", repeated[0]["title"])
        self.assertNotIn("UUID", repeated[0]["title"])

    def test_compact_repeated_patterns_humanizes_player_save_failure(self) -> None:
        recent_log = "\n".join(
            [
                "[22:36:05] [Server thread/ERROR]: [PyroFishingPro] Player had an error when saving user data",
                "[22:36:06] [Server thread/ERROR]: [PyroFishingPro] Player had an error when saving user data",
            ]
        )
        full_log = "\n".join(
            [
                "[21:33:19] [Server thread/INFO]: Starting minecraft server version 1.21.8",
                '[21:34:33] [Server thread/INFO]: Done (98.510s)! For help, type "help"',
            ]
        )

        with patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_recent_logs", return_value=recent_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_latest_log_path", return_value=Path("latest.log")), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.read_text_file", return_value=full_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_plugins", return_value={"plugins": [{"name": "PyroFishingPro"}]}):
            result = analyze_recent_logs(50, compact=True)

        repeated = result["compact_summary"]["repeated_patterns"]
        self.assertGreaterEqual(len(repeated), 1)
        self.assertEqual(repeated[0]["issue_family"], "player_save_failure")
        self.assertEqual(repeated[0]["issue_label"], "Player save failure")
        self.assertIn("Player save failure pattern", repeated[0]["title"])

    def test_compact_repeated_patterns_humanizes_packetevents_unhandled_exception(self) -> None:
        recent_log = "\n".join(
            [
                "[22:36:05] [Server thread/WARN]: [com.github.retrooper.packetevents.PacketEventsAPI] PacketEvents caught unhandled exception calling event",
                "[22:36:06] [Server thread/WARN]: [com.github.retrooper.packetevents.PacketEventsAPI] PacketEvents caught unhandled exception calling event",
            ]
        )
        full_log = "\n".join(
            [
                "[21:33:19] [Server thread/INFO]: Starting minecraft server version 1.21.8",
                '[21:34:33] [Server thread/INFO]: Done (98.510s)! For help, type "help"',
            ]
        )

        with patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_recent_logs", return_value=recent_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_latest_log_path", return_value=Path("latest.log")), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.read_text_file", return_value=full_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_plugins", return_value={"plugins": []}):
            result = analyze_recent_logs(50, compact=True)

        repeated = result["compact_summary"]["repeated_patterns"]
        self.assertGreaterEqual(len(repeated), 1)
        self.assertEqual(repeated[0]["issue_family"], "packet_handling_failure")
        self.assertEqual(repeated[0]["issue_label"], "Packet handling failure")
        self.assertIn("Packet handling failure pattern", repeated[0]["title"])
        self.assertIn("PacketEventsAPI", repeated[0]["title"])

    def test_compact_repeated_patterns_humanizes_missing_dependency_from_context(self) -> None:
        recent_log = "\n".join(
            [
                "[22:36:05] [Server thread/ERROR]: java.lang.NoClassDefFoundError: me.clip.placeholderapi.PlaceholderAPI",
                "[22:36:06] [Server thread/ERROR]: java.lang.NoClassDefFoundError: me.clip.placeholderapi.PlaceholderAPI",
            ]
        )
        full_log = "\n".join(
            [
                "[21:33:19] [Server thread/INFO]: Starting minecraft server version 1.21.8",
                '[21:34:33] [Server thread/INFO]: Done (98.510s)! For help, type "help"',
            ]
        )

        with patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_recent_logs", return_value=recent_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_latest_log_path", return_value=Path("latest.log")), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.read_text_file", return_value=full_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_plugins", return_value={"plugins": [{"name": "FancyPlugin"}]}):
            result = analyze_recent_logs(50, compact=True)

        repeated = result["compact_summary"]["repeated_patterns"]
        self.assertGreaterEqual(len(repeated), 1)
        self.assertIn("Missing plugin dependency PlaceholderAPI", repeated[0]["title"])

    def test_analyze_recent_logs_marks_likely_dependency_as_present_when_inventory_contains_it(self) -> None:
        recent_log = "java.lang.NoClassDefFoundError: me/clip/placeholderapi/PlaceholderAPI\n"
        full_log = "\n".join(
            [
                "[21:33:19] [Server thread/INFO]: Starting minecraft server version 1.21.8",
                '[21:34:33] [Server thread/INFO]: Done (98.510s)! For help, type "help"',
            ]
        )

        with patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_recent_logs", return_value=recent_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_latest_log_path", return_value=Path("latest.log")), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.read_text_file", return_value=full_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_plugins", return_value={"plugins": [{"name": "FancyPlugin"}, {"name": "PlaceholderAPI"}]}):
            result = analyze_recent_logs(50)

        item = next(entry for entry in result["diagnostics"] if entry["category"] == "missing_dependency")
        self.assertTrue(item["context"]["likely_dependency_found_in_inventory"])
        self.assertIn("dependency_present", item["tags"])
        self.assertTrue(any("PlaceholderAPI" in recommendation for recommendation in item["recommendations"]))

    def test_compact_repeated_patterns_humanizes_startup_compatibility_warning(self) -> None:
        recent_log = "\n".join(
            [
                "[21:33:30] [Server thread/WARN]: [DeluxeMenus] Could not setup a NMS hook for your server version!",
                "[21:33:31] [Server thread/WARN]: [DeluxeMenus] Could not setup a NMS hook for your server version!",
            ]
        )
        full_log = "\n".join(
            [
                "[21:33:19] [Server thread/INFO]: Starting minecraft server version 1.21.8",
                '[21:34:33] [Server thread/INFO]: Done (98.510s)! For help, type "help"',
            ]
        )

        with patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_recent_logs", return_value=recent_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_latest_log_path", return_value=Path("latest.log")), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.read_text_file", return_value=full_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_plugins", return_value={"plugins": [{"name": "DeluxeMenus"}]}):
            result = analyze_recent_logs(50, compact=True)

        repeated = result["compact_summary"]["repeated_patterns"]
        self.assertGreaterEqual(len(repeated), 1)
        self.assertEqual(repeated[0]["issue_family"], "server_hook_unavailable")
        self.assertEqual(repeated[0]["issue_label"], "Server version hook unavailable")
        self.assertIn("DeluxeMenus", repeated[0]["title"])

    def test_compact_repeated_patterns_humanize_exception_chain_to_specific_error(self) -> None:
        recent_log = "\n".join(
            [
                "[22:36:05] [Server thread/ERROR]: java.lang.IllegalStateException: zip file closed",
                "[22:36:06] [Server thread/ERROR]: java.lang.IllegalStateException: zip file closed",
            ]
        )
        full_log = "\n".join(
            [
                "[21:33:19] [Server thread/INFO]: Starting minecraft server version 1.21.8",
                '[21:34:33] [Server thread/INFO]: Done (98.510s)! For help, type "help"',
            ]
        )

        with patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_recent_logs", return_value=recent_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.get_latest_log_path", return_value=Path("latest.log")), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.read_text_file", return_value=full_log), \
             patch("minecraft_diagnostic_mcp.services.log_analysis_service.list_plugins", return_value={"plugins": []}):
            result = analyze_recent_logs(50, compact=True)

        repeated = result["compact_summary"]["repeated_patterns"]
        self.assertGreaterEqual(len(repeated), 1)
        self.assertEqual(repeated[0]["issue_family"], "zip_file_closed")
        self.assertEqual(repeated[0]["issue_label"], "Zip file closed")


if __name__ == "__main__":
    unittest.main()
