# Parking lot — rules seen once, may generalize later

Rules in this file appeared in exactly one project so far. They graduate into a
tier-1 or tier-2 module the second time the same rule (or a near-equivalent)
needs to apply elsewhere. Until then they live here, with a pointer to the
project they came from.

*Note: some entries reference substrates or kit infrastructure that is private to
the upstream masterbook source and not yet shipped publicly; those references
have been generalized.*

---

## Claude Code hook contracts (Anthropic-doc-derived)

**Source project:** an earlier private substrate (2026-05-27 spec review).
**Promote when:** a second substrate ships a SessionStart or Stop hook.

The following are not opinions — they're contract details from the Anthropic
hooks reference (https://code.claude.com/docs/en/hooks). They burned someone
once already; recording so they don't again.

- **SessionStart `matcher` is `source`, NOT a tool glob.** Valid values: `startup | resume | clear | compact`. The wildcard `"*"` works but obscures intent. Name the source you mean.
- **`Stop` `matcher` is ignored.** The existing `session-paperwork/settings-fragment.json` omits it; follow that pattern.
- **`additionalContext` should be emitted as structured JSON on stdout**, in the shape `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}, "suppressOutput": true}`. Plain stdout also works for SessionStart but doesn't let you set `suppressOutput`, so the orientation text leaks into the visible transcript.
- **10,000-char hard cap** on hook output (additionalContext, systemMessage, plain stdout — all of them). Overflow spills to a file. Future-proof: leave headroom (~5k for `additionalContext`).
- **Phrase `additionalContext` as factual statements, not imperative instructions.** Anthropic explicitly flags imperative phrasing as a prompt-injection vector. "Workspace: …" not "You are in …".
- **Exit codes:** `0` silent; `0 + JSON` for structured control; `2` blocking error (stderr fed to Claude). Pick one approach per hook — never mix exit code 2 with JSON.
- **`$CLAUDE_PROJECT_DIR`** is the canonical absolute path. Always quote it. Bare path (no `/usr/bin/env python3` prefix) in `settings.json` `command:` fields — the shebang inside the .py does the work.
- **Forward-looking: `stop_hook_active`.** If a Stop hook ever blocks (exit 2), it MUST check the `stop_hook_active` field in input JSON before exiting non-zero — otherwise Claude can infinite-loop on it (Anthropic issue #55754, entire session can be lost). Audit `paperwork-enforcement/stop_paperwork_check.py` next time it's touched.

## Subagents are context-isolated

**Source:** ongoing masterbook work (External research).
**Promote when:** another substrate ships behavior that relies on cross-subagent context.

- `SessionStart` does NOT fire for subagents (Anthropic issues #27661, #14859).
- Parent hooks / permissions are NOT inherited by subagents.
- Implication for masterbook: anything that ships orientation, memory, or methodology via SessionStart-injected `additionalContext` is invisible to dispatched subagents. The work-around is to write the orientation to a file the subagent reads (the session log, CLAUDE.md, etc.) — the file-system handoff survives where the hook does not.

## `gh` silently falls back to unauthenticated requests

**Source:** ongoing masterbook work (External research; cli/cli #13317).
**Promote when:** a second masterbook substrate or hook uses `gh`.

- On keychain failure, `gh` silently drops auth and issues unauthenticated requests (60 req/hr limit instead of 5000).
- Any substrate using `gh` should:
  1. Call `gh auth status` once at entry. If non-zero, surface the error verbatim.
  2. Either abort the gh-dependent codepath OR continue with reduced functionality, but never silently fall back to anonymous calls.
- Pattern documented in the source substrate's `commands/begin-session.md` step 3.

## CLAUDE.md is the conversation memo, full stop

**Source:** ongoing masterbook work (Skills review).
**Promote when:** a third substrate considers shipping methodology content.

- Claude Code auto-loads `CLAUDE.md` into every conversation. The mechanism is built in.
- Do NOT invent parallel "read this once per conversation" files (e.g., `HOW_WE_WORK.md`, `METHODOLOGY.md`, `README_FOR_CLAUDE.md`). They duplicate machinery that's already wired up, and the model has to be told to read them — defeating the point.
- If a substrate needs to ship a methodology memo, the assembler should write it to `CLAUDE.md` in the target workspace (overwrite or copy-if-absent per the substrate's intent).
- This project's own `CLAUDE.md` is generated from `CLAUDE.source.md` via `tools/assemble.py` — the same model applies to shipped kits.

## Idempotent installer convention

**Source:** ongoing masterbook work (External research).
**Promote when:** a second masterbook artifact ships an installer.

Three file classes, three policies:
- **Machine-managed files** (hooks, settings.json, commands): **overwrite** every install. The installer is the source-of-truth.
- **User-editable files** (`CLAUDE.md`, configuration, `.gitignore`): **copy only if absent**. User edits survive re-installs.
- **Live source** (links to other repos, working clones): **symlink** with user consent. Don't duplicate; don't move.

## Vendoring shared code: rule of three

**Source:** ongoing masterbook work (vendored helpers).
**Promote when:** the same logic is vendored into a third substrate.

- Current answer when two substrates need the same logic: duplicate it. Each substrate is self-contained; the assembler doesn't reach across substrates.
- Vendoring should be documented: a `vendored-from:` field in the substrate's `module.md` frontmatter pointing at the canonical source, plus a header comment in the vendored file. Makes the "must port future updates manually" obligation discoverable.
- When the same logic is vendored a third time, build a shared helper library inside `masterbook/helpers/` and import from it.

## No-network-on-SessionStart as discipline

**Source:** ongoing masterbook work.
**Promote when:** a second SessionStart hook ships.

- `SessionStart` hooks block conversation startup until they return.
- `git fetch`, `gh issue list`, network calls of any kind can hang or take seconds. On a slow network they cripple session startup.
- Rule: `SessionStart` hooks are strictly offline. Live state lives in slash commands (user-triggered, can afford the latency).
- Worth elevating to a tier-1 rule once a second SessionStart hook respects it.

## Session log as handoff, not cached state files

**Source:** ongoing masterbook work.
**Promote when:** validated by usage; or when a second substrate considers a state-cache file.

- Tempting design: write a `STATE.md` cache file the SessionStart hook reads.
- Better design: the previous session log IS the handoff. Frontmatter (status, ended_at, repos, followups) + a "Repo state at close" body section.
- Wins: single source of truth, no derived state to invalidate, no freshness gates, no `--refresh` flag.
- Trade-off: requires `/debrief` discipline. Mitigation: red-flag table in debrief.md ("'Tiny session, no need to debrief' → next-session orientation breaks").

## Skills-authoring TDD with subagents

**Source:** ongoing masterbook work (Skills review).
**Promote when:** a substrate is rejected by review for discipline-content thinness.

- Writing-skills central tenet: `NO SKILL WITHOUT A FAILING TEST FIRST`.
- For substrates shipping process/discipline content (paperwork, verification, gated handoffs), the test is a subagent pressure test:
  1. RED: dispatch a subagent given the task without the substrate. Observe failure mode (skip the checklist, claim done with broken tests, etc.).
  2. GREEN: ship the substrate. Re-dispatch the subagent. Observe compliance.
  3. REFACTOR: harvest the subagent's rationalizations into a "Common Rationalizations" table inside the substrate's commands.
- Some substrates ship without this loop. Apply for any future paperwork-style substrate.

## Substrate frontmatter completeness

**Source:** ongoing masterbook work (Internal review).
**Promote:** already a project convention; consider validating in `assemble.py`.

- Every substrate's `module.md` must carry: `id`, `name`, `tier`, `default`, `applies_when`, `conflicts_with`, `requires`, `summary`.
- Existing substrates that omit any of these should be backfilled.
- `assemble.py` could grow a validator that errors on missing fields, but for now this is convention not enforcement.

## Iron Law / Red Flags / Rationalization tables as superpowers house style

**Source:** ongoing masterbook work (Skills review).
**Promote when:** a substrate ships discipline content that needs to bite.

- Reference superpowers skills (verification-before-completion, systematic-debugging) lead with: an Iron Law (e.g., "NO CLAIM WITHOUT EVIDENCE"), a Red Flags table ("these thoughts mean STOP"), and a Common Rationalizations table.
- Numbered-list recipes ("do these 5 things") read like suggestions; the three-section structure reads like enforcement.
- Some current substrates ship lightweight Red Flags tables only. Adopt the full pattern for any substrate that enforces a load-bearing process.
