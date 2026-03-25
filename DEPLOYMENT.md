# Deployment Guide

This guide explains how to run `minecraft-diagnostic-mcp` outside a personal dev shell.

The goal is practical deployment, not infrastructure maximalism.

## Deployment Modes

Choose one of these depending on what you are diagnosing:

- backup mode
  - safest read-only path
  - no live player/runtime visibility
- runtime + local backend
  - for a locally running Minecraft server process
  - requires RCON
- runtime + docker backend
  - for containerized Minecraft servers
  - requires Docker CLI and working in-container `rcon-cli`

## Minimal VM Deployment

Example on Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Set environment variables for one mode only.

### Backup Mode

```bash
export MCP_TRANSPORT=streamable-http
export MCP_HTTP_HOST=127.0.0.1
export MCP_HTTP_PORT=38127
export MCP_HTTP_PATH=/mcp
export MCP_ANALYSIS_MODE=backup
export MCP_SERVER_ROOT=/srv/minecraft-backup
export MCP_PLUGINS_DIR=plugins
export MCP_LOGS_DIR=logs
python -m minecraft_diagnostic_mcp
```

### Docker Runtime Mode

```bash
export MCP_TRANSPORT=streamable-http
export MCP_HTTP_HOST=127.0.0.1
export MCP_HTTP_PORT=38127
export MCP_HTTP_PATH=/mcp
export MCP_ANALYSIS_MODE=runtime
export MCP_RUNTIME_BACKEND=docker
export MCP_CONTAINER_NAME=mc
python -m minecraft_diagnostic_mcp
```

### Local Runtime Mode

```bash
export MCP_TRANSPORT=streamable-http
export MCP_HTTP_HOST=127.0.0.1
export MCP_HTTP_PORT=38127
export MCP_HTTP_PATH=/mcp
export MCP_ANALYSIS_MODE=runtime
export MCP_RUNTIME_BACKEND=local
export MCP_SERVER_ROOT=/srv/minecraft
export MCP_LOCAL_RCON_HOST=127.0.0.1
export MCP_LOCAL_RCON_PORT=25575
export MCP_LOCAL_RCON_PASSWORD=change-me
python -m minecraft_diagnostic_mcp
```

## `systemd` Example

Example service file:

```ini
[Unit]
Description=Minecraft Diagnostic MCP
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/minecraft-diagnostic-mcp
Environment="MCP_TRANSPORT=streamable-http"
Environment="MCP_HTTP_HOST=127.0.0.1"
Environment="MCP_HTTP_PORT=38127"
Environment="MCP_HTTP_PATH=/mcp"
Environment="MCP_ANALYSIS_MODE=runtime"
Environment="MCP_RUNTIME_BACKEND=docker"
Environment="MCP_CONTAINER_NAME=mc"
ExecStart=/opt/minecraft-diagnostic-mcp/.venv/bin/python -m minecraft_diagnostic_mcp
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable minecraft-diagnostic-mcp
sudo systemctl start minecraft-diagnostic-mcp
sudo systemctl status minecraft-diagnostic-mcp
```

## HTTP Exposure Safety

Default safe recommendation:

- bind MCP to `127.0.0.1`
- expose it only through:
  - reverse proxy
  - VPN
  - SSH tunnel
  - Tailscale / equivalent private network

Do **not** expose a raw unauthenticated MCP endpoint publicly unless you fully understand the risk.

If you must expose it:

- prefer a reverse proxy with HTTPS
- restrict by firewall/source IP if possible
- keep the server read-only
- review Discord webhook and other env secrets carefully

## Firewall Expectations

For local-only use:

- no public firewall opening is needed

For remote access:

- open only the chosen MCP HTTP port
- restrict source IPs where possible
- document the public URL clearly for the MCP client

## Reverse Proxy Expectations

If using `streamable-http` behind a reverse proxy:

- preserve the MCP path, e.g. `/mcp`
- forward HTTP streaming correctly
- prefer HTTPS at the edge
- keep upstream bound to localhost where possible

## Backup Mode As Safe Workflow

Backup mode is the safest workflow when:

- you do not want to touch the live server runtime
- you only need plugin/config/log diagnostics
- you want to inspect a copied server tree offline

Recommended backup workflow:

1. copy the server tree
2. point `MCP_SERVER_ROOT` at the copy
3. run `get_server_snapshot()`
4. inspect deeper with:
   - `inspect_plugin`
   - `lint_server_config`
   - `analyze_recent_logs(include_archives=true, compact=true)`

## Production Checklist

Before calling a deployment “real”:

- Python environment created and pinned enough for the install path
- `pip install -e .` completed successfully
- MCP server starts via `python -m minecraft_diagnostic_mcp`
- chosen execution mode is explicit
- chosen runtime backend is explicit
- `streamable-http` host/port/path are explicit
- firewall/network exposure is deliberate
- any Discord webhook secret is stored outside Git
- runtime readiness is green or degraded-mode is intentional
