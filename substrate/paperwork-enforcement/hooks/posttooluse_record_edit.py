#!/usr/bin/env python3
"""PostToolUse hook: append one entry to the paperwork edit log per Edit / Write / NotebookEdit.

Reads the tool envelope from stdin; resolves the project's in-flight session
log to scope the entry by started_at; appends one JSONL line to
.claude/state/paperwork-edit-log.jsonl with a real now()-stamped ts.

Non-blocking: always exits 0. If anything goes wrong (no in-flight log,
unparseable envelope, IO error) we log to stderr and return 0 — never
block the user's edits because paperwork isn't initialized.

Substrate-wide invariant: every timestamp produced here comes from
datetime.now(tz=local) at the moment of capture.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

# Sibling _paperwork_* modules sit next to this file; sys.path[0] is the script
# directory when invoked as `python <path>`.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import _paperwork_session_log as sl
import _paperwork_edit_log as el


TRACKED_TOOLS = {"Edit", "Write", "NotebookEdit"}


def _extract_path(tool_name: str, tool_input: dict) -> str | None:
    if tool_name == "NotebookEdit":
        return tool_input.get("notebook_path")
    return tool_input.get("file_path")


def _now_iso() -> str:
    """Real-time ISO 8601 with local tz offset. Substrate-wide invariant."""
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def main() -> int:
    try:
        raw = sys.stdin.read()
        envelope = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        print(f"posttooluse_record_edit: bad envelope: {exc}", file=sys.stderr)
        return 0

    tool_name = envelope.get("tool_name")
    if tool_name not in TRACKED_TOOLS:
        return 0
    tool_input = envelope.get("tool_input", {})
    raw_path = _extract_path(tool_name, tool_input)
    if not raw_path:
        return 0

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
    # Resolve the session-log dir from paperwork.yaml so non-default layouts
    # (e.g. docs/sessions) still get their edits recorded. Stay non-blocking:
    # any config problem falls back to the default "sessions".
    session_log_dir = "sessions"
    try:
        import _paperwork_config as cfg

        config_path = project_dir / ".claude" / "paperwork.yaml"
        if config_path.is_file():
            session_log_dir = cfg.load_and_validate(config_path).get(
                "session-log-dir", "sessions"
            )
    except Exception:
        session_log_dir = "sessions"
    sessions_dir = project_dir / session_log_dir
    inflight = sl.find_in_flight_log(sessions_dir)
    if inflight is None:
        return 0  # silent no-op

    try:
        text = inflight.read_text()
    except OSError as exc:
        print(f"posttooluse_record_edit: could not read in-flight log: {exc}", file=sys.stderr)
        return 0
    started_at, _slug = sl.parse_started_at_and_slug(text)
    if started_at is None:
        return 0  # silent no-op

    canon = el.canonicalize_path(raw_path, project_dir=project_dir)
    log_file = project_dir / ".claude" / "state" / "paperwork-edit-log.jsonl"
    try:
        el.append_entry(
            log_file,
            started_at=started_at,
            tool=tool_name,
            path=canon,
            ts=_now_iso(),
        )
    except OSError as exc:
        print(f"posttooluse_record_edit: could not write log: {exc}", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
