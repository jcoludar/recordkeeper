---
id: substrate/session-manifest
name: Session manifest
tier: substrate
default: false
summary: Machine-trustworthy session lifecycle over session-paperwork — authoritative in-flight pointer, monotonic session_no, generated index, ghost surfacing.
requires:
  - substrate/session-paperwork
---

## When to opt in

When a project uses `session-paperwork`'s flat session logs and wants the in-flight
session tracked authoritatively (not guessed by mtime), a stable `session_no` handle,
a generated `sessions/INDEX.md`, and unclosed ("ghost") sessions surfaced — without
giving up hand-editable logs.

## What it deploys

- `manifest_stop_update.py` — a non-blocking Stop hook (recorder, fails open) that, every
  turn, resolves the in-flight log (pointer-first, mtime fallback), stamps `session_no`
  if absent, refreshes the in-flight pointer (clears it on `status: done`), and
  regenerates `sessions/INDEX.md`.
- `_manifest_atomic.py`, `_manifest_pointer.py`, `_manifest_index.py` — stdlib-only
  helpers deployed alongside the hook.

It also makes `session-paperwork`'s and `paperwork-enforcement`'s `find_in_flight_log`
pointer-aware, and narrows `session_stop_log_timing.py` to stamp `ended_at` only on a
real close (`status: done`) — so a mid-session pause never records a premature end time.

## State

- `.claude/state/session-manifest/in-flight.json` — `{log, slug, started_at}` (atomic).
- `.claude/state/session-manifest/counter` — monotonic `session_no` source (atomic).
- `sessions/INDEX.md` — generated; do not hand-edit.

## Out of scope (v1)

Cadence-reminder emission (session_no enables it; emit at /begin-session when built, never
at Stop). Cross-midnight sessions. Auto-closing abandoned logs (surfaced, never rewritten).
masterbook/helpers promotion + assemble.py deploy_helpers (helpers vendored in hooks/ for now).
