import re
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import minecraft_diagnostic_mcp


class PackageContractTests(unittest.TestCase):
    def test_package_version_matches_pyproject(self) -> None:
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(minecraft_diagnostic_mcp.__version__, match.group(1))


if __name__ == "__main__":
    unittest.main()
