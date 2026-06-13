---
description: Start-of-session orientation — read priors, declare focus, create the session log
---

# /begin-session — start-of-session orientation

Run before doing task work for the session. Sets up context, intent, and the session record.

## 1. Read the previous session's log

Open the most recent file in `sessions/`. Read its `## Handoff` (state-at-close · next · blockers)
first — it was written for exactly this moment — then note:
- **Status.** If the prior session is `paused` or `in_progress`, address that first.
- **Follow-ups.** Which apply today? Surface any blockers to the user.
- **Decisions worth remembering.** Patterns the prior session validated.

**If the most recent log is still `in_progress` (an unclosed prior session)**, surface it to the user —
"the previous session (`<slug>`) didn't close cleanly; here's its handoff/followups" — and OFFER to
close it. NEVER silently rewrite or auto-close another session's record; closing it is the user's call.

(If this is the first session in the project, skip this step.)

## 2. Read the priority dashboard

If the project maintains a priorities file (`OVERVIEW.md`, `NOW.md`, etc.), read it. It overrides individual followups when they've been overtaken by events.

## 3. Declare focus for this session

State to the user what you intend to do this session. Examples:
- "Focus: finish T6 fix from yesterday."
- "Open-ended: user wants to discuss Wave 3 design before any code."

This declaration anchors the session — `/debrief` later checks: did we do what we said?

## 4. Create the session log now

Write `sessions/YYYY-MM-DD-<slug>.md` with frontmatter:

```yaml
---
date: YYYY-MM-DD
started_at: YYYY-MM-DDTHH:MM:SS+ZZ:ZZ
slug: <unique-within-today>
status: in_progress
---
```

- `started_at:` is the current timestamp in ISO 8601 with the system's local timezone offset (e.g. `2026-05-12T08:30:00+02:00`).
- `slug:` must be unique among today's session logs in `sessions/`.
- `status: in_progress` while the session is live.

The body opens with your focus statement from step 3. You'll add to it during the session and finalize it at `/debrief`.
