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
import time
from pathlib import Path


# ── TWO REFUSALS, each paid for by a wrong timestamp somebody had to chase ──────────────
#
# This hook's selection is `newest mtime`, which is a GUESS: it cannot tell whose log it is
# looking at. Both gates below exist because a guess with no bound will confidently answer a
# question it was never able to ask.
#
# ⚠ THE DOCTRINE, and it decides every tie here: PREFER NO STAMP OVER A FABRICATED ONE.
# A missing `ended_at:` is honestly missing and anyone can see it. A fabricated one is
# indistinguishable from a real measurement for the rest of the file's life — it survives
# `git log`, it survives review, and it will be quoted back as evidence.

# GATE 2's tolerance. A log that THIS session closed was written seconds ago; one untouched
# for hours belongs to a session that is long gone.
#   Measured, 2026-08-21, in a project running this hook: a log whose session ran 05:12→05:44
#   was stamped `09:42:55` — by a DIFFERENT session that ended four hours later and merely
#   happened to be the next one to end in that directory.
#   ⚠ Deliberately generous. The cost of being too tight is a missing stamp (honest, visible,
#   fixable by hand); the cost of being too loose is a fabricated one (invisible, permanent).
#   Those costs are not symmetric, so the threshold is not centred.
STALE_TOLERANCE_SECONDS = 1800  # 30 minutes


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


_STATUS_RE = re.compile(r"^status:\s*[\"']?([A-Za-z_]+)", re.MULTILINE)

# The author-declared terminal states. `paused` is HERE ON PURPOSE and it is the one line in
# this file most likely to be "tidied" into `== "done"` by a future reader copying the
# substrate's Stop hook. Do not.
#   SessionEnd fires ONCE, at true session end. Stop fires at EVERY assistant stop, so the
#   Stop hook must demand `done` or it would stamp mid-session. This hook has the opposite
#   problem: a session that ends `paused` really did end, and its end time is real. Requiring
#   `done` here would make the hook silently inert for every paused session forever.
_TERMINAL_STATUSES = frozenset({"done", "paused"})


def status_value(text: str) -> str | None:
    fm = frontmatter_region(text)
    if not fm:
        return None
    m = _STATUS_RE.search(fm)
    return m.group(1) if m else None


def is_closed_by_its_author(text: str) -> bool:
    """GATE 1 — has anyone declared this session over?

    An `in_progress` log is a session still being written. Stamping it asserts an end time
    for something nobody has said has ended — measured: a log received `ended_at: 22:52:51`
    while `status:` still read `in_progress` and its session ran 13 minutes longer.

    A MISSING `status:` is refused too, and that is not an oversight: absence is not consent.
    A log with no status has had no author declare anything about it.
    """
    return status_value(text) in _TERMINAL_STATUSES


def was_touched_this_session(path: Path, now: float | None = None) -> bool:
    """GATE 2 — is this plausibly a log THIS session wrote?

    Selection is newest-mtime and there is no record here saying which log belongs to which
    session (the session-manifest substrate has one; the plugin core ships no state dir).
    So the honest bound is recency: a log this session closed was written moments ago.

    ⚠ STATED BOUND, because it is a heuristic and should never be mistaken for a record:
    this cannot separate two CONCURRENT sessions in one project — both write recently, and
    mtime cannot attribute either. It only catches the measured case, which is a NEW session
    ending in a repo that still holds an OLDER unstamped log. Fixing the concurrent case
    needs a record, not a better guess.
    """
    try:
        age = (time.time() if now is None else now) - path.stat().st_mtime
    except OSError:
        return False
    return age <= STALE_TOLERANCE_SECONDS


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
        # Both refusals SAY SO on stderr. A hook that declines in silence is
        # indistinguishable from one that is not installed, and this project has already
        # paid for that confusion once — a peer spent a morning asking what had written a
        # timestamp, because nothing anywhere announced who was writing them.
        if not is_closed_by_its_author(text):
            print(
                f"session_end_stamp: {path.name} status is "
                f"{status_value(text)!r}, not a terminal state; not stamping ended_at",
                file=sys.stderr,
            )
            return 0
        if not was_touched_this_session(path):
            print(
                f"session_end_stamp: {path.name} was last modified more than "
                f"{STALE_TOLERANCE_SECONDS}s ago — it belongs to an earlier session, "
                f"not this one; not stamping ended_at",
                file=sys.stderr,
            )
            return 0
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
