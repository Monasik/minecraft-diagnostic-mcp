from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _normalize_header_name(name: str) -> str:
    return name.strip().lower()


def is_http_auth_enabled(settings: Any) -> bool:
    return bool(getattr(settings, "http_auth_enabled", False) and getattr(settings, "http_auth_bearer_token", "").strip())


def is_request_authorized(headers: Mapping[str, str], settings: Any) -> bool:
    if not is_http_auth_enabled(settings):
        return True

    expected_token = str(getattr(settings, "http_auth_bearer_token", "")).strip()
    auth_header_name = _normalize_header_name(getattr(settings, "http_auth_header_name", "Authorization"))
    header_value = headers.get(auth_header_name)
    if not header_value:
        return False

    if auth_header_name == "authorization":
        prefix = str(getattr(settings, "http_auth_scheme", "Bearer")).strip() or "Bearer"
        expected_value = f"{prefix} {expected_token}"
        return header_value.strip() == expected_value

    return header_value.strip() == expected_token


def build_authenticated_streamable_http_app(mcp, settings):
    app = mcp.streamable_http_app()
    if not is_http_auth_enabled(settings):
        return app

    from starlette.responses import PlainTextResponse

    class StaticTokenAuthMiddleware:
        def __init__(self, inner_app):
            self.inner_app = inner_app

        async def __call__(self, scope, receive, send):
            if scope.get("type") != "http":
                await self.inner_app(scope, receive, send)
                return

            headers = {
                key.decode("latin-1").lower(): value.decode("latin-1")
                for key, value in scope.get("headers", [])
            }
            if not is_request_authorized(headers, settings):
                scheme = str(getattr(settings, "http_auth_scheme", "Bearer")).strip() or "Bearer"
                response = PlainTextResponse(
                    "Unauthorized",
                    status_code=401,
                    headers={"WWW-Authenticate": scheme},
                )
                await response(scope, receive, send)
                return

            await self.inner_app(scope, receive, send)

    return StaticTokenAuthMiddleware(app)
