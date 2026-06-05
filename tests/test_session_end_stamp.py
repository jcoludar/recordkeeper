# tests/test_session_end_stamp.py
import importlib.util
import io
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "session_end_stamp", ROOT / "hooks" / "session_end_stamp.py"
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_insert_ended_at_before_closing_fence():
    text = "---\nslug: x\nstatus: done\n---\nbody\n"
    out = mod.insert_ended_at(text, "2026-06-05T17:00:00+02:00")
    assert "ended_at: 2026-06-05T17:00:00+02:00\n---" in out


def test_has_ended_at_true_and_false():
    assert mod.has_ended_at("---\nended_at: 2026-01-01T00:00:00+00:00\n---\n")
    assert not mod.has_ended_at("---\nslug: x\n---\n")


def test_clamp_never_before_started():
    started = "2026-06-05T17:00:00+02:00"
    earlier = "2026-06-05T16:00:00+02:00"
    assert mod.clamp_ended_at(earlier, started) == started


def test_find_in_flight_picks_most_recent_without_ended_at(tmp_path):
    sdir = tmp_path / "sessions"
    sdir.mkdir()
    old = sdir / "2026-06-01-a.md"
    old.write_text("---\nslug: a\nstatus: done\n---\n")
    new = sdir / "2026-06-02-b.md"
    new.write_text("---\nslug: b\nstatus: paused\n---\n")
    closed = sdir / "2026-06-03-c.md"
    closed.write_text("---\nslug: c\nended_at: 2026-06-03T00:00:00+00:00\n---\n")
    os.utime(old, (1, 1))
    os.utime(new, (2, 2))
    os.utime(closed, (3, 3))
    assert mod.find_in_flight_log(sdir) == new


def test_resolve_project_dir_from_stdin_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(tmp_path)})))
    assert mod.resolve_project_dir() == tmp_path


def test_main_stamps_regardless_of_status(tmp_path, monkeypatch):
    sdir = tmp_path / "sessions"
    sdir.mkdir()
    log = sdir / "2026-06-05-x.md"
    log.write_text(
        "---\nslug: x\nstarted_at: 2026-06-05T10:00:00+02:00\nstatus: paused\n---\nbody\n"
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert mod.main() == 0
    assert mod.has_ended_at(log.read_text())


def test_main_fails_open_with_no_sessions_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert mod.main() == 0


def test_main_stamps_frontmatter_only_log_without_trailing_newline(tmp_path, monkeypatch):
    sdir = tmp_path / "sessions"
    sdir.mkdir()
    log = sdir / "2026-06-05-y.md"
    # frontmatter-only, no body, NO trailing newline after the closing fence
    log.write_text(
        "---\nslug: y\nstarted_at: 2026-06-05T09:00:00+02:00\nstatus: in_progress\n---"
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert mod.main() == 0
    assert mod.has_ended_at(log.read_text())


def test_clamp_returns_ended_when_unparseable():
    assert mod.clamp_ended_at("not-a-date", "also-not-a-date") == "not-a-date"


def test_main_does_not_double_stamp_closed_log(tmp_path, monkeypatch):
    sdir = tmp_path / "sessions"
    sdir.mkdir()
    log = sdir / "2026-06-05-z.md"
    original = (
        "---\nslug: z\nstarted_at: 2026-06-05T08:00:00+02:00\n"
        "ended_at: 2026-06-05T12:00:00+02:00\nstatus: done\n---\nbody\n"
    )
    log.write_text(original)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert mod.main() == 0
    assert log.read_text() == original
