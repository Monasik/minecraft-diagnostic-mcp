# Discord Alerting Guide

`minecraft-diagnostic-mcp` can optionally send Discord webhook alerts while the MCP server is running.

This guide explains how it behaves operationally.

## Minimum Configuration

```bash
export MCP_DISCORD_ALERTS_ENABLED=true
export MCP_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Optional tuning:

```bash
export MCP_DISCORD_ALERT_USERNAME="Minecraft Diagnostic MCP"
export MCP_DISCORD_ALERT_POLL_SECONDS=30
export MCP_DISCORD_ALERT_SCAN_LINES=400
export MCP_DISCORD_ALERT_MIN_PRIORITY=50
export MCP_DISCORD_ALERT_STATE_FILE=/var/lib/minecraft-diagnostic-mcp/alert-state.json
export MCP_DISCORD_ALERT_COOLDOWN_SECONDS=1800
export MCP_DISCORD_ALERT_MAX_BATCH_ITEMS=3
```

## What It Alerts On

The alert loop is intentionally conservative.

It prefers:

- active issues only
- serious categories
- errors and critical issues
- startup/config/security failures over routine runtime noise

Typical alert candidates:

- plugin startup failures
- missing dependency failures
- startup security warnings
- serious config issues
- parse failures
- exception-heavy active incidents

Typical non-alert noise:

- player movement warnings
- monitoring/profiler warnings
- routine lag hints unless they surface as more serious problems
- historical issues marked as resolved

## Polling Behavior

The MCP server runs a background poller when alerting is enabled.

Key controls:

- `MCP_DISCORD_ALERT_POLL_SECONDS`
- `MCP_DISCORD_ALERT_SCAN_LINES`
- `MCP_DISCORD_ALERT_MIN_PRIORITY`
- `MCP_DISCORD_ALERT_COOLDOWN_SECONDS`
- `MCP_DISCORD_ALERT_MAX_BATCH_ITEMS`

Recommended starting values:

- poll every `30` seconds
- scan `400` recent log lines
- minimum priority `50`
- cooldown `1800` seconds
- batch size `3`

## Deduplication And State File

Alerts are deduplicated through a local state file.

Cooldown behavior:

- the same alert fingerprint is suppressed until the cooldown window expires
- default cooldown is `1800` seconds
- setting cooldown to `0` disables repeated sends for previously seen fingerprints until the state file is cleared

Default behavior:

- if `MCP_DISCORD_ALERT_STATE_FILE` is set, that path is used
- otherwise the server uses:
  - `<server_root>/.mcp_discord_alert_state.json`

Operational consequences:

- restarting the MCP server does not necessarily resend the same alert
- deleting the state file can cause already-seen alerts to be sent again

## Recovery Behavior After Restart

After restart:

- the alert loop resumes polling
- old alerts are suppressed if their fingerprint is still present in the state file
- new active issues still alert normally

If the state file is lost:

- deduplication history is lost too
- currently active serious findings may alert again

## Noise Expectations

Expected low-noise behavior:

- resolved historical issues should not alert
- routine runtime warning spam should not alert
- repeated alerts should be limited by fingerprint deduplication and cooldown windows
- related alerts can be batched into one webhook delivery with multiple embeds

If alert volume is too high:

1. raise `MCP_DISCORD_ALERT_MIN_PRIORITY`
2. reduce `MCP_DISCORD_ALERT_SCAN_LINES`
3. increase `MCP_DISCORD_ALERT_COOLDOWN_SECONDS`
4. reduce `MCP_DISCORD_ALERT_MAX_BATCH_ITEMS`
5. review whether a specific warning family should stay non-alerting

## Dry-Run Preview

For testing or tuning, the codebase also exposes an internal preview helper:

- `preview_alert_candidates()`

It returns the currently eligible alert candidates without sending the webhook.

## Suggested Operational Use

Good fit:

- small self-hosted server
- one Discord channel for serious server health issues
- pairing alerting with `get_server_snapshot()` during investigation

Bad fit:

- high-volume incident management platform expectations
- wanting advanced alert grouping, batching, or escalations

This alerting layer is intentionally lightweight.
