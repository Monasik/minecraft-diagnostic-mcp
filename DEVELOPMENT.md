# DEVELOPMENT.md

This is a small practical guide for local development on `minecraft-diagnostic-mcp`.

## Local Setup

From the project root:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -e .
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -e .
```

## Running Tests

```bash
python -m unittest discover -s tests -v
```

## Common Run Modes

### Backup mode

```bash
set MCP_ANALYSIS_MODE=backup
set MCP_SERVER_ROOT=C:\path\to\mcserver
set MCP_PLUGINS_DIR=plugins
set MCP_LOGS_DIR=logs
python -m minecraft_diagnostic_mcp
```

### Local runtime mode

```bash
set MCP_ANALYSIS_MODE=runtime
set MCP_RUNTIME_BACKEND=local
set MCP_SERVER_ROOT=C:\path\to\mcserver-runtime
set MCP_LOCAL_RCON_HOST=127.0.0.1
set MCP_LOCAL_RCON_PORT=25575
set MCP_LOCAL_RCON_PASSWORD=change-me
python -m minecraft_diagnostic_mcp
```

### Docker runtime mode

```bash
set MCP_ANALYSIS_MODE=runtime
set MCP_RUNTIME_BACKEND=docker
set MCP_CONTAINER_NAME=mc
python -m minecraft_diagnostic_mcp
```

### Streamable HTTP mode

```bash
set MCP_TRANSPORT=streamable-http
set MCP_HTTP_HOST=127.0.0.1
set MCP_HTTP_PORT=38127
set MCP_HTTP_PATH=/mcp
python -m minecraft_diagnostic_mcp
```

## Discord Alerting

Optional Discord webhook alerting:

```bash
set MCP_DISCORD_ALERTS_ENABLED=true
set MCP_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
set MCP_DISCORD_ALERT_POLL_SECONDS=30
set MCP_DISCORD_ALERT_SCAN_LINES=400
set MCP_DISCORD_ALERT_MIN_PRIORITY=50
python -m minecraft_diagnostic_mcp
```

Alerting is designed to stay lightweight:

- active issues only
- no historical resolved alerts
- no routine runtime noise alerts
- cooldown windows and batching are configurable through env

## Debugging Tips

- start with `get_server_snapshot()`
- then use `analyze_recent_logs()` for detail
- when archive history matters, use:
  - `analyze_recent_logs(lines=5000, include_archives=true, compact=true)`
- if diagnostics feel too noisy, compare:
  - current active diagnostics
  - compact repeated patterns
  - resolved historical issues
- for alerting changes, start with the internal preview helper before enabling a live webhook:
  - `preview_alert_candidates()`

## File Areas

When changing behavior:

- log reading and archive support:
  - `src/minecraft_diagnostic_mcp/collectors/filesystem_collector.py`
- log heuristics and compact summaries:
  - `src/minecraft_diagnostic_mcp/services/log_analysis_service.py`
  - `src/minecraft_diagnostic_mcp/analyzers/log_analyzer.py`
- snapshot behavior:
  - `src/minecraft_diagnostic_mcp/services/snapshot_service.py`
- alerting:
  - `src/minecraft_diagnostic_mcp/services/alert_service.py`

## Release Hygiene

Before a release:

1. run the unit tests
2. make sure `.env` with real secrets is not tracked
3. confirm README and `.env.example` match the actual config surface
4. confirm no local runtime or backup data is staged
