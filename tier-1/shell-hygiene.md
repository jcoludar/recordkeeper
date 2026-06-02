---
id: tier-1/shell-hygiene
name: Shell hygiene
tier: 1
default: true
applies_when: [any]
conflicts_with: []
requires: []
summary: One command per Bash call. No `python -c`. No `echo >>` / heredoc append. Edit, don't redirect.
---

# Shell hygiene

These rules are enforced by a `PreToolUse(Bash)` hook (exit 2 — Claude cannot bypass).

1. **No chained commands in Bash.** No `&&`, `;`, `||`, `|`. One command per Bash call. If you need a sequence, make multiple Bash calls. If you need a pipeline, write a helper script.
2. **No `python -c "..."` blocks.** Write a real `.py` file under `scripts/` (or `helpers/`) and run it. Inline Python in Bash hides logic from review and from git history.
3. **No `echo >>` / `printf >>` / `cat <<EOF` for file writes or appends.** Use the `Edit` tool for surgical changes and `Write` for new files. The shell is not a text editor.
4. **Prefer dedicated tools over Bash.** `Read` instead of `cat`, `Edit` instead of `sed`, `Write` instead of redirected `echo`. Bash is for shell-only work — `awk`, `grep`, `find`, `jq`, `git`, `ls`, etc.
5. **Use absolute paths.** Never `cd /abs/path && cmd`; the chained form fails permission allowlist matching and breaks unattended runs.

**Why:** Each `&&` / `|` / `;` makes the compound string fail to match any single allowlist rule, triggering an interactive approval prompt that breaks unattended sessions. Helper scripts are reproducible artifacts; throwaway pipelines are not.
