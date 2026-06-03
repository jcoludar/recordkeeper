#!/usr/bin/env python3
"""Stop hook: write `ended_at:` into the most-recent in-flight session log.

Looks for files under `<CLAUDE_PROJECT_DIR>/sessions/*.md` whose frontmatter
has NO `ended_at:` line. Among those, picks the most-recently-mtime'd one
and surgically inserts `ended_at: <ISO-8601-with-tz>` just before the
closing `---` fence. Never round-trips through a YAML parser, so the
file's hand-edited formatting is preserved.

Non-blocking: always exits 0. If there's no sessions/ dir, or no in-flight
log, prints a stderr warning and exits 0. The next /debrief surfaces the gap.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sys
from pathlib import Path


def _frontmatter_region(text: str) -> str | None:
    """Return the YAML region between the opening and closing `---` fences,
    EXCLUSIVE of both fences. Returns None if no well-formed frontmatter."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    return text[4:end]


_ENDED_AT_RE = re.compile(r"^ended_at:\s*\S", re.MULTILINE)


def _has_ended_at(text: str) -> bool:
    """True if the frontmatter region contains an `ended_at:` line with a value."""
    fm = _frontmatter_region(text)
    if fm is None:
        return False
    return bool(_ENDED_AT_RE.search(fm))


def insert_ended_at(text: str, timestamp: str) -> str:
    """Insert `ended_at: <timestamp>` just before the closing `---` fence.

    Caller has verified `ended_at:` is not already present and that the
    text has well-formed open/close fences.
    """
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("no closing frontmatter fence")
    return text[:end] + f"\nended_at: {timestamp}" + text[end:]


def now_iso() -> str:
    """Current local time in ISO 8601 with timezone offset (e.g. 2026-05-12T13:15:00+02:00)."""
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def find_in_flight_log(sessions_dir: Path) -> Path | None:
    """Return the most-recently-mtime'd .md under sessions_dir whose frontmatter
    lacks `ended_at:`. Returns None if directory is missing or no candidates.

    Files without parseable frontmatter are skipped (not treated as in-flight).
    """
    if not sessions_dir.is_dir():
        return None
    candidates: list[Path] = []
    for path in sessions_dir.glob("*.md"):
        try:
            text = path.read_text()
        except OSError:
            continue
        if _frontmatter_region(text) is None:
            continue
        if _has_ended_at(text):
            continue
        candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def main() -> int:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    sessions_dir = Path(project_dir) / "sessions"
    if not sessions_dir.is_dir():
        print(
            f"session_stop_log_timing: no sessions/ dir at {sessions_dir}; nothing to do",
            file=sys.stderr,
        )
        return 0
    path = find_in_flight_log(sessions_dir)
    if path is None:
        print(
            f"session_stop_log_timing: no in-flight session log in {sessions_dir}",
            file=sys.stderr,
        )
        return 0
    text = path.read_text()
    timestamp = now_iso()
    new_text = insert_ended_at(text, timestamp)
    path.write_text(new_text)
    print(
        f"session_stop_log_timing: wrote ended_at={timestamp} into {path.name}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
