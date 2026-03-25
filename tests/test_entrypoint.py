import unittest
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import minecraft_diagnostic_mcp


class _FakeFastMCP:
    def __init__(self, _name: str) -> None:
        self.settings = SimpleNamespace(
            host="127.0.0.1",
            port=8000,
            streamable_http_path="/mcp",
        )

    def tool(self):
        def decorator(func):
            return func

        return decorator

    def run(self, **_kwargs) -> None:
        return None


def _install_fake_mcp() -> None:
    mcp_module = ModuleType("mcp")
    server_module = ModuleType("mcp.server")
    fastmcp_module = ModuleType("mcp.server.fastmcp")
    fastmcp_module.FastMCP = _FakeFastMCP
    server_module.fastmcp = fastmcp_module
    mcp_module.server = server_module

    sys.modules.setdefault("mcp", mcp_module)
    sys.modules.setdefault("mcp.server", server_module)
    sys.modules.setdefault("mcp.server.fastmcp", fastmcp_module)


_install_fake_mcp()

import minecraft_diagnostic_mcp.server as server_module


class EntrypointTests(unittest.TestCase):
    def test_package_main_delegates_to_server_main(self) -> None:
        with patch("minecraft_diagnostic_mcp.server.main") as mocked_main:
            minecraft_diagnostic_mcp.main()

        mocked_main.assert_called_once_with()

    def test_server_main_runs_stdio_transport_by_default(self) -> None:
        fake_settings = SimpleNamespace(
            transport="stdio",
            http_host="127.0.0.1",
            http_port=38127,
            http_path="/mcp",
        )

        with patch.object(server_module, "settings", fake_settings), \
             patch.object(server_module, "start_background_alert_loop") as mocked_alerts, \
             patch.object(server_module.mcp, "run") as mocked_run:
            server_module.main()

        mocked_alerts.assert_called_once_with()
        mocked_run.assert_called_once_with(transport="stdio")

    def test_server_main_configures_streamable_http_transport(self) -> None:
        fake_settings = SimpleNamespace(
            transport="http",
            http_host="0.0.0.0",
            http_port=38127,
            http_path="/mcp",
        )

        original_host = server_module.mcp.settings.host
        original_port = server_module.mcp.settings.port
        original_path = getattr(server_module.mcp.settings, "streamable_http_path", None)
        try:
            with patch.object(server_module, "settings", fake_settings), \
                 patch.object(server_module, "start_background_alert_loop") as mocked_alerts, \
                 patch.object(server_module.mcp, "run") as mocked_run:
                server_module.main()

            self.assertEqual(server_module.mcp.settings.host, "0.0.0.0")
            self.assertEqual(server_module.mcp.settings.port, 38127)
            self.assertEqual(server_module.mcp.settings.streamable_http_path, "/mcp")
            mocked_alerts.assert_called_once_with()
            mocked_run.assert_called_once_with(transport="streamable-http")
        finally:
            server_module.mcp.settings.host = original_host
            server_module.mcp.settings.port = original_port
            server_module.mcp.settings.streamable_http_path = original_path


if __name__ == "__main__":
    unittest.main()
