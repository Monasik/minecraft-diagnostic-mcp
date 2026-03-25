# RELEASE_CHECKLIST.md

Release checklist for `minecraft-diagnostic-mcp`.

`1.0.0` execution status is recorded here.

## Code And Tests

- [x] `python -m unittest discover -s tests -v` passes
- [x] packaging smoke passes
- [x] entrypoint smoke passes
- [x] no broken imports from a clean environment

## Runtime Confidence

- [x] backup mode works against a realistic sample server tree
- [x] runtime readiness messaging is clear in degraded environments
- [x] `stdio` bootstrap works
- [x] `streamable-http` bootstrap works

## Docs

- [x] `README.md` reflects actual supported modes
- [x] `.env.example` reflects actual config surface
- [x] `DEVELOPMENT.md` is still accurate
- [x] `DEPLOYMENT.md` is still accurate
- [x] `ALERTING.md` is still accurate
- [x] `CONTRACT.md` matches current payload guarantees
- [x] `SUPPORT.md` matches current support boundary
- [x] `CHANGELOG.md` includes the release changes

## Repository Hygiene

- [x] no tracked secrets
- [x] no tracked runtime logs or private backup data
- [x] no tracked caches or `__pycache__`
- [x] no accidental local-only files in the release diff

## Release Decision

- [x] public MCP tool names are intentionally stable
- [x] unstable settings are either documented or removed from the public story
- [x] version in `pyproject.toml` matches intended tag
- [x] release scope is short, clear, and honest
