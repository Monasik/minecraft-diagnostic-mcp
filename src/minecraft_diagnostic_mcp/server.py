from mcp.server.fastmcp import FastMCP

from minecraft_diagnostic_mcp.http_auth import build_authenticated_streamable_http_app
from minecraft_diagnostic_mcp.settings import settings
from minecraft_diagnostic_mcp.services.alert_service import start_background_alert_loop
from minecraft_diagnostic_mcp.tools.admin_tools import register_admin_tools
from minecraft_diagnostic_mcp.tools.diagnostic_tools import register_diagnostic_tools


mcp = FastMCP("Minecraft Diagnostic MCP")
register_admin_tools(mcp)
register_diagnostic_tools(mcp)


def _normalize_transport(transport: str) -> str:
    normalized = transport.strip().lower()
    if normalized in {"streamable-http", "http"}:
        return "streamable-http"
    return "stdio"


def main() -> None:
    transport = _normalize_transport(settings.transport)
    start_background_alert_loop()
    if transport == "streamable-http":
        mcp.settings.host = settings.http_host
        mcp.settings.port = settings.http_port
        mcp.settings.streamable_http_path = settings.http_path
        _run_streamable_http_server()
        return
    mcp.run(transport=transport)


def _run_streamable_http_server() -> None:
    import uvicorn

    app = build_authenticated_streamable_http_app(mcp, settings)
    config = uvicorn.Config(
        app,
        host=settings.http_host,
        port=settings.http_port,
        log_level=str(getattr(mcp.settings, "log_level", "info")).lower(),
    )
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
