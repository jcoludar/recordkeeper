---
description: Run the end-of-session paperwork checklist before stopping
---

# /debrief — end-of-session checklist

When invoked, work through each item below. If anything is missing, fix it now — don't claim done.

## 1. Session log written for today

Today's session log should exist at `sessions/YYYY-MM-DD-<slug>.md` with frontmatter:

```yaml
---
date: YYYY-MM-DD
started_at: YYYY-MM-DDTHH:MM:SS+ZZ:ZZ
slug: short-name
status: done | paused
followups: [...]
---
```

Body must cover: what we did, why, decisions worth remembering, files touched, what's next.

## 2. Status set honestly

- `done` — all planned work landed.
- `paused` — incomplete but at a safe stopping point; followups describe the next concrete step.

If you can't write `done` truthfully, write `paused` and explain why in the body.

## 3. Follow-ups captured in frontmatter

Every loose end the next session needs to know about goes in `followups:` (a YAML list). Prose alone is not enough — the next session may grep the field.

## 4. Blockers surfaced

If anything blocks the next session (failing test, env issue, unresolved decision), it appears in `followups:`.

## On `ended_at:`

You don't write this field. The **SessionEnd** hook fills it automatically when the session ends — once, at the real end, and it can never block your stop. Just confirm to the user that paperwork is closed.

## Edge case: `/begin-session` was skipped

If no session log exists for today, write one now. Set `started_at:` to your best estimate of when work began.

## Closing

Report status: which items passed, which (if any) couldn't be completed. Don't claim the checklist passed when it didn't.
