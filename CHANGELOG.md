# Changelog

All notable changes to recordkeeper will be documented in this file.

## 0.2.10

### Fixed
- **🧨 `assemble.py` deleted every hook a project had registered by hand.** `settings.json` was
  written wholesale from substrate data with **no read of the existing file**, so the documented
  deploy command silently removed any hook, and any `permissions.allow` rule, the consumer had added
  themselves. Exit code 0, printed summary unchanged, and the only symptom was that those hooks
  quietly stopped firing.

  Measured 2026-08-20 in the development hub: running the assembler to deploy an *unrelated* change
  removed three live hook registrations added by hand that afternoon. It is invisible from both
  sides — the tool never loaded the prior state, and a deleted registration is observationally
  identical to one that was never added — which is why nothing was watching for it.

  `merge_settings()` now takes an optional `existing=` and carries over every hook entry and
  allow-rule that no substrate produces. Preserved entries are copied **verbatim**, including
  `timeout` and `statusMessage`, which the substrate-hook normalisation drops — a generator that
  silently rewrites a field it does not understand is the same defect one size smaller. The
  preservation is **printed**, because the whole failure was that it happened quietly. An
  unparseable `settings.json` is now **refused rather than overwritten** (exit 2).

  `existing=` defaults to `None`, so every caller written before this change is unaffected.

  *A generator may own what it generates. It may not own what it did not write.*

## 0.2.9

### Added
- **`/begin-session` now carries the standing session shape (step 3b), so it stops living in the
  operator's typing.** The budget and the cold-start standard — *work to roughly 400K tokens, then
  close with a debrief sufficient to start a successor cold* — were being re-entered by hand into
  the opening prompt of every session in every project. **A rule that survives only by being
  re-typed is absent the first time someone is tired**, which makes it a property of one person's
  patience rather than of the process.
  Three things are stated rather than left to inference. It is a **default with a named override
  path** (`unless the user says otherwise in this session's prompt`, and durably in a project's own
  `CLAUDE.md`, where the override is visible) — a default that cannot be overridden is a mandate,
  and the point is that the common case stops being *stated*, not that the rare case is lost. It is
  a **ceiling on running long and not a floor on stopping short**: a written number becomes a
  target, and a session padded to reach it manufactures exactly the low-value tail the cold-start
  standard exists to prevent. And **"enough to start a successor COLD"** is named as the acceptance
  test for the closing ritual, which is what makes a debrief checkable at all rather than a
  checklist of sections that can each be present and useless.
  Adds 4 tests. No configuration change; projects that want a different budget override it in their
  own `CLAUDE.md`.

## 0.2.8

> ⚠ Labelled retroactively on 2026-08-25. This section read `## Unreleased` while its content was
> already on `main` and public: `VERSION` was bumped to `0.2.8` inside the fix commit (`3d7a956`)
> rather than by a release commit, so the header was never written and the next release wrote
> `## 0.2.9` above it. The work shipped; only the label was missing.

### Fixed
- **A stale `ended_at:` is now correctable — and only by a record.** `session_stop_log_timing.py`
  considered only logs whose frontmatter had no `ended_at:` line, so a session that ran `/debrief`
  (status → `done`, stamp written) and then kept working carried a **permanently wrong end time**.
  The substrate whose stated purpose is curing end-time drift reintroduced it, silently.
  The cause was one conflation: a single predicate answered both *"which log belongs to this
  session?"* and *"may I write into it?"*, so the second question's answer silently rewrote the
  first's — a closed log became **invisible**, which is indistinguishable from absent (hence the
  symptom `no in-flight session log` rather than a refusal to overwrite).
  Selection and authority are now separate. `select_log()` returns `(log, tier)` over three tiers of
  evidence — the session-manifest **pointer**, the paperwork-enforcement **edit log**, then newest
  **mtime** — and **only a record tier may correct a stamp already in the file.** The mtime tier may
  still stamp an *open* log, never overwrite a committed value, and where it sees a stamp its own
  mtime contradicts by more than two minutes it refuses and names both instants. A guess that
  overwrites a record is worse than no correction: mtime reorders under a `git checkout` or a file-
  sync with no session having run.
  Adds 21 tests. No configuration change; projects running neither sibling substrate keep the
  previous behaviour plus the advisory.

- **The `SessionEnd` core stamper now refuses two things it used to do silently.** `hooks/
  session_end_stamp.py` selects by **newest mtime**, which is a guess: it cannot tell whose log it
  is looking at. It had no bound on that guess, and both failures below were found by other
  projects running this hook and having to chase where a timestamp came from.
  - **An `in_progress` log is no longer stamped.** Measured: a log received
    `ended_at: 22:52:51` while `status:` still read `in_progress` and its session ran 13 minutes
    longer. A missing `status:` is refused too — absence is not consent.
    ⚠ **`paused` remains stampable, deliberately.** `SessionEnd` fires *once*, at true session end,
    so a paused session really did end and its end time is real. This is **not** the Stop hook's
    `status == "done"` rule: `Stop` fires at every assistant stop and must be stricter. Copying that
    rule here would make the hook silently inert for every paused session.
  - **A log this session plainly did not write is no longer stamped.** When a *new* session ends in
    a repo still holding an *older* unstamped log, the old log used to get today's wall clock.
    Measured in a peer project: a log whose session ran 05:12→05:44 was stamped **09:42:55** by a
    different session that ended four hours later. A log this session closed was written seconds
    ago, so the hook now refuses one untouched for more than `STALE_TOLERANCE_SECONDS` (30 min).
  - Both refusals **print their reason**; a hook that declines in silence is indistinguishable from
    one that is not installed, which is exactly the confusion that made this take a morning to
    diagnose.
  - ⚠ **Stated bound:** recency cannot separate two *concurrent* sessions in one project — both
    write recently and mtime cannot attribute either. Fixing that needs a record, not a better
    guess. Adds 6 tests; 7 of 7 mutants killed.
  - ⛔ **Correction to the report that prompted this:** the hook was described for several weeks as
    *"overwriting committed values."* It never could — it selects only logs lacking `ended_at:` and
    has no `replace_ended_at`. It **fabricates a stamp into an empty field**, which is a different
    defect and, on a repo with no correcting Stop hook, a permanent one.

### Fixed — packaging
- `.claude-plugin/plugin.json` declared `0.2.6` while `VERSION` declared `0.2.7`, and
  `tests/test_packaging_metadata.py::test_version_matches_manifest` failed on `main` because of it
  (the v0.2.7 release bumped `VERSION` without the manifest). Both now carry the same version, so
  the parity test passes. **This is bookkeeping, not a version decision** — it makes the manifest
  state the version that was already released rather than choosing a new one.

## v0.2.7 — 2026-07-07

### Changed
- **`validate.py` now collects all faults in one pass instead of failing fast.** Each check
  (`validate_module` / `validate_index` / `validate_settings_fragments` / `validate_hooks` /
  `validate_commands`) previously raised on the first bad file, so latent faults hid behind whichever
  one the run happened to hit first — real problems got peeled off one run at a time. Every check now
  returns `list[str]` and `main()` prints one `VALIDATION ERROR:` line per fault, so a single run gives
  the whole health picture. The `ValidationError` class is gone; the test suite moved to the
  return-list contract and gained a regression test asserting two broken command files both surface in
  one pass. No change to what counts as valid — only to how completely failures are reported.

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
