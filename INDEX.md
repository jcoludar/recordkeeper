# recordkeeper — module index

This index is the contract `tools/validate.py` checks: every module listed here must exist on disk; every module on disk under `tier-1/` should appear here.

## Substrates

- `substrate/session-paperwork/` — start/end session paperwork primitives.
- `substrate/paperwork-enforcement/` — blocking Stop hook + declarative `paperwork.yaml` rule engine.

## Tier-1 (always-on modules)

- [File safety](tier-1/file-safety.md) — Read before edit; Know-Check-Overwrite; Edit don't Write on existing docs; versioned writes when uncertain.
- [Recovery path](tier-1/recovery-path.md) — Every project documents how to undo before it has need of one.
- [Reproducibility](tier-1/reproducibility.md) — Helpers as `.py` files; absolute paths; venv-pinned Python; no inline scripting in chat or shell.
- [Scope and boundaries](tier-1/scope-and-boundaries.md) — Stay inside the project working tree. Ask before touching source-of-truth files in shared locations.
- [Secrets and credentials](tier-1/secrets.md) — Never read, paste, log, or commit `.env`, `*.key`, `*.pem`, `credentials*`, `*_secret*`, `*_token*` files.
- [Session discipline](tier-1/session-discipline.md) — Session log on changed-file days; append-only audit/decision logs; commit before stop when files changed.
- [Shell hygiene](tier-1/shell-hygiene.md) — One command per Bash call. No `python -c`. No `echo >>` / heredoc append. Edit, don't redirect.

## Helpers

- `helpers/recovery_template.md` — Starter template for a project's recovery-path document.

## Build system

- `tools/assemble.py` — composes selected substrates into a project's `CLAUDE.md` and `.claude/` directory.
- `tools/validate.py` — validates this index against the on-disk tree.
