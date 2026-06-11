"""Tests for masterbook/substrate/paperwork-enforcement/hooks/_paperwork_session_log.py."""
import sys
from pathlib import Path

import pytest

SUBSTRATE_HOOKS = (
    Path(__file__).resolve().parent.parent
    / "substrate"
    / "paperwork-enforcement"
    / "hooks"
)
if str(SUBSTRATE_HOOKS) not in sys.path:
    sys.path.insert(0, str(SUBSTRATE_HOOKS))

import _paperwork_session_log as sl  # noqa: E402


# ── frontmatter_region ────────────────────────────────────────────────────


def test_frontmatter_region_extracts_between_fences():
    text = "---\ndate: 2026-05-13\nslug: x\n---\n\n# Body\n"
    assert sl.frontmatter_region(text) == "date: 2026-05-13\nslug: x"


def test_frontmatter_region_returns_none_when_no_open_fence():
    assert sl.frontmatter_region("# Body only\n") is None


def test_frontmatter_region_returns_none_when_no_close_fence():
    assert sl.frontmatter_region("---\ndate: 2026-05-13\n") is None


# ── has_ended_at ──────────────────────────────────────────────────────────


def test_has_ended_at_true_when_present():
    text = "---\ndate: 2026-05-13\nended_at: 2026-05-13T13:00:00+02:00\n---\n\nBody.\n"
    assert sl.has_ended_at(text) is True


def test_has_ended_at_false_when_absent():
    text = "---\ndate: 2026-05-13\nstarted_at: 2026-05-13T08:00:00+02:00\n---\n\nBody.\n"
    assert sl.has_ended_at(text) is False


def test_has_ended_at_ignores_match_outside_frontmatter():
    text = "---\ndate: 2026-05-13\n---\n\nended_at: this is body\n"
    assert sl.has_ended_at(text) is False


# ── parse_started_at_and_slug ─────────────────────────────────────────────


def test_parse_started_at_and_slug_happy_path():
    text = (
        "---\n"
        "date: 2026-05-13\n"
        "started_at: 2026-05-13T08:00:00+02:00\n"
        "slug: wave-3-spec\n"
        "---\n\nBody.\n"
    )
    assert sl.parse_started_at_and_slug(text) == (
        "2026-05-13T08:00:00+02:00",
        "wave-3-spec",
    )


def test_parse_started_at_and_slug_missing_started_at():
    text = "---\ndate: 2026-05-13\nslug: x\n---\n\nBody.\n"
    assert sl.parse_started_at_and_slug(text) == (None, "x")


def test_parse_started_at_and_slug_missing_slug():
    text = "---\ndate: 2026-05-13\nstarted_at: 2026-05-13T08:00:00+02:00\n---\n\n"
    assert sl.parse_started_at_and_slug(text) == ("2026-05-13T08:00:00+02:00", None)


def test_parse_started_at_and_slug_no_frontmatter():
    assert sl.parse_started_at_and_slug("body only\n") == (None, None)


def test_parse_started_at_and_slug_strips_quotes():
    """Tolerates quoted YAML scalars."""
    text = (
        "---\n"
        'started_at: "2026-05-13T08:00:00+02:00"\n'
        "slug: 'wave-3'\n"
        "---\n"
    )
    assert sl.parse_started_at_and_slug(text) == (
        "2026-05-13T08:00:00+02:00",
        "wave-3",
    )


# ── find_in_flight_log ────────────────────────────────────────────────────


def test_find_in_flight_log_picks_most_recent_without_ended_at(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()

    old = sessions / "2026-05-12-old.md"
    old.write_text("---\ndate: 2026-05-12\nended_at: 2026-05-12T17:00:00+02:00\n---\nbody\n")

    inflight = sessions / "2026-05-13-current.md"
    inflight.write_text("---\ndate: 2026-05-13\nstarted_at: 2026-05-13T08:00:00+02:00\nslug: current\n---\nbody\n")

    result = sl.find_in_flight_log(sessions)
    assert result == inflight


def test_find_in_flight_log_returns_none_when_dir_missing(tmp_path):
    assert sl.find_in_flight_log(tmp_path / "nope") is None


def test_find_in_flight_log_returns_none_when_no_candidates(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    closed = sessions / "2026-05-12-closed.md"
    closed.write_text("---\nended_at: 2026-05-12T17:00:00+02:00\n---\n")
    assert sl.find_in_flight_log(sessions) is None


def test_find_in_flight_log_skips_files_without_frontmatter(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    bad = sessions / "no-frontmatter.md"
    bad.write_text("Just a body, no frontmatter.\n")
    assert sl.find_in_flight_log(sessions) is None


def test_find_in_flight_prefers_pointer(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    # Two today-dated open logs land in the SAME tier (today_open); mtime would pick
    # the stale one. Only the pointer can override to the real current session.
    stale = sessions / "2026-06-03-stale.md"
    stale.write_text("---\ndate: 2026-06-03\nstarted_at: 2026-06-03T07:00:00+02:00\nslug: stale\nstatus: in_progress\n---\n\nx\n")
    cur = sessions / "2026-06-03-cur.md"
    cur.write_text("---\ndate: 2026-06-03\nstarted_at: 2026-06-03T08:00:00+02:00\nslug: cur\nstatus: in_progress\n---\n\nx\n")
    import os, datetime as dt
    now = dt.datetime.now().timestamp()
    os.utime(cur, (now - 5000, now - 5000))   # cur is OLDER by mtime
    os.utime(stale, (now, now))                # stale is NEWER by mtime → wins the tier without pointer
    ptr = tmp_path / ".claude" / "state" / "session-manifest" / "in-flight.json"
    ptr.parent.mkdir(parents=True)
    ptr.write_text('{"log": "sessions/2026-06-03-cur.md", "slug": "cur", "started_at": "2026-06-03T08:00:00+02:00"}')
    result = sl.find_in_flight_log(sessions, today="2026-06-03")
    assert result is not None and result.name == "2026-06-03-cur.md"


def test_find_in_flight_falls_back_without_pointer(tmp_path):
    # No pointer file → unchanged tiered behavior (today's open log wins).
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    cur = sessions / "2026-06-03-cur.md"
    cur.write_text("---\ndate: 2026-06-03\nstarted_at: 2026-06-03T08:00:00+02:00\nslug: cur\nstatus: in_progress\n---\n\nx\n")
    result = sl.find_in_flight_log(sessions, today="2026-06-03")
    assert result is not None and result.name == "2026-06-03-cur.md"
