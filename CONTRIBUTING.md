# Contributing to recordkeeper

Thanks for your interest. recordkeeper is small on purpose — it ships building blocks ("substrates") that compose into a Claude Code project's `CLAUDE.md` and `.claude/` machinery. The bar for additions is *load-bearing in two or more projects*, not *interesting in one*.

## Adding a new substrate

A substrate is a self-contained bundle of slash commands, hooks, and config fragments. Its `module.md` carries this frontmatter:

```yaml
---
id: <kebab-slug>
name: <Human Readable Name>
tier: substrate
default: opt-in | opt-out
applies_when: "<short condition describing when this substrate is relevant>"
conflicts_with: [<other substrate ids>]
requires: [<substrate ids this one depends on>]
summary: |
  <one paragraph describing what the substrate provides>
---
```

The body of `module.md` describes the substrate's contract, behavior, and any constraints. See `substrate/session-paperwork/module.md` for a reference shape.

## The rule-of-two promotion model

Some content lives in `PARKING_LOT.md` first — a rule or observation that came from one project. It graduates into `tier-1/` or `tier-2/` when the same rule needs to apply to a second project. Don't promote prematurely.

## Test discipline — subagent pressure test

For substrates that ship process discipline (paperwork, verification, gated handoffs), the test is a subagent pressure test:

1. **RED:** Dispatch a subagent with the task without the substrate. Observe the failure mode (skips a checklist item, claims done with broken tests, etc.).
2. **GREEN:** Ship the substrate. Re-dispatch. Observe compliance.
3. **REFACTOR:** Harvest the subagent's rationalizations into a "Common Rationalizations" table inside the substrate's slash commands.

## PR conventions

- One substrate per PR where possible.
- Include the subagent pressure test results in the PR description for discipline-ship substrates.
- Run `pytest tests/` and `python scripts/publishability_audit.py .` before opening; both must pass.
- Small, focused commits beat large mega-PRs.
