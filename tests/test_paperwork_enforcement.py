"""End-to-end integration test for paperwork-enforcement substrate."""
import importlib.util
import json
import shutil
import sys
from datetime import date, datetime
from io import StringIO
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MASTERBOOK = REPO_ROOT
FIXTURE_SRC = MASTERBOOK / "tests" / "fixtures" / "with_paperwork_enforcement" / "project"


def _assemble_fixture(tmp_path: Path) -> Path:
    """Copy the fixture into tmp_path and run assemble.py against it."""
    project = tmp_path / "proj"
    shutil.copytree(FIXTURE_SRC, project)
    out = project / "CLAUDE.md"

    sys.path.insert(0, str(MASTERBOOK / "tools"))
    import assemble
    rc = assemble.main(argv=[
        "--masterbook", str(MASTERBOOK),
        "--source", str(project / "CLAUDE.source.md"),
        "--out", str(out),
    ])
    assert rc == 0
    return project


def _load_stop_hook(project: Path):
    hook_path = project / ".claude" / "hooks" / "stop_paperwork_check.py"
    sys.path.insert(0, str(hook_path.parent))
    spec = importlib.util.spec_from_file_location("stop_paperwork_check_e2e", hook_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["stop_paperwork_check_e2e"] = module
    spec.loader.exec_module(module)
    return module


def _today() -> str:
    return date.today().isoformat()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def test_substrates_deployed_to_project(tmp_path):
    project = _assemble_fixture(tmp_path)
    # session-paperwork artifacts
    assert (project / ".claude" / "commands" / "begin-session.md").is_file()
    assert (project / ".claude" / "commands" / "debrief.md").is_file()
    assert (project / ".claude" / "hooks" / "session_stop_log_timing.py").is_file()
    # paperwork-enforcement artifacts
    assert (project / ".claude" / "hooks" / "posttooluse_record_edit.py").is_file()
    assert (project / ".claude" / "hooks" / "stop_paperwork_check.py").is_file()
    # Internal helpers should also be there.
    for fname in [
        "_paperwork_session_log.py",
        "_paperwork_edit_log.py",
        "_paperwork_interpolation.py",
        "_paperwork_config.py",
        "_paperwork_predicates.py",
        "_paperwork_engine.py",
    ]:
        assert (project / ".claude" / "hooks" / fname).is_file(), f"missing helper: {fname}"
    # Settings should include the new matchers.
    settings = json.loads((project / ".claude" / "settings.json").read_text())
    matchers = [m["matcher"] for m in settings["hooks"]["PostToolUse"]]
    assert "Edit" in matchers
    assert "Write" in matchers
    assert "NotebookEdit" in matchers


def test_end_to_end_pass_case(tmp_path, monkeypatch):
    """Assemble fixture → write valid session log → enqueue edit-log entry → stop hook exits 0."""
    project = _assemble_fixture(tmp_path)
    today = _today()
    slug = "integration-pass"
    started_at = _now_iso()

    sessions = project / "sessions"
    sessions.mkdir()
    log = sessions / f"{today}-{slug}.md"
    log.write_text(
        f"---\n"
        f"date: {today}\n"
        f"started_at: {started_at}\n"
        f"slug: {slug}\n"
        f"status: done\n"
        f"followups: []\n"
        f"---\n\n"
        f"# Pass case\n"
    )

    state_dir = project / ".claude" / "state"
    state_dir.mkdir()
    (state_dir / "paperwork-edit-log.jsonl").write_text(
        json.dumps({
            "started_at": started_at, "ts": _now_iso(),
            "tool": "Edit", "path": f"sessions/{today}-{slug}.md",
        }) + "\n"
    )

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    hook = _load_stop_hook(project)
    rc = hook.main()
    assert rc == 0


def test_end_to_end_fail_case_missing_required_frontmatter(tmp_path, monkeypatch, capsys):
    """Session log missing required `status:` field → stop hook exits 2 with actionable report."""
    project = _assemble_fixture(tmp_path)
    today = _today()
    slug = "integration-fail"
    started_at = _now_iso()

    sessions = project / "sessions"
    sessions.mkdir()
    log = sessions / f"{today}-{slug}.md"
    log.write_text(
        f"---\n"
        f"date: {today}\n"
        f"started_at: {started_at}\n"
        f"slug: {slug}\n"
        # NO status, NO followups
        f"---\n"
        f"\nbody\n"
    )

    state_dir = project / ".claude" / "state"
    state_dir.mkdir()
    (state_dir / "paperwork-edit-log.jsonl").write_text(
        json.dumps({
            "started_at": started_at, "ts": _now_iso(),
            "tool": "Edit", "path": f"sessions/{today}-{slug}.md",
        }) + "\n"
    )

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    hook = _load_stop_hook(project)
    rc = hook.main()
    err = capsys.readouterr().err
    assert rc == 2
    assert "paperwork-enforcement" in err
    assert "status" in err
    assert "followups" in err
    assert "fix each item" in err.lower()


def test_end_to_end_fail_case_no_inflight_log(tmp_path, monkeypatch, capsys):
    """No session log at all → stop hook exits 2 telling the model to run /begin-session."""
    project = _assemble_fixture(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    hook = _load_stop_hook(project)
    rc = hook.main()
    err = capsys.readouterr().err.lower()
    assert rc == 2
    assert "no in-flight session log" in err


def test_end_to_end_passes_when_no_paperwork_yaml(tmp_path, monkeypatch):
    """Removing paperwork.yaml turns the substrate into a no-op."""
    project = _assemble_fixture(tmp_path)
    (project / ".claude" / "paperwork.yaml").unlink()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr("sys.stdin", StringIO("{}"))
    hook = _load_stop_hook(project)
    rc = hook.main()
    assert rc == 0


def test_end_to_end_posttooluse_records_edits(tmp_path, monkeypatch):
    """PostToolUse hook appends entries with real timestamps."""
    import re
    project = _assemble_fixture(tmp_path)
    today = _today()
    slug = "ptu-test"
    started_at = _now_iso()

    sessions = project / "sessions"
    sessions.mkdir()
    log = sessions / f"{today}-{slug}.md"
    log.write_text(
        f"---\ndate: {today}\nstarted_at: {started_at}\nslug: {slug}\n---\nbody\n"
    )

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    envelope = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(log)},
    }
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(envelope)))

    hook_path = project / ".claude" / "hooks" / "posttooluse_record_edit.py"
    sys.path.insert(0, str(hook_path.parent))
    spec = importlib.util.spec_from_file_location("posttooluse_e2e", hook_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["posttooluse_e2e"] = module
    spec.loader.exec_module(module)
    rc = module.main()
    assert rc == 0

    el_file = project / ".claude" / "state" / "paperwork-edit-log.jsonl"
    entry = json.loads(el_file.read_text().strip())
    assert entry["started_at"] == started_at
    assert entry["tool"] == "Write"
    assert entry["path"] == f"sessions/{today}-{slug}.md"
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$", entry["ts"])
