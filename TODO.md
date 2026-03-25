# TODO.md

Practical backlog for `minecraft-diagnostic-mcp` after `1.0.0`.

The `1.0.0` release gate is considered complete.

That release included:

- diagnostic quality hardening
- runtime and contract hardening
- deployment and alerting documentation
- integration-style confidence checks
- release prep, docs audit, and changelog discipline

## Current Position

The project now has a stable `1.0.0` core with:

- backup analysis
- local runtime analysis
- Docker runtime analysis
- `stdio` and `streamable-http`
- plugin inventory and plugin inspection
- config linting
- startup-aware log analysis
- `.log.gz` historical log analysis
- compact historical log summaries
- grouped diagnostics
- Discord webhook alerting
- workflow-style smoke coverage on top of the unit suite

## Highest-Value Next Work

If you want the most useful post-`1.0` work, start here:

1. expand runtime flow confidence for more branches and environments
2. add a few more high-signal diagnostics where real logs justify them
3. improve operations ergonomics without widening scope too much

## Post-`1.0.0` Backlog

### Diagnostics

- [ ] Add more high-signal config heuristics.
- [ ] Surface heuristic confidence hints where they improve decision-making.
- [ ] Keep reducing generic fallback exception buckets when log evidence supports a specific failure family.
- [ ] Add a few more plugin-specific repeated-pattern titles for clearly high-signal real-world incidents.

### Runtime

- [ ] Add more mocked runtime flow tests for local and Docker execution branches.
- [ ] Improve local runtime support beyond the current Windows-first boundary.
- [ ] Improve local runtime stats on platforms where richer metrics can be supported cleanly.

### Operations

- [ ] Add a few more polished MCP desktop client examples.
- [ ] Improve alerting ergonomics further if real-world noise patterns justify it.
- [ ] Expand deployment examples only where users actually need them.

### Release Engineering

- [ ] Keep changelog and release-note discipline consistent.
- [ ] Grow CI only where it catches meaningful regressions.
- [ ] Periodically re-audit repo hygiene before each release.

## Explicitly Not A Priority

These remain deliberately outside the main product direction:

- deep bytecode analysis
- autonomous repair or auto-fix actions
- dashboards or reporting products
- a general-purpose Minecraft control plane
