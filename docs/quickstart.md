# Quickstart

Get to a working blocking Stop hook in five minutes.

## 1. Clone the repo

```bash
git clone https://github.com/jcoludar/recordkeeper.git ~/code/recordkeeper
```

## 2. Install Python dependencies

```bash
pip install -r ~/code/recordkeeper/requirements.txt
```

You need Python 3.11+ and `pyyaml`. To run recordkeeper's own test suite, install the dev extras too: `pip install -r ~/code/recordkeeper/requirements-dev.txt`.

## 3. Copy the example project

```bash
cp -r ~/code/recordkeeper/examples/minimal-project ~/my-claude-project
cd ~/my-claude-project
```

The example ships a working `CLAUDE.source.md`, a minimal `paperwork.yaml`, and a `sessions/README.md` template.

## 4. Run the assembler

```bash
python ~/code/recordkeeper/tools/assemble.py ~/code/recordkeeper .
```

This writes `CLAUDE.md` and `.claude/` (containing `settings.json`, hooks, and slash commands) into your project.

## 5. Start a Claude Code session in the project

Open Claude Code in `~/my-claude-project`. The `/begin-session` slash command orients you and creates a session log under `sessions/`.

## 6. Try to end the session without paperwork

Tell Claude to stop. The Stop hook fires, reads `paperwork.yaml`, finds no in-flight session log matching today's date, and exits 2. The model sees the error and refuses to end. You're blocked.

## 7. Write the session log, then end again

Use `/begin-session` (or hand-write a log following the template). The Stop hook re-runs, finds the log, validates its frontmatter, and exits 0. Session ends cleanly.

## What's next

- Read `docs/concepts.md` for the vocabulary.
- Read `docs/hook-contracts.md` if you plan to author your own hooks.
- Read `docs/substrate-authoring.md` to extend recordkeeper with your own substrates.
- Read `PARKING_LOT.md` for things you'll wish you had known.
