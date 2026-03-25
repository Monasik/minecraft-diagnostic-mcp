# AGENTS.md

This document is a practical guide for contributors, coding agents, and future maintainers working on `minecraft-diagnostic-mcp`.

## Project Intent

`minecraft-diagnostic-mcp` is an external Model Context Protocol server for diagnosing Minecraft server environments.

It is:

- not a Minecraft plugin
- not a server-side mod
- not intended to run inside the game JVM

It runs beside an MCP client and inspects:

- backup directories on disk
- local runtime servers
- Docker-based runtime servers

## Current Goals

The project currently focuses on a stable diagnostic core:

- plugin inventory and plugin inspection
- config linting
- startup-aware log analysis
- compact log history summaries
- grouped diagnostics with explanations and recommended actions
- read-only runtime inspection
- optional Discord webhook alerting

The project does **not** currently aim to be:

- a full plugin-specific expert system
- a deep bytecode analyzer
- a general-purpose Minecraft control plane
- an automated remediation system

## Architecture

The architecture is intentionally layered and modest.

- `src/minecraft_diagnostic_mcp/tools/`
  - MCP tool registration and public tool surface
- `src/minecraft_diagnostic_mcp/services/`
  - orchestration and use-case logic
- `src/minecraft_diagnostic_mcp/collectors/`
  - low-level reads from filesystem, Docker, RCON, local runtime
- `src/minecraft_diagnostic_mcp/parsers/`
  - tolerant parsing of manifests, configs, and logs
- `src/minecraft_diagnostic_mcp/analyzers/`
  - heuristic classification and lint rules
- `src/minecraft_diagnostic_mcp/models/`
  - structured models for diagnostics, context, findings, snapshot data

## Execution Modes

Supported execution combinations:

- `backup`
- `runtime + local`
- `runtime + docker`

Transport modes:

- `stdio`
- `streamable-http`

## Design Constraints

When changing the project, prefer:

- small, targeted changes
- robust read-only behavior
- tolerant parsing over brittle assumptions
- explicit structured output over raw text
- stability over cleverness

Avoid:

- large redesigns unless clearly necessary
- feature creep in unrelated areas
- coupling new behavior directly into MCP tool functions when a service layer is cleaner
- hardcoding one specific server layout or one specific plugin ecosystem

## Diagnostic Principles

Diagnostics should aim to be:

- structured
- explainable
- prioritizable
- compact when needed
- useful for both humans and AI clients

Important rules:

- historical resolved issues should not be treated as active alerts
- routine runtime noise should not outrank startup/config/security issues
- compact summaries should prefer signal over exhaustive dumps

## Alerting Principles

Discord alerting is intentionally lightweight.

It should:

- remain optional
- only send new active serious issues
- ignore resolved historical items
- avoid spamming repeated low-value runtime noise

It should not evolve into a complex incident platform unless that becomes an explicit project goal.

## Safe Change Areas

Usually safe to extend incrementally:

- new log heuristics
- compact summary wording
- context normalization
- snapshot wording
- alert filtering
- plugin manifest edge-case support

Usually higher-risk:

- transport changes
- runtime collector behavior
- RCON backend behavior
- major schema changes in diagnostic output

## Recommended Workflow

Before making changes:

1. inspect the current service and tests around the affected area
2. prefer adding or adjusting tests first when behavior is subtle
3. keep MCP public tool names stable unless there is a strong reason
4. run:
   - `python -m unittest discover -s tests -v`

## Good Next Work

Good future improvements:

- better plugin-specific incident naming
- more explicit structured metadata for repeated patterns
- snapshot-level use of compact historical log patterns
- deployment docs for VM/systemd

## Avoid For Now

Unless explicitly requested, do not jump into:

- HTTP auth/reverse proxy architecture
- plugin-specific deep semantic config engines
- bytecode scanning
- dependency graph engines
- autonomous remediation

