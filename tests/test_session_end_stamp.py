# tests/test_session_end_stamp.py
import importlib.util
import io
import json
import os
import time
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
    # frontmatter-only, no body, NO trailing newline after the closing fence.
    # ⚠ `status:` changed in_progress -> done when the in-progress gate landed. This test is
    # about the missing trailing NEWLINE and nothing else; leaving it `in_progress` would have
    # made it fail for a reason that has nothing to do with what it is named for.
    log.write_text("---\nslug: y\nstarted_at: 2026-06-05T09:00:00+02:00\nstatus: done\n---")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert mod.main() == 0
    assert mod.has_ended_at(log.read_text())


def test_clamp_returns_ended_when_unparseable():
    assert mod.clamp_ended_at("not-a-date", "also-not-a-date") == "not-a-date"


# ---------------------------------------------------------------------------
# Two gates the stamper never had. Both were found by a peer project running
# this hook and asking where a wrong timestamp came from.
#
# GATE 1 — an `in_progress` log has not been closed by its author, and stamping
# it asserts an end time for a session nobody has declared over. Measured: a log
# received `ended_at: 22:52:51` while `status:` still read `in_progress` and its
# session ran 13 more minutes.
#   ⚠ `done` AND `paused` both stay stampable. SessionEnd fires ONCE, at true
#   session end, so a paused session really did end and its end time is real.
#   This is deliberately NOT the substrate Stop hook's `status == "done"` rule:
#   Stop fires at every assistant stop, so it must be stricter. Copying that
#   gate here would refuse every paused session forever.
#
# GATE 2 — selection is newest-mtime, which cannot tell whose log it is. When a
# NEW session ends in a repo holding an OLDER unstamped log, the old log gets
# today's wall clock. Measured in a peer repo: a log whose session ran
# 05:12->05:44 was stamped `09:42:55` by a session that ended four hours later.
#   ⇒ A log this session closed was written seconds ago. One untouched for
#   hours belongs to somebody else. PREFER NO STAMP OVER A FABRICATED ONE: a
#   missing `ended_at` is honestly missing, while a fabricated one is
#   indistinguishable from a real measurement forever after.


def _payload_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))


def test_an_in_progress_log_is_NOT_stamped(tmp_path, monkeypatch):
    sdir = tmp_path / "sessions"
    sdir.mkdir()
    log = sdir / "2026-06-05-live.md"
    original = (
        "---\nslug: live\nstarted_at: 2026-06-05T10:00:00+02:00\nstatus: in_progress\n---\nbody\n"
    )
    log.write_text(original)
    _payload_env(monkeypatch, tmp_path)
    assert mod.main() == 0
    assert log.read_text() == original, "a live log must not be given an end time"


def test_a_paused_log_IS_still_stamped(tmp_path, monkeypatch):
    """⚠ THE PREMISE FOR THE TEST ABOVE, pinned beside it. If the gate ever widens to
    `status == "done"`, this fails loudly instead of the hook going quietly inert for
    every paused session."""
    sdir = tmp_path / "sessions"
    sdir.mkdir()
    log = sdir / "2026-06-05-paused.md"
    log.write_text(
        "---\nslug: paused\nstarted_at: 2026-06-05T10:00:00+02:00\nstatus: paused\n---\nbody\n"
    )
    _payload_env(monkeypatch, tmp_path)
    assert mod.main() == 0
    assert mod.has_ended_at(log.read_text())


def test_a_log_nobody_touched_this_session_is_NOT_stamped(tmp_path, monkeypatch):
    """The peer-repo case: a closed-but-unstamped log from hours ago."""
    sdir = tmp_path / "sessions"
    sdir.mkdir()
    log = sdir / "2026-06-05-stale.md"
    original = (
        "---\nslug: stale\nstarted_at: 2026-06-05T05:12:00+02:00\nstatus: done\n---\nbody\n"
    )
    log.write_text(original)
    old = time.time() - (4 * 3600)              # four hours untouched
    os.utime(log, (old, old))
    _payload_env(monkeypatch, tmp_path)
    assert mod.main() == 0
    assert log.read_text() == original, "a log from another session must not be stamped"


def test_a_log_written_moments_ago_IS_stamped(tmp_path, monkeypatch):
    """⚠ THE PREMISE FOR THE TEST ABOVE. Without this, the staleness gate could be
    implemented as `never stamp anything` and the suite would still be green — the
    absence-assertion trap."""
    sdir = tmp_path / "sessions"
    sdir.mkdir()
    log = sdir / "2026-06-05-fresh.md"
    log.write_text(
        "---\nslug: fresh\nstarted_at: 2026-06-05T10:00:00+02:00\nstatus: done\n---\nbody\n"
    )
    _payload_env(monkeypatch, tmp_path)
    assert mod.main() == 0
    assert mod.has_ended_at(log.read_text())


def test_a_missing_status_is_NOT_stamped(tmp_path, monkeypatch):
    """No `status:` at all means no author ever declared this session over."""
    sdir = tmp_path / "sessions"
    sdir.mkdir()
    log = sdir / "2026-06-05-nostatus.md"
    original = "---\nslug: nostatus\nstarted_at: 2026-06-05T10:00:00+02:00\n---\nbody\n"
    log.write_text(original)
    _payload_env(monkeypatch, tmp_path)
    assert mod.main() == 0
    assert log.read_text() == original


def test_a_log_whose_mtime_cannot_be_READ_is_refused(tmp_path):
    """🧨 ADDED BECAUSE A MUTANT SURVIVED. Flipping the `except OSError` arm from False to
    True left the whole suite green — the gate's failure path was unpinned.

    It is narrow (the file must vanish between selection and the gate) but it is not
    academic, and the direction is the whole doctrine: when the hook CANNOT TELL whether
    this session wrote the log, it must refuse. 'I could not check' is not 'it checked out'.
    """
    assert mod.was_touched_this_session(tmp_path / "does-not-exist.md") is False


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
