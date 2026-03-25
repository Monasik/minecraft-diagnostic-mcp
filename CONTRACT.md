# Contract Notes

This document describes the public contract for `minecraft-diagnostic-mcp` at `1.0.0`.

It is intentionally practical:

- what is supported
- which MCP tools are considered stable
- which response fields are expected to stay predictable
- where degraded-mode behavior is intentional

## Supported Modes

Execution modes:

- `backup`
- `runtime` with `docker` backend
- `runtime` with `local` backend

Transports:

- `stdio`
- `streamable-http`

## Stable MCP Tool Names

The following MCP tool names should be treated as stable unless there is a strong release-blocking reason to change them:

- `rcon`
- `list_players`
- `help`
- `server_stats`
- `server_logs`
- `check_server_status`
- `list_plugins`
- `inspect_plugin`
- `lint_server_config`
- `analyze_recent_logs`
- `get_server_snapshot`

These names should be treated as frozen for `1.x` unless there is a release-blocking compatibility reason to change them.

## Stable Diagnostic Shapes

These field groups are intended to remain predictable for MCP clients.

### `inspect_plugin()`

Top-level fields:

- `plugins_dir`
- `exists`
- `plugin_found`
- `query`
- `message`
- `plugin`
- `diagnostics`

### `lint_server_config()`

Top-level fields:

- `config_files`
- `diagnostics`
- `summary`

Summary fields:

- `config_count`
- `item_count`
- `issue_count`
- `warning_count`
- `error_count`
- `critical_count`
- `info_count`
- `message`

### `analyze_recent_logs()`

Top-level fields:

- `scanned_lines`
- `archives_included`
- `detail_mode`
- `log_files_scanned`
- `diagnostics`
- `summary`

Optional but expected when available:

- `startup_window`
- `log_category_counts`
- `compact_summary`

Summary fields:

- `record_count`
- `item_count`
- `finding_count`
- `info_count`
- `warning_count`
- `error_count`
- `critical_count`
- `message`

### `get_server_snapshot()`

Top-level fields:

- `status`
- `stats`
- `plugin_summary`
- `config_summary`
- `log_summary`
- `diagnostics`
- `problem_groups`
- `summary`

Status fields:

- `execution_mode`
- `container_name`
- `container_status`
- `rcon_responsive`
- `players_online_raw`
- `runtime_readiness`
- `backup_readiness`

Runtime readiness fields:

- `execution_mode`
- `runtime_backend`
- `docker_available`
- `container_exists`
- `container_status`
- `logs_available`
- `local_process_running`
- `local_process_id`
- `readiness_reason`
- `ready`
- `message`

Backup readiness fields:

- `server_root`
- `plugins_dir`
- `plugins_available`
- `logs_available`
- `latest_log_path`
- `readiness_reason`
- `ready`
- `message`

RCON readiness is exposed indirectly through:

- `status.rcon_responsive`
- admin tool degraded-mode messages

Optional freshness metadata:

- `runtime_readiness.checked_at`
- `backup_readiness.checked_at`
- collector readiness payloads may include `checked_at` timestamps when that helps explain freshness

## Stable Diagnostic Item Contract

`DiagnosticItem` payloads are expected to keep these core fields:

- `severity`
- `category`
- `source_type`
- `source_name`
- `title`
- `summary`
- `suspected_component`
- `evidence`
- `recommendations`
- `tags`
- `context`
- `priority`

Supported severities:

- `info`
- `warning`
- `error`
- `critical`

## Configuration Stability Notes

The project now treats these settings as part of the intended stable `1.0` operating surface:

- `MCP_TRANSPORT`
- `MCP_HTTP_HOST`
- `MCP_HTTP_PORT`
- `MCP_HTTP_PATH`
- `MCP_ANALYSIS_MODE`
- `MCP_RUNTIME_BACKEND`
- `MCP_SERVER_ROOT`
- `MCP_PLUGINS_DIR`
- `MCP_LOGS_DIR`
- `MCP_CONTAINER_NAME`
- `MCP_LOCAL_RCON_HOST`
- `MCP_LOCAL_RCON_PORT`
- `MCP_LOCAL_RCON_PASSWORD`
- `MCP_DISCORD_ALERTS_ENABLED`
- `MCP_DISCORD_WEBHOOK_URL`
- `MCP_DISCORD_ALERT_USERNAME`
- `MCP_DISCORD_ALERT_POLL_SECONDS`
- `MCP_DISCORD_ALERT_SCAN_LINES`
- `MCP_DISCORD_ALERT_MIN_PRIORITY`
- `MCP_DISCORD_ALERT_STATE_FILE`

These settings should be treated as operational tuning, not strong client-facing API guarantees:

- `MCP_DEFAULT_LOG_LINES`
- `MCP_SUBPROCESS_TIMEOUT_SECONDS`
- `MCP_MAX_LOG_FILES`
- `MCP_MAX_LOG_LINES_TOTAL`
- `MCP_LOCAL_SERVER_JAR`

## Degraded-Mode Behavior

The project intentionally returns safe structured output instead of failing hard when possible.

Expected degraded cases include:

- Docker CLI missing
- Docker container missing
- local runtime selected but process missing
- RCON unavailable or unresponsive
- backup inputs missing
- config parse failures
- unreadable or absent log inputs

These cases should prefer:

- explicit `message`
- explicit `ready` / `rcon_responsive` style booleans
- predictable fallback summary objects

## Non-Goals Of The Contract

These are intentionally not promised as fully stable yet:

- exact wording of all human-readable summaries
- exhaustive plugin-specific heuristics
- every diagnostic `context` key outside the documented core categories
- exact ordering of lower-priority noise findings
