import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.parsers.yaml_parser import parse_yaml


class YamlParserTests(unittest.TestCase):
    def test_parse_yaml_parses_mapping(self) -> None:
        result = parse_yaml("settings:\n  allow-end: true\n")
        self.assertTrue(result["parsed"])
        self.assertEqual(result["data"]["settings"]["allow-end"], True)

    def test_parse_yaml_returns_structured_error_for_invalid_yaml(self) -> None:
        result = parse_yaml("settings: [broken\n")
        self.assertFalse(result["parsed"])
        self.assertIsNotNone(result["parse_error"])


if __name__ == "__main__":
    unittest.main()
