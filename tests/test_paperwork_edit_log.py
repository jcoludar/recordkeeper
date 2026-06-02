"""Tests for _paperwork_edit_log."""
import json
import sys
from pathlib import Path

SUBSTRATE_HOOKS = (
    Path(__file__).resolve().parent.parent
    / "substrate"
    / "paperwork-enforcement"
    / "hooks"
)
if str(SUBSTRATE_HOOKS) not in sys.path:
    sys.path.insert(0, str(SUBSTRATE_HOOKS))

import _paperwork_edit_log as el  # noqa: E402


# ── canonicalize_path ─────────────────────────────────────────────────────


def test_canonicalize_path_under_project_dir_becomes_relative(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    sub = project / "sub" / "file.md"
    sub.parent.mkdir(parents=True)
    sub.touch()
    assert el.canonicalize_path(str(sub), project_dir=project) == "sub/file.md"


def test_canonicalize_path_outside_project_dir_stays_absolute(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    other = tmp_path / "elsewhere" / "x.md"
    other.parent.mkdir(parents=True)
    other.touch()
    result = el.canonicalize_path(str(other), project_dir=project)
    assert result == str(other.resolve())


def test_canonicalize_path_handles_relative_input(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "a.md").touch()
    monkeypatch.chdir(project)
    assert el.canonicalize_path("a.md", project_dir=project) == "a.md"


# ── append_entry ──────────────────────────────────────────────────────────


def test_append_entry_creates_file_and_writes_jsonl(tmp_path):
    log = tmp_path / "edit-log.jsonl"
    el.append_entry(
        log,
        started_at="2026-05-13T08:00:00+02:00",
        tool="Edit",
        path="sessions/2026-05-13-x.md",
        ts="2026-05-13T08:23:00+02:00",
    )
    lines = log.read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry == {
        "started_at": "2026-05-13T08:00:00+02:00",
        "ts": "2026-05-13T08:23:00+02:00",
        "tool": "Edit",
        "path": "sessions/2026-05-13-x.md",
    }


def test_append_entry_appends_to_existing(tmp_path):
    log = tmp_path / "edit-log.jsonl"
    el.append_entry(log, started_at="A", tool="Edit", path="x", ts="t1")
    el.append_entry(log, started_at="A", tool="Write", path="y", ts="t2")
    assert len(log.read_text().splitlines()) == 2


def test_append_entry_creates_parent_dir_if_needed(tmp_path):
    log = tmp_path / "deep" / "nested" / "edit-log.jsonl"
    el.append_entry(log, started_at="A", tool="Edit", path="x", ts="t1")
    assert log.exists()


# ── read_entries ──────────────────────────────────────────────────────────


def test_read_entries_returns_empty_when_file_missing(tmp_path):
    assert el.read_entries(tmp_path / "missing.jsonl") == []


def test_read_entries_parses_all_valid_lines(tmp_path):
    log = tmp_path / "edit-log.jsonl"
    log.write_text(
        '{"started_at": "A", "ts": "t1", "tool": "Edit", "path": "x"}\n'
        '{"started_at": "B", "ts": "t2", "tool": "Write", "path": "y"}\n'
    )
    entries = el.read_entries(log)
    assert len(entries) == 2
    assert entries[0]["started_at"] == "A"
    assert entries[1]["path"] == "y"


def test_read_entries_skips_corrupted_lines(tmp_path):
    log = tmp_path / "edit-log.jsonl"
    log.write_text(
        '{"started_at": "A", "ts": "t1", "tool": "Edit", "path": "x"}\n'
        'not-valid-json\n'
        '{"started_at": "B", "ts": "t2", "tool": "Write", "path": "y"}\n'
    )
    entries = el.read_entries(log)
    assert len(entries) == 2


def test_read_entries_skips_empty_lines(tmp_path):
    log = tmp_path / "edit-log.jsonl"
    log.write_text(
        '{"started_at": "A", "ts": "t1", "tool": "Edit", "path": "x"}\n'
        '\n'
        '   \n'
        '{"started_at": "B", "ts": "t2", "tool": "Write", "path": "y"}\n'
    )
    assert len(el.read_entries(log)) == 2


# ── filter_for_session ────────────────────────────────────────────────────


def test_filter_for_session_returns_only_matching():
    entries = [
        {"started_at": "A", "ts": "t1", "tool": "Edit", "path": "x"},
        {"started_at": "B", "ts": "t2", "tool": "Edit", "path": "y"},
        {"started_at": "A", "ts": "t3", "tool": "Write", "path": "z"},
    ]
    result = el.filter_for_session(entries, started_at="A")
    assert len(result) == 2
    assert all(e["started_at"] == "A" for e in result)


def test_filter_for_session_empty_when_no_match():
    entries = [{"started_at": "B", "ts": "t1", "tool": "Edit", "path": "x"}]
    assert el.filter_for_session(entries, started_at="A") == []
