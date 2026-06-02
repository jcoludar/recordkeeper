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
- `session_stop_log_timing.py` — a non-blocking Stop hook that surgically writes `ended_at:` into the most-recent in-flight session log when the session ends. Fixes the lived problem that end-times drift if the model writes them manually.

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

## Relationship to future Wave 3

This substrate provides the *primitives*: canonical content for what valid paperwork looks like, plus accurate end-of-session timing. The future `paperwork-enforcement` substrate (Wave 3) adds BLOCKING enforcement on top: a separate Stop hook that refuses to let the session end until each `/debrief` checklist item passes. This substrate stays non-blocking forever.
