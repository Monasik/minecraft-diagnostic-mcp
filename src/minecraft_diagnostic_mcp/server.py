from mcp.server.fastmcp import FastMCP

from minecraft_diagnostic_mcp.tools.admin_tools import register_admin_tools
from minecraft_diagnostic_mcp.tools.diagnostic_tools import register_diagnostic_tools


mcp = FastMCP("Minecraft Diagnostic MCP")
register_admin_tools(mcp)
register_diagnostic_tools(mcp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
