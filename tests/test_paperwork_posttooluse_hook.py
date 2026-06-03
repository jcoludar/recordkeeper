"""Tests for posttooluse_record_edit hook."""
import importlib.util
import json
import sys
from io import StringIO
from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).resolve().parent.parent
    / "substrate"
    / "paperwork-enforcement"
    / "hooks"
    / "posttooluse_record_edit.py"
)


def _load_hook():
    """Import the hook module by path (sibling _paperwork_* imports work via sys.path)."""
    SUBSTRATE_HOOKS = HOOK_PATH.parent
    if str(SUBSTRATE_HOOKS) not in sys.path:
        sys.path.insert(0, str(SUBSTRATE_HOOKS))
    spec = importlib.util.spec_from_file_location("posttooluse_record_edit", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["posttooluse_record_edit"] = module
    spec.loader.exec_module(module)
    return module


def _project_with_inflight_log(tmp_path: Path, started_at: str = "2026-05-13T08:00:00+02:00") -> Path:
    """Set up a tmp project with an in-flight session log."""
    project = tmp_path / "proj"
    project.mkdir()
    sessions = project / "sessions"
    sessions.mkdir()
    log = sessions / "2026-05-13-x.md"
    log.write_text(
        f"---\ndate: 2026-05-13\nstarted_at: {started_at}\nslug: x\n---\n\nbody\n"
    )
    return project


def test_edit_tool_appends_entry(tmp_path, monkeypatch):
    hook = _load_hook()
    project = _project_with_inflight_log(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    edited = project / "sessions" / "2026-05-13-x.md"
    envelope = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(edited)},
    }
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(envelope)))

    rc = hook.main()
    assert rc == 0

    log_file = project / ".claude" / "state" / "paperwork-edit-log.jsonl"
    assert log_file.is_file()
    entry = json.loads(log_file.read_text().strip())
    assert entry["started_at"] == "2026-05-13T08:00:00+02:00"
    assert entry["tool"] == "Edit"
    assert entry["path"] == "sessions/2026-05-13-x.md"
    assert "ts" in entry


def test_write_tool_appends_entry(tmp_path, monkeypatch):
    hook = _load_hook()
    project = _project_with_inflight_log(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    envelope = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(project / "new.md")},
    }
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(envelope)))
    assert hook.main() == 0
    log_file = project / ".claude" / "state" / "paperwork-edit-log.jsonl"
    entry = json.loads(log_file.read_text().strip())
    assert entry["tool"] == "Write"
    assert entry["path"] == "new.md"


def test_notebookedit_uses_notebook_path(tmp_path, monkeypatch):
    hook = _load_hook()
    project = _project_with_inflight_log(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    envelope = {
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": str(project / "nb.ipynb"), "cell_id": "c1"},
    }
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(envelope)))
    assert hook.main() == 0
    log_file = project / ".claude" / "state" / "paperwork-edit-log.jsonl"
    entry = json.loads(log_file.read_text().strip())
    assert entry["tool"] == "NotebookEdit"
    assert entry["path"] == "nb.ipynb"


def test_unsupported_tool_noops(tmp_path, monkeypatch):
    hook = _load_hook()
    project = _project_with_inflight_log(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    envelope = {"tool_name": "Read", "tool_input": {"file_path": "x"}}
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(envelope)))
    assert hook.main() == 0
    log_file = project / ".claude" / "state" / "paperwork-edit-log.jsonl"
    assert not log_file.exists()


def test_no_inflight_log_silently_noops(tmp_path, monkeypatch, capsys):
    hook = _load_hook()
    project = tmp_path / "proj"
    project.mkdir()
    # No sessions/ at all.
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    envelope = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(project / "x.md")},
    }
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(envelope)))
    assert hook.main() == 0
    log_file = project / ".claude" / "state" / "paperwork-edit-log.jsonl"
    assert not log_file.exists()


def test_missing_started_at_silently_noops(tmp_path, monkeypatch):
    hook = _load_hook()
    project = tmp_path / "proj"
    project.mkdir()
    sessions = project / "sessions"
    sessions.mkdir()
    (sessions / "x.md").write_text("---\ndate: 2026-05-13\nslug: x\n---\nbody\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    envelope = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(project / "x.md")},
    }
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(envelope)))
    assert hook.main() == 0
    log_file = project / ".claude" / "state" / "paperwork-edit-log.jsonl"
    assert not log_file.exists()


def test_malformed_envelope_exits_zero(tmp_path, monkeypatch, capsys):
    hook = _load_hook()
    project = _project_with_inflight_log(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("not-json"))
    assert hook.main() == 0  # never block


def test_ts_is_iso_with_offset(tmp_path, monkeypatch):
    """Substrate-wide invariant: ts comes from datetime.now() — ISO with tz offset."""
    import re
    hook = _load_hook()
    project = _project_with_inflight_log(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    envelope = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(project / "x.md")},
    }
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(envelope)))
    assert hook.main() == 0
    log_file = project / ".claude" / "state" / "paperwork-edit-log.jsonl"
    entry = json.loads(log_file.read_text().strip())
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$", entry["ts"])


def test_records_against_todays_log_not_a_newer_stale_open_log(tmp_path, monkeypatch):
    """When a stale never-closed log from another day has a NEWER mtime than
    today's in-flight log, the recorder must still key the edit to TODAY's session
    — matching the Stop hook (which passes today). Otherwise the two hooks resolve
    different logs and `must-be-modified-this-session` falsely fails."""
    import datetime as _dt
    import os

    hook = _load_hook()
    project = tmp_path / "proj"
    project.mkdir()
    sessions = project / "sessions"
    sessions.mkdir()
    today = _dt.date.today().isoformat()
    today_started = f"{today}T09:00:00+02:00"
    today_log = sessions / f"{today}-current.md"
    today_log.write_text(
        f"---\ndate: {today}\nstarted_at: {today_started}\nslug: current\n---\n\nbody\n"
    )
    stale = sessions / "2026-05-13-stale.md"
    stale.write_text(
        "---\ndate: 2026-05-13\nstarted_at: 2026-05-13T08:00:00+02:00\nslug: stale\n---\n\nbody\n"
    )
    # Make the stale log the most-recently-modified, defeating any mtime fallback.
    bump = today_log.stat().st_mtime + 100
    os.utime(stale, (bump, bump))

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    envelope = {"tool_name": "Edit", "tool_input": {"file_path": str(today_log)}}
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(envelope)))
    assert hook.main() == 0

    log_file = project / ".claude" / "state" / "paperwork-edit-log.jsonl"
    entry = json.loads(log_file.read_text().strip())
    assert entry["started_at"] == today_started  # today's session, not the newer stale one
    assert entry["path"] == f"sessions/{today}-current.md"
