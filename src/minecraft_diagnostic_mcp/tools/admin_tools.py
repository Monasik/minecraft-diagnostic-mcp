from typing import Optional

from minecraft_diagnostic_mcp.collectors.docker_collector import (
    get_container_status,
    get_recent_logs,
    get_runtime_readiness,
    get_server_stats,
)
from minecraft_diagnostic_mcp.collectors.rcon_collector import get_rcon_readiness, run_rcon_command
from minecraft_diagnostic_mcp.settings import settings


def rcon(command: str) -> str:
    """Issue commands to the Minecraft server via RCON.

    Best practices and common patterns include:

    ## Player Location & Building
    1. ALWAYS get player coordinates first before building:
       - `data get entity player_name Pos`
       - This returns coordinates in format: [X.XXd, Y.XXd, Z.XXd]
       - Store these coordinates and use them as the base for building
    2. Building Commands:
       - Direct placement: `setblock x y z block_type`
       - Fill command: `fill x1 y1 z1 x2 y2 z2 block_type [replace|keep|outline|hollow]`
       - Clone command: `clone x1 y1 z1 x2 y2 z2 dest_x dest_y dest_z`
    3. Entity Commands:
       - Summon entities: `summon <entity> <x> <y> <z>`
       - Teleport entities: `tp @e[type=<type>] <x> <y> <z>`
       - Execute as entities: `execute as @e[type=<type>] at @s run <command>`
    4. View/Perspective Commands:
       - Teleport to location: `tp @p x y z`
       - Spectate entity: `spectate <target> [player]`
       - Execute from position: `execute positioned x y z run <command>`

    ## Common Command Patterns
    Item Commands:
    - give rgbkrk coal 12
    - give rgbkrk iron_axe[enchantments={levels:{"minecraft:sharpness":5,"minecraft:efficiency":5,"minecraft:fortune":5}}] 1
    - give @a iron_pickaxe[unbreakable={}]

    Effect Commands:
    - effect give @a speed 300 2
    - effect give LoganTheParrot minecraft:night_vision 1000 1
    - effect give rgbkrk water_breathing infinite 1 true

    Potion Commands:
    - Basic item: give rgbkrk potion[minecraft:potion_contents={potion:"minecraft:fire_resistance"}]
    - Multiple items: give rgbkrk potion[minecraft:potion_contents={potion:"minecraft:strength"}] 5
    - Splash/lingering variants: give rgbkrk splash_potion[minecraft:potion_contents={potion:"minecraft:poison"}]

    ## Targeting Players
    - Use `@a` for all players
    - Use a player name to target a specific player (e.g. rgbkrk)
    - Can get specific player coordinates: `data get entity player_name Pos`
    - Position returns format: [X.XXd, Y.XXd, Z.XXd]

    ## Block Placement Best Practices
    1. Get player coordinates first
    2. Calculate relative positions from stored coordinates
    3. Build structures using absolute coordinates
    4. Test for block type existence before using (some modded blocks may not exist)

    ## Block States
    - Use square brackets for block states: `block_type[property=value]`
    - Example: `lantern[hanging=true]`
    - Multiple properties use comma separation

    ## Relative vs Absolute Coordinates
    - Absolute: Uses exact coordinates (x y z)
    - Relative to player: Uses tilde notation (~)
    - `~` means current position
    - `~1` means one block offset
    - `~-1` means one block negative offset

    ## Common Gotchas
    - NEVER build large structures relative to the player's current position. GET the location needed first.
    - RCON needs player context for certain commands like `locate`
    - Block placement might need block states specified
    - Fill commands include both start and end coordinates
    - Coordinates are exclusive (e.g., ~0 to ~15 creates a 16-block span)
    - Test for block existence before using modded or unusual blocks
    """
    return run_rcon_command(command)


def list_players() -> str:
    """List all currently connected players on the Minecraft server."""
    return rcon("list")


def help(command: Optional[str] = None) -> str:
    """Get help for Minecraft commands."""
    return rcon(f"help {command}" if command else "help")


def server_stats() -> str:
    """Get server statistics including CPU, memory usage, and uptime."""
    try:
        stats = get_server_stats()
        return f"Server Stats:\n{stats}"
    except Exception as e:
        readiness = get_runtime_readiness()
        return f"Error getting server stats: {str(e)}\nRuntime readiness: {readiness.get('message', 'unknown')}"


def server_logs(lines: int = settings.default_log_lines) -> str:
    """Get recent server logs.

    Args:
      lines: Number of recent log lines to fetch (default: 10)
    """
    try:
        logs = get_recent_logs(lines)
        return logs
    except Exception as e:
        readiness = get_runtime_readiness()
        return f"Error fetching logs: {str(e)}\nRuntime readiness: {readiness.get('message', 'unknown')}"


def check_server_status() -> str:
    """Check if the Minecraft server is running and responsive."""
    try:
        status = get_container_status()
        runtime_readiness = get_runtime_readiness()
        rcon_readiness = get_rcon_readiness()
        if status == "running":
            try:
                response = rcon("list")
                return f"Server is running and responsive.\nStatus: {status}\n{response}"
            except Exception:
                return (
                    f"Server is running but may not be fully initialized.\n"
                    f"Status: {status}\n"
                    f"Runtime readiness: {runtime_readiness.get('message', 'unknown')}\n"
                    f"RCON readiness: {rcon_readiness.get('message', 'unknown')}"
                )
        return f"Server is not running.\nStatus: {status}"
    except Exception as e:
        runtime_readiness = get_runtime_readiness()
        rcon_readiness = get_rcon_readiness()
        return (
            f"Error checking server status: {str(e)}\n"
            f"Runtime readiness: {runtime_readiness.get('message', 'unknown')}\n"
            f"RCON readiness: {rcon_readiness.get('message', 'unknown')}"
        )


def register_admin_tools(mcp) -> None:
    mcp.tool()(rcon)
    mcp.tool()(list_players)
    mcp.tool()(help)
    mcp.tool()(server_stats)
    mcp.tool()(server_logs)
    mcp.tool()(check_server_status)
