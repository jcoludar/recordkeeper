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
- "Open-ended: user wants to discuss the design before any code."

This declaration anchors the session — `/debrief` later checks: did we do what we said?

## 3b. The standing session shape — assume it, do not ask for it

**UNLESS THE USER SAYS OTHERWISE IN THIS SESSION'S PROMPT, these are the defaults. They are not a
suggestion to confirm and not a question to raise — a user who wants a different shape will say so.**

- **Work to roughly 400K tokens**, then stop and run `/debrief`. Do not wind down early "to be
  safe", and do not blow past it to finish one more thing.
- **The debrief must be enough to start a successor COLD** — a session that has none of this
  conversation, none of its context, and only the log. That is the acceptance test for the whole
  closing ritual, and it is what the handover section is measured against.
- ⚠ **A budget is not a licence to fill it.** If the declared work finishes at 120K, close cleanly
  at 120K. The number is a *ceiling on running long*, never a floor on stopping short — padding a
  session to reach it produces exactly the low-value tail a successor has to read past.

🧨 **WHY THIS IS WRITTEN DOWN RATHER THAN REPEATED.** An operator was typing this rule into the
prompt of **every session in every project**, which makes it a property of that operator's patience
rather than of the process — and a rule that survives only by being re-typed is one bad day away
from being absent. ⇒ If a project genuinely needs a different budget, it overrides here in its own
`CLAUDE.md`, where the override is visible; it does not get re-negotiated per session.

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
