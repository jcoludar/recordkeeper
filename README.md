# recordkeeper

**Effortless session record-keeping for Claude Code: orient at the start, run a
checklist at the end, get accurate end-times — and it can _never_ refuse to let
you stop.**

Most Claude Code add-ons give the model more capability. recordkeeper gives it
*memory and discipline*: every working session leaves a dated log with reliable
timestamps, written without you having to think about it.

## Install (Claude Code plugin)

```bash
/plugin marketplace add github:jcoludar/recordkeeper
/plugin install recordkeeper
```

That's the supported path. You immediately get the **core**:

- **`/begin-session`** — orient against your priorities and the previous session,
  then write a new session log with `started_at:` filled in.
- **`/debrief`** — walk the end-of-session checklist (status, follow-ups, blockers)
  before you stop.
- **Automatic `ended_at:` stamping on `SessionEnd`** — a non-blocking hook writes the
  real end-time into the in-flight log when the session closes, so end-times never
  drift the way they do when the model writes them by hand.

The core is **non-blocking by construction — it can never refuse to let you stop.**
It has zero blocking exit paths; the worst it can do on a bad day is fail open and
write nothing.

## What makes the core different

- **It records, it doesn't gate.** Most ecosystem Stop / SessionEnd hooks
  auto-checkpoint or summarize. recordkeeper's core simply guarantees an accurate,
  honestly-timestamped session log — and otherwise stays out of your way.
- **Timestamps you can trust.** `started_at:` is written when you begin;
  `ended_at:` is stamped by the harness at `SessionEnd`, not guessed by the model
  after the fact.
- **No runtime dependency.** Python + PyYAML, no npm, no service to run.

## Legacy: the assembler & blocking enforcement (opt-in)

Before the plugin, recordkeeper shipped as an **assembler**: `tools/assemble.py`
composes self-contained *substrates* — bundles of slash commands, hooks, and
config fragments — into a project's `CLAUDE.md` and `.claude/` directory. One build
step, no runtime dependency on this repo afterward. That distribution remains for
now, and it's where the **blocking** behavior lives.

> **Blocking Stop hooks — refuse to end a session until your project's session
> logs, frontmatter, and cross-doc invariants check out.** A declarative
> `paperwork.yaml` describes what a project requires before a session can end — a
> session log at the expected path, specific frontmatter fields, edits reflected in
> changelogs, findings that appear in both the session log and the tracking doc.
> When the model tries to stop with rules unsatisfied, the Stop hook exits non-zero
> and the session can't close. The model fixes its paperwork, then ends.

This is the opposite of the plugin core's promise, and that's deliberate: it's an
**opt-in** layer for projects that have committed to a paperwork contract and want
it machine-enforced. The plugin core never blocks; the enforcement substrate is for
teams who explicitly want a gate.

### Assembler quickstart

```bash
git clone https://github.com/jcoludar/recordkeeper.git ~/code/recordkeeper
pip install -r ~/code/recordkeeper/requirements.txt

cp -r ~/code/recordkeeper/examples/minimal-project ~/my-claude-project
cd ~/my-claude-project
python ~/code/recordkeeper/tools/assemble.py ~/code/recordkeeper .
```

Start a Claude Code session in `~/my-claude-project`, try to end it without writing
a session log → the Stop hook blocks. Done.

### Substrates in the box

- **`substrate/session-paperwork/`** — `/begin-session` and `/debrief`, the
  session-log template, and a *non-blocking* Stop hook that fills `ended_at:`
  automatically.
- **`substrate/paperwork-enforcement/`** — the *blocking* Stop hook driven by a
  declarative `paperwork.yaml`. Predicates: file existence, frontmatter validation,
  edit-log filtering, cross-document consistency.
- **`tools/assemble.py`** — composes selected substrates into a project's
  `CLAUDE.md` and `.claude/`. Takes two positional args: the recordkeeper repo root
  and the target project directory.

Richer plugin-native layers (blocking enforcement, a session manifest, guard dials,
human-only sentinels, multi-session orchestration) are planned for later releases.

If you're authoring your own hooks, read [`PARKING_LOT.md`](./PARKING_LOT.md) first —
it documents hard-won Anthropic hook-contract gotchas plus other
substrate-engineering lessons the docs don't.

## Prior art

- [anthropics/skills](https://github.com/anthropics/skills) — the official skill
  format; recordkeeper does not compete with it, it complements it.
- [carlrannaberg/claudekit](https://github.com/carlrannaberg/claudekit) — the
  closest framework-like project; uses Stop hooks for auto-checkpointing.
- [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) —
  the leading skill aggregator. Read it for the breadth of what's possible.

## License

MIT. See [LICENSE](./LICENSE).
