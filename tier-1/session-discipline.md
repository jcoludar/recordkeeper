---
id: tier-1/session-discipline
name: Session discipline
tier: 1
default: true
applies_when: [any]
conflicts_with: []
requires: []
summary: Session log on changed-file days; append-only audit/decision logs; commit before stop when files changed.
---

# Session discipline

A `Stop` hook checks: if any tracked file was modified today and no `sessions/YYYY-MM-DD-*.md` log exists, the hook blocks the stop and asks for a session log.

1. **At session start:** read the most recent `sessions/*.md` for context on what was done previously and any handed-off TODOs.
2. **At session end:** write `sessions/YYYY-MM-DD-<short-name>.md` capturing what was done, why, key decisions, and what's next. One file per session.
3. **If today's work is genuinely trivial** (e.g., reading-only, or a typo fix the user explicitly tagged as not worth logging), say so explicitly to the user and let the hook clear once they acknowledge.
4. **Append-only logs.** Audit logs, decision logs, KNOWN_ISSUES.md, and STATE_OF_KNOWLEDGE.md are append-only at the *file* level. To revise an entry, append a new dated section that supersedes the old one — never edit history in place.
5. **Commit before Stop on changed-file days.** If the project is under git, the session log + the day's work should be in one or more commits before the session ends. The user controls commit timing; do not commit autonomously without permission.
