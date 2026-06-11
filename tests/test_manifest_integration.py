# masterbook/tests/test_manifest_integration.py
import importlib.util
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "substrate" / "session-manifest" / "hooks"
TIMING = Path(__file__).resolve().parent.parent / "substrate" / "session-paperwork" / "hooks" / "session_stop_log_timing.py"


def _load(path, name):
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_lifecycle_begin_stop_debrief(tmp_path, monkeypatch):
    manifest = _load(HOOKS / "manifest_stop_update.py", "manifest_stop_update")
    timing = _load(TIMING, "session_stop_log_timing")
    proj = tmp_path / "proj"
    sessions = proj / "sessions"
    sessions.mkdir(parents=True)
    log = sessions / "2026-06-03-work.md"
    # /begin-session created this (status in_progress, accurate started_at)
    log.write_text("---\ndate: 2026-06-03\nstarted_at: 2026-06-03T08:00:00+02:00\nslug: work\nstatus: in_progress\nfollowups: []\n---\n\n# focus\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(proj))

    # Turn 1 Stop: manifest stamps session_no + pointer + index; timing skips ended_at (not done).
    manifest.main()
    timing.main()
    t1 = log.read_text()
    assert "session_no: 1" in t1
    assert "ended_at: " not in t1
    ptr = proj / ".claude" / "state" / "session-manifest" / "in-flight.json"
    assert ptr.is_file()

    # /debrief sets status done; next Stop: timing stamps ended_at, manifest clears pointer.
    log.write_text(t1.replace("status: in_progress", "status: done"))
    timing.main()
    manifest.main()
    t2 = log.read_text()
    assert "ended_at: " in t2
    assert not ptr.exists()
