# Changelog

All notable changes to recordkeeper will be documented in this file.

## v0.1.0 — first public release (2026-06-03)

Initial public extraction from the masterbook substrate library.

### Ships
- `substrate/session-paperwork/` — start/end session paperwork primitives
- `substrate/paperwork-enforcement/` — blocking Stop hook + declarative `paperwork.yaml` rule engine
- `hooks/` — always-deployed baseline (shell hygiene, secrets block, session-log existence check)
- `settings-fragments/` — always-merged settings fragments
- `tier-1/` — always-on modules (shell hygiene, etc.)
- `tools/assemble.py` — substrate composition build system
- `tools/validate.py` — masterbook-tree self-validator (module frontmatter, INDEX cross-refs)
- `examples/minimal-project/` — runnable end-to-end demo
- `docs/` — concepts, quickstart, hook contracts reference, substrate authoring
- `PARKING_LOT.md` — 11 entries of hard-won hook-authoring and substrate-engineering knowledge

### Deferred to later releases
- `substrate/cross-repo-orientation/` — needs generalization (v0.1.x)
- `substrate/post-edit-formatting/` — v0.2
- `substrate/store-write-approval/` — v0.2
- Kit-as-deliverable (`tools/assemble_kit.py` and friends) — v1
