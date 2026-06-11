# masterbook/tests/test_manifest_stop_hook.py
import importlib.util
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "substrate" / "session-manifest" / "hooks"


def _load_hook():
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location("manifest_stop_update", HOOKS / "manifest_stop_update.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["manifest_stop_update"] = mod
    spec.loader.exec_module(mod)
    return mod


def _project(tmp_path):
    proj = tmp_path / "proj"
    (proj / "sessions").mkdir(parents=True)
    return proj


def _log(proj, name, **fm):
    lines = ["---"] + [f"{k}: {v}" for k, v in fm.items()] + ["---", "", "# body"]
    (proj / "sessions" / name).write_text("\n".join(lines) + "\n")


def test_stamps_session_no_and_writes_pointer(tmp_path, monkeypatch):
    hook = _load_hook()
    proj = _project(tmp_path)
    _log(proj, "2026-06-03-a.md", date="2026-06-03", slug="a", status="in_progress",
         started_at="2026-06-03T08:00:00+02:00")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(proj))
    assert hook.main() == 0
    log_text = (proj / "sessions" / "2026-06-03-a.md").read_text()
    assert "session_no: 1" in log_text
    import json
    ptr = json.loads((proj / ".claude" / "state" / "session-manifest" / "in-flight.json").read_text())
    assert ptr["log"] == "sessions/2026-06-03-a.md"
    assert (proj / "sessions" / "INDEX.md").is_file()


def test_does_not_reallocate_session_no(tmp_path, monkeypatch):
    hook = _load_hook()
    proj = _project(tmp_path)
    _log(proj, "2026-06-03-a.md", date="2026-06-03", slug="a", status="in_progress",
         started_at="2026-06-03T08:00:00+02:00", session_no="7")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(proj))
    hook.main()
    assert "session_no: 7" in (proj / "sessions" / "2026-06-03-a.md").read_text()


def test_clears_pointer_when_done(tmp_path, monkeypatch):
    hook = _load_hook()
    proj = _project(tmp_path)
    _log(proj, "2026-06-03-a.md", date="2026-06-03", slug="a", status="done", session_no="1",
         started_at="2026-06-03T08:00:00+02:00", ended_at="2026-06-03T09:00:00+02:00")
    # seed a pointer naming this log
    import json
    sm = proj / ".claude" / "state" / "session-manifest"
    sm.mkdir(parents=True)
    (sm / "in-flight.json").write_text(json.dumps({"log": "sessions/2026-06-03-a.md", "slug": "a", "started_at": "2026-06-03T08:00:00+02:00"}))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(proj))
    hook.main()
    assert not (sm / "in-flight.json").exists()


def test_fails_open_on_internal_error(tmp_path, monkeypatch, capsys):
    hook = _load_hook()
    proj = _project(tmp_path)
    _log(proj, "2026-06-03-a.md", date="2026-06-03", slug="a", status="in_progress",
         started_at="2026-06-03T08:00:00+02:00")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(proj))
    monkeypatch.setattr(hook, "_resolve_inflight", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert hook.main() == 0
    assert "manifest_stop_update" in capsys.readouterr().err


def test_no_sessions_dir_is_noop(tmp_path, monkeypatch):
    hook = _load_hook()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "empty"))
    assert hook.main() == 0


def test_fenceless_pointer_log_does_not_burn_counter(tmp_path, monkeypatch):
    """Regression for the fan-review finding: a pointer naming a log WITHOUT a closing
    frontmatter fence must NOT be resolved as in-flight — otherwise main() bumps the
    counter every Stop while _insert_field silently no-ops (unbounded counter leak +
    pointer clobbering). The pointer branch must apply the same frontmatter guard the
    mtime branch already uses."""
    import json
    hook = _load_hook()
    proj = _project(tmp_path)
    # A corrupt log: opening fence but NO closing fence.
    (proj / "sessions" / "2026-06-03-broken.md").write_text(
        "---\ndate: 2026-06-03\nstatus: in_progress\nslug: broken\nno closing fence ever\n"
    )
    sm = proj / ".claude" / "state" / "session-manifest"
    sm.mkdir(parents=True)
    (sm / "in-flight.json").write_text(
        json.dumps({"log": "sessions/2026-06-03-broken.md", "slug": "broken", "started_at": "2026-06-03T08:00:00+02:00"})
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(proj))
    hook.main()
    hook.main()
    hook.main()
    # The fence-less log is never resolved → counter never created/bumped.
    assert not (sm / "counter").exists()
    # The corrupt log is never mutated (no session_no inserted).
    assert "session_no" not in (proj / "sessions" / "2026-06-03-broken.md").read_text()
    # It is surfaced in the index as unparseable, not silently dropped.
    assert "⚠ unparseable" in (proj / "sessions" / "INDEX.md").read_text()
