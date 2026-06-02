"""Tests for stop_session_log.py — runs the hook via subprocess against a fixture project."""
import datetime as dt
import json
import os
import subprocess
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "stop_session_log.py"


def _run(payload: dict, project_root: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PROJECT_ROOT"] = str(project_root)
    return subprocess.run(
        ["/usr/bin/env", "python3", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


def test_no_changes_today_passes(tmp_path):
    f = tmp_path / "old.txt"
    f.write_text("x")
    yesterday = dt.datetime.now().timestamp() - 86400 * 2
    os.utime(f, (yesterday, yesterday))
    r = _run({"stop_hook_active": False}, tmp_path)
    assert r.returncode == 0


def test_changes_but_log_exists(tmp_path):
    today_iso = dt.date.today().isoformat()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / f"{today_iso}-test.md").write_text("log")
    f = tmp_path / "modified.txt"
    f.write_text("x")
    r = _run({"stop_hook_active": False}, tmp_path)
    assert r.returncode == 0


def test_changes_no_log_blocks(tmp_path):
    f = tmp_path / "modified.txt"
    f.write_text("x")
    r = _run({"stop_hook_active": False}, tmp_path)
    out = json.loads(r.stdout)
    assert out["decision"] == "block"
    assert "session log" in out["reason"].lower()


def test_recursion_guard(tmp_path):
    f = tmp_path / "modified.txt"
    f.write_text("x")
    r = _run({"stop_hook_active": True}, tmp_path)
    assert r.returncode == 0
    assert r.stdout.strip() == ""
