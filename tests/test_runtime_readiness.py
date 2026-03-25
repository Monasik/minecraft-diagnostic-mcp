import unittest
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.collectors.docker_collector import get_runtime_readiness
from minecraft_diagnostic_mcp.collectors.filesystem_collector import get_backup_readiness
from minecraft_diagnostic_mcp.collectors.rcon_collector import get_rcon_readiness


class RuntimeReadinessTests(unittest.TestCase):
    def test_get_runtime_readiness_reports_missing_docker_cli_clearly(self) -> None:
        with patch("minecraft_diagnostic_mcp.collectors.docker_collector.resolve_execution_mode", return_value="runtime"), \
             patch("minecraft_diagnostic_mcp.collectors.docker_collector.get_runtime_backend", return_value="docker"), \
             patch("minecraft_diagnostic_mcp.collectors.docker_collector.is_docker_available", return_value=False), \
             patch("minecraft_diagnostic_mcp.collectors.docker_collector.get_latest_log_path", return_value=None):
            readiness = get_runtime_readiness()

        self.assertFalse(readiness["ready"])
        self.assertIn("Docker CLI is not available", readiness["message"])
        self.assertEqual(readiness["readiness_reason"], "docker_cli_missing")
        self.assertIn("local_process_running", readiness)

    def test_get_runtime_readiness_reports_missing_container_clearly(self) -> None:
        with patch("minecraft_diagnostic_mcp.collectors.docker_collector.resolve_execution_mode", return_value="runtime"), \
             patch("minecraft_diagnostic_mcp.collectors.docker_collector.get_runtime_backend", return_value="docker"), \
             patch("minecraft_diagnostic_mcp.collectors.docker_collector.is_docker_available", return_value=True), \
             patch("minecraft_diagnostic_mcp.collectors.docker_collector.container_exists", return_value=False), \
             patch("minecraft_diagnostic_mcp.collectors.docker_collector.get_latest_log_path", return_value=None):
            readiness = get_runtime_readiness()

        self.assertFalse(readiness["ready"])
        self.assertIn("was not found", readiness["message"])
        self.assertEqual(readiness["readiness_reason"], "container_missing")
        self.assertIsNone(readiness["local_process_id"])

    def test_get_runtime_readiness_reports_local_backend_process_absence_clearly(self) -> None:
        with patch("minecraft_diagnostic_mcp.collectors.docker_collector.resolve_execution_mode", return_value="runtime"), \
             patch("minecraft_diagnostic_mcp.collectors.docker_collector.get_runtime_backend", return_value="local"), \
             patch("minecraft_diagnostic_mcp.collectors.docker_collector.get_local_process_info", return_value=None), \
             patch("minecraft_diagnostic_mcp.collectors.docker_collector.get_latest_log_path", return_value=Path("latest.log")):
            readiness = get_runtime_readiness()

        self.assertFalse(readiness["ready"])
        self.assertIn("no matching local Java server process was found", readiness["message"])
        self.assertEqual(readiness["readiness_reason"], "local_process_missing")
        self.assertFalse(readiness["docker_available"])

    def test_get_backup_readiness_reports_missing_inputs_clearly(self) -> None:
        with patch("minecraft_diagnostic_mcp.collectors.filesystem_collector.get_latest_log_path", return_value=None), \
             patch("minecraft_diagnostic_mcp.collectors.filesystem_collector.plugins_dir_exists", return_value=False), \
             patch("minecraft_diagnostic_mcp.collectors.filesystem_collector.get_server_root", return_value=Path(".")), \
             patch("minecraft_diagnostic_mcp.collectors.filesystem_collector.get_plugins_dir", return_value=Path("plugins")):
            readiness = get_backup_readiness()

        self.assertFalse(readiness["ready"])
        self.assertIn("No backup analysis inputs were found", readiness["message"])
        self.assertEqual(readiness["readiness_reason"], "backup_inputs_missing")

    def test_get_rcon_readiness_reports_local_auth_missing_clearly(self) -> None:
        with patch("minecraft_diagnostic_mcp.collectors.rcon_collector.resolve_execution_mode", return_value="runtime"), \
             patch("minecraft_diagnostic_mcp.collectors.rcon_collector.get_runtime_backend", return_value="local"), \
             patch("minecraft_diagnostic_mcp.collectors.rcon_collector.settings", SimpleNamespace(local_rcon_password="")), \
             patch("minecraft_diagnostic_mcp.collectors.rcon_collector.run_rcon_command", side_effect=RuntimeError("Local RCON password is not configured.")):
            readiness = get_rcon_readiness()

        self.assertFalse(readiness["ready"])
        self.assertFalse(readiness["auth_configured"])
        self.assertEqual(readiness["readiness_reason"], "local_rcon_auth_missing")

    def test_get_rcon_readiness_reports_docker_cli_missing_clearly(self) -> None:
        with patch("minecraft_diagnostic_mcp.collectors.rcon_collector.resolve_execution_mode", return_value="runtime"), \
             patch("minecraft_diagnostic_mcp.collectors.rcon_collector.get_runtime_backend", return_value="docker"), \
             patch("minecraft_diagnostic_mcp.collectors.rcon_collector.is_docker_available", return_value=False):
            readiness = get_rcon_readiness()

        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["readiness_reason"], "docker_cli_missing")


if __name__ == "__main__":
    unittest.main()
