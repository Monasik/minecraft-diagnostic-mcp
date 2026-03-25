# ROADMAP.md

Roadmap for `minecraft-diagnostic-mcp` after `1.0.0`.

`1.0.0` is the first stable public release of the project.

That means:

- the public MCP tool surface is intentionally stable
- configuration and support boundaries are documented
- backup, local runtime, and Docker runtime modes are defined clearly
- deployment and alerting docs exist for practical self-hosting
- release confidence includes more than isolated unit tests

## What Led To `1.0.0`

The path to `1.0.0` covered:

- diagnostic quality sharpening
- support-matrix and contract hardening
- deployment and alerting documentation
- integration-style confidence checks
- final release preparation and docs audit

## Post-`1.0.0` Direction

The best future version of the project is still not the biggest one.

The highest-value work after `1.0` is:

- improving diagnostic precision where it clearly helps actionability
- strengthening runtime confidence and portability
- making self-hosting and operations smoother
- adding carefully chosen quality-of-life improvements without turning the project into a control plane

## Work Tracks

### Diagnostics

- add more high-signal config heuristics
- improve heuristic confidence hints where that adds value
- keep reducing generic fallback buckets when real log evidence allows it
- add selected plugin-specific repeated-pattern naming only for clearly high-signal real-world failures

### Runtime And Portability

- improve local runtime behavior beyond the current Windows-first boundary
- add more mocked runtime flow coverage for Docker and local branches
- improve local runtime stats fidelity on non-Windows platforms when support expands

### Operations

- expand deployment examples for more hosting styles
- improve alerting tuning and operational ergonomics
- improve examples for MCP desktop clients where that helps adoption

### Release Engineering

- keep changelog discipline
- grow CI only where it catches real regressions
- maintain contract clarity as the project evolves

## Anti-Goals

These still should not drive the project by default:

- deep bytecode analysis
- autonomous repair
- dashboards
- unrelated admin-platform features
- broad plugin-specific specialization for every Minecraft ecosystem

## Short Version

`1.0.0` is the point where the product promise becomes stable.

After that, the project should grow by:

- targeted quality improvements
- careful portability work
- practical operations polish

not by uncontrolled feature creep.
