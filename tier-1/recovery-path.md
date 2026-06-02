---
id: tier-1/recovery-path
name: Recovery path
tier: 1
default: true
applies_when: [any]
conflicts_with: []
requires: []
summary: Every project documents how to undo before it has need of one.
---

# Recovery path

Every project ships with a populated `RECOVERY.md` (template in `masterbook/helpers/recovery_template.md`) describing, in order of preference, how to undo a destructive action. Each project picks the path that applies to its data:

1. **Cloud-sync version history** (default for `data/` cloud-sync-linked projects): right-click → Version history (single file) or Rewind folder (folder-level). 30+ days of history per file.
2. **Local backup snapshot** (default for non-cloud-sync content).
3. **Git reflog / `git restore --source` / branch-from-reflog** (for git-tracked files).
4. **Re-fetch from upstream** (for downloaded datasets, public sequences, generated artifacts).
5. **Re-run pipeline scripts** (last resort — costs compute time).

**Tell the user about the recovery path BEFORE proposing destructive operations.** If the only recovery path is "re-run the pipeline (4 hours)", the cost calculus is different from "cloud-sync restore (30 seconds)".

If the project's data has no recovery path, the recovery file says so explicitly: *"This project has no automatic recovery for `<directory>`. Treat any overwrite as permanent."*
