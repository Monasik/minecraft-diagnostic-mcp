# SUPPORT.md

Support statement for `minecraft-diagnostic-mcp`.

This document describes what the project is willing to guarantee for `1.0.0`.

## Product Support Boundary

`minecraft-diagnostic-mcp` is a read-only diagnostic MCP server for Minecraft environments.

It is intended to help MCP clients:

- inspect plugin inventory and plugin metadata
- lint core server configuration
- analyze recent and historical server logs
- build a compact diagnostic snapshot
- optionally emit Discord webhook alerts for high-signal issues

It is not intended to be:

- a Minecraft plugin
- a remote control plane
- an automatic repair system
- a general-purpose hosting dashboard

## Supported Execution Modes

### Backup mode

Status: supported

Use when:

- you want safe, read-only analysis of a server tree on disk
- the server is not running
- you want to inspect backups or copied server folders

Expected capabilities:

- plugin inventory and plugin inspection
- config linting
- recent and historical log analysis, including `.log.gz`
- snapshot generation

Known limitations:

- no live RCON
- no live player list
- no live runtime stats

### Runtime mode with Docker backend

Status: supported

Use when:

- the Minecraft server runs in Docker
- Docker CLI is available to the MCP process
- the configured container name is correct

Expected capabilities:

- runtime readiness checks
- recent live log access
- RCON-backed admin/read-only checks
- snapshot generation with runtime context

Known limitations:

- requires Docker CLI visibility from the MCP process
- assumes `rcon-cli` is available in the target container workflow already used by this project

### Runtime mode with local backend

Status: supported with current platform boundary

Current support boundary:

- Windows local runtime is supported
- Linux/macOS local runtime should be treated as experimental until explicitly expanded

Expected capabilities:

- local runtime readiness checks
- direct TCP RCON for local server processes
- local log reading
- snapshot generation with local runtime context

Known limitations:

- local process detection is more OS-sensitive than backup mode
- runtime stats are lighter-weight than Docker stats

## Supported Transports

### `stdio`

Status: supported

Best for:

- local MCP desktop clients
- direct process launch integrations

### `streamable-http`

Status: supported

Best for:

- local loopback MCP access
- VM/self-hosted access behind controlled networking

Known limitations:

- public exposure requires your own network safety choices
- this project does not add its own HTTP auth layer

## Platform Statement

Supported at `1.0.0`:

- Python 3.10+
- Windows for backup mode and local runtime mode
- Linux for backup mode and Docker runtime mode

Not promised at `1.0.0`:

- macOS local runtime parity
- container orchestration support beyond the current direct Docker workflow
- cloud-provider-specific deployment automation

## Stable Public MCP Surface

The following MCP tool names are intended to remain stable across `1.x` unless there is a critical reason to change them:

- `list_plugins`
- `inspect_plugin`
- `lint_server_config`
- `analyze_recent_logs`
- `get_server_snapshot`
- `check_server_status`
- `server_stats`
- `server_logs`
- `list_players`
- `rcon`
- `help`

See [CONTRACT.md](C:\Users\JELENPC\Desktop\Minecraft MCP Server\rcon-mcp\CONTRACT.md) for stable payload expectations.

## Configuration Promise At `1.0.0`

At `1.0.0`, the project keeps the main deployment-facing environment variables stable enough for real users to rely on them.

Stable configuration surface:

- transport selection
- HTTP bind/path settings
- execution mode and runtime backend settings
- backup filesystem path settings
- container name and local RCON settings
- Discord webhook alerting settings

Not promised as strongly stable:

- low-level tuning knobs for subprocess timeouts and log sweep limits
- internal heuristic details that do not change the documented MCP contract

## Explicitly Unsupported At `1.0.0`

The following are intentionally out of scope:

- deep bytecode analysis
- autonomous repair actions
- HTTP remote management platform features
- plugin-specific expert support for every ecosystem
- dashboards, analytics products, or report generators

## Operational Expectation

`minecraft-diagnostic-mcp` should be considered:

- reliable for read-only diagnostics within the documented support modes
- safe to run in backup mode without modifying server data
- suitable for low-touch self-hosting with explicit deployment docs

It should not be treated as a guaranteed complete explanation engine for every third-party plugin failure.
