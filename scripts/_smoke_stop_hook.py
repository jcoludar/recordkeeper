#!/usr/bin/env python3
"""One-shot smoke test helper: run stop_paperwork_check.py against a project dir.

Usage:
    python scripts/_smoke_stop_hook.py <project_dir>

Synthesizes a minimal Stop-hook JSON envelope on stdin, captures stderr + exit code,
and prints both. Exit code mirrors the hook's exit code.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <project_dir>", file=sys.stderr)
        return 1

    project_dir = Path(sys.argv[1]).resolve()
    hook = project_dir / ".claude" / "hooks" / "stop_paperwork_check.py"

    if not hook.is_file():
        print(f"stop_paperwork_check.py not found at {hook}", file=sys.stderr)
        return 1

    envelope = json.dumps({"session_id": "test", "stop_hook_active": False, "cwd": str(project_dir)})
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)

    result = subprocess.run(
        [sys.executable, str(hook)],
        input=envelope,
        capture_output=True,
        text=True,
        env=env,
    )

    print(f"exit code: {result.returncode}")
    print("--- stderr ---")
    print(result.stderr, end="")
    if result.stdout:
        print("--- stdout ---")
        print(result.stdout, end="")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
