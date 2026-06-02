# Changelog

All notable changes to recordkeeper will be documented in this file.

## v0.1.0 — first public release (TBD)

Initial extraction from a private masterbook substrate library (masterbook @ f9540d3).

### Ships
- `substrate/session-paperwork/` — start/end session paperwork primitives
- `substrate/paperwork-enforcement/` — blocking Stop hook + declarative `paperwork.yaml` rule engine
- `hooks/` — always-deployed baseline (shell hygiene, secrets block, session log timing)
- `settings-fragments/` — always-merged settings fragments
- `tier-1/` — always-on modules (shell hygiene, etc.)
- `tools/assemble.py` — substrate composition build system
- `tools/validate.py` — config schema validator
- `scripts/publishability_audit.py` — bundled meta-tool for leakage scans
- `examples/minimal-project/` — runnable end-to-end demo (added in v0.1.0)
- `docs/` — concepts, quickstart, hook contracts reference, substrate authoring (stubs in v0.1.0; prose in v0.1.x)
- `PARKING_LOT.md` — 11 entries of hard-won Anthropic hook-contract knowledge

### Deferred to later releases
- `substrate/cross-repo-orientation/` — needs generalization (v0.1.x)
- `substrate/post-edit-formatting/` — v0.2
- `substrate/store-write-approval/` — v0.2
- Kit-as-deliverable (`tools/assemble_kit.py` and friends) — v1
