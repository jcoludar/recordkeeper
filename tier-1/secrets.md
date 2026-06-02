---
id: tier-1/secrets
name: Secrets and credentials
tier: 1
default: true
applies_when: [any]
conflicts_with: []
requires: []
summary: Never read, paste, log, or commit `.env`, `*.key`, `*.pem`, `credentials*`, `*_secret*`, `*_token*` files.
---

# Secrets and credentials

A `PreToolUse(Read|Edit|Write)` hook blocks file access for paths matching any of these patterns:

- `.env`, `.env.*` (environment files)
- `*.key`, `*.pem` (cryptographic keys)
- `credentials*` (credential containers)
- `*_secret*`, `*_token*` (named secrets and tokens)

If the hook blocks legitimate access (e.g., you genuinely need to read a *public* key), add a project-specific override in `.claude/settings.json` `permissions.allow` — narrow the override to the specific path, never the whole pattern.

**Never:**
- Paste secret values into chat or code comments.
- Commit a file containing secrets, even if it's in `.gitignore` (`.gitignore` doesn't help if it's already tracked).
- Log secret values to stdout, telemetry, or session logs.

**Recovery if a secret leaks:** treat the leaked value as compromised — rotate immediately, not "later". Force-pushing to remove it from git history is not sufficient (caches, mirrors, forks retain).
