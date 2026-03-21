import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.parsers.properties_parser import parse_properties


class PropertiesParserTests(unittest.TestCase):
    def test_parse_properties_collects_key_values_and_invalid_lines(self) -> None:
        result = parse_properties(
            "# comment\nserver-port=25565\nenable-rcon:true\ninvalid-line\n"
        )

        self.assertEqual(result["data"]["server-port"], "25565")
        self.assertEqual(result["data"]["enable-rcon"], "true")
        self.assertIn("Invalid property syntax", result["parse_error"])


if __name__ == "__main__":
    unittest.main()
