#!/usr/bin/env python3
"""Stop hook — at end of assistant response, ensure today's session log exists.

Project root is taken from $CLAUDE_PROJECT_DIR (preferred) or cwd.
Session logs live in <project>/sessions/YYYY-MM-DD-*.md.
Honors `stop_hook_active` to avoid recursion.
"""
import datetime
import json
import os
import sys
from pathlib import Path

REPO = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
SESSIONS = REPO / "sessions"

EXCLUDE_DIRS = {".venv", "__pycache__", ".git"}
EXCLUDE_PATH_FRAGMENTS = ("scripts/tmp/",)

today = datetime.date.today()
today_iso = today.isoformat()  # YYYY-MM-DD


def file_modified_today(path: Path) -> bool:
    try:
        mtime = datetime.date.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return False
    return mtime == today


def repo_modified_today() -> bool:
    """Any tracked-ish file modified today?"""
    for child in REPO.rglob("*"):
        if not child.is_file():
            continue
        rel = child.relative_to(REPO).as_posix()
        if any(rel.startswith(f"{d}/") or rel == d for d in EXCLUDE_DIRS):
            continue
        if any(frag in rel for frag in EXCLUDE_PATH_FRAGMENTS):
            continue
        if file_modified_today(child):
            return True
    return False


def session_log_exists_today() -> bool:
    if not SESSIONS.exists():
        return False
    for log in SESSIONS.glob(f"{today_iso}-*.md"):
        if file_modified_today(log):
            return True
    return False


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if payload.get("stop_hook_active"):
        sys.exit(0)

    if not repo_modified_today():
        sys.exit(0)

    if session_log_exists_today():
        sys.exit(0)

    reason = (
        "Session log missing.\n"
        f"Files were modified in the repo today but no `sessions/{today_iso}-*.md` "
        "file was updated.\n"
        "Before stopping, write a session log capturing what we did, why, and "
        "what's next. See `sessions/README.md` for the template.\n"
        "If today's work is genuinely trivial and not worth logging, say so "
        "explicitly and stop again."
    )
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


if __name__ == "__main__":
    main()
