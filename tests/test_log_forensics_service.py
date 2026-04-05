import gzip
from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.services.log_forensics_service import (
    extract_raw_logs,
    incident_timeline,
    list_cant_keep_up_events,
    list_log_sources,
    list_player_commands,
    list_stacktrace_plugins,
    search_logs,
)


class LogForensicsServiceTests(unittest.TestCase):
    def test_list_log_sources_reports_time_ranges_without_mixing_latest_by_default_date_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            latest_path = logs_dir / "latest.log"
            latest_path.write_text(
                "[22:00:00] [Server thread/INFO]: Starting minecraft server version 1.21.8\n"
                '[22:10:00] [Server thread/INFO]: Done (10.0s)! For help, type "help"\n',
                encoding="utf-8",
            )
            archive_path = logs_dir / "2026-04-03-1.log.gz"
            with gzip.open(archive_path, "wt", encoding="utf-8") as handle:
                handle.write(
                    "[22:35:29] [Server thread/WARN]: Can't keep up! Is the server overloaded? Running 2000ms or 40 ticks behind\n"
                    "[22:35:30] [Server thread/ERROR]: Watchdog Thread/ERROR dump follows\n"
                )

            fake_logs = [
                type("LogFileInfo", (), {"path": str(latest_path), "file_type": "log", "modified_time": datetime(2026, 4, 5, 12, 0, 0)})(),
                type("LogFileInfo", (), {"path": str(archive_path), "file_type": "log.gz", "modified_time": datetime(2026, 4, 3, 23, 59, 0)})(),
            ]

            with patch("minecraft_diagnostic_mcp.services.log_forensics_service.get_logs_dir", return_value=logs_dir), \
                 patch("minecraft_diagnostic_mcp.services.log_forensics_service.list_log_files", return_value=fake_logs):
                result = list_log_sources(source="all", date_value="2026-04-03")

        self.assertEqual(result["source_count"], 1)
        self.assertEqual(result["sources"][0]["name"], "2026-04-03-1.log.gz")
        self.assertEqual(result["sources"][0]["source_kind"], "archive_log")
        self.assertEqual(result["sources"][0]["time_range"]["first_time"], "22:35:29")
        self.assertIn("Applied exact date filter 2026-04-03", result["precision"]["notices"][0])

    def test_extract_raw_logs_can_target_one_archive_and_keep_full_watchdog_stacktrace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            archive_path = logs_dir / "2026-04-03-1.log.gz"
            with gzip.open(archive_path, "wt", encoding="utf-8") as handle:
                handle.write(
                    "[22:35:20] [Server thread/INFO]: PlayerAlice issued server command: /shop open\n"
                    "[22:35:29] [Server thread/ERROR]: Watchdog Thread/ERROR: A single server tick took 60.00 seconds\n"
                    "    at org.bukkit.craftbukkit.block.CraftChest.getInventory(CraftChest.java:10)\n"
                    "    at com.smpmarket.storage.PlayerMarketStorageListener.onOpen(PlayerMarketStorageListener.java:88)\n"
                    "Caused by: java.lang.IllegalStateException: Watchdog panic\n"
                    "[22:36:10] [Server thread/INFO]: Saving players\n"
                )

            fake_logs = [
                type("LogFileInfo", (), {"path": str(archive_path), "file_type": "log.gz", "modified_time": datetime(2026, 4, 3, 23, 59, 0)})(),
            ]

            with patch("minecraft_diagnostic_mcp.services.log_forensics_service.get_logs_dir", return_value=logs_dir), \
                 patch("minecraft_diagnostic_mcp.services.log_forensics_service.list_log_files", return_value=fake_logs):
                result = extract_raw_logs(
                    source="file:2026-04-03-1.log.gz",
                    date_value="2026-04-03",
                    around="22:35:29",
                    window_seconds=120,
                    max_lines=50,
                    mode="full_raw",
                )

        self.assertEqual(result["matched_record_count"], 1)
        record = result["records"][0]
        self.assertEqual(record["source"]["source_kind"], "archive_log")
        self.assertIn("Watchdog Thread/ERROR", record["full_raw"])
        self.assertIn("PlayerMarketStorageListener", record["full_raw"])
        self.assertIn("CraftChest", record["full_raw"])
        self.assertTrue(record["has_stacktrace"])

    def test_search_logs_finds_plugin_stacktrace_in_archives_by_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            archive_path = logs_dir / "2026-04-03-1.log.gz"
            with gzip.open(archive_path, "wt", encoding="utf-8") as handle:
                handle.write(
                    "[22:35:29] [Server thread/ERROR]: Could not pass event InventoryOpenEvent to SMPMarket v1.0\n"
                    "    at com.smpmarket.storage.PlayerMarketStorageListener.onOpen(PlayerMarketStorageListener.java:88)\n"
                    "    at org.bukkit.craftbukkit.block.CraftChest.getInventory(CraftChest.java:10)\n"
                )

            fake_logs = [
                type("LogFileInfo", (), {"path": str(archive_path), "file_type": "log.gz", "modified_time": datetime(2026, 4, 3, 23, 59, 0)})(),
            ]

            with patch("minecraft_diagnostic_mcp.services.log_forensics_service.get_logs_dir", return_value=logs_dir), \
                 patch("minecraft_diagnostic_mcp.services.log_forensics_service.list_log_files", return_value=fake_logs):
                result = search_logs(
                    source="archives",
                    date_value="2026-04-03",
                    contains="SMPMarket",
                    max_lines=50,
                    mode="full_raw",
                )

        self.assertEqual(result["matched_record_count"], 1)
        self.assertIn("PlayerMarketStorageListener", result["records"][0]["full_raw"])
        self.assertIn("CraftChest", result["records"][0]["full_raw"])

    def test_incident_timeline_includes_preceding_commands_and_following_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            archive_path = logs_dir / "2026-04-03-1.log.gz"
            with gzip.open(archive_path, "wt", encoding="utf-8") as handle:
                handle.write(
                    "[22:30:00] [Server thread/INFO]: PlayerAlice issued server command: /market sell diamond\n"
                    "[22:34:59] [Server thread/WARN]: Can't keep up! Is the server overloaded? Running 2000ms or 40 ticks behind\n"
                    "[22:35:29] [Server thread/ERROR]: Watchdog Thread/ERROR: A single server tick took 60.00 seconds\n"
                    "    at com.smpmarket.storage.PlayerMarketStorageListener.onOpen(PlayerMarketStorageListener.java:88)\n"
                    "[22:36:10] [Server thread/INFO]: Saving players\n"
                )

            fake_logs = [
                type("LogFileInfo", (), {"path": str(archive_path), "file_type": "log.gz", "modified_time": datetime(2026, 4, 3, 23, 59, 0)})(),
            ]

            with patch("minecraft_diagnostic_mcp.services.log_forensics_service.get_logs_dir", return_value=logs_dir), \
                 patch("minecraft_diagnostic_mcp.services.log_forensics_service.list_log_files", return_value=fake_logs):
                result = incident_timeline(
                    source="archives",
                    date_value="2026-04-03",
                    around="22:35:29",
                    window_seconds=60,
                    before_minutes=10,
                    after_minutes=5,
                    max_lines=100,
                    mode="full",
                )

        self.assertTrue(result["incident_found"])
        self.assertEqual(result["incident_timestamp"], "2026-04-03 22:35:29")
        self.assertGreaterEqual(len(result["preceding_player_actions"]), 1)
        self.assertIn("/market sell diamond", result["preceding_player_actions"][0]["command"])
        self.assertGreaterEqual(len(result["relevant_plugin_stacktraces"]), 1)
        self.assertGreaterEqual(len(result["following_recovery_events"]), 1)

    def test_helper_tools_return_day_scoped_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            archive_path = logs_dir / "2026-04-03-1.log.gz"
            with gzip.open(archive_path, "wt", encoding="utf-8") as handle:
                handle.write(
                    "[22:00:00] [Server thread/WARN]: Can't keep up! Is the server overloaded? Running 2000ms or 40 ticks behind\n"
                    "[22:35:29] [Server thread/ERROR]: Watchdog Thread/ERROR: A single server tick took 60.00 seconds\n"
                    "    at com.smpmarket.storage.PlayerMarketStorageListener.onOpen(PlayerMarketStorageListener.java:88)\n"
                    "[22:40:00] [Server thread/INFO]: PlayerAlice issued server command: /spawn\n"
                )

            fake_logs = [
                type("LogFileInfo", (), {"path": str(archive_path), "file_type": "log.gz", "modified_time": datetime(2026, 4, 3, 23, 59, 0)})(),
            ]

            with patch("minecraft_diagnostic_mcp.services.log_forensics_service.get_logs_dir", return_value=logs_dir), \
                 patch("minecraft_diagnostic_mcp.services.log_forensics_service.list_log_files", return_value=fake_logs), \
                 patch("minecraft_diagnostic_mcp.services.log_forensics_service.list_plugins", return_value={"plugins": [{"name": "SMPMarket"}]}):
                lag_result = list_cant_keep_up_events(source="archives", date_value="2026-04-03")
                plugins_result = list_stacktrace_plugins(source="archives", date_value="2026-04-03")
                commands_result = list_player_commands(
                    source="archives",
                    date_value="2026-04-03",
                    time_from="22:39:00",
                    time_to="22:41:00",
                )

        self.assertEqual(lag_result["matched_record_count"], 1)
        self.assertEqual(plugins_result["plugin_count"], 1)
        self.assertEqual(plugins_result["plugins"][0]["plugin"], "SMPMarket")
        self.assertEqual(commands_result["command_count"], 1)
        self.assertEqual(commands_result["commands"][0]["command"], "/spawn")


if __name__ == "__main__":
    unittest.main()
