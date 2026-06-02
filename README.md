# recordkeeper

**Blocking Stop hooks for Claude Code — refuse to end a session until your project's
session logs, frontmatter, and cross-doc invariants check out.**

Most Claude Code add-ons give the model more capability. recordkeeper does the
opposite: it tells the model *no*. A declarative `paperwork.yaml` describes what
your project requires before a session can end — a session log at the expected
path, specific frontmatter fields, edits reflected in changelogs, findings that
appear in both the session log and the tracking doc. When the model tries to stop
with rules unsatisfied, the Stop hook exits non-zero and the session can't close.
The model fixes its paperwork, then ends.

The rule engine is the headline, but the unit of reuse is the **substrate** — a
self-contained bundle of slash commands, hooks, and config fragments that drop
into any project. v0 ships two: session paperwork (start/end discipline) and
paperwork enforcement (the rule engine). An assembler composes the substrates you
pick into a single `CLAUDE.md` plus a populated `.claude/` directory. One build
step, no runtime dependency on this repo after install.

Five-minute install, MIT, Python + PyYAML, no npm. Read [`PARKING_LOT.md`](./PARKING_LOT.md)
first if you're authoring your own hooks — it documents eleven Anthropic
hook-contract gotchas the docs don't.

## Quickstart

```bash
git clone https://github.com/OWNER/recordkeeper.git ~/code/recordkeeper
pip install -r ~/code/recordkeeper/requirements.txt

cp -r ~/code/recordkeeper/examples/minimal-project ~/my-claude-project
cd ~/my-claude-project
python ~/code/recordkeeper/tools/assemble.py ~/code/recordkeeper .
```

Start a Claude Code session in `~/my-claude-project`. Try to end it without
writing a session log → the Stop hook blocks. Done.

## What's in the box

- **`substrate/session-paperwork/`** — `/begin-session` and `/debrief` slash
  commands, session log template, non-blocking Stop hook that fills `ended_at:`
  automatically.
- **`substrate/paperwork-enforcement/`** — blocking Stop hook driven by a
  declarative `paperwork.yaml`. Predicates: file existence, frontmatter
  validation, edit-log filtering, cross-document consistency.
- **`tools/assemble.py`** — composes selected substrates into a project's
  `CLAUDE.md` and `.claude/` directory. Takes two positional args: the
  recordkeeper repo root and the target project directory.

## What makes this different

- **Declarative paperwork rules in YAML, not procedural JS.** Rules read as
  contracts, not as scripts.
- **Stop hooks that gate state, not just save it.** Most ecosystem Stop hooks
  auto-checkpoint or summarize. This one refuses to end the session.
- **Substrate composition through a build system.** Project conventions
  compose; you pick the substrates you want and the assembler produces a
  single `CLAUDE.md` + populated `.claude/`.

## Prior art

- [anthropics/skills](https://github.com/anthropics/skills) — the official skill
  format; recordkeeper does not compete with it, it complements it.
- [carlrannaberg/claudekit](https://github.com/carlrannaberg/claudekit) — the
  closest framework-like project; uses Stop hooks for auto-checkpointing.
- [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) —
  the leading skill aggregator. Read it for the breadth of what's possible.

## License

MIT. See [LICENSE](./LICENSE).
