import gzip
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.collectors.filesystem_collector import list_log_files, read_log_text


class FilesystemCollectorTests(unittest.TestCase):
    def test_read_log_text_supports_gzip_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gzip_path = Path(temp_dir) / "latest.log.gz"
            with gzip.open(gzip_path, "wt", encoding="utf-8") as handle:
                handle.write("line-1\nline-2\n")

            content = read_log_text(gzip_path)

        self.assertIn("line-1", content)
        self.assertIn("line-2", content)

    def test_list_log_files_prioritizes_latest_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir)
            (logs_dir / "latest.log").write_text("latest", encoding="utf-8")
            with gzip.open(logs_dir / "2026-03-20-1.log.gz", "wt", encoding="utf-8") as handle:
                handle.write("archived")

            with patch("minecraft_diagnostic_mcp.collectors.filesystem_collector.get_logs_dir", return_value=logs_dir):
                log_files = list_log_files()

        self.assertGreaterEqual(len(log_files), 2)
        self.assertEqual(Path(log_files[0].path).name, "latest.log")


if __name__ == "__main__":
    unittest.main()
