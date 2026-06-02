---
masterbook:
  modules: []
  substrates:
    - session-paperwork
    - paperwork-enforcement
  commands: []
  permissions_extra: []
---

# example-project

A minimal example project demonstrating recordkeeper's session-paperwork and
paperwork-enforcement substrates working end to end.

## How sessions are tracked

Every Claude Code session in this project gets a session log under `sessions/`
(see `sessions/README.md` for the template). The `/begin-session` slash command
creates the log at the start of a session; `/debrief` walks the closing checklist.

The Stop hook refuses to let the session end until `paperwork.yaml`'s rules pass.
