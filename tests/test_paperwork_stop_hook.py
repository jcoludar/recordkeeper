"""Tests for stop_paperwork_check hook."""
import importlib.util
import json
import sys
from io import StringIO
from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).resolve().parent.parent
    / "substrate"
    / "paperwork-enforcement"
    / "hooks"
    / "stop_paperwork_check.py"
)


def _load_hook():
    SUBSTRATE_HOOKS = HOOK_PATH.parent
    if str(SUBSTRATE_HOOKS) not in sys.path:
        sys.path.insert(0, str(SUBSTRATE_HOOKS))
    spec = importlib.util.spec_from_file_location("stop_paperwork_check", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["stop_paperwork_check"] = module
    spec.loader.exec_module(module)
    return module


def _empty_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    return project


_FIXTURE_DATE = "2026-05-13"
_FIXTURE_STARTED_AT = "2026-05-13T08:00:00+02:00"


def _project_with_inflight_log(
    tmp_path: Path,
    started_at: str = _FIXTURE_STARTED_AT,
    slug: str = "wave-3",
    sessions_dir: str = "sessions",
) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    sessions = project / sessions_dir
    sessions.mkdir(parents=True)
    log = sessions / f"{_FIXTURE_DATE}-{slug}.md"
    log.write_text(
        f"---\ndate: {_FIXTURE_DATE}\nstarted_at: {started_at}\nslug: {slug}\nstatus: done\nfollowups: []\n---\n\nbody\n"
    )
    return project


def _write_config(project: Path, body: str) -> Path:
    config = project / ".claude" / "paperwork.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(body)
    return config


# ── Missing config → silent exit 0 ────────────────────────────────────────


def test_missing_config_exits_zero_silent(tmp_path, monkeypatch, capsys):
    hook = _load_hook()
    project = _empty_project(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    assert hook.main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""


# ── Malformed config → exit 2 ─────────────────────────────────────────────


def test_malformed_config_exits_two(tmp_path, monkeypatch, capsys):
    hook = _load_hook()
    project = _empty_project(tmp_path)
    _write_config(project, "files: [\n  - path: 'unclosed\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    assert hook.main() == 2
    err = capsys.readouterr().err.lower()
    assert "malformed yaml" in err


def test_unknown_top_level_key_exits_two(tmp_path, monkeypatch, capsys):
    hook = _load_hook()
    project = _empty_project(tmp_path)
    _write_config(project, "fles: []\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    assert hook.main() == 2
    err = capsys.readouterr().err
    assert "unknown key" in err.lower()
    assert "fles" in err


# ── No in-flight log + rules need context → exit 2 ────────────────────────


def test_no_inflight_log_when_rules_need_session_context(tmp_path, monkeypatch, capsys):
    hook = _load_hook()
    project = _empty_project(tmp_path)
    _write_config(project, "files:\n  - path: 'sessions/{today}-*.md'\n    must-exist: true\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    assert hook.main() == 2
    err = capsys.readouterr().err.lower()
    assert "no in-flight session log" in err


def test_no_inflight_log_when_rules_dont_need_context(tmp_path, monkeypatch):
    hook = _load_hook()
    project = _empty_project(tmp_path)
    _write_config(project, "consistency:\n  - name: x\n    find: foo\n    in: a.md\n    must-also-appear-in: [b.md]\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    assert hook.main() == 0


# ── Pass case → silent ────────────────────────────────────────────────────


def test_passing_rules_exit_zero_silent(tmp_path, monkeypatch, capsys):
    hook = _load_hook()
    project = _project_with_inflight_log(tmp_path)
    _write_config(project, "files:\n  - path: 'sessions/{today}-{session-slug}.md'\n    must-exist: true\n")
    # Pre-populate the edit log to mark the session log as modified.
    started_at = _FIXTURE_STARTED_AT
    log_path = project / ".claude" / "state" / "paperwork-edit-log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps({
        "started_at": started_at, "ts": started_at,
        "tool": "Edit", "path": f"sessions/{_FIXTURE_DATE}-wave-3.md",
    }) + "\n")
    # No `must-be-modified-this-session: true` so this only checks must-exist.
    # Pin {today} to the fixture date so the resolved path matches the fixture file.
    monkeypatch.setattr(hook, "_today_iso", lambda: _FIXTURE_DATE)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    rc = hook.main()
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""


# ── Fail case → exit 2 + report ──────────────────────────────────────────


def test_failing_rules_exit_two_with_report(tmp_path, monkeypatch, capsys):
    hook = _load_hook()
    project = _project_with_inflight_log(tmp_path)
    _write_config(
        project,
        "files:\n"
        "  - path: 'sessions/{today}-{session-slug}.md'\n"
        "    must-exist: true\n"
        "    must-be-modified-this-session: true\n"  # nothing in edit log → fails
        "    frontmatter:\n"
        "      missing_field: {required: true}\n",  # field absent → fails
    )
    # Pin {today} to the fixture date so the resolved path matches the fixture file.
    monkeypatch.setattr(hook, "_today_iso", lambda: _FIXTURE_DATE)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    rc = hook.main()
    err = capsys.readouterr().err
    assert rc == 2
    assert "paperwork-enforcement" in err
    assert "rule(s) failed" in err
    assert "missing_field" in err
    assert "not modified" in err.lower()
    assert "fix each item" in err.lower()


# ── --validate-config CLI ────────────────────────────────────────────────


def test_validate_config_cli_zero_on_valid(tmp_path):
    hook = _load_hook()
    config = tmp_path / "paperwork.yaml"
    config.write_text("files: []\n")
    rc = hook.main(argv=["--validate-config", str(config)])
    assert rc == 0


def test_validate_config_cli_two_on_invalid(tmp_path, capsys):
    hook = _load_hook()
    config = tmp_path / "paperwork.yaml"
    config.write_text("fles: []\n")
    rc = hook.main(argv=["--validate-config", str(config)])
    assert rc == 2
    err = capsys.readouterr().err.lower()
    assert "unknown key" in err


# ── Configurable session-log-dir ─────────────────────────────────────────


def test_configurable_session_log_dir_used(tmp_path, monkeypatch, capsys):
    hook = _load_hook()
    project = _project_with_inflight_log(tmp_path, sessions_dir="docs/sessions")
    _write_config(
        project,
        "session-log-dir: docs/sessions\n"
        "files:\n"
        "  - path: 'docs/sessions/{today}-{session-slug}.md'\n"
        "    must-exist: true\n",
    )
    # Pin {today} to the fixture date so the resolved path matches the fixture file.
    monkeypatch.setattr(hook, "_today_iso", lambda: _FIXTURE_DATE)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    rc = hook.main()
    assert rc == 0


# ── Internal error → exit 2 ───────────────────────────────────────────────


def test_internal_error_exits_two(tmp_path, monkeypatch, capsys):
    """If something unexpected raises, we exit 2 with an `internal error` message."""
    hook = _load_hook()
    project = _project_with_inflight_log(tmp_path)
    _write_config(project, "files:\n  - path: 'sessions/{today}-{session-slug}.md'\n    must-exist: true\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))

    # Force run_all to throw.
    sys.path.insert(0, str(HOOK_PATH.parent))
    import _paperwork_engine as eng
    monkeypatch.setattr(eng, "run_all", lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")))

    rc = hook.main()
    err = capsys.readouterr().err.lower()
    assert rc == 2
    assert "internal error" in err
