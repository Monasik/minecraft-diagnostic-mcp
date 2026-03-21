import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.parsers.log_parser import parse_log_records


class LogParserTests(unittest.TestCase):
    def test_parse_log_records_groups_stacktrace_with_exception(self) -> None:
        raw_log = (
            "[12:00:00 INFO]: Starting\n"
            "[12:00:01 ERROR]: Could not load plugin FancyPlugin\n"
            "java.lang.NoClassDefFoundError: Example\n"
            "    at com.example.Plugin.onEnable(Plugin.java:10)\n"
            "Caused by: java.lang.ClassNotFoundException: Example\n"
        )

        records = parse_log_records(raw_log)

        self.assertEqual(len(records), 3)
        self.assertEqual(records[1]["level"], "ERROR")
        self.assertTrue(records[2]["has_stacktrace"])

    def test_parse_log_records_prefers_first_line_level_for_warn_records(self) -> None:
        raw_log = "[12:36:50 WARN]: If the command subsequently completes without any errors, this warning should be ignored.\n"

        records = parse_log_records(raw_log)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["level"], "WARN")


if __name__ == "__main__":
    unittest.main()
