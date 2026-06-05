#!/usr/bin/env python3
"""SessionEnd hook: stamp `ended_at:` into the most-recent in-flight session log.

recordkeeper CORE. Fires once when the session ends. SessionEnd is structurally
unable to block termination, so this can NEVER refuse a stop. Finds the most-
recently-modified `sessions/*.md` whose frontmatter lacks `ended_at:` and
surgically inserts `ended_at: <ISO-8601-with-tz>` before the closing `---`,
never round-tripping YAML (hand-edited formatting preserved).

Always exits 0. Resolves the project dir from CLAUDE_PROJECT_DIR, falling back
to the SessionEnd event's `cwd` on stdin, then to the current directory.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path


# A session log's frontmatter is delimited by `---` fences. The CLOSING fence is
# `\n---` followed by either a newline or end-of-file, so a frontmatter-only log
# with no trailing newline is still recognized (and stamped) rather than silently
# skipped. NOTE: LF line endings are assumed; a CRLF (`\r\n`) log is treated as
# having no frontmatter and is left untouched.
_CLOSE_FENCE_RE = re.compile(r"\n---(?:\n|\Z)")


def _closing_fence_index(text: str) -> int | None:
    """Start index of the closing `---` fence, or None if no frontmatter.

    Requires the opening `---` fence on line 1; matches the first closing fence
    at or after it, terminated by a newline or end-of-file.
    """
    if not text.startswith("---\n"):
        return None
    m = _CLOSE_FENCE_RE.search(text, 4)
    return m.start() if m else None


def frontmatter_region(text: str) -> str | None:
    """The YAML between the opening and closing `---` fences, exclusive. None if absent."""
    end = _closing_fence_index(text)
    return None if end is None else text[4:end]


_ENDED_AT_RE = re.compile(r"^ended_at:\s*\S", re.MULTILINE)


def has_ended_at(text: str) -> bool:
    fm = frontmatter_region(text)
    return bool(fm and _ENDED_AT_RE.search(fm))


def insert_ended_at(text: str, timestamp: str) -> str:
    """Insert `ended_at: <timestamp>` just before the closing `---` fence."""
    end = _closing_fence_index(text)
    if end is None:
        raise ValueError("no closing frontmatter fence")
    return text[:end] + f"\nended_at: {timestamp}" + text[end:]


def now_iso() -> str:
    """Current local time, ISO 8601 with tz offset (e.g. 2026-06-05T17:00:00+02:00)."""
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


_STARTED_AT_RE = re.compile(r"^started_at:\s*(\S+)", re.MULTILINE)


def started_at_value(text: str) -> str | None:
    fm = frontmatter_region(text)
    if not fm:
        return None
    m = _STARTED_AT_RE.search(fm)
    return m.group(1) if m else None


def clamp_ended_at(ended: str, started: str | None) -> str:
    """Never earlier than `started` (guards clock skew). Unchanged if unparseable."""
    if not started:
        return ended
    try:
        if dt.datetime.fromisoformat(ended) < dt.datetime.fromisoformat(started):
            return started
    except (ValueError, TypeError):
        return ended
    return ended


def find_in_flight_log(sessions_dir: Path) -> Path | None:
    """Most-recently-mtime'd `*.md` whose frontmatter lacks `ended_at:`. None if none."""
    if not sessions_dir.is_dir():
        return None
    candidates: list[Path] = []
    for path in sessions_dir.glob("*.md"):
        try:
            text = path.read_text()
        except OSError:
            continue
        if frontmatter_region(text) is None:
            continue
        if has_ended_at(text):
            continue
        candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    return candidates[0]


def resolve_project_dir() -> Path:
    """CLAUDE_PROJECT_DIR, else the SessionEnd event `cwd` on stdin, else cwd."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    try:
        data = json.load(sys.stdin)
        cwd = data.get("cwd") if isinstance(data, dict) else None
        if cwd:
            return Path(cwd)
    except (ValueError, OSError):
        pass
    return Path.cwd()


def main() -> int:
    # Recorder fails OPEN: always exit 0. A bookkeeping error must never hold a
    # session hostage — and on SessionEnd it structurally cannot block anyway.
    try:
        sessions_dir = resolve_project_dir() / "sessions"
        path = find_in_flight_log(sessions_dir)
        if path is None:
            print(
                f"session_end_stamp: no in-flight session log under {sessions_dir}",
                file=sys.stderr,
            )
            return 0
        text = path.read_text()
        timestamp = clamp_ended_at(now_iso(), started_at_value(text))
        path.write_text(insert_ended_at(text, timestamp))
        print(
            f"session_end_stamp: wrote ended_at={timestamp} into {path.name}",
            file=sys.stderr,
        )
        return 0
    except Exception as exc:  # noqa: BLE001 — recorder fails open and degrades
        print(f"session_end_stamp: degraded (exit 0) — {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
