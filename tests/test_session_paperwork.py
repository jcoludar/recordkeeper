"""Tests for masterbook/substrate/session-paperwork/hooks/session_stop_log_timing.py."""
import datetime as dt
import importlib.util
import json
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
        "status: done\n"
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
        "status: done\n"
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
        f"---\ndate: 2026-05-12\nstarted_at: {started}\nslug: foo\nstatus: done\n---\n\n# Body\n"
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
        "---\ndate: 2026-05-12\nstarted_at: 2026-05-12T08:00:00+02:00\nslug: foo\nstatus: done\n---\n\n# Body\n"
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
        "---\ndate: 2026-05-12\nstarted_at: 2026-05-12T08:00:00+02:00\nstatus: done\n---\n\nBody.\n"
    )
    newer.write_text(
        "---\ndate: 2026-05-12\nstarted_at: 2026-05-12T10:00:00+02:00\nstatus: done\n---\n\nBody.\n"
    )
    import os
    now = dt.datetime.now().timestamp()
    os.utime(older, (now - 1000, now - 1000))
    os.utime(newer, (now, now))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    hook.main()
    assert "ended_at: " in newer.read_text()
    assert "ended_at: " not in older.read_text()


def test_find_in_flight_prefers_pointer(tmp_path, monkeypatch):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    # An OLDER stale open log with NEWER mtime would normally win the mtime race.
    stale = sessions / "2026-05-01-stale.md"
    stale.write_text("---\ndate: 2026-05-01\nstarted_at: 2026-05-01T08:00:00+02:00\nslug: stale\nstatus: in_progress\n---\n\nbody\n")
    current = sessions / "2026-06-03-cur.md"
    current.write_text("---\ndate: 2026-06-03\nstarted_at: 2026-06-03T08:00:00+02:00\nslug: cur\nstatus: in_progress\n---\n\nbody\n")
    import os, datetime as dt
    now = dt.datetime.now().timestamp()
    os.utime(current, (now - 5000, now - 5000))   # current is OLDER by mtime
    os.utime(stale, (now, now))                    # stale is NEWER by mtime
    # Pointer names the current log.
    ptr = tmp_path / ".claude" / "state" / "session-manifest" / "in-flight.json"
    ptr.parent.mkdir(parents=True)
    ptr.write_text('{"log": "sessions/2026-06-03-cur.md", "slug": "cur", "started_at": "2026-06-03T08:00:00+02:00"}')
    result = hook.find_in_flight_log(sessions)
    assert result is not None and result.name == "2026-06-03-cur.md"


def test_find_in_flight_falls_back_without_pointer(tmp_path):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "open.md").write_text("---\ndate: 2026-06-03\nstarted_at: 2026-06-03T08:00:00+02:00\nslug: open\n---\n\nbody\n")
    # No pointer file → unchanged mtime behavior.
    assert hook.find_in_flight_log(sessions).name == "open.md"


def test_main_skips_ended_at_when_not_done(tmp_path, monkeypatch):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-06-03-p.md"
    log.write_text("---\ndate: 2026-06-03\nstarted_at: 2026-06-03T08:00:00+02:00\nslug: p\nstatus: paused\n---\n\nbody\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert hook.main() == 0
    assert "ended_at: " not in log.read_text()  # paused → no premature stamp


def test_main_stamps_ended_at_when_done(tmp_path, monkeypatch):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-06-03-d.md"
    log.write_text("---\ndate: 2026-06-03\nstarted_at: 2026-06-03T08:00:00+02:00\nslug: d\nstatus: done\n---\n\nbody\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert hook.main() == 0
    assert "ended_at: " in log.read_text()


# ── a STALE ended_at must be correctable ──────────────────────────────────
#
# The hook only ever considered logs where `_has_ended_at()` was false (`:116`,
# `:142`), so a session that debriefed (status -> done, stamp written) and then
# kept working carried a PERMANENTLY wrong end time. The substrate whose stated
# purpose is curing end-time drift reintroduced it, silently, and it ships.
#
# The rule the fix encodes: **only a RECORD may correct a stamp.** The session
# manifest's in-flight pointer and the paperwork edit log are records of which
# log belongs to THIS session; newest-mtime is a guess, and a guess must never
# overwrite a value already committed to a file.


def _write_edit_log(project_dir: Path, entries: list[dict]) -> None:
    """Write the paperwork-enforcement PostToolUse record for a project."""
    state = project_dir / ".claude" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "paperwork-edit-log.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in entries)
    )


STALE_LOG = (
    "---\n"
    "date: 2026-08-20\n"
    "started_at: 2026-08-20T13:10:00+02:00\n"
    "ended_at: 2026-08-20T15:44:00+02:00\n"
    "slug: kept-working\n"
    "status: done\n"
    "---\n"
    "\n"
    "# Body\n"
)


# ── _ended_at_value ───────────────────────────────────────────────────────


def test_ended_at_value_returns_the_stamp():
    hook = _load_hook()
    assert hook._ended_at_value(STALE_LOG) == "2026-08-20T15:44:00+02:00"


def test_ended_at_value_none_when_absent():
    hook = _load_hook()
    assert hook._ended_at_value("---\nslug: x\nstatus: done\n---\n\nbody\n") is None


def test_ended_at_value_ignores_matches_in_the_body():
    hook = _load_hook()
    text = "---\nslug: x\nstatus: done\n---\n\nended_at: 2026-01-01T00:00:00+02:00\n"
    assert hook._ended_at_value(text) is None


def test_ended_at_value_strips_yaml_quotes():
    hook = _load_hook()
    text = "---\nended_at: '2026-08-20T15:44:00+02:00'\nstatus: done\n---\n\nbody\n"
    assert hook._ended_at_value(text) == "2026-08-20T15:44:00+02:00"


# ── replace_ended_at ──────────────────────────────────────────────────────


def test_replace_ended_at_swaps_the_value_in_place():
    hook = _load_hook()
    out = hook.replace_ended_at(STALE_LOG, "2026-08-20T17:02:11+02:00")
    assert "ended_at: 2026-08-20T17:02:11+02:00" in out
    assert "15:44" not in out
    assert out.count("ended_at:") == 1  # never a second key
    assert out.splitlines()[3].startswith("ended_at:")  # same line position
    assert out.endswith("---\n\n# Body\n")  # body untouched


def test_replace_ended_at_raises_when_no_stamp_present():
    hook = _load_hook()
    with pytest.raises(ValueError):
        hook.replace_ended_at("---\nslug: x\nstatus: done\n---\n\nbody\n", "2026-08-20T17:00:00+02:00")


def test_replace_ended_at_refuses_a_body_only_stamp():
    """No stamp in the frontmatter is a REFUSAL, not licence to edit the body.

    (A mutation campaign found this: dropping the head/tail split left the
    function rewriting the first `ended_at:` line anywhere in the document, and
    every other test still passed because in the normal case that line is the
    frontmatter one.)
    """
    hook = _load_hook()
    text = "---\nslug: x\nstatus: done\n---\n\nended_at: 2026-01-01T00:00:00+02:00\n"
    with pytest.raises(ValueError):
        hook.replace_ended_at(text, "2026-08-20T17:02:11+02:00")


def test_replace_ended_at_never_touches_the_body():
    hook = _load_hook()
    text = (
        "---\nended_at: 2026-08-20T15:44:00+02:00\nstatus: done\n---\n\n"
        "The log quotes its own frontmatter: ended_at: 2026-08-20T15:44:00+02:00\n"
    )
    out = hook.replace_ended_at(text, "2026-08-20T17:02:11+02:00")
    assert out.split("\n---\n", 1)[1] == text.split("\n---\n", 1)[1]


# ── _edit_log_session ─────────────────────────────────────────────────────


def test_edit_log_session_returns_the_last_session_and_its_newest_edit(tmp_path):
    hook = _load_hook()
    _write_edit_log(tmp_path, [
        {"started_at": "A", "ts": "2026-08-20T09:00:00+02:00"},
        {"started_at": "B", "ts": "2026-08-20T15:40:00+02:00"},
        {"started_at": "B", "ts": "2026-08-20T17:00:00+02:00"},
    ])
    assert hook._edit_log_session(tmp_path) == ("B", "2026-08-20T17:00:00+02:00")


def test_edit_log_session_does_not_read_another_sessions_timestamp(tmp_path):
    """A later ts belonging to a DIFFERENT session must not be read as this one's."""
    hook = _load_hook()
    _write_edit_log(tmp_path, [
        {"started_at": "B", "ts": "2026-08-20T17:00:00+02:00"},
        {"started_at": "A", "ts": "2026-08-20T23:00:00+02:00"},
        {"started_at": "B", "ts": "2026-08-20T16:00:00+02:00"},
    ])
    assert hook._edit_log_session(tmp_path) == ("B", "2026-08-20T17:00:00+02:00")


def test_edit_log_session_none_when_file_missing(tmp_path):
    hook = _load_hook()
    assert hook._edit_log_session(tmp_path) is None


def test_edit_log_session_skips_unparseable_lines(tmp_path):
    hook = _load_hook()
    state = tmp_path / ".claude" / "state"
    state.mkdir(parents=True)
    (state / "paperwork-edit-log.jsonl").write_text(
        '{"started_at": "B", "ts": "2026-08-20T17:00:00+02:00"}\n'
        "not json at all\n"
        "\n"
        "[1, 2, 3]\n"
    )
    assert hook._edit_log_session(tmp_path) == ("B", "2026-08-20T17:00:00+02:00")


def test_edit_log_session_none_when_entries_lack_the_keys(tmp_path):
    hook = _load_hook()
    _write_edit_log(tmp_path, [{"tool": "Edit", "path": "x"}])
    assert hook._edit_log_session(tmp_path) is None


# ── select_log: which tier of evidence named this log ─────────────────────


def test_select_log_by_edit_log_returns_a_STAMPED_log(tmp_path):
    """The record tier is the only one allowed to hand back a closed log."""
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-08-20-kept-working.md"
    log.write_text(STALE_LOG)
    _write_edit_log(tmp_path, [
        {"started_at": "2026-08-20T13:10:00+02:00", "ts": "2026-08-20T17:00:00+02:00"},
    ])
    assert hook.select_log(sessions) == (log, "edit-log")


def test_select_log_matches_a_quoted_started_at(tmp_path):
    """The edit log stores a quote-stripped value; the log may carry quotes."""
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-08-20-q.md"
    log.write_text(STALE_LOG.replace(
        "started_at: 2026-08-20T13:10:00+02:00",
        "started_at: '2026-08-20T13:10:00+02:00'",
    ))
    _write_edit_log(tmp_path, [
        {"started_at": "2026-08-20T13:10:00+02:00", "ts": "2026-08-20T17:00:00+02:00"},
    ])
    assert hook.select_log(sessions) == (log, "edit-log")


def test_select_log_refuses_an_ambiguous_record_match(tmp_path):
    """Two logs, one started_at: no log is named while a candidate goes unread."""
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "2026-08-20-a.md").write_text(STALE_LOG)
    (sessions / "2026-08-20-b.md").write_text(STALE_LOG)
    _write_edit_log(tmp_path, [
        {"started_at": "2026-08-20T13:10:00+02:00", "ts": "2026-08-20T17:00:00+02:00"},
    ])
    path, how = hook.select_log(sessions)
    assert how != "edit-log"
    assert path is None  # both are closed, so the mtime tier has no candidate


def test_select_log_falls_back_to_mtime_without_a_record(tmp_path):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-08-20-open.md"
    log.write_text("---\ndate: 2026-08-20\nstarted_at: 2026-08-20T13:10:00+02:00\nslug: open\n---\n\nbody\n")
    assert hook.select_log(sessions) == (log, "mtime")


def test_select_log_mtime_tier_never_returns_a_closed_log(tmp_path):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "2026-08-20-closed.md").write_text(STALE_LOG)
    assert hook.select_log(sessions) == (None, "")


def test_select_log_prefers_the_pointer_over_the_edit_log(tmp_path):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    pointed = sessions / "2026-08-20-pointed.md"
    pointed.write_text(STALE_LOG)
    other = sessions / "2026-08-20-other.md"
    other.write_text(STALE_LOG.replace("13:10:00", "13:11:00"))
    state = tmp_path / ".claude" / "state" / "session-manifest"
    state.mkdir(parents=True)
    (state / "in-flight.json").write_text(json.dumps({"log": "sessions/2026-08-20-pointed.md"}))
    _write_edit_log(tmp_path, [
        {"started_at": "2026-08-20T13:11:00+02:00", "ts": "2026-08-20T17:00:00+02:00"},
    ])
    assert hook.select_log(sessions) == (pointed, "pointer")


def test_pointer_tier_returns_a_stamped_log(tmp_path):
    """The pointer names THIS session's log; a stamp on it is exactly what we fix."""
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-08-20-kept-working.md"
    log.write_text(STALE_LOG)
    state = tmp_path / ".claude" / "state" / "session-manifest"
    state.mkdir(parents=True)
    (state / "in-flight.json").write_text(json.dumps({"log": "sessions/2026-08-20-kept-working.md"}))
    assert hook.select_log(sessions) == (log, "pointer")


# ── main(): the correction, and its refusals ──────────────────────────────


def test_main_restamps_a_stale_ended_at(tmp_path, monkeypatch, capsys):
    """The headline case: debriefed 15:44, kept working to 17:00 → corrected."""
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-08-20-kept-working.md"
    log.write_text(STALE_LOG)
    _write_edit_log(tmp_path, [
        {"started_at": "2026-08-20T13:10:00+02:00", "ts": "2026-08-20T17:00:00+02:00"},
    ])
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert hook.main() == 0
    text = log.read_text()
    assert "2026-08-20T15:44:00+02:00" not in text  # the stale value is GONE
    assert text.count("ended_at:") == 1
    fresh = hook._ended_at_value(text)
    assert dt.datetime.fromisoformat(fresh) > dt.datetime.fromisoformat("2026-08-20T15:44:00+02:00")
    assert "re-stamped" in capsys.readouterr().err


def test_main_does_not_restamp_when_the_last_edit_predates_the_stamp(tmp_path, monkeypatch):
    """/debrief edits at 15:43, Stop stamps 15:44 — a further Stop changes nothing."""
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-08-20-kept-working.md"
    log.write_text(STALE_LOG)
    _write_edit_log(tmp_path, [
        {"started_at": "2026-08-20T13:10:00+02:00", "ts": "2026-08-20T15:43:00+02:00"},
    ])
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert hook.main() == 0
    assert log.read_text() == STALE_LOG  # byte-for-byte


def test_main_restamp_is_idempotent(tmp_path, monkeypatch):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-08-20-kept-working.md"
    log.write_text(STALE_LOG)
    _write_edit_log(tmp_path, [
        {"started_at": "2026-08-20T13:10:00+02:00", "ts": "2026-08-20T17:00:00+02:00"},
    ])
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    hook.main()
    first = log.read_text()
    hook.main()
    assert log.read_text() == first  # the edit log did not move; neither does the stamp


def test_main_leaves_a_closed_log_alone_when_only_mtime_is_available(tmp_path, monkeypatch, capsys):
    """mtime is a guess, and a guess must not overwrite a committed value.

    Newest-mtime selection handing back the wrong file has been measured six
    independent times; a `git checkout`, or a file-sync client re-materialising
    a folder, reorders every mtime without any session having run.
    """
    import os
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-08-20-closed.md"
    log.write_text(STALE_LOG)
    future = dt.datetime.now().timestamp() + 10_000
    os.utime(log, (future, future))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert hook.main() == 0
    assert log.read_text() == STALE_LOG  # untouched
    assert "cannot correct" in capsys.readouterr().err  # refuse AND warn


def test_main_stale_advisory_does_not_fire_on_a_freshly_stamped_log(tmp_path, monkeypatch, capsys):
    """A warning that fires on every ordinary Stop is one you learn to ignore."""
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-08-20-d.md"
    log.write_text("---\ndate: 2026-08-20\nstarted_at: 2026-08-20T13:10:00+02:00\nslug: d\nstatus: done\n---\n\nbody\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    hook.main()  # stamps, and the write sets mtime a hair later than the stamp
    capsys.readouterr()
    assert hook.main() == 0  # second Stop, no work in between
    assert "cannot correct" not in capsys.readouterr().err


def test_is_after_answers_false_when_it_cannot_prove_anything():
    """A recorder that cannot PROVE a stamp is stale must not overwrite it."""
    hook = _load_hook()
    assert hook._is_after("2026-08-20T17:00:00+02:00", "2026-08-20T15:44:00+02:00") is True
    assert hook._is_after("2026-08-20T15:44:00+02:00", "2026-08-20T17:00:00+02:00") is False
    assert hook._is_after("2026-08-20T17:00:00+02:00", "2026-08-20T17:00:00+02:00") is False
    assert hook._is_after(None, "2026-08-20T15:44:00+02:00") is False
    assert hook._is_after("2026-08-20T17:00:00+02:00", None) is False
    assert hook._is_after("", "") is False
    assert hook._is_after("yesterday afternoon", "2026-08-20T15:44:00+02:00") is False


def test_main_refuses_to_correct_a_stamp_handed_to_it_by_the_mtime_tier(tmp_path, monkeypatch, capsys):
    """main()'s own refusal, exercised directly.

    `select_log` will not hand a stamped log to the mtime tier, so this branch
    is unreachable end-to-end — and a mutation campaign duly reported it as
    surviving. The rule ("a guess must never overwrite a committed value") is
    stated in two places and only one of them was live; the untested copy is
    the one that rots. So the tier is injected here rather than provoked.
    """
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-08-20-closed.md"
    log.write_text(STALE_LOG)
    monkeypatch.setattr(hook, "select_log", lambda _dir: (log, "mtime"))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert hook.main() == 0
    assert log.read_text() == STALE_LOG
    assert "mtime alone cannot correct a stamp" in capsys.readouterr().err


def test_main_restamped_value_is_clamped_to_started_at(tmp_path, monkeypatch):
    """A session cannot end before it began, on the correction path either."""
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    far_future = (dt.datetime.now().astimezone() + dt.timedelta(days=3650)).isoformat(timespec="seconds")
    log = sessions / "2026-08-20-skew.md"
    log.write_text(
        f"---\ndate: 2026-08-20\nstarted_at: {far_future}\n"
        "ended_at: 2026-08-20T15:44:00+02:00\nslug: skew\nstatus: done\n---\n\nbody\n"
    )
    _write_edit_log(tmp_path, [{"started_at": far_future, "ts": "2026-08-20T17:00:00+02:00"}])
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert hook.main() == 0
    assert hook._ended_at_value(log.read_text()) == far_future


def test_main_does_not_restamp_a_log_whose_status_is_not_done(tmp_path, monkeypatch, capsys):
    """A re-opened log is not a closed one; the existing not-done refusal holds."""
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-08-20-reopened.md"
    text = STALE_LOG.replace("status: done", "status: in_progress")
    log.write_text(text)
    _write_edit_log(tmp_path, [
        {"started_at": "2026-08-20T13:10:00+02:00", "ts": "2026-08-20T17:00:00+02:00"},
    ])
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert hook.main() == 0
    assert log.read_text() == text
    assert "not 'done'" in capsys.readouterr().err


def test_main_restamps_via_the_pointer_without_an_edit_log(tmp_path, monkeypatch):
    """No edit log: the pointer still names this session's log, and the Stop
    itself is the evidence that it is still running."""
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-08-20-kept-working.md"
    log.write_text(STALE_LOG)
    state = tmp_path / ".claude" / "state" / "session-manifest"
    state.mkdir(parents=True)
    (state / "in-flight.json").write_text(json.dumps({"log": "sessions/2026-08-20-kept-working.md"}))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert hook.main() == 0
    assert "2026-08-20T15:44:00+02:00" not in log.read_text()


def test_main_still_stamps_an_unstamped_log_found_by_the_record(tmp_path, monkeypatch):
    hook = _load_hook()
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    log = sessions / "2026-08-20-open.md"
    log.write_text("---\ndate: 2026-08-20\nstarted_at: 2026-08-20T13:10:00+02:00\nslug: open\nstatus: done\n---\n\nbody\n")
    _write_edit_log(tmp_path, [
        {"started_at": "2026-08-20T13:10:00+02:00", "ts": "2026-08-20T17:00:00+02:00"},
    ])
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert hook.main() == 0
    assert hook._ended_at_value(log.read_text()) is not None
