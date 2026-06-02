"""JSONL edit-log helpers for paperwork-enforcement.

The PostToolUse hook calls `append_entry` once per Edit / Write / NotebookEdit
tool use. The Stop hook calls `read_entries` + `filter_for_session` to gather
the set of files modified in the current session (keyed by started_at).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def canonicalize_path(path_str: str, *, project_dir: Path) -> str:
    """Return path repo-relative if under `project_dir`, else as a resolved absolute string.

    Relative inputs are first resolved against the current cwd.
    """
    p = Path(path_str)
    if not p.is_absolute():
        p = p.resolve()
    else:
        p = p.resolve()
    project_dir = project_dir.resolve()
    try:
        return str(p.relative_to(project_dir))
    except ValueError:
        return str(p)


def append_entry(
    log_path: Path,
    *,
    started_at: str,
    tool: str,
    path: str,
    ts: str,
) -> None:
    """Append one JSONL entry to log_path. Creates parent dirs as needed."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "started_at": started_at,
        "ts": ts,
        "tool": tool,
        "path": path,
    }
    with log_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def read_entries(log_path: Path) -> list[dict[str, Any]]:
    """Read all valid JSONL entries from log_path. Missing file → []. Corrupted lines skipped."""
    if not log_path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line in log_path.read_text().splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            entries.append(json.loads(s))
        except json.JSONDecodeError:
            continue
    return entries


def filter_for_session(
    entries: list[dict[str, Any]], *, started_at: str
) -> list[dict[str, Any]]:
    """Return only entries whose `started_at` matches the session."""
    return [e for e in entries if e.get("started_at") == started_at]
