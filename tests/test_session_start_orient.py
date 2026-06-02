"""Tests for session_start_orient.py — SessionStart hook, offline-only."""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = (
    Path(__file__).resolve().parent.parent
    / "substrate"
    / "cross-repo-orientation"
    / "hooks"
    / "session_start_orient.py"
)

sys.path.insert(0, str(HOOK.parent))
import session_start_orient


def _write_session_log(sessions: Path, slug: str, frontmatter: dict, body: str = "") -> Path:
    sessions.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append(body)
    path = sessions / f"{frontmatter.get('date', '2026-05-27')}-{slug}.md"
    path.write_text("\n".join(lines) + "\n")
    return path


def test_read_last_session_log_returns_most_recent_by_mtime(tmp_path):
    sessions = tmp_path / "sessions"
    old = _write_session_log(sessions, "old", {"date": "2026-05-26", "slug": "old", "status": "done"})
    newer = _write_session_log(sessions, "new", {"date": "2026-05-27", "slug": "new", "status": "done"})
    os.utime(old, (1000, 1000))
    os.utime(newer, (2000, 2000))
    info = session_start_orient.read_last_session_log(sessions)
    assert info is not None
    assert info["path"] == newer
    assert info["frontmatter"]["slug"] == "new"


def test_read_last_session_log_returns_recently_edited_old_log(tmp_path):
    """Catch-up edit to an older log makes it the handoff (mtime trumps date)."""
    sessions = tmp_path / "sessions"
    older_date = _write_session_log(sessions, "may26", {"date": "2026-05-26", "slug": "may26", "status": "done"})
    newer_date = _write_session_log(sessions, "may27", {"date": "2026-05-27", "slug": "may27", "status": "done"})
    os.utime(newer_date, (1000, 1000))
    os.utime(older_date, (2000, 2000))
    info = session_start_orient.read_last_session_log(sessions)
    assert info["path"] == older_date


def test_read_last_session_log_handles_empty_dir(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    assert session_start_orient.read_last_session_log(sessions) is None


def test_read_last_session_log_handles_missing_dir(tmp_path):
    assert session_start_orient.read_last_session_log(tmp_path / "missing") is None


def test_read_last_session_log_skips_malformed_frontmatter(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "2026-05-27-broken.md").write_text("not frontmatter\n")
    good = _write_session_log(sessions, "good", {"date": "2026-05-26", "slug": "good", "status": "done"})
    info = session_start_orient.read_last_session_log(sessions)
    assert info is not None
    assert info["path"] == good


def test_build_context_with_recent_session(tmp_path):
    log = {
        "path": Path("sessions/2026-05-27-foo.md"),
        "frontmatter": {
            "status": "done",
            "ended_at": "2026-05-27T18:00:00+02:00",
            "repos": ["example-tool_web"],
            "followups": [
                "[example-tool_web] finish filter-menu refactor",
                "[example-tool] rerun toxprot demo",
                "[example-tool_web] bump playwright",
            ],
        },
    }
    now = dt.datetime(2026, 5, 27, 18, 5, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
    ctx = session_start_orient.build_context(log, now=now)
    assert "Workspace: example-tool cross-repo dev kit." in ctx
    assert "Last session: sessions/2026-05-27-foo.md" in ctx
    assert "status=done" in ctx
    assert "3 followups" in ctx
    assert "[example-tool_web] finish filter-menu refactor" in ctx
    assert "ended ~5 min ago" in ctx
    # No imperative phrasing.
    assert "You are " not in ctx
    assert "You must " not in ctx


def test_build_context_with_no_session():
    ctx = session_start_orient.build_context(None, now=None)
    assert "no prior session log" in ctx.lower()
    assert "/begin-session" in ctx


def test_build_context_truncates_when_huge():
    log = {
        "path": Path("sessions/2026-05-27-x.md"),
        "frontmatter": {
            "status": "paused",
            "followups": ["x" * 10000] * 50,
        },
    }
    ctx = session_start_orient.build_context(log, now=None)
    assert len(ctx) <= session_start_orient.ADDITIONAL_CONTEXT_LIMIT


def test_build_context_handles_no_ended_at(tmp_path):
    log = {
        "path": Path("sessions/2026-05-27-x.md"),
        "frontmatter": {"status": "in_progress", "followups": []},
    }
    ctx = session_start_orient.build_context(log, now=None)
    assert "ended" not in ctx.lower() or "no ended_at" in ctx.lower()


def test_parse_frontmatter_handles_inline_empty_list(tmp_path):
    """Repos: [] and followups: [] (as written by /begin-session) parse as empty lists."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "2026-05-27-empty.md").write_text(
        "---\ndate: 2026-05-27\nslug: empty\nstatus: in_progress\nrepos: []\nfollowups: []\n---\nbody\n"
    )
    info = session_start_orient.read_last_session_log(sessions)
    assert info["frontmatter"]["repos"] == []
    assert info["frontmatter"]["followups"] == []


def test_parse_frontmatter_handles_inline_list_with_items(tmp_path):
    """Repos: [example-tool, example-tool_web] parses to a real list."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "2026-05-27-inline.md").write_text(
        "---\ndate: 2026-05-27\nslug: inline\nstatus: done\n"
        "repos: [example-tool, example-tool_web]\n---\nbody\n"
    )
    info = session_start_orient.read_last_session_log(sessions)
    assert info["frontmatter"]["repos"] == ["example-tool", "example-tool_web"]


def _run_hook(project_dir: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        ["/usr/bin/env", "python3", str(HOOK)],
        input="{}",
        capture_output=True,
        text=True,
        env=env,
    )


def test_main_emits_json_with_session_log(tmp_path):
    sessions = tmp_path / "sessions"
    _write_session_log(
        sessions,
        "test",
        {
            "date": "2026-05-27",
            "slug": "test",
            "status": "done",
            "ended_at": "2026-05-27T10:00:00+02:00",
            "repos": ["example-tool"],
            "followups": ["[example-tool] do thing"],
        },
    )
    r = _run_hook(tmp_path)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "Last session:" in data["hookSpecificOutput"]["additionalContext"]
    assert data["suppressOutput"] is True


def test_main_emits_json_with_no_session_log(tmp_path):
    (tmp_path / "sessions").mkdir()
    r = _run_hook(tmp_path)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert "no prior session log" in data["hookSpecificOutput"]["additionalContext"].lower()


def test_main_emits_json_when_no_sessions_dir(tmp_path):
    r = _run_hook(tmp_path)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert "no prior session log" in data["hookSpecificOutput"]["additionalContext"].lower()


def test_main_emits_json_when_project_dir_missing(tmp_path):
    env = os.environ.copy()
    env.pop("CLAUDE_PROJECT_DIR", None)
    r = subprocess.run(
        ["/usr/bin/env", "python3", str(HOOK)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "hookSpecificOutput" in data


def test_main_output_under_10k_chars(tmp_path):
    sessions = tmp_path / "sessions"
    big_followups = [f"[example-tool] item {i} " + ("x" * 200) for i in range(500)]
    _write_session_log(
        sessions,
        "huge",
        {"date": "2026-05-27", "slug": "huge", "status": "done", "followups": big_followups},
    )
    r = _run_hook(tmp_path)
    assert r.returncode == 0
    assert len(r.stdout) < session_start_orient.TOTAL_OUTPUT_LIMIT
