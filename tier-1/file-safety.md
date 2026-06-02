---
id: tier-1/file-safety
name: File safety
tier: 1
default: true
applies_when: [any]
conflicts_with: []
requires: []
summary: Read before edit; Know-Check-Overwrite; Edit don't Write on existing docs; versioned writes when uncertain.
---

# File safety

1. **Read before Edit.** Never edit a file without reading it first in the current session. The state in your head is not the state on disk.
2. **Know, Check, then Overwrite.** To overwrite a file, all three must be true: you KNOW what's in it and why it's wrong (stated, not assumed); you CHECKED that it actually is what you think (headers read, rows counted); you've told the user what will change. If any check fails, write to a NEW timestamped filename `<basename>.<YYYYMMDD_HHMMSS>.<ext>` and let the user manage cleanup.
3. **Edit, don't Write, on existing documentation.** Surgical `Edit` calls on existing docs are fine. Never use `Write` to overwrite an existing markdown doc unless explicitly approved. Append-only logs (audit log, decision log, session log) are *file-level* append-only — to revise, write a new timestamped version and link it.
4. **Preserve existing files during refactors.** Never delete component files during upgrades. Add new ones alongside. Migration happens explicitly, not by silent replacement.
5. **No `--force` flags without explicit user approval.** `--force` silently overwrites many files at once; you cannot Know-Check all of them. Default to running without `--force`; if a script says "skipping because output exists", that's correct behavior.
6. **When in doubt, ask. When certain, ask anyway.** The cost of a 30-second confirmation is always lower than the cost of lost data. "I'll just check this one thing" precedes most file destruction.
