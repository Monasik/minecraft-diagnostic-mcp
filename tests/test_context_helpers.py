import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.models.context import (
    CONTEXT_SCHEMAS,
    build_missing_dependency_context,
    build_plugin_startup_context,
    normalize_context,
)


class ContextHelperTests(unittest.TestCase):
    def test_context_schemas_define_expected_core_categories(self) -> None:
        self.assertIn("missing_dependency", CONTEXT_SCHEMAS)
        self.assertIn("plugin_startup", CONTEXT_SCHEMAS)
        self.assertIn("rcon_configuration", CONTEXT_SCHEMAS)
        self.assertIn("security_configuration", CONTEXT_SCHEMAS)
        self.assertIn("parse_error", CONTEXT_SCHEMAS)

    def test_builders_and_normalizer_produce_safe_context(self) -> None:
        dependency_context = build_missing_dependency_context("FancyPlugin", ["MissingLib", "MissingLib"], None)
        startup_context = build_plugin_startup_context("FancyPlugin", "12", "docker_logs", "true")
        generic_context = normalize_context("plugin_startup", {"plugin_name": "FancyPlugin", "line_number": "x", "source": 123})

        self.assertEqual(dependency_context["plugin_name"], "FancyPlugin")
        self.assertEqual(dependency_context["missing_dependencies"], ["MissingLib"])
        self.assertEqual(startup_context["line_number"], 12)
        self.assertTrue(startup_context["plugin_found_in_inventory"])
        self.assertNotIn("line_number", generic_context)
        self.assertEqual(generic_context["source"], "123")


if __name__ == "__main__":
    unittest.main()
