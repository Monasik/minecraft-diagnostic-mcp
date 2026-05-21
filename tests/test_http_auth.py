import unittest
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from minecraft_diagnostic_mcp.http_auth import is_request_authorized


class HttpAuthTests(unittest.TestCase):
    def test_authorization_header_accepts_bearer_token(self) -> None:
        settings = SimpleNamespace(
            http_auth_enabled=True,
            http_auth_bearer_token="secret-token",
            http_auth_header_name="Authorization",
            http_auth_scheme="Bearer",
        )

        self.assertTrue(is_request_authorized({"authorization": "Bearer secret-token"}, settings))
        self.assertFalse(is_request_authorized({"authorization": "Bearer wrong"}, settings))

    def test_custom_header_accepts_plain_token(self) -> None:
        settings = SimpleNamespace(
            http_auth_enabled=True,
            http_auth_bearer_token="secret-token",
            http_auth_header_name="X-MCP-Token",
            http_auth_scheme="Bearer",
        )

        self.assertTrue(is_request_authorized({"x-mcp-token": "secret-token"}, settings))
        self.assertFalse(is_request_authorized({"x-mcp-token": "wrong"}, settings))


if __name__ == "__main__":
    unittest.main()
