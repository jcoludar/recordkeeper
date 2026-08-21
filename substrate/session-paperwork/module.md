---
id: substrate/session-paperwork
name: Session paperwork
tier: substrate
default: false
applies_when: "project keeps per-session logs under sessions/ (or docs/sessions/)"
conflicts_with: []
requires: []
summary: Slash commands and a Stop hook for per-session paperwork discipline — begin / debrief / accurate end-time tracking.
---

## When to opt in

When the project keeps per-session logs under `sessions/` and the user wants discipline around start-of-session and end-of-session paperwork: orientation at start, checklist at end, accurate timestamps for both.

## What this substrate deploys

- `/begin-session` slash command — orient at session start, declare focus, write the session log with `started_at:` filled.
- `/debrief` slash command — work the end-of-session paperwork checklist; verify the log carries `status`, `followups`, blockers.
- `session_stop_log_timing.py` — a non-blocking Stop hook that surgically writes `ended_at:` into this session's log when the session ends. Fixes the lived problem that end-times drift if the model writes them manually.
  It picks the log by the strongest evidence available (`select_log`): the session-manifest **pointer**, else the paperwork-enforcement **edit log**, else newest **mtime**. **Only a record may correct a stamp already in the file** — a session that debriefs and then keeps working is re-stamped when a record names its log, while the mtime tier may stamp an *open* log but never overwrite a committed value, and instead reports a stamp its own mtime contradicts. (A guess that overwrites a record is worse than no correction: mtime reorders under a `git checkout`, or when a file-sync client re-materialises a folder, with no session having run at all.)

## The session-log frontmatter contract

A session log should carry these fields once the session is closed:

```yaml
---
date: YYYY-MM-DD
started_at: YYYY-MM-DDTHH:MM:SS+ZZ:ZZ
ended_at: YYYY-MM-DDTHH:MM:SS+ZZ:ZZ
slug: short-name-unique-within-today
status: done | paused
followups: [...]
---
```

`status: in_progress` is set at `/begin-session` and replaced at `/debrief`. The `started_at:` is written by the model at `/begin-session` (reliable). The `ended_at:` is written by the Stop hook automatically (the model is not asked to write it — that's the cure for the end-time drift problem).

## Convention assumption

Session logs live at `<project>/sessions/YYYY-MM-DD-<slug>.md`. The hook hardcodes this path. Projects with a different convention either fork this substrate or wait for a future configurable-path enhancement.

## Relationship to enforcement

This substrate is the non-blocking recording layer: canonical content for what valid paperwork looks like, plus accurate end-of-session timing. The separate `paperwork-enforcement` substrate adds the opt-in **gate** on top — a blocking Stop hook that refuses to let a session end until each `/debrief` checklist item passes. Keeping them separate is deliberate: this substrate stays non-blocking by design, so a project gets honest records with zero risk of a wedged session and turns on enforcement only when it wants the contract held.
