# Quickstart

recordkeeper has two on-ramps. Start with the **core** — install the plugin, and your sessions get oriented at the start and honestly timestamped at the end, with nothing that can ever wedge a session. When a project wants more, **turn it up**: the assembler adds a blocking gate that won't let a session close until its paperwork checks out.

## The core (install the plugin)

### 1. Install

```bash
/plugin marketplace add github:jcoludar/recordkeeper
/plugin install recordkeeper
```

### 2. Begin a session

Run `/begin-session`. It orients you against your priorities and the previous session, then writes a new `sessions/YYYY-MM-DD-<slug>.md` log with `started_at:` filled in.

### 3. Work, then end

Run `/debrief` to walk the closing checklist (status, follow-ups, blockers) and finalize the log. When the session ends, a non-blocking `SessionEnd` hook stamps the real `ended_at:` into the in-flight log — so end-times never drift the way they do when the model writes them by hand.

That's the whole core. It can never refuse to let you stop; on a bad day the worst it does is fail open and write nothing.

## Turn it up: the blocking gate (assembler)

When a project has committed to a paperwork contract and wants it machine-checked, recordkeeper can **hold the line** — a blocking Stop hook that refuses to end a session until the project's `paperwork.yaml` rules are satisfied. Today that gate ships through the **assembler** rather than the plugin.

### 1. Clone the repo

```bash
git clone https://github.com/jcoludar/recordkeeper.git ~/code/recordkeeper
```

### 2. Install Python dependencies

```bash
pip install -r ~/code/recordkeeper/requirements.txt
```

You need Python 3.11+ and `pyyaml`. To run recordkeeper's own test suite, install the dev extras too: `pip install -r ~/code/recordkeeper/requirements-dev.txt`.

### 3. Copy the example project

```bash
cp -r ~/code/recordkeeper/examples/minimal-project ~/my-claude-project
cd ~/my-claude-project
```

The example ships a working `CLAUDE.source.md`, a minimal `paperwork.yaml`, and a `sessions/README.md` template.

### 4. Run the assembler

```bash
python ~/code/recordkeeper/tools/assemble.py ~/code/recordkeeper .
```

This writes `CLAUDE.md` and `.claude/` (containing `settings.json`, hooks, and slash commands) into your project.

### 5. Start a session and try to end it without paperwork

Open Claude Code in `~/my-claude-project` and tell Claude to stop before writing a session log. The Stop hook fires, reads `paperwork.yaml`, finds no in-flight session log, and exits 2 — the model sees the error and refuses to end. You're blocked.

### 6. Write the session log, then end again

Use `/begin-session` (or hand-write a log following the template). The Stop hook re-runs, finds the log, validates its frontmatter, and exits 0. The session ends cleanly.

## What's next

- Read `docs/concepts.md` for the vocabulary.
- Read `docs/hook-contracts.md` if you plan to author your own hooks.
- Read `docs/substrate-authoring.md` to extend recordkeeper with your own substrates.
- Read `PARKING_LOT.md` for things you'll wish you had known.
