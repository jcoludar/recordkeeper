# Substrate authoring

How to write a substrate for recordkeeper.

## File layout

A substrate is a directory under `substrate/<your-substrate-name>/`. Inside:

- `module.md` — required. Declares the substrate's identity, defaults, and dependencies via YAML frontmatter, and describes its behavior in the body.
- `settings-fragment.json` — required. Lists the hooks this substrate registers in `.claude/settings.json`.
- `hooks/` — optional. Python scripts referenced by `settings-fragment.json`.
- `commands/` — optional. Slash command markdown files (e.g. `begin-session.md`).
- Any other supporting files (templates, schemas) — optional.

## `module.md` frontmatter

```yaml
---
id: substrate/<kebab-slug>
name: <Human Readable Name>
tier: substrate
default: true | false
applies_when: "<short condition describing when this substrate is relevant>"
conflicts_with: [<list of substrate ids this substrate cannot coexist with>]
requires: [<list of substrate ids this substrate depends on>]
summary: |
  <one paragraph describing what the substrate provides>
---
```

The first five fields (`id`, `name`, `tier`, `default`, `summary`) are required and
enforced by `tools/validate.py`. `applies_when`, `conflicts_with`, and `requires` are
required by convention but not yet machine-validated.

## `settings-fragment.json`

A partial `.claude/settings.json`. The assembler merges this with other selected substrates' fragments plus the baseline `settings-fragments/*.json`.

Example fragment registering a Stop hook:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/usr/bin/env python3 $CLAUDE_PROJECT_DIR/.claude/hooks/my_stop_check.py"
          }
        ]
      }
    ]
  }
}
```

## Hook scripts

Live under `hooks/<your-script>.py`. The assembler copies them into `<project>/.claude/hooks/` (and sets `+x`). Reference them in `settings-fragment.json` via `/usr/bin/env python3 $CLAUDE_PROJECT_DIR/.claude/hooks/<your-script>.py`.

Read `docs/hook-contracts.md` for the contract details (matcher fields, exit codes, output formats, `stop_hook_active`).

## Testing

Write a subagent pressure test for any substrate that ships discipline. See `CONTRIBUTING.md` for the RED → GREEN → REFACTOR pattern.

## Stuck?

`substrate/session-paperwork/` and `substrate/paperwork-enforcement/` are reference shapes. Copy their structure.
