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


# ── stop_hook_active recursion guard ──────────────────────────────────────


def test_stop_hook_active_bows_out_without_blocking(tmp_path, monkeypatch, capsys):
    """A re-entrant Stop (stop_hook_active=true) must exit 0 even when rules would
    otherwise fail — else a blocking Stop hook can infinite-loop and lose the
    whole session (Anthropic #55754)."""
    hook = _load_hook()
    project = _empty_project(tmp_path)
    # Needs session context; with no in-flight log this blocks (exit 2) normally.
    _write_config(
        project,
        "files:\n  - path: 'sessions/{today}-{session-slug}.md'\n    must-exist: true\n",
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    # Sanity: without the flag, this configuration blocks.
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    assert hook.main() == 2
    capsys.readouterr()  # drain the block message from the first call
    # With stop_hook_active set, the hook bows out cleanly and prints nothing.
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps({"stop_hook_active": True})))
    assert hook.main() == 0
    assert capsys.readouterr().err == ""


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


# ── Fail-policy: gate fails CLOSED on its own code error, with reachable bypass ──


def test_import_failure_fails_closed(tmp_path, monkeypatch, capsys):
    """If the hook's own helper imports fail to load, the gate must BLOCK (exit 2),
    not wave the Stop through (exit 1 = non-blocking = fail-open). tier-1/hook-resilience."""
    hook = _load_hook()
    project = _project_with_inflight_log(tmp_path)
    _write_config(project, "files:\n  - path: 'sessions/{today}-{session-slug}.md'\n    must-exist: true\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.delenv("PAPERWORK_ENFORCEMENT_BYPASS", raising=False)
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    # Simulate a broken dependency (ImportError captured at module load).
    monkeypatch.setattr(hook, "_IMPORT_ERROR", ImportError("No module named '_paperwork_engine'"))
    rc = hook.main()
    err = capsys.readouterr().err
    assert rc == 2
    assert "PAPERWORK_ENFORCEMENT_BYPASS" in err  # the bypass is advertised


def test_bypass_env_exits_zero_even_when_rules_would_block(tmp_path, monkeypatch, capsys):
    """The reachable bypass lets the operator past a gate (broken or otherwise);
    it is loud (prints to stderr) and is checked before the fragile code path."""
    hook = _load_hook()
    project = _empty_project(tmp_path)
    # This config blocks normally (rules need session context, no in-flight log).
    _write_config(project, "files:\n  - path: 'sessions/{today}-{session-slug}.md'\n    must-exist: true\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setenv("PAPERWORK_ENFORCEMENT_BYPASS", "1")
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    rc = hook.main()
    err = capsys.readouterr().err
    assert rc == 0
    assert "bypass" in err.lower()


def test_bypass_reaches_past_broken_imports(tmp_path, monkeypatch, capsys):
    """A broken gate must still be bypassable — the bypass is checked before imports
    are consulted, so it works even when the helpers failed to load."""
    hook = _load_hook()
    project = _project_with_inflight_log(tmp_path)
    _write_config(project, "files:\n  - path: 'sessions/{today}-{session-slug}.md'\n    must-exist: true\n")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setenv("PAPERWORK_ENFORCEMENT_BYPASS", "1")
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    monkeypatch.setattr(hook, "_IMPORT_ERROR", ImportError("boom"))
    assert hook.main() == 0


# ── tier: deferred (tier-2) rules don't block; tier-1 do ──────────────────


def test_tier2_only_failure_does_not_block(tmp_path, monkeypatch, capsys):
    """A failing tier-2 (deferred) rule is surfaced as an advisory but must NOT
    block the Stop (exit 0)."""
    hook = _load_hook()
    project = _project_with_inflight_log(tmp_path)
    _write_config(project, "files:\n  - path: 'NONEXISTENT.md'\n    must-exist: true\n    tier: 2\n")
    monkeypatch.setattr(hook, "_today_iso", lambda: _FIXTURE_DATE)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    rc = hook.main()
    err = capsys.readouterr().err
    assert rc == 0
    assert "deferred" in err.lower()
    assert "NONEXISTENT.md" in err


def test_tier1_failure_blocks_even_alongside_tier2(tmp_path, monkeypatch, capsys):
    """A failing tier-1 rule blocks (exit 2); a tier-2 failure in the same run is
    still reported, as an advisory."""
    hook = _load_hook()
    project = _project_with_inflight_log(tmp_path)
    _write_config(
        project,
        "files:\n"
        "  - path: 'MISSING_BLOCKING.md'\n"
        "    must-exist: true\n"
        "  - path: 'MISSING_DEFERRED.md'\n"
        "    must-exist: true\n"
        "    tier: 2\n",
    )
    monkeypatch.setattr(hook, "_today_iso", lambda: _FIXTURE_DATE)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    rc = hook.main()
    err = capsys.readouterr().err
    assert rc == 2
    assert "MISSING_BLOCKING.md" in err
    assert "rule(s) failed" in err
    # The deferred item is still surfaced (advisory section).
    assert "MISSING_DEFERRED.md" in err


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


# ── Cross-midnight session — resolve against the log's own {session-date} ──
#
# A session that STARTED yesterday and stops after midnight has a log dated
# yesterday. {today} (system date) no longer matches the log's filename/date, so
# a {today}-built path false-blocks. {session-date} (the in-flight log's OWN date)
# resolves the rule against the log actually in play.

_CM_LOG_DATE = "2026-06-11"
_CM_TODAY = "2026-06-12"


def _project_with_yesterday_log(tmp_path, slug="night-owl", status="in_progress"):
    project = tmp_path / "proj"
    project.mkdir()
    sessions = project / "sessions"
    sessions.mkdir(parents=True)
    started = f"{_CM_LOG_DATE}T23:30:00+02:00"
    (sessions / f"{_CM_LOG_DATE}-{slug}.md").write_text(
        f"---\ndate: {_CM_LOG_DATE}\nstarted_at: {started}\nslug: {slug}\n"
        f"status: {status}\n---\n\nbody\n"
    )
    return project


def test_cross_midnight_session_date_resolves_to_real_log(tmp_path, monkeypatch, capsys):
    """With {session-date} the rule resolves against the log's OWN date, so a
    session spanning midnight does NOT false-block (exit 0)."""
    hook = _load_hook()
    project = _project_with_yesterday_log(tmp_path)
    _write_config(
        project,
        "files:\n"
        "  - path: 'sessions/{session-date}-{session-slug}.md'\n"
        "    must-exist: true\n"
        "    frontmatter:\n"
        "      date: {required: true, equals: '{session-date}'}\n",
    )
    monkeypatch.setattr(hook, "_today_iso", lambda: _CM_TODAY)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    rc = hook.main()
    err = capsys.readouterr().err
    assert rc == 0
    assert err == ""


def test_cross_midnight_today_token_false_blocks(tmp_path, monkeypatch, capsys):
    """Regression rationale (the cross-midnight bug): the OLD {today}-built path
    false-blocks the same cross-midnight session, because the log is dated yesterday."""
    hook = _load_hook()
    project = _project_with_yesterday_log(tmp_path)
    _write_config(
        project,
        "files:\n  - path: 'sessions/{today}-{session-slug}.md'\n    must-exist: true\n",
    )
    monkeypatch.setattr(hook, "_today_iso", lambda: _CM_TODAY)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    rc = hook.main()
    assert rc == 2
