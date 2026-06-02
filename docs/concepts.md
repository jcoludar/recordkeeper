# Concepts

Three terms recur across recordkeeper's documentation. Knowing them lets the rest of the docs read fast.

## Substrate

A **substrate** is a self-contained bundle of: a `module.md` describing its purpose and contract, a `settings-fragment.json` registering its hooks, zero or more Python hook scripts under `hooks/`, and zero or more slash commands under `commands/`. A substrate has no source files outside its own directory.

The assembler (`tools/assemble.py`) walks a list of selected substrates, merges their settings fragments into a single `.claude/settings.json`, copies their hook scripts and slash commands into `.claude/`, and produces a single `CLAUDE.md` for the target project.

The unit of reuse is the substrate. Adding a substrate to a project is a one-line edit to `CLAUDE.source.md`.

## Assembler

The **assembler** is `tools/assemble.py`. It takes two positional arguments: the recordkeeper repo root and the target project directory. It reads `<project>/CLAUDE.source.md`, picks substrates listed under `masterbook.substrates:`, and writes the project's `CLAUDE.md` plus a populated `.claude/` directory.

The assembler is the only build step. After it runs, the target project has no runtime dependency on recordkeeper — the hooks and commands live inside `.claude/` and execute via the Claude Code harness.

## Blocking enforcement

A **blocking Stop hook** is a Python script registered as a Stop hook in `.claude/settings.json`. When Claude Code emits a Stop event (the model trying to end its turn), the hook runs. If it exits non-zero, the Stop event is refused — the model gets the stderr as feedback and tries again.

recordkeeper's `paperwork-enforcement` substrate ships a blocking Stop hook driven by a declarative `paperwork.yaml`. The YAML describes which files must exist, which frontmatter fields are required, which content must appear in multiple places. The Stop hook refuses to let a session end until those rules are satisfied.

This is what "blocking" means in recordkeeper: not advisory, not after-the-fact — the session literally cannot close until the paperwork is honest.
