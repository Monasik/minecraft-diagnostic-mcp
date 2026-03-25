import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.tools.admin_tools import check_server_status, server_logs, server_stats
from minecraft_diagnostic_mcp.collectors.docker_collector import _get_local_server_stats


class RuntimeToolFlowTests(unittest.TestCase):
    def test_local_runtime_server_stats_uses_richer_process_metrics(self) -> None:
        with patch(
            "minecraft_diagnostic_mcp.collectors.docker_collector.get_local_process_info",
            return_value={"process_id": 42, "working_set_size": 268435456},
        ), patch(
            "minecraft_diagnostic_mcp.collectors.docker_collector._get_local_performance_info",
            return_value={
                "cpu_percent": 12.5,
                "working_set_size": 536870912,
                "io_read_bytes_persec": 1024,
                "io_write_bytes_persec": 2048,
            },
        ):
            stats = _get_local_server_stats()

        self.assertEqual(stats, "12.5%\t512.0MiB\t1.0KiB/s / 2.0KiB/s")

    def test_server_status_reports_local_runtime_ready(self) -> None:
        with patch("minecraft_diagnostic_mcp.tools.admin_tools.get_container_status", return_value="running"), \
             patch("minecraft_diagnostic_mcp.tools.admin_tools.get_runtime_readiness", return_value={"message": "Local runtime backend is ready.", "ready": True}), \
             patch("minecraft_diagnostic_mcp.tools.admin_tools.get_rcon_readiness", return_value={"message": "Local RCON responded successfully.", "rcon_responsive": True}), \
             patch("minecraft_diagnostic_mcp.tools.admin_tools.rcon", return_value="There are 1 of a max of 20 players online: Steve"):
            result = check_server_status()

        self.assertIn("Server is running and responsive.", result)
        self.assertIn("There are 1 of a max of 20 players online: Steve", result)

    def test_server_logs_reports_runtime_readiness_context_when_unavailable(self) -> None:
        with patch("minecraft_diagnostic_mcp.tools.admin_tools.get_recent_logs", side_effect=RuntimeError("Docker CLI is not available.")), \
             patch("minecraft_diagnostic_mcp.tools.admin_tools.get_runtime_readiness", return_value={"message": "Docker runtime backend is selected but Docker CLI is not available."}):
            result = server_logs(20)

        self.assertIn("Error fetching logs: Docker CLI is not available.", result)
        self.assertIn("Runtime readiness: Docker runtime backend is selected but Docker CLI is not available.", result)

    def test_server_stats_reports_runtime_readiness_context_when_local_process_missing(self) -> None:
        with patch("minecraft_diagnostic_mcp.tools.admin_tools.get_server_stats", side_effect=RuntimeError("Local server process was not found.")), \
             patch("minecraft_diagnostic_mcp.tools.admin_tools.get_runtime_readiness", return_value={"message": "Local runtime backend is selected but no matching local Java server process was found."}):
            result = server_stats()

        self.assertIn("Error getting server stats: Local server process was not found.", result)
        self.assertIn("Runtime readiness: Local runtime backend is selected but no matching local Java server process was found.", result)

    def test_local_process_info_falls_back_to_jar_name_match(self) -> None:
        empty_primary = ""
        fallback_result = "ProcessId : 4242\nWorkingSetSize : 1048576"
        with patch(
            "minecraft_diagnostic_mcp.collectors.docker_collector._run_powershell_script",
            side_effect=[empty_primary, fallback_result],
        ):
            from minecraft_diagnostic_mcp.collectors.docker_collector import get_local_process_info

            info = get_local_process_info()

        self.assertEqual(info["process_id"], 4242)
        self.assertEqual(info["working_set_size"], 1048576)


if __name__ == "__main__":
    unittest.main()
