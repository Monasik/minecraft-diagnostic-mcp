import unittest
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
