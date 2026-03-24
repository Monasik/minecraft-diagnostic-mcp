import importlib
import os
import unittest


class SettingsTests(unittest.TestCase):
    def test_settings_default_transport_values(self) -> None:
        original = dict(os.environ)
        try:
            for key in (
                "MCP_TRANSPORT",
                "MCP_HTTP_HOST",
                "MCP_HTTP_PORT",
                "MCP_HTTP_PATH",
            ):
                os.environ.pop(key, None)

            import minecraft_diagnostic_mcp.settings as settings_module

            settings_module = importlib.reload(settings_module)
            self.assertEqual(settings_module.settings.transport, "stdio")
            self.assertEqual(settings_module.settings.http_host, "127.0.0.1")
            self.assertEqual(settings_module.settings.http_port, 8000)
            self.assertEqual(settings_module.settings.http_path, "/mcp")
        finally:
            os.environ.clear()
            os.environ.update(original)
            import minecraft_diagnostic_mcp.settings as settings_module

            importlib.reload(settings_module)

    def test_settings_reads_http_transport_env(self) -> None:
        original = dict(os.environ)
        try:
            os.environ["MCP_TRANSPORT"] = "streamable-http"
            os.environ["MCP_HTTP_HOST"] = "0.0.0.0"
            os.environ["MCP_HTTP_PORT"] = "9000"
            os.environ["MCP_HTTP_PATH"] = "/"

            import minecraft_diagnostic_mcp.settings as settings_module

            settings_module = importlib.reload(settings_module)
            self.assertEqual(settings_module.settings.transport, "streamable-http")
            self.assertEqual(settings_module.settings.http_host, "0.0.0.0")
            self.assertEqual(settings_module.settings.http_port, 9000)
            self.assertEqual(settings_module.settings.http_path, "/")
        finally:
            os.environ.clear()
            os.environ.update(original)
            import minecraft_diagnostic_mcp.settings as settings_module

            importlib.reload(settings_module)
