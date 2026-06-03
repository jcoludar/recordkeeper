---
id: substrate/paperwork-enforcement
name: Paperwork enforcement
tier: substrate
default: false
applies_when: "project has a .claude/paperwork.yaml describing required artifacts"
conflicts_with: []
requires:
  - substrate/session-paperwork
summary: Blocking Stop-hook + rule engine that enforces a project's paperwork contract declared in .claude/paperwork.yaml.
---

## When to opt in

When the project has committed to a paperwork contract — session logs with specific frontmatter, cross-document consistency rules, conditional handoff requirements — and wants those rules machine-checked at every Stop event, not left to discipline. Pair with `session-paperwork` (required dependency); this substrate enforces what that one describes.

## What this substrate deploys

- `posttooluse_record_edit.py` — non-blocking PostToolUse hook for `Edit` / `Write` / `NotebookEdit`. Appends one JSONL entry to `.claude/state/paperwork-edit-log.jsonl` keyed by the in-flight session's `started_at`.
- `stop_paperwork_check.py` — BLOCKING Stop hook. Loads `.claude/paperwork.yaml`, runs all configured rules, exits 0 silently on pass or 2 with a structured stderr report on fail.
- Six `_paperwork_*` helper modules (session log reader, edit log JSONL, config loader/validator, token interpolation, predicates, rule engine) deployed alongside the hooks.

The substrate becomes active only when the project also writes `.claude/paperwork.yaml`. Without that config, both hooks are no-ops.

## The `.claude/paperwork.yaml` contract

Top-level shape:

```yaml
session-log-dir: "sessions"     # default; projects that keep logs under docs/sessions/ set "docs/sessions"
files:                           # list of file-rule entries
  - path: "sessions/{today}-{session-slug}.md"
    must-exist: true
    must-be-modified-this-session: true
    frontmatter:
      status: {required: true, in: [done, paused]}
    when:
      when-files-modified-matching: "src/**"
consistency:                     # list of cross-document rules
  - name: "every finding in session log appears in TECHNICAL_DEBT"
    find: "F\\d+"
    in: "sessions/{today}-*.md"
    must-also-appear-in: ["TECHNICAL_DEBT.md"]
```

**Interpolation tokens** (expanded in every string value): `{today}` (today's date), `{session-slug}` (from the in-flight log's `slug:` field).

**Predicate vocabulary v1:**
- `must-exist: <bool>` — at least one (or zero) matched files.
- `must-be-modified-this-session: <bool>` — matched file(s) appear in this session's edit log.
- `frontmatter.<field>: {required, equals, in, matches}` — field-by-field assertions.
- `when.when-files-modified-matching: <glob>` — gate a file rule on edit-log activity.
- `tier: <1|2>` — rule severity, on any file or consistency rule. Tier 1 (default) blocks the Stop; tier 2 is surfaced as a non-blocking advisory ("deferred"). Lets a project distinguish "must fix before next session" from "track but don't block".
- `consistency` — for each regex capture in source body, the literal capture must appear in every listed target file (or in at least one match of a glob target). The `find:` regex is validated at config load (must compile; at most one capturing group).

See `paperwork.yaml.example` shipped with this substrate for a fully-annotated template.

## How enforcement fires

Every Stop event:
1. Load `paperwork.yaml`. Missing → silent no-op.
2. Resolve in-flight session log under `session-log-dir`.
3. Interpolate `{today}` / `{session-slug}` in the config.
4. Filter the edit log to the current session via `started_at`.
5. Walk every `files:` and `consistency:` rule; collect every failure.
6. Exit 0 silent on pass. Any tier-1 failure → exit 2 with `paperwork-enforcement: N rule(s) failed.` + grouped reasons. Tier-2-only failures → exit 0 with a non-blocking advisory.

Failed Stop blocks the session from ending. Fix each item, end session again — fresh evaluation, no cached state.

## Substrate-wide invariant: real timestamps only

Every timestamp the substrate writes (PostToolUse edit log `ts:`, `{today}` interpolation) comes from `datetime.now(tz=local)` or `date.today()` at moment of capture. Never derived, never reconstructed. This invariant is load-bearing for any time-window predicate the rule engine ever grows.

## Validation CLI

`python .claude/hooks/stop_paperwork_check.py --validate-config <path>` checks a `paperwork.yaml` standalone (no Stop-hook context) — useful in CI or `pre-commit`. Returns 0 / 2.

## Out of scope (intentional)

Project-specific interpolation tokens beyond `{today}` / `{session-slug}` (no `{ticket-id}` etc. — those need pluggable extractors, a future substrate). Tag-based `when:` conditions. Time-window predicates. Auto-fix mode (substrate reports, never edits). Cross-day session enforcement.
