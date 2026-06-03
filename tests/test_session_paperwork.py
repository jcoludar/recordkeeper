"""Tests for masterbook/substrate/session-paperwork/hooks/session_stop_log_timing.py."""
import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).resolve().parent.parent
    / "substrate"
    / "session-paperwork"
    / "hooks"
    / "session_stop_log_timing.py"
)


def _load_hook():
    """Import the hook module by path (it's not on sys.path)."""
    spec = importlib.util.spec_from_file_location("session_stop_log_timing", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["session_stop_log_timing"] = module
    spec.loader.exec_module(module)
    return module


# ── _frontmatter_region ───────────────────────────────────────────────────


def test_frontmatter_region_extracts_between_fences():
    hook = _load_hook()
    text = "---\ndate: 2026-05-12\nslug: x\n---\n\n# Body\n"
    assert hook._frontmatter_region(text) == "date: 2026-05-12\nslug: x"


def test_frontmatter_region_returns_none_when_no_open_fence():
    hook = _load_hook()
    assert hook._frontmatter_region("# Body only\n") is None


def test_frontmatter_region_returns_none_when_no_close_fence():
    hook = _load_hook()
    text = "---\ndate: 2026-05-12\nno closing fence ever\n"
    assert hook._frontmatter_region(text) is None


# ── _has_ended_at ─────────────────────────────────────────────────────────


def test_has_ended_at_true_when_present():
    hook = _load_hook()
    text = (
        "---\n"
        "date: 2026-05-12\n"
        "ended_at: 2026-05-12T13:00:00+02:00\n"
        "---\n\nBody.\n"
    )
    assert hook._has_ended_at(text) is True


def test_has_ended_at_false_when_absent():
    hook = _load_hook()
    text = "---\ndate: 2026-05-12\nstarted_at: 2026-05-12T08:00:00+02:00\n---\n\nBody.\n"
    assert hook._has_ended_at(text) is False


def test_has_ended_at_false_when_no_frontmatter():
    hook = _load_hook()
    assert hook._has_ended_at("just a body\n") is False


def test_has_ended_at_ignores_match_outside_frontmatter():
    """A literal `ended_at:` in the body must not register."""
    hook = _load_hook()
    text = (
        "---\ndate: 2026-05-12\n---\n\n"
        "ended_at: this is in the body, not the frontmatter\n"
    )
    assert hook._has_ended_at(text) is False


# ── insert_ended_at ───────────────────────────────────────────────────────


def test_insert_ended_at_places_before_closing_fence():
    hook = _load_hook()
    text = (
        "---\n"
        "date: 2026-05-12\n"
        "slug: foo\n"
        "---\n\n# Body\n"
    )
    out = hook.insert_ended_at(text, "2026-05-12T13:15:00+02:00")
    assert out == (
        "---\n"
        "date: 2026-05-12\n"
        "slug: foo\n"
        "ended_at: 2026-05-12T13:15:00+02:00\n"
        "---\n\n# Body\n"
    )


def test_insert_ended_at_preserves_body_bytes_exactly():
    """Body content (with trailing whitespace, blank lines, etc.) must be untouched."""
    hook = _load_hook()
    text = "---\ndate: 2026-05-12\n---\n\n# Body with  trailing  spaces  \n\n\nend.\n"
    out = hook.insert_ended_at(text, "2026-05-12T13:15:00+02:00")
    # Body region (everything after the closing fence) is byte-identical.
    body_in = text[text.find("\n---\n") + 5:]
    body_out = out[out.find("\n---\n") + 5:]
    assert body_in == body_out


def test_insert_ended_at_raises_on_no_closing_fence():
    hook = _load_hook()
    with pytest.raises(ValueError, match="closing"):
        hook.insert_ended_at("---\nincomplete frontmatter\n", "2026-05-12T13:15:00+02:00")


# ── now_iso ───────────────────────────────────────────────────────────────


def test_now_iso_returns_iso8601_with_timezone():
    hook = _load_hook()
    s = hook.now_iso()
    # Parses back to a datetime via fromisoformat
    parsed = dt.datetime.fromisoformat(s)
    # Has a tzinfo (not naive)
    assert parsed.tzinfo is not None
    # Matches the second-precision shape (no microseconds)
    assert "." not in s


# ── find_in_flight_log ────────────────────────────────────────────────────


def _write_log(path: Path, *, ended: bool, mtime_offset: int = 0) -> None:
    """Helper: write a session log with or without ended_at:, set mtime."""
    parts = ["---", "date: 2026-05-12", f"slug: {path.stem}"]
    if ended:
        parts.append("ended_at: 2026-05-11T20:00:00+02:00")
    parts.append("status: done")
    parts.append("---")
    parts.append("")
    parts.append("# Body")
    path.write_text("\n".join(parts) + "\n")
    import os
    now = dt.datetime.now().timestamp()
    os.utime(path, (now + mtime_offset, now + mtime_offset))


def test_find_in_flight_log_returns_none_when_dir_missing(tmp_path):
    hook = _load_hook()
    assert hook.find_in_flight_log(tmp_path / "nonexistent") is None


def test_find_in_flight_log_returns_none_when_all_closed(tmp_path):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _write_log(sessions / "a.md", ended=True)
    _write_log(sessions / "b.md", ended=True)
    assert hook.find_in_flight_log(sessions) is None


def test_find_in_flight_log_picks_in_flight(tmp_path):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _write_log(sessions / "closed.md", ended=True)
    _write_log(sessions / "open.md", ended=False)
    result = hook.find_in_flight_log(sessions)
    assert result is not None
    assert result.name == "open.md"


def test_find_in_flight_log_picks_most_recent_when_multiple(tmp_path):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _write_log(sessions / "older.md", ended=False, mtime_offset=-1000)
    _write_log(sessions / "newer.md", ended=False, mtime_offset=0)
    result = hook.find_in_flight_log(sessions)
    assert result is not None
    assert result.name == "newer.md"


def test_find_in_flight_log_skips_files_without_frontmatter(tmp_path):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "no_fm.md").write_text("# Just a body, no frontmatter at all.\n")
    _write_log(sessions / "open.md", ended=False)
    result = hook.find_in_flight_log(sessions)
    assert result is not None
    assert result.name == "open.md"


# ── clamp_ended_at (end >= start) ─────────────────────────────────────────


def test_clamp_ended_at_clamps_up_when_end_before_start():
    """A session cannot end before it began; clock skew that yields an earlier
    end-time is clamped up to started_at."""
    hook = _load_hook()
    started = "2026-05-12T10:00:00+02:00"
    earlier = "2026-05-12T09:00:00+02:00"
    assert hook.clamp_ended_at(earlier, started) == started


def test_clamp_ended_at_keeps_later_end():
    hook = _load_hook()
    started = "2026-05-12T10:00:00+02:00"
    later = "2026-05-12T11:30:00+02:00"
    assert hook.clamp_ended_at(later, started) == later


def test_clamp_ended_at_passthrough_on_unparseable_or_missing_started():
    hook = _load_hook()
    ended = "2026-05-12T11:30:00+02:00"
    assert hook.clamp_ended_at(ended, "not-a-timestamp") == ended
    assert hook.clamp_ended_at(ended, None) == ended


# ── main() integration ────────────────────────────────────────────────────


def test_main_writes_ended_at_on_in_flight(tmp_path, monkeypatch, capsys):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-05-12-foo.md"
    log.write_text(
        "---\n"
        "date: 2026-05-12\n"
        "started_at: 2026-05-12T08:00:00+02:00\n"
        "slug: foo\n"
        "status: in_progress\n"
        "---\n\n"
        "# Body\n"
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    rc = hook.main()
    assert rc == 0
    text = log.read_text()
    assert "ended_at: " in text
    # ended_at line appears INSIDE the frontmatter region.
    fm = hook._frontmatter_region(text)
    assert fm is not None
    assert "ended_at:" in fm


def test_main_idempotent(tmp_path, monkeypatch):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-05-12-foo.md"
    log.write_text(
        "---\n"
        "date: 2026-05-12\n"
        "started_at: 2026-05-12T08:00:00+02:00\n"
        "slug: foo\n"
        "---\n\n"
        "# Body\n"
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    hook.main()
    first = log.read_text()
    hook.main()
    second = log.read_text()
    assert first == second  # second run is a no-op


def test_main_no_sessions_dir(tmp_path, monkeypatch, capsys):
    hook = _load_hook()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    rc = hook.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "no sessions/ dir" in captured.err


def test_main_no_in_flight_log(tmp_path, monkeypatch, capsys):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "closed.md").write_text(
        "---\n"
        "date: 2026-05-12\n"
        "started_at: 2026-05-12T08:00:00+02:00\n"
        "ended_at: 2026-05-12T13:00:00+02:00\n"
        "---\n\nBody.\n"
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    rc = hook.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "no in-flight" in captured.err


def test_main_clamps_ended_at_to_started_when_clock_skewed(tmp_path, monkeypatch):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    started = "2026-05-12T10:00:00+02:00"
    log = sessions / "2026-05-12-foo.md"
    log.write_text(
        f"---\ndate: 2026-05-12\nstarted_at: {started}\nslug: foo\n---\n\n# Body\n"
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    # now() reports a time *before* the session started (clock skew).
    monkeypatch.setattr(hook, "now_iso", lambda: "2026-05-12T09:00:00+02:00")
    rc = hook.main()
    assert rc == 0
    assert f"ended_at: {started}" in log.read_text()


def test_main_fails_open_on_internal_error(tmp_path, monkeypatch, capsys):
    """A non-blocking recorder must exit 0 even if its own code throws — never block
    the session because bookkeeping broke (tier-1/hook-resilience: recorders fail open)."""
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-05-12-foo.md"
    log.write_text(
        "---\ndate: 2026-05-12\nstarted_at: 2026-05-12T08:00:00+02:00\nslug: foo\n---\n\n# Body\n"
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    def boom(*a, **k):
        raise RuntimeError("disk gone")

    monkeypatch.setattr(hook, "insert_ended_at", boom)
    rc = hook.main()
    err = capsys.readouterr().err
    assert rc == 0
    assert "session_stop_log_timing" in err


def test_main_multiple_in_flight_picks_newest(tmp_path, monkeypatch):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    older = sessions / "older.md"
    newer = sessions / "newer.md"
    older.write_text(
        "---\ndate: 2026-05-12\nstarted_at: 2026-05-12T08:00:00+02:00\n---\n\nBody.\n"
    )
    newer.write_text(
        "---\ndate: 2026-05-12\nstarted_at: 2026-05-12T10:00:00+02:00\n---\n\nBody.\n"
    )
    import os
    now = dt.datetime.now().timestamp()
    os.utime(older, (now - 1000, now - 1000))
    os.utime(newer, (now, now))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    hook.main()
    assert "ended_at: " in newer.read_text()
    assert "ended_at: " not in older.read_text()
