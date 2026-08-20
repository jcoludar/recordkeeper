#!/usr/bin/env python3
"""Stop hook: write `ended_at:` into this session's log.

Surgically inserts (or corrects) `ended_at: <ISO-8601-with-tz>` inside the
frontmatter of `<CLAUDE_PROJECT_DIR>/sessions/*.md`. Never round-trips through
a YAML parser, so the file's hand-edited formatting is preserved.

WHICH LOG — three tiers of evidence, strongest first (`select_log`):

  1. `pointer`  — the session-manifest in-flight pointer. A RECORD of which log
                  belongs to this session.
  2. `edit-log` — the paperwork-enforcement PostToolUse record. Names this
                  session's `started_at` and the instant of its newest edit;
                  the log carrying that `started_at` is this session's.
  3. `mtime`    — newest unstamped log. A GUESS, and the only tier available
                  when neither sibling substrate is deployed.

⚠ **Only a RECORD may correct an existing stamp.** A session that debriefs
(status -> done, stamp written) and then keeps working carries a stale end
time; tiers 1 and 2 re-stamp it, because they know the log is this session's.
Tier 3 never overwrites a committed value — newest-mtime selection handing back
the wrong file has been measured repeatedly (a file-sync client re-materialising
a folder, or a `git checkout`, reorders every mtime with no session having run
at all), and a
guess that overwrites a record is worse than no correction at all. Where tier 3
sees a stamp that its own mtime contradicts by more than STALE_TOLERANCE_SECONDS,
it refuses and says so.

Non-blocking: always exits 0. If there's no sessions/ dir, or no in-flight
log, prints a stderr warning and exits 0. The next /debrief surfaces the gap.
"""
from __future__ import annotations

import datetime as dt
import json
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
_ENDED_AT_VALUE_RE = re.compile(r"^ended_at:\s*(\S+)", re.MULTILINE)
_ENDED_AT_LINE_RE = re.compile(r"^ended_at:.*$", re.MULTILINE)


def _strip_yaml_quotes(value: str) -> str:
    """Drop one matching pair of surrounding quotes, if present."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _has_ended_at(text: str) -> bool:
    """True if the frontmatter region contains an `ended_at:` line with a value."""
    fm = _frontmatter_region(text)
    if fm is None:
        return False
    return bool(_ENDED_AT_RE.search(fm))


def _ended_at_value(text: str) -> str | None:
    """Return the `ended_at:` value from the frontmatter region, or None."""
    fm = _frontmatter_region(text)
    if fm is None:
        return None
    m = _ENDED_AT_VALUE_RE.search(fm)
    return _strip_yaml_quotes(m.group(1)) if m else None


def replace_ended_at(text: str, timestamp: str) -> str:
    """Rewrite the existing `ended_at:` line in the frontmatter, in place.

    The line keeps its position; the body is untouched byte-for-byte, including
    any line that happens to look like frontmatter. Raises if there is no
    closing fence or no `ended_at:` line to replace — a correction that silently
    became an insertion would put two `ended_at:` keys in one document.
    """
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("no closing frontmatter fence")
    head, tail = text[:end], text[end:]
    new_head, n = _ENDED_AT_LINE_RE.subn(f"ended_at: {timestamp}", head, count=1)
    if n == 0:
        raise ValueError("no ended_at: line to replace")
    return new_head + tail


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


_STARTED_AT_RE = re.compile(r"^started_at:\s*(\S+)", re.MULTILINE)


def _started_at_value(text: str) -> str | None:
    """Return the `started_at:` value from the frontmatter region, or None."""
    fm = _frontmatter_region(text)
    if fm is None:
        return None
    m = _STARTED_AT_RE.search(fm)
    return _strip_yaml_quotes(m.group(1)) if m else None


def clamp_ended_at(ended: str, started: str | None) -> str:
    """Return `ended`, but never earlier than `started` — a session cannot end
    before it began (guards against clock skew). If `started` is missing or
    unparseable, or `ended >= started`, `ended` is returned unchanged.
    """
    if not started:
        return ended
    try:
        ended_dt = dt.datetime.fromisoformat(ended)
        started_dt = dt.datetime.fromisoformat(started)
        if ended_dt < started_dt:
            return started
    except (ValueError, TypeError):
        # Unparseable, or a naive/aware mismatch — don't guess, keep ended.
        return ended
    return ended


_STATUS_RE = re.compile(r"^status:\s*(\S+)", re.MULTILINE)


def _status_value(text: str) -> str | None:
    fm = _frontmatter_region(text)
    if fm is None:
        return None
    m = _STATUS_RE.search(fm)
    return m.group(1) if m else None


def _pointer_inflight(sessions_dir: Path) -> Path | None:
    """Prefer the session-manifest in-flight pointer when present and valid.

    The pointer is a RECORD of which log belongs to this session, so it is
    returned whether or not the log already carries `ended_at:` — a stale stamp
    on the pointed log is precisely the case this hook exists to correct.
    """
    project_dir = sessions_dir.parent
    ptr = project_dir / ".claude" / "state" / "session-manifest" / "in-flight.json"
    try:
        data = json.loads(ptr.read_text())
    except (OSError, ValueError):
        return None
    log = data.get("log") if isinstance(data, dict) else None
    if not log:
        return None
    cand = project_dir / log
    try:
        if cand.is_file() and cand.parent == sessions_dir:
            return cand
    except OSError:
        return None
    return None


def _edit_log_session(project_dir: Path) -> tuple[str, str] | None:
    """Return `(started_at, newest_edit_ts)` for the session the paperwork edit
    log is currently recording, or None.

    The in-flight session is the one owning the LAST parseable entry; its newest
    edit is the max `ts` among that session's entries only — a later edit by a
    different session says nothing about this one. Entries are appended by a
    PostToolUse hook on Edit/Write, so this hook's own `write_text` never
    appears here: the instant is genuine work, not the recorder's own footprint.
    """
    path = project_dir / ".claude" / "state" / "paperwork-edit-log.jsonl"
    try:
        raw = path.read_text()
    except OSError:
        return None
    entries: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("started_at") and obj.get("ts"):
            entries.append(obj)
    if not entries:
        return None
    started = entries[-1]["started_at"]
    newest: str | None = None
    newest_dt: dt.datetime | None = None
    for entry in entries:
        if entry["started_at"] != started:
            continue
        try:
            when = dt.datetime.fromisoformat(entry["ts"])
        except (ValueError, TypeError):
            continue
        if newest_dt is None or when > newest_dt:
            newest_dt, newest = when, entry["ts"]
    if newest is None:
        return None  # nothing parseable: cannot prove anything, so claim nothing
    return (started, newest)


def _edit_log_inflight(sessions_dir: Path) -> Path | None:
    """The log whose frontmatter `started_at:` matches the edit log's session."""
    session = _edit_log_session(sessions_dir.parent)
    if session is None:
        return None
    started, _newest = session
    matches: list[Path] = []
    for path in sessions_dir.glob("*.md"):
        try:
            text = path.read_text()
        except OSError:
            continue
        if _frontmatter_region(text) is None:
            continue
        if _started_at_value(text) == started:
            matches.append(path)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        # Two logs claiming one started_at. Naming either would settle a genuine
        # tie by sort order; the weaker tier decides, and says nothing false.
        print(
            "session_stop_log_timing: %d logs share started_at=%s; no log named by the edit log"
            % (len(matches), started),
            file=sys.stderr,
        )
    return None


def select_log(sessions_dir: Path) -> tuple[Path | None, str]:
    """Return `(log, tier)` — this session's log and the evidence that named it.

    `tier` is one of "pointer", "edit-log", "mtime", or "" when nothing was
    found. The caller needs the tier, not just the path: only a record tier may
    overwrite a stamp that is already in the file.
    """
    if not sessions_dir.is_dir():
        return (None, "")
    pointed = _pointer_inflight(sessions_dir)
    if pointed is not None:
        return (pointed, "pointer")
    by_record = _edit_log_inflight(sessions_dir)
    if by_record is not None:
        return (by_record, "edit-log")
    candidates: list[Path] = []
    for path in sessions_dir.glob("*.md"):
        try:
            text = path.read_text()
        except OSError:
            continue
        if _frontmatter_region(text) is None:
            continue
        if _has_ended_at(text):
            continue  # the mtime tier is a guess and may only touch open logs
        candidates.append(path)
    if not candidates:
        return (None, "")
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return (candidates[0], "mtime")


def find_in_flight_log(sessions_dir: Path) -> Path | None:
    """This session's log, by the strongest available evidence (`select_log`).

    Files without parseable frontmatter are skipped. A log that already carries
    `ended_at:` is returned only when a RECORD named it — never by mtime.
    """
    return select_log(sessions_dir)[0]


#: How far a file's mtime must run past its own `ended_at:` before the mtime
#: tier will call the stamp suspect. The hook's own write moves mtime a fraction
#: of a second past the value it just wrote, and an advisory that fires on every
#: ordinary Stop is one every session learns to ignore. Two minutes separates
#: "the recorder just wrote this" from "work continued after the debrief".
STALE_TOLERANCE_SECONDS = 120


def _is_after(later: str | None, earlier: str | None) -> bool:
    """True only when both parse and `later` is strictly after `earlier`.

    Unparseable input answers False: a recorder that cannot PROVE a stamp is
    stale must leave the value in the file alone.
    """
    if not later or not earlier:
        return False
    try:
        return dt.datetime.fromisoformat(later) > dt.datetime.fromisoformat(earlier)
    except (ValueError, TypeError):
        return False


def _advise_uncorrectable_stamp(sessions_dir: Path) -> None:
    """Name a stamp that the file's own mtime contradicts, without touching it.

    Reached only when no record named a log — i.e. neither the session-manifest
    pointer nor the paperwork edit log is deployed here. The advisory is the
    honest half of the fix for such a project: report, and say what would make
    the correction possible, rather than writing on the strength of a guess.
    """
    newest: Path | None = None
    newest_mtime = 0.0
    for path in sessions_dir.glob("*.md"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if newest is None or mtime > newest_mtime:
            newest, newest_mtime = path, mtime
    if newest is None:
        return
    try:
        stamp = _ended_at_value(newest.read_text())
    except OSError:
        return
    if stamp is None:
        return
    try:
        stamped_at = dt.datetime.fromisoformat(stamp).timestamp()
    except (ValueError, TypeError, OverflowError):
        return
    drift = newest_mtime - stamped_at
    if drift <= STALE_TOLERANCE_SECONDS:
        return
    print(
        f"session_stop_log_timing: {newest.name} carries ended_at={stamp} but was modified "
        f"{int(drift // 60)} min later — cannot correct it: no session record (manifest pointer "
        "or paperwork edit log) names this session's log, and mtime alone is not evidence",
        file=sys.stderr,
    )


def main() -> int:
    # Non-blocking recorder: ALWAYS exit 0. Any unexpected failure degrades
    # (logs a warning) rather than blocking the session — a bookkeeping error
    # must never hold a session hostage (tier-1/hook-resilience: recorders fail
    # open). exit 1 here would surface a non-blocking error to the user for no gain.
    try:
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        sessions_dir = Path(project_dir) / "sessions"
        if not sessions_dir.is_dir():
            print(
                f"session_stop_log_timing: no sessions/ dir at {sessions_dir}; nothing to do",
                file=sys.stderr,
            )
            return 0
        path, tier = select_log(sessions_dir)
        if path is None:
            print(
                f"session_stop_log_timing: no in-flight session log in {sessions_dir}",
                file=sys.stderr,
            )
            _advise_uncorrectable_stamp(sessions_dir)
            return 0
        text = path.read_text()
        if _status_value(text) != "done":
            print(
                f"session_stop_log_timing: {path.name} status is not 'done'; not stamping ended_at",
                file=sys.stderr,
            )
            return 0
        timestamp = clamp_ended_at(now_iso(), _started_at_value(text))
        existing = _ended_at_value(text)
        if existing is None:
            path.write_text(insert_ended_at(text, timestamp))
            print(
                f"session_stop_log_timing: wrote ended_at={timestamp} into {path.name}",
                file=sys.stderr,
            )
            return 0
        # The log already carries a stamp. Only a RECORD may correct it.
        if tier == "mtime":
            print(
                f"session_stop_log_timing: {path.name} already carries ended_at={existing}; "
                "mtime alone cannot correct a stamp",
                file=sys.stderr,
            )
            return 0
        if tier == "edit-log":
            session = _edit_log_session(sessions_dir.parent)
            newest = session[1] if session else None
            if not _is_after(newest, existing):
                print(
                    f"session_stop_log_timing: {path.name} ended_at={existing} is still current "
                    f"(newest recorded edit {newest}); nothing to correct",
                    file=sys.stderr,
                )
                return 0
        path.write_text(replace_ended_at(text, timestamp))
        print(
            f"session_stop_log_timing: re-stamped {path.name} ended_at={timestamp} "
            f"(was {existing}, stale by the {tier} record)",
            file=sys.stderr,
        )
        return 0
    except Exception as exc:  # noqa: BLE001 — recorder fails open and degrades
        print(
            f"session_stop_log_timing: degraded (exit 0), could not write ended_at — {exc}",
            file=sys.stderr,
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
