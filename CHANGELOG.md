# Changelog

All notable changes to `minecraft-diagnostic-mcp` should be documented in this file.

The format is intentionally lightweight and practical.

## [1.0.0] - 2026-03-25

### Added

- Added explicit diagnostic context fields for missing dependency analysis:
  - `missing_target_type`
  - `missing_symbol`
  - `likely_dependency_name`
  - `likely_dependency_found_in_inventory`
- Added tests covering:
  - missing plugin dependency vs classpath failure classification
  - snapshot reuse of compact pattern naming
  - dependency-present inventory correlation
  - high-signal log error promotion out of generic buckets
  - startup compatibility repeated-pattern naming
  - exception-family naming cleanup
  - runtime and backup readiness messaging
  - entrypoint and transport bootstrap smoke behavior
- Added `CONTRACT.md` documenting stable MCP tool names, intended response fields, and degraded-mode expectations.
- Added `DEPLOYMENT.md` with VM deployment, `systemd`, HTTP exposure, and production checklist guidance.
- Added `ALERTING.md` with Discord webhook alerting operations guidance.
- Added `SUPPORT.md` with the intended `1.0.0` support boundary.
- Added `RELEASE_CHECKLIST.md` for pre-release verification.
- Added tests covering runtime readiness messaging and package-version contract checks.
- Added a fixture-driven backup workflow integration test that exercises plugin inventory, config linting, log analysis, and snapshot generation together against a realistic temporary server tree.
- Added alert cooldown and batching configuration:
  - `MCP_DISCORD_ALERT_COOLDOWN_SECONDS`
  - `MCP_DISCORD_ALERT_MAX_BATCH_ITEMS`
- Added a preview helper for Discord alert candidates so alert tuning can be tested without sending webhooks.

### Changed

- Improved snapshot problem groups so they can reuse compact historical log pattern titles when those titles add real signal.
- Prevented snapshot group titles from downgrading to generic compact labels such as `Log issue` or other low-value fallback wording.
- Improved log analysis to distinguish:
  - missing plugin dependencies
  - missing bundled library or classpath failures
- Improved dependency interpretation so classloading failures can recognize when the likely dependency plugin is already installed, which helps point toward version or compatibility issues instead of falsely saying the plugin is simply missing.
- Improved compact log naming so missing dependency findings can render as more actionable repeated patterns such as `Missing plugin dependency PlaceholderAPI`.
- Improved snapshot explanations and actions for dependency-related groups so plugin dependency failures and classpath/library failures are described differently.
- Improved log analysis so known high-signal failures such as SQLite corruption, invalid plugin manifests, and event dispatch failures are promoted out of generic `log_error` / `exception` buckets more often.
- Improved compact historical pattern naming for startup compatibility warnings and more exception-derived incident families, so snapshot and compact log summaries use a more consistent vocabulary.
- Improved runtime and backup readiness outputs so degraded states explain whether Docker CLI is missing, a container is missing, a local process is missing, or backup inputs are missing.
- Improved admin tool error messages so runtime-readiness context is included when status, logs, or stats fail.
- Normalized runtime and backup readiness payloads so they carry predictable `ready`, `readiness_reason`, and `message` fields across execution branches.
- Expanded CI with a packaging/install smoke check so entrypoint installation regressions are easier to catch.
- Expanded CI with an integration-style smoke subset covering entrypoint bootstrap, contract outputs, and a realistic backup workflow.
- Improved local runtime stats so the local backend can report CPU and I/O activity when process performance counters are available.
- Improved local process detection with a jar-name fallback when strict server-root matching is too narrow.
- Added freshness timestamps to readiness payloads.
