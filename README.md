# Minecraft Diagnostic MCP

`minecraft-diagnostic-mcp` is a Model Context Protocol diagnostic server for Minecraft environments. It is not a Minecraft plugin, it does not go into the server `plugins/` folder, and it does not run inside the game server; it runs alongside your MCP client and inspects a server through files, logs, local runtime access, or Docker runtime access.

It can inspect a server from three practical angles:

- backup analysis from server files on disk
- local runtime analysis against a locally running Minecraft server
- Docker runtime analysis against a containerized Minecraft server

It can also be exposed to MCP clients over:

- `stdio` for local process-based integrations
- `streamable-http` for desktop or browser-style MCP connection flows

Optionally, it can also send Discord webhook alerts for newly detected serious runtime issues while the MCP server is running.

The project is designed as a small, layered MCP core with:

- plugin inventory and plugin inspection
- server config linting
- recent log analysis with startup-aware diagnostics
- grouped diagnostics with explanations and recommended actions
- a unified snapshot entrypoint for AI clients

Additional project docs:

- `AGENTS.md` for maintainers and coding agents
- `ALERTING.md` for Discord alerting behavior and tuning
- `CONTRACT.md` for supported surfaces and stable response fields
- `DEVELOPMENT.md` for local setup and workflow
- `DEPLOYMENT.md` for VM/systemd and HTTP exposure guidance
- `SUPPORT.md` for the intended `1.0` support boundary
- `RELEASE_CHECKLIST.md` for pre-release verification
- `TODO.md` for the practical backlog

## Use Cases

Typical use cases include:

- debugging broken plugins after a failed startup
- inspecting startup warnings that get buried under runtime log noise
- analyzing a backup without running the server
- doing lightweight runtime inspection of a local or Dockerized server
- giving an MCP client a structured diagnostic view instead of raw logs only
- forwarding serious newly detected runtime issues to Discord via webhook

## Not a Plugin

This project is not a Bukkit, Spigot, Paper, or Purpur plugin.

It does not go into the server `plugins/` directory and it does not extend the game server from inside the JVM.

Instead, it is an external MCP server that inspects Minecraft server state from the outside.

## What It Supports

Supported execution modes:

- `backup`: read-only analysis of a server directory on disk
- `runtime` + `local` backend: direct RCON and filesystem access against a locally running server
- `runtime` + `docker` backend: Docker CLI plus in-container `rcon-cli`
- `auto`: prefer runtime when available, otherwise fall back to backup analysis when possible

Current MCP tools:

- Admin tools:
  - `rcon`
  - `list_players`
  - `help`
  - `server_stats`
  - `server_logs`
  - `check_server_status`
- Diagnostic tools:
  - `list_plugins`
  - `inspect_plugin`
  - `lint_server_config`
  - `analyze_recent_logs`
  - `get_server_snapshot`

## Installation

Python requirement:

- Python `3.10+`

Install the project in editable mode:

```bash
pip install -e .
```

That gives you two practical entrypoints:

```bash
python -m minecraft_diagnostic_mcp
```

or

```bash
minecraft-diagnostic-mcp
```

For Claude Desktop or other MCP clients, you can also point them at the installed console script or run the module directly.

## Configuration

Configuration is environment-variable based. A sample configuration file is provided in `.env.example`.

For local development, copy the example values into your shell environment or your preferred local env-loading workflow and then adjust only the variables relevant to your mode.

Core settings:

- `MCP_TRANSPORT`
  - `stdio`
  - `streamable-http`
- `MCP_HTTP_HOST`
- `MCP_HTTP_PORT`
- `MCP_HTTP_PATH`
- `MCP_ANALYSIS_MODE`
  - `backup`
  - `runtime`
  - `auto`
- `MCP_RUNTIME_BACKEND`
  - `docker`
  - `local`
- `MCP_SERVER_ROOT`
- `MCP_PLUGINS_DIR`
- `MCP_LOGS_DIR`
- `MCP_CONTAINER_NAME`
- `MCP_LOCAL_RCON_HOST`
- `MCP_LOCAL_RCON_PORT`
- `MCP_LOCAL_RCON_PASSWORD`
- `MCP_LOCAL_SERVER_JAR`
- `MCP_DISCORD_ALERTS_ENABLED`
- `MCP_DISCORD_WEBHOOK_URL`
- `MCP_DISCORD_ALERT_USERNAME`
- `MCP_DISCORD_ALERT_POLL_SECONDS`
- `MCP_DISCORD_ALERT_SCAN_LINES`
- `MCP_DISCORD_ALERT_MIN_PRIORITY`
- `MCP_DISCORD_ALERT_STATE_FILE`

### Mode Examples

Backup mode:

```bash
set MCP_TRANSPORT=stdio
set MCP_ANALYSIS_MODE=backup
set MCP_SERVER_ROOT=C:\path\to\mcserver
set MCP_PLUGINS_DIR=plugins
set MCP_LOGS_DIR=logs
python -m minecraft_diagnostic_mcp
```

Local runtime mode:

```bash
set MCP_TRANSPORT=stdio
set MCP_ANALYSIS_MODE=runtime
set MCP_RUNTIME_BACKEND=local
set MCP_SERVER_ROOT=C:\path\to\mcserver-runtime
set MCP_PLUGINS_DIR=plugins
set MCP_LOGS_DIR=logs
set MCP_LOCAL_RCON_HOST=127.0.0.1
set MCP_LOCAL_RCON_PORT=25575
set MCP_LOCAL_RCON_PASSWORD=your-local-rcon-password
python -m minecraft_diagnostic_mcp
```

Docker runtime mode:

```bash
set MCP_TRANSPORT=stdio
set MCP_ANALYSIS_MODE=runtime
set MCP_RUNTIME_BACKEND=docker
set MCP_CONTAINER_NAME=mc
set MCP_SERVER_ROOT=/optional/fallback/path
python -m minecraft_diagnostic_mcp
```

Streamable HTTP mode for desktop-style MCP connection UIs:

```bash
set MCP_TRANSPORT=streamable-http
set MCP_HTTP_HOST=127.0.0.1
set MCP_HTTP_PORT=8000
set MCP_HTTP_PATH=/mcp
set MCP_ANALYSIS_MODE=backup
set MCP_SERVER_ROOT=C:\path\to\mcserver
python -m minecraft_diagnostic_mcp
```

Then use:

- Name: `minecraft-diagnostic-mcp`
- Transport: `Streamable HTTP`
- URL: `http://127.0.0.1:8000/mcp`

Discord webhook alerts:

```bash
set MCP_DISCORD_ALERTS_ENABLED=true
set MCP_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
set MCP_DISCORD_ALERT_POLL_SECONDS=30
set MCP_DISCORD_ALERT_SCAN_LINES=400
set MCP_DISCORD_ALERT_MIN_PRIORITY=50
python -m minecraft_diagnostic_mcp
```

With alerts enabled, the server runs a lightweight background poller that checks recent diagnostics and sends a Discord alert only for newly detected active high-severity issues. Resolved historical items and routine runtime noise are ignored.

## Run Flow

Recommended run flow for each mode:

1. Set the mode-specific environment variables.
2. Start the MCP server with `python -m minecraft_diagnostic_mcp`.
3. In the MCP client, begin with `get_server_snapshot()`.
4. Drill down with:
   - `analyze_recent_logs()`
   - `lint_server_config()`
   - `list_plugins()`
   - `inspect_plugin("PluginName")`

## Testing

Run the test suite with:

```bash
python -m unittest discover -s tests -v
```

The tests are intentionally lightweight and focused on:

- parser behavior
- service layer behavior
- snapshot aggregation
- startup-aware log analysis

They do not require a live Minecraft server or Docker daemon.

## Developer Notes

For local development:

- edit environment variables directly or start from `.env.example`
- run tests with `python -m unittest discover -s tests -v`
- run the MCP server locally with `python -m minecraft_diagnostic_mcp`
- use `MCP_TRANSPORT=streamable-http` if your MCP client expects a URL instead of a local command

If you are iterating on runtime behavior, prefer:

- `backup` mode for read-only fixture-style debugging
- `runtime + local` for a locally running sandbox server
- `runtime + docker` for a real containerized deployment target

## Limitations

Current scope:

- no add-on/plugin ecosystem outside the current plugin-manifest coverage
- no full incident management workflow
- no deep bytecode analysis
- no dependency graph engine
- no auto-remediation or automatic report generation

Runtime notes:

- Docker runtime mode expects Docker CLI access and a reachable container
- Local runtime mode expects a running Minecraft server with RCON enabled
- Backup mode is read-only and does not provide live player/runtime information

## Support Matrix

Current intended support boundary:

- `backup` mode
  - status: supported
  - expectation: read-only filesystem analysis
- `runtime + docker`
  - status: supported
  - expectation: Docker CLI available, target container exists, in-container `rcon-cli` works
- `runtime + local`
  - status: supported on Windows for the current local-process workflow
  - expectation: local server process is running and RCON is enabled
- `stdio`
  - status: supported
- `streamable-http`
  - status: supported

Degraded-mode behavior:

- if Docker CLI is missing, the runtime readiness output now says so explicitly
- if the target Docker container is missing, readiness output says that explicitly
- if the local backend is selected but no matching Java process is found, readiness output says that explicitly
- if backup inputs are missing, backup readiness says that explicitly
- runtime and backup readiness payloads also carry freshness timestamps

For the formal support boundary and release promise, see:

- `SUPPORT.md`
- `CONTRACT.md`
- `RELEASE_CHECKLIST.md`

## Project Structure

High-level layout:

```text
src/minecraft_diagnostic_mcp/
  collectors/
  analyzers/
  parsers/
  services/
  tools/
  models/
```

The architecture is intentionally modest:

- tools expose MCP functions
- services orchestrate use-cases
- collectors read from Docker, filesystem, or local runtime
- parsers normalize raw input
- analyzers produce structured diagnostics

## Release Scope

Current stable release: `1.0.0`

`1.0.0` includes:

- stable MCP tool names
- explicit support boundaries for backup/runtime/transport modes
- predictable diagnostic payloads for MCP clients
- realistic deployment and alerting documentation
- confidence from both unit tests and workflow-style smoke checks

Deliberately out of scope for `1.0.0`:

- deep bytecode analysis
- auto-remediation
- dashboards or report products
- general-purpose Minecraft control-plane features

## Pre-release Checklist

- tests passing
- support boundary documented
- release checklist executed
- `.env.example` present
- README updated
- no `__pycache__` tracked in the repository
