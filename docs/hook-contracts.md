# Claude Code hook contracts

A reference for hook authors, distilled from Anthropic's hook documentation and from real burns.

## Why this exists

Claude Code's hook surface is documented at https://code.claude.com/docs/en/hooks. The docs are accurate but terse. This file collects the contract details that are easy to miss and expensive to discover the hard way.

## SessionStart matcher

`SessionStart`'s `matcher` field is **not** a tool glob. Valid values: `startup | resume | clear | compact`. The wildcard `"*"` works but obscures intent. Name the source you mean.

## Stop matcher

`Stop`'s `matcher` is **ignored**. The hook fires unconditionally on every Stop event. recordkeeper's settings fragments omit the `matcher` key for Stop hooks — follow that pattern.

## additionalContext output format

Emit as structured JSON on stdout:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "..."
  },
  "suppressOutput": true
}
```

Plain stdout also works for SessionStart but doesn't let you set `suppressOutput` — the orientation text then leaks into the visible transcript.

## 10,000-char output cap

Hook output (`additionalContext`, `systemMessage`, plain stdout — all of them) has a 10,000-character hard cap. Overflow spills to a file. Future-proof by leaving headroom: aim for ~5,000 characters for `additionalContext`.

## Imperative vs factual phrasing

Phrase `additionalContext` as factual statements, not imperative instructions. Anthropic explicitly flags imperative phrasing as a prompt-injection vector. Use "Workspace: ..." not "You are in ...".

## Exit codes

`0` is silent. `0` + JSON is structured control. `2` is a blocking error (stderr is fed back to Claude). Pick one approach per hook — never mix exit code 2 with JSON.

## CLAUDE_PROJECT_DIR

`$CLAUDE_PROJECT_DIR` is the canonical absolute path for the project. Always quote it. In `settings.json` `command:` fields, use a bare path — the shebang inside the .py does the work; don't prefix with `/usr/bin/env python3`.

## stop_hook_active and infinite loops

If a Stop hook ever blocks (exit 2), it MUST check the `stop_hook_active` field in the input JSON before exiting non-zero. Otherwise Claude can infinite-loop on it (Anthropic issue #55754; entire session can be lost).

## Subagents are context-isolated

`SessionStart` does **not** fire for subagents (Anthropic issues #27661, #14859). Parent hooks and permissions are **not** inherited by subagents. Anything that ships orientation, memory, or methodology via SessionStart-injected `additionalContext` is invisible to dispatched subagents. The workaround is to write orientation to a file the subagent reads — the file-system handoff survives where the hook does not.
