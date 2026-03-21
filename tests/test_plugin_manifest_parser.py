import unittest
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.parsers.plugin_manifest_parser import parse_plugin_manifest


class PluginManifestParserTests(unittest.TestCase):
    def test_parse_plugin_manifest_extracts_expected_fields(self) -> None:
        plugin_yml = b"""
name: ExamplePlugin
version: 1.2.3
main: com.example.PluginMain
depend: [Vault]
softdepend: [PlaceholderAPI]
loadbefore: [AnotherPlugin]
commands:
  example:
    description: Example command
    usage: /example
    permission: example.use
permissions:
  example.use:
    description: Use the example command
description: Demo plugin
website: https://example.com
authors: [Alice, Bob]
"""
        plugin = parse_plugin_manifest(Path("plugins/ExamplePlugin.jar"), plugin_yml)

        self.assertEqual(plugin.name, "ExamplePlugin")
        self.assertEqual(plugin.manifest_name, "plugin.yml")
        self.assertEqual(plugin.version, "1.2.3")
        self.assertEqual(plugin.main, "com.example.PluginMain")
        self.assertEqual(plugin.depend, ["Vault"])
        self.assertEqual(plugin.softdepend, ["PlaceholderAPI"])
        self.assertEqual(plugin.loadbefore, ["AnotherPlugin"])
        self.assertEqual(plugin.commands[0].name, "example")
        self.assertEqual(plugin.permissions, ["example.use"])
        self.assertEqual(plugin.authors, ["Alice", "Bob"])

    def test_parse_plugin_manifest_supports_paper_plugin_manifest(self) -> None:
        plugin_yml = b"""
name: PaperOnlyPlugin
version: 2.0.0
main: com.example.PaperOnly
api-version: '1.21'
"""
        plugin = parse_plugin_manifest(Path("plugins/PaperOnlyPlugin.jar"), plugin_yml, manifest_name="paper-plugin.yml")

        self.assertEqual(plugin.name, "PaperOnlyPlugin")
        self.assertEqual(plugin.manifest_name, "paper-plugin.yml")


if __name__ == "__main__":
    unittest.main()
