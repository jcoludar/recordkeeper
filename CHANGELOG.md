# Changelog

All notable changes to recordkeeper will be documented in this file.

## v0.2.6 — 2026-06-24

### Fixed
- **Plugin command parity.** The plugin's top-level `commands/begin-session.md` and `commands/debrief.md`
  had drifted from `substrate/session-paperwork/commands/` since v0.2.4: the structured `## Handoff`
  section and unclosed-session ("ghost") detection had landed only in the substrate copies, so the plugin
  core shipped a lighter handoff for two releases. The plugin commands are now at parity — `/debrief`
  writes a structured `## Handoff` (state-at-close · next · blockers) and `/begin-session` reads it cold
  and surfaces an unclosed prior session. The one intentional difference remains: the plugin stamps
  `ended_at:` on `SessionEnd`, the substrate on `Stop`.

### Added
- **README "Plugin or assembler?" chooser.** A short section orienting new users to the two install
  paths — the non-blocking plugin core vs. the assembler's `session-manifest` layer and blocking
  enforcement gate.

## v0.2.5 — 2026-06-23

### Added
- **Status-conditional enforcement (`when-frontmatter`).** `paperwork.yaml` `when:` clauses can now
  gate a rule on the in-flight session log's frontmatter (e.g. `when-frontmatter: {status: [done, paused]}`),
  combining with `when-files-modified-matching` via AND. This enables the recommended **two-entry
  session-log split** — a creation contract that always applies plus a debrief contract that arms only
  once the log declares it is closing.

### Fixed
- **No more false-block on the first Stop after `/begin-session`.** A single session-log rule asserting
  the debrief fields fired against a freshly-created `in_progress` log and blocked the Stop once. The
  two-entry split (above) lets the `in_progress` log pass while the debrief contract is enforced the
  moment `status` goes terminal. The bundled `paperwork.yaml.example` now shows the split.

### Changed
- **README/quickstart/plugin re-pitched** around "keeps your Claude Code sessions on track": the
  always-on core (orient + honest, timestamped record) leads; the opt-in enforcement gate is the
  "won't close until the record checks out" upgrade. README now lists the shipped `session-manifest`
  substrate (no longer mis-filed as "planned").

### Notes
- v0.2.3 was intentionally skipped (0.2.2 → 0.2.4 in a prior release).

## v0.2.4 — 2026-06-13

### Changed
- **The session log IS the handoff.** `/debrief` now writes a `## Handoff` section
  (state-at-close · next · blockers) at the bottom of the session log instead of
  pointing at a separate `NEXT_SESSION_HANDOFF.md`; `/begin-session` reads that
  handoff first and, on finding an unclosed (`in_progress`) prior log, surfaces it
  to the user and offers to close it — never silently rewriting another session's
  record. The session-log template gains a matching `## Handoff` section.

### Fixed
- **Cross-midnight enforcement false-block.** A session that started yesterday and
  stops after midnight has a log dated yesterday, but the `paperwork-enforcement`
  Stop hook rebuilt the session-log path and `date:` assertion from `{today}`
  (system date) — so the rule resolved to a non-existent today-dated file and
  false-blocked the Stop once (it passed on retry via `stop_hook_active`). A new
  `{session-date}` interpolation token — the in-flight log's OWN date, read from its
  filename prefix — resolves file rules against the log actually in play. The
  bundled example configs (the `paperwork.yaml.example` template and the
  `examples/paperwork-configs/` snippets) now use `{session-date}` for the
  session-log path and `date: equals`; `{today}` is kept for rules that genuinely
  mean "today". This keeps `date: equals` a real invariant (frontmatter date must
  equal the filename date).

## v0.2.2 — 2026-06-12

### Changed
- **README + plugin description reframed for a coherent enforcement story.** Stopped
  selling "never refuse to let you stop" as the product's whole identity and filing
  blocking enforcement under "Legacy / the opposite of our promise." Enforcement is now
  presented as what it is — the *discipline* in the tagline, made literal — and **opt-in
  purely for ease of adoption**, not because a gate conflicts with the core. The core's
  non-blocking, can't-wedge-your-session guarantee is kept, now framed as a virtue of the
  default. README `## Legacy: …` → `## Turn it up: blocking enforcement (opt-in)`; the
  assembler is described as a packaging detail (plugin-native gate on the roadmap) rather
  than a deprecated path.
- `substrate/session-paperwork/module.md` — `Relationship to future Wave 3` →
  `Relationship to enforcement`; dropped internal "Wave 3" jargon and the implication that
  enforcement is unbuilt (the `paperwork-enforcement` substrate ships today).

## v0.2.1 — 2026-06-11

### Added
- `substrate/session-manifest/` — a new opt-in substrate (`requires: session-paperwork`)
  that gives a project a machine-trustworthy session lifecycle: an authoritative
  in-flight pointer (`.claude/state/session-manifest/in-flight.json`), a monotonic
  `session_no`, a generated `sessions/INDEX.md`, and unclosed ("ghost") sessions
  surfaced — without giving up hand-editable logs. A non-blocking Stop hook
  (`manifest_stop_update.py`, a recorder that fails open) owns all machine state and
  refreshes it every turn; the helpers (`_manifest_atomic.py`, `_manifest_pointer.py`,
  `_manifest_index.py`) are stdlib-only.

### Changed
- `session-paperwork` and `paperwork-enforcement` `find_in_flight_log` are now
  **pointer-aware**: when the session-manifest in-flight pointer names a valid in-flight
  log, it is preferred over the most-recent-mtime heuristic (killing the stale-log
  fragility where an old never-closed log wins the race). Fully backward-compatible —
  no pointer file means byte-identical behavior to before.
- `session_stop_log_timing.py` now stamps `ended_at` **only on `status: done`**
  (premature-finalization protection): a Stop is a turn boundary, not a session end, so a
  mid-session pause no longer records a wrong end time. The session ends only at an
  explicit `/debrief` close.

## v0.2.0 — 2026-06-11

recordkeeper now installs as a **Claude Code plugin**. The non-blocking session
record-keeper — orient at the start, run the closing checklist at the end, and get
accurate end-times written automatically — is the headline path; the blocking
paperwork-enforcement layer is reframed as legacy/opt-in.

### Added
- Plugin packaging: a `.claude-plugin/` manifest + marketplace entry, installable via
  `/plugin marketplace add github:jcoludar/recordkeeper`.
- `/begin-session` and `/debrief` commands ported into the plugin.
- A `SessionEnd` `ended_at` stamper — non-binding, fail-open, stdin/cwd-aware,
  registered via `hooks.json` — that writes the real end time when a session ends.

### Changed
- README leads with the non-blocking plugin; the blocking enforcement layer is
  presented as legacy/opt-in.
- The plugin's hook directory is separated from the assembler's baseline hooks.

### Fixed
- Plugin manifests conformed to the Claude Code plugin schema (a live install-smoke
  caught a dead-on-install manifest bug).

### Tests
- End-to-end `SessionEnd` stamp exercised via subprocess + stdin; a guard against
  bare-path hook invocations (exit-126 regression).

## v0.1.2 — 2026-06-03

### Added
- `tier-1/hook-resilience.md` — the hook fail-policy contract: gates fail CLOSED
  (exit 2) with a reachable bypass on their own code error; recorders fail OPEN
  (exit 0) and degrade; the exit-code contract (never mix exit-2 with a JSON
  decision block); the `stop_hook_active` guard.
- `paperwork.yaml` `tier: 1|2` rule annotation — tier 1 (default) blocks the Stop;
  tier 2 is surfaced as a non-blocking advisory ("deferred").

### Fixed
- paperwork-enforcement Stop hook: helper imports are guarded so a broken
  dependency fails CLOSED (block) instead of exiting 1 (non-blocking = fail-open);
  reachable `PAPERWORK_ENFORCEMENT_BYPASS` escape hatch checked before any
  fragile code.
- `find:` consistency regex is validated at config load (must compile; at most
  one capturing group).
- An unclosed frontmatter fence now raises a parse error instead of silently
  returning `None`.
- `session_stop_log_timing.py`: `ended_at` is clamped to `>= started_at`
  (clock-skew guard); the recorder is wrapped to fail open (always exit 0).
- `tools/validate.py`: strip `#fragment` / `?query` from INDEX links before
  matching module ids; enforce the full 8-field frontmatter convention for
  tier-1/tier-2 modules (5-field schema for substrate modules).

## v0.1.1 — 2026-06-03

### Fixed
- PostToolUse edit recorder now resolves the **same** in-flight session log as the
  blocking Stop hook (it passes `today`). Previously the recorder called
  `find_in_flight_log` without `today`, falling back to "most-recent open log
  across all dates" — so with stale, never-closed session logs present it keyed
  edits to the wrong session and `must-be-modified-this-session` could never pass.

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
