---
id: tier-1/reproducibility
name: Reproducibility
tier: 1
default: true
applies_when: [any]
conflicts_with: []
requires: []
summary: Helpers as `.py` files; absolute paths; venv-pinned Python; no inline scripting in chat or shell.
---

# Reproducibility

1. **Logic lives in files, not in chat or shell.** For data inspection, parsing, aggregation: write a helper to `scripts/` or `helpers/` and run it. Inline `python -c` blocks and ad-hoc shell pipelines vanish from history; helper scripts persist as reproducible artifacts.
2. **Pin the Python interpreter.** Use the project's `.venv/bin/python` by absolute path, not whatever `python` happens to resolve to. If the project has multiple venvs (e.g., a tool that requires Python 3.11 and another that requires 3.13), document which path is correct for which subsystem.
3. **Absolute paths over `cd`.** Avoid `cd /path && cmd` chains. If a tool requires a specific working directory, set it explicitly inside the helper script (`os.chdir`) and document why.
4. **Random seeds are part of the experiment.** For ML / sampling / bootstrap workflows, set explicit seeds (`random_state=42` is the default convention) and record them in any output. See `tier-2/reproducibility-manifest` for the full discipline.
5. **Don't write to source-of-truth without a sidecar.** When a script outputs to a path used by another tool, it should also write a small log entry (CLI args, git revision, timestamp) so a future reader can reproduce the run.
