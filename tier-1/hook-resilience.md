---
id: tier-1/hook-resilience
name: Hook resilience
tier: 1
default: true
applies_when: [any]
conflicts_with: []
requires: []
summary: How a hook behaves when its own code breaks — gates fail closed with a reachable bypass; recorders fail open and degrade. Plus the exit-code contract and the stop_hook_active guard.
---

# Hook resilience

The contract every recordkeeper hook obeys, and the contract every substrate's hooks are checked against. A hook is one of two kinds, and the kind decides what happens when the hook's *own* code fails (import error, unhandled exception, broken dependency).

## Two kinds of hook

1. **Gate** — a hook that can *block* (a `Stop` hook that exits 2, a `PreToolUse` hook that denies a tool call). Enforcement and security live here.
2. **Recorder** — a hook that never blocks (a `PostToolUse` logger, the non-blocking `Stop` end-time writer). Bookkeeping lives here.

## The fail-policy (the load-bearing rule)

3. **Gates fail CLOSED, with a reachable bypass.** If a gate's own code cannot run, it must block (exit 2) — never wave the action through. A gate that fails open silently stops enforcing and nobody notices. But a gate whose code is broken must not brick the session: ship a documented bypass (an environment variable) checked *first*, before any import or logic that can fail, so the operator can always get past a broken gate to fix it. The bypass is loud — print to stderr that the gate was bypassed.
4. **Recorders fail OPEN and degrade.** If a recorder's own code fails, catch it, print a one-line stderr warning, and exit 0. Never block a user's work because bookkeeping broke. "Always exits 0" must be *true*, not just intended — wrap the body so an unhandled exception cannot turn into a non-zero exit.

## The exit-code contract

5. **Pick one mechanism per hook; never mix.** Exit `0` = allow (silent). Exit `0` *plus* a JSON decision block on stdout = structured control (e.g. `{"decision": "block", "reason": "..."}`). Exit `2` = block, with the reason on **stderr** (fed back to the model). A JSON decision block is delivered on a **zero** exit — emitting `{"decision":"block"}` while also exiting 2 is the contradiction to avoid. Decide per hook: stderr-on-exit-2, *or* JSON-on-exit-0. Both are valid; mixing them is the bug.

## The stop_hook_active guard

6. **Any Stop hook that can exit 2 MUST honor `stop_hook_active` first.** Read the Stop envelope from stdin; if `stop_hook_active` is true, the hook already blocked once and the model is re-running Stop — bow out with exit 0. A blocking Stop hook that ignores this can infinite-loop and burn the whole session (Anthropic issue #55754).

**Why:** the failure mode of a gate (let a bad action through) and the failure mode of a recorder (block good work) are opposites, so their resilience must be opposite too. Encoding which-is-which here means every hook author — and every review — has one place to check the behavior against.
