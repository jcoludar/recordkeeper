import importlib.util
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "substrate" / "session-manifest" / "hooks"


def _load(name):
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _log(sessions, name, **fm):
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append("# body")
    (sessions / name).write_text("\n".join(lines) + "\n")


def test_read_fields_extracts_frontmatter(tmp_path):
    m = _load("_manifest_index")
    f = tmp_path / "x.md"
    f.write_text("---\ndate: 2026-06-03\nstatus: done\nsession_no: 4\n---\n\nbody\n")
    fields = m.read_fields(f)
    assert fields["status"] == "done"
    assert fields["session_no"] == "4"


def test_regenerate_sorts_by_session_no(tmp_path):
    m = _load("_manifest_index")
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _log(sessions, "2026-06-03-b.md", date="2026-06-03", slug="b", session_no="2", status="done",
         started_at="2026-06-03T10:00:00+02:00", ended_at="2026-06-03T11:00:00+02:00")
    _log(sessions, "2026-06-03-a.md", date="2026-06-03", slug="a", session_no="1", status="done",
         started_at="2026-06-03T08:00:00+02:00", ended_at="2026-06-03T09:00:00+02:00")
    m.regenerate_index(sessions)
    text = (sessions / "INDEX.md").read_text()
    assert text.index("| 1 |") < text.index("| 2 |")
    assert "do not edit by hand" in text.lower()


def test_regenerate_marks_unclosed(tmp_path):
    m = _load("_manifest_index")
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _log(sessions, "2026-06-03-open.md", date="2026-06-03", slug="open", session_no="1",
         status="in_progress", started_at="2026-06-03T08:00:00+02:00", ended_at="")
    m.regenerate_index(sessions)
    assert "⚠ unclosed" in (sessions / "INDEX.md").read_text()


def test_regenerate_marks_unparseable_not_crash(tmp_path):
    m = _load("_manifest_index")
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "broken.md").write_text("---\nno close fence\n")
    m.regenerate_index(sessions)  # must not raise
    assert "⚠ unparseable" in (sessions / "INDEX.md").read_text()


def test_regenerate_excludes_index_and_readme(tmp_path):
    m = _load("_manifest_index")
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "README.md").write_text("# readme\n")
    _log(sessions, "2026-06-03-a.md", date="2026-06-03", slug="a", session_no="1", status="done",
         started_at="2026-06-03T08:00:00+02:00", ended_at="2026-06-03T09:00:00+02:00")
    m.regenerate_index(sessions)
    text = (sessions / "INDEX.md").read_text()
    assert "README" not in text


def test_regenerate_tolerates_non_utf8_log(tmp_path):
    """A non-UTF-8 log must degrade to one ⚠ unparseable row, not abort the whole regen.
    Regression for the fan-review finding: read_text() raises UnicodeDecodeError (a
    ValueError, NOT an OSError), which escaped the per-file guard and aborted regen."""
    m = _load("_manifest_index")
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "2026-06-03-good.md").write_bytes(
        b"---\ndate: 2026-06-03\nslug: good\nsession_no: 1\nstatus: done\n"
        b"started_at: 2026-06-03T08:00:00+02:00\nended_at: 2026-06-03T09:00:00+02:00\n---\n\nbody\n"
    )
    (sessions / "2026-06-03-bad.md").write_bytes(b"---\ndate: 2026-06-03\nslug: \xff\xfe bad\n---\nbody\n")
    m.regenerate_index(sessions)  # must NOT raise
    text = (sessions / "INDEX.md").read_text()
    assert "good" in text            # the good log is still indexed
    assert "⚠ unparseable" in text   # the bad log is surfaced, not crashed on
