# Sessions

One file per Claude Code session. Together they form a long-running record of what we've done, why, and what's pending.

## Naming

`sessions/YYYY-MM-DD-<short-name>.md` — date first, kebab-case slug after. Multiple sessions in one day is fine; differentiate by slug.

## Template

Copy this for every new session:

```markdown
---
date: 2026-01-15
started_at: 2026-01-15T10:00:00+00:00   # filled by /begin-session, don't hand-edit
ended_at: 2026-01-15T11:30:00+00:00     # filled by Stop hook, don't hand-edit
slug: short-name-here
topics: [feature-flag-ramp, refactor]   # short keywords — fuel for the index
areas: [engineering]                    # which top-level area folders this touched
status: in_progress                     # in_progress (during) → done | paused (at /debrief)
followups: []                           # short bullets; index will surface these
---

# <Session title — natural language>

## What we did

(Narrative — what got done, in roughly the order it happened.)

## Why

(Motivation. The trigger, the goal, what made this worth a session.)

## Decisions worth remembering

- Decision and the reasoning behind it.

## Files / artefacts touched

- `path/to/file.py` — brief note
- ...

## Open threads / next steps

- [ ] Concrete TODO that survives this session.
- ...
```

**Vocabulary note.** `status` uses underscored values (`in_progress`, `done`, `paused`).
`in_progress` is set automatically by `/begin-session` and replaced at `/debrief`.

`started_at` is filled by `/begin-session`. `ended_at` is filled automatically by the Stop hook. Don't hand-edit either.

## Reading order at the start of a new session

1. Check your project's overview or dashboard — what's urgent.
2. The most recent file in this folder — what just happened.
3. Any index file covering session history — wider context, searchable by topic.
