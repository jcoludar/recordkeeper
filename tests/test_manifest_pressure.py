"""Pressure test for the session-manifest pointer.

Seeds a project with SEVERAL stale never-closed logs whose mtimes are NEWER than the
real current session log, then shows:
  1. the bare most-recent-mtime heuristic selects the WRONG (stale) log — the documented
     fragility that motivated this substrate;
  2. once the in-flight pointer names the real log, selection is REPAIRED — both the
     session-paperwork timing hook's find_in_flight_log and the manifest hook's own
     _resolve_inflight pick the right log.

This is the parking-lot "subagent pressure test" captured as a deterministic regression.
"""
import datetime as dt
import importlib.util
import os
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "substrate" / "session-manifest" / "hooks"
TIMING = (
    Path(__file__).resolve().parent.parent
    / "substrate"
    / "session-paperwork"
    / "hooks"
    / "session_stop_log_timing.py"
)


def _load(path, name):
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_log(path, *, started_at, status="in_progress", ended=False):
    parts = ["---", "date: 2026-06-03", f"started_at: {started_at}", f"slug: {path.stem}", f"status: {status}"]
    if ended:
        parts.append("ended_at: 2026-06-03T09:00:00+02:00")
    parts += ["---", "", "# body"]
    path.write_text("\n".join(parts) + "\n")


def _seed_stale_field(sessions, *, n_stale=3):
    """Create n_stale never-closed logs with NEWER mtimes + one real current log with the
    OLDEST mtime. Returns the real current log path."""
    now = dt.datetime.now().timestamp()
    real = sessions / "2026-06-03-real-current.md"
    _write_log(real, started_at="2026-06-03T08:00:00+02:00")
    os.utime(real, (now - 10000, now - 10000))  # real is OLDEST by mtime
    for i in range(n_stale):
        stale = sessions / f"2026-06-03-stale-{i}.md"
        _write_log(stale, started_at=f"2026-06-03T1{i}:00:00+02:00")
        os.utime(stale, (now - 100 + i, now - 100 + i))  # all NEWER than real
    return real


def _write_pointer(root, sessions_relative_name):
    ptr = root / ".claude" / "state" / "session-manifest" / "in-flight.json"
    ptr.parent.mkdir(parents=True)
    ptr.write_text(
        '{"log": "sessions/' + sessions_relative_name + '", "slug": "real-current", '
        '"started_at": "2026-06-03T08:00:00+02:00"}'
    )
    return ptr


def test_bare_mtime_glob_picks_wrong_stale_log(tmp_path):
    """Documents the fragility: with NO pointer, the newest-mtime stale log wins."""
    timing = _load(TIMING, "session_stop_log_timing")
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    real = _seed_stale_field(sessions)
    picked = timing.find_in_flight_log(sessions)
    assert picked is not None
    assert picked.name != real.name  # the heuristic does NOT find the real log...
    assert picked.name.startswith("2026-06-03-stale-")  # ...it picks a stale one


def test_pointer_repairs_timing_selection(tmp_path):
    """The session-manifest pointer makes find_in_flight_log select the RIGHT log."""
    timing = _load(TIMING, "session_stop_log_timing")
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    real = _seed_stale_field(sessions)
    _write_pointer(tmp_path, real.name)
    assert timing.find_in_flight_log(sessions).name == real.name


def test_manifest_resolve_inflight_under_pressure(tmp_path):
    """The manifest hook's own _resolve_inflight follows mtime without a pointer, and
    the pointer under pressure."""
    manifest = _load(HOOKS / "manifest_stop_update.py", "manifest_stop_update")
    proj = tmp_path / "proj"
    sessions = proj / "sessions"
    sessions.mkdir(parents=True)
    real = _seed_stale_field(sessions)
    bare = manifest._resolve_inflight(sessions, proj)
    assert bare is not None and bare.name.startswith("2026-06-03-stale-")
    _write_pointer(proj, real.name)
    assert manifest._resolve_inflight(sessions, proj).name == real.name
