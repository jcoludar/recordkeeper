# recordkeeper

**recordkeeper keeps your Claude Code sessions on track.** It orients your
agent at the start and leaves an honest, accurately-timestamped record at the
end — so it can stay oriented on what you're doing and where you're going. That works
out of the box and can never wedge a session; turn the dial up and an opt-in
gate won't let a session close until its record checks out.

Beyond that plugin core, the assembler composes a blocking enforcement gate
and a session-manifest layer today, with richer plugin-native layers on the
way — see below.

## Plugin or assembler?

Same product, two install paths:

- **Plugin** (two commands, below) — oriented starts, the `/begin-session` ↔
  `/debrief` loop with a structured `## Handoff` the next session reads cold, and
  honest `ended_at:` stamping. Zero config, no dependencies, and it can never block
  a session.
- **Assembler** with `substrates: [session-paperwork, session-manifest]` —
  everything the plugin does, plus a machine-trustworthy session lifecycle: a
  monotonic `session_no`, a generated `sessions/INDEX.md`, and unclosed-session
  detection. Still non-blocking.
- **Assembler + `paperwork-enforcement`** — adds the blocking Stop gate that won't
  let a session close until its record checks out (frontmatter present, findings
  mirrored into your tracking docs, changelogs in sync).

Rule of thumb: install the plugin to try it; reach for the assembler when you want a
durable session index or machine-enforced discipline. Coders and researchers
juggling many repos usually want the assembler's session layer.

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
- **No runtime dependency.** The plugin core is pure-Python stdlib — no PyYAML, no
  npm, no service to run. (PyYAML is needed only by the opt-in enforcement layer.)

## Turn it up: blocking enforcement (opt-in)

The core records. When a project is ready to go further, recordkeeper can **hold the
line** — a blocking Stop hook that refuses to end a session until the project's
session logs, frontmatter, and cross-doc invariants check out.

> **Refuse to end a session until your paperwork checks out.** A declarative
> `paperwork.yaml` describes what a project requires before a session can close — a
> session log at the expected path, specific frontmatter fields, edits reflected in
> changelogs, findings that appear in both the session log and the tracking doc.
> When the model tries to stop with rules unsatisfied, the Stop hook exits non-zero
> and the session can't close. The model fixes its paperwork, then ends.

This is the *discipline* in the tagline, made literal — not advisory, not
after-the-fact. It's **opt-in** purely so the default stays a zero-friction on-ramp,
not because a gate is at odds with the core: same product, dial turned up. The core
records; the enforcement layer holds the line. A project switches it on once it has
committed to a paperwork contract and wants it machine-checked instead of left to
good intentions.

Today that gate ships through recordkeeper's **assembler** rather than the plugin (a
plugin-native gate is on the roadmap below). The assembler — `tools/assemble.py` —
composes self-contained *substrates* (bundles of slash commands, hooks, and config
fragments) into a project's `CLAUDE.md` and `.claude/` directory in one build step,
with no runtime dependency on this repo afterward.

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
- **`substrate/session-manifest/`** — machine-trustworthy session lifecycle on
  top of session-paperwork: an authoritative in-flight pointer, a monotonic
  `session_no`, a generated `sessions/INDEX.md`, and unclosed ("ghost") sessions
  surfaced — without giving up hand-editable logs. Non-blocking (a recorder that
  fails open). Requires `session-paperwork`.
- **`tools/assemble.py`** — composes selected substrates into a project's
  `CLAUDE.md` and `.claude/`. Takes two positional args: the recordkeeper repo root
  and the target project directory.

Richer plugin-native layers (a plugin-native gate, a plugin-native session
manifest, guard dials, human-only sentinels, multi-session orchestration) are
planned for later releases.

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
