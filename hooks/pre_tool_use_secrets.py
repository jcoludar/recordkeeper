#!/usr/bin/env python3
"""PreToolUse hook — block reads/edits/writes of secret-like files.

Patterns blocked (case-insensitive substring match on filename):
  - .env, .env.* (env files)
  - *.key, *.pem (cryptographic keys)
  - credentials*, *_secret*, *_token* (credential containers)

Exit 2 = block; stderr message visible to Claude.
Exit 0 = allow.
"""
import json
import re
import sys
from pathlib import Path

PATTERNS = [
    re.compile(r"(^|/)\.env(\..*)?$", re.IGNORECASE),
    re.compile(r"\.key$", re.IGNORECASE),
    re.compile(r"\.pem$", re.IGNORECASE),
    re.compile(r"(^|/)credentials[^/]*$", re.IGNORECASE),
    re.compile(r"_secret[^/]*$", re.IGNORECASE),
    re.compile(r"_token[^/]*$", re.IGNORECASE),
]

GUARDED_TOOLS = {"Read", "Edit", "Write"}


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool = payload.get("tool_name") or payload.get("tool")
    if tool not in GUARDED_TOOLS:
        sys.exit(0)

    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not file_path:
        sys.exit(0)

    name = Path(file_path).name
    full = file_path
    for pat in PATTERNS:
        if pat.search(name) or pat.search(full):
            print(
                f"Secrets hook blocked {tool} on {file_path}.\n"
                "If this file is intentionally non-secret (e.g., a public key), add it to "
                ".claude/settings.json `permissions.allow` for this project specifically.",
                file=sys.stderr,
            )
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
