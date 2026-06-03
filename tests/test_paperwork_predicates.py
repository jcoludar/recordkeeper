"""Tests for _paperwork_predicates — must-exist + must-be-modified-this-session."""
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

import _paperwork_predicates as pred  # noqa: E402


# ── must_exist ────────────────────────────────────────────────────────────


def test_must_exist_true_passes_when_glob_matches(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "2026-05-13-x.md").touch()
    matches = pred.resolve_glob(tmp_path, "sessions/2026-05-13-*.md")
    r = pred.must_exist(matches, expected=True)
    assert r.passed is True


def test_must_exist_true_fails_when_glob_matches_nothing(tmp_path):
    matches = pred.resolve_glob(tmp_path, "sessions/2026-05-13-*.md")
    r = pred.must_exist(matches, expected=True)
    assert r.passed is False
    assert "no file matches" in r.reason.lower()


def test_must_exist_false_passes_when_glob_empty(tmp_path):
    matches = pred.resolve_glob(tmp_path, "no-such/*.md")
    r = pred.must_exist(matches, expected=False)
    assert r.passed is True


def test_must_exist_false_fails_when_glob_non_empty(tmp_path):
    (tmp_path / "x.md").touch()
    matches = pred.resolve_glob(tmp_path, "x.md")
    r = pred.must_exist(matches, expected=False)
    assert r.passed is False


# ── must_be_modified_this_session ─────────────────────────────────────────


def test_must_be_modified_true_passes_when_glob_match_in_log(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "2026-05-13-x.md").touch()
    matches = pred.resolve_glob(tmp_path, "sessions/2026-05-13-*.md")
    log = [{"path": "sessions/2026-05-13-x.md", "tool": "Edit"}]
    r = pred.must_be_modified_this_session(
        matches, edit_log=log, project_dir=tmp_path, expected=True
    )
    assert r.passed is True


def test_must_be_modified_true_fails_when_glob_match_absent_from_log(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "2026-05-13-x.md").touch()
    matches = pred.resolve_glob(tmp_path, "sessions/2026-05-13-*.md")
    log: list[dict] = []
    r = pred.must_be_modified_this_session(
        matches, edit_log=log, project_dir=tmp_path, expected=True
    )
    assert r.passed is False
    assert "not modified" in r.reason.lower()


def test_must_be_modified_true_passes_when_at_least_one_match(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "a.md").touch()
    (tmp_path / "sessions" / "b.md").touch()
    matches = pred.resolve_glob(tmp_path, "sessions/*.md")
    log = [{"path": "sessions/a.md"}]
    r = pred.must_be_modified_this_session(
        matches, edit_log=log, project_dir=tmp_path, expected=True
    )
    assert r.passed is True


def test_must_be_modified_false_passes_when_no_glob_match_in_log(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "a.md").touch()
    matches = pred.resolve_glob(tmp_path, "sessions/*.md")
    log = [{"path": "other.md"}]
    r = pred.must_be_modified_this_session(
        matches, edit_log=log, project_dir=tmp_path, expected=False
    )
    assert r.passed is True


def test_must_be_modified_false_fails_when_a_match_in_log(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "a.md").touch()
    matches = pred.resolve_glob(tmp_path, "sessions/*.md")
    log = [{"path": "sessions/a.md"}]
    r = pred.must_be_modified_this_session(
        matches, edit_log=log, project_dir=tmp_path, expected=False
    )
    assert r.passed is False


# ── resolve_glob ──────────────────────────────────────────────────────────


def test_resolve_glob_double_star(tmp_path):
    (tmp_path / "a" / "b" / "c").mkdir(parents=True)
    (tmp_path / "a" / "b" / "c" / "x.md").touch()
    matches = pred.resolve_glob(tmp_path, "a/**/*.md")
    assert any(m.name == "x.md" for m in matches)


def test_resolve_glob_returns_empty_when_no_match(tmp_path):
    matches = pred.resolve_glob(tmp_path, "nope/*.md")
    assert matches == []


def test_resolve_glob_returns_repo_relative_paths(tmp_path):
    (tmp_path / "x.md").touch()
    matches = pred.resolve_glob(tmp_path, "x.md")
    # matches are absolute Paths
    assert matches[0].is_absolute() is True
    assert matches[0].name == "x.md"


# ── parse_frontmatter ─────────────────────────────────────────────────────


def test_parse_frontmatter_returns_dict_for_valid_file(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("---\nfoo: bar\nbaz: 42\n---\nbody\n")
    fm = pred.parse_frontmatter_dict(f)
    assert fm == {"foo": "bar", "baz": 42}


def test_parse_frontmatter_returns_none_for_no_frontmatter(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("just a body\n")
    assert pred.parse_frontmatter_dict(f) is None


def test_parse_frontmatter_raises_on_malformed_yaml(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("---\nfoo: [unclosed\n---\nbody\n")
    with pytest.raises(pred.FrontmatterParseError):
        pred.parse_frontmatter_dict(f)


def test_parse_frontmatter_raises_on_unclosed_fence(tmp_path):
    """An opening `---` with no closing fence is present-but-malformed frontmatter,
    not 'no frontmatter'. It must raise (so the engine reports a parse error), not
    return None (which would be read as an empty-frontmatter pass/fail)."""
    f = tmp_path / "x.md"
    f.write_text("---\nstatus: done\nslug: foo\nno closing fence ever\n")
    with pytest.raises(pred.FrontmatterParseError):
        pred.parse_frontmatter_dict(f)


# ── check_frontmatter — required ──────────────────────────────────────────


def test_frontmatter_required_passes_when_field_present():
    results = pred.check_frontmatter(
        fm={"status": "done"},
        field="status",
        spec={"required": True},
    )
    assert all(r.passed for r in results)


def test_frontmatter_required_fails_when_field_missing():
    results = pred.check_frontmatter(
        fm={},
        field="status",
        spec={"required": True},
    )
    assert any(not r.passed for r in results)
    assert "missing" in results[0].reason.lower()


def test_frontmatter_required_false_optional_field_absent_passes():
    """required: false + field absent → no constraint check needed → pass."""
    results = pred.check_frontmatter(
        fm={},
        field="status",
        spec={"required": False, "equals": "done"},
    )
    assert all(r.passed for r in results)


def test_frontmatter_default_required_true_when_any_constraint_specified():
    """No explicit required → defaults to True when other constraints present."""
    results = pred.check_frontmatter(
        fm={},
        field="status",
        spec={"equals": "done"},  # implies required: true
    )
    assert any(not r.passed for r in results)


# ── check_frontmatter — equals ────────────────────────────────────────────


def test_frontmatter_equals_passes_when_value_matches():
    results = pred.check_frontmatter(
        fm={"date": "2026-05-13"},
        field="date",
        spec={"equals": "2026-05-13"},
    )
    assert all(r.passed for r in results)


def test_frontmatter_equals_fails_when_value_differs():
    results = pred.check_frontmatter(
        fm={"date": "2026-05-12"},
        field="date",
        spec={"equals": "2026-05-13"},
    )
    assert any(not r.passed for r in results)


def test_frontmatter_equals_compares_via_str():
    """YAML `true` boolean compared against spec `true` (string) — both stringify to 'True'/'true' differently.
    The semantics is: str(fm_value) == str(spec_value).
    """
    # YAML bool True stringifies to "True"; spec value "True" matches.
    results = pred.check_frontmatter(
        fm={"formal": True},
        field="formal",
        spec={"equals": "True"},
    )
    assert all(r.passed for r in results)


# ── check_frontmatter — in ────────────────────────────────────────────────


def test_frontmatter_in_passes_when_value_in_set():
    results = pred.check_frontmatter(
        fm={"status": "done"},
        field="status",
        spec={"in": ["done", "paused"]},
    )
    assert all(r.passed for r in results)


def test_frontmatter_in_fails_when_value_not_in_set():
    results = pred.check_frontmatter(
        fm={"status": "in_progress"},
        field="status",
        spec={"in": ["done", "paused"]},
    )
    assert any(not r.passed for r in results)


# ── check_frontmatter — matches ───────────────────────────────────────────


def test_frontmatter_matches_passes_on_regex_match():
    results = pred.check_frontmatter(
        fm={"session_id": "S0036"},
        field="session_id",
        spec={"matches": "^S\\d{4}$"},
    )
    assert all(r.passed for r in results)


def test_frontmatter_matches_fails_on_regex_mismatch():
    results = pred.check_frontmatter(
        fm={"session_id": "X42"},
        field="session_id",
        spec={"matches": "^S\\d{4}$"},
    )
    assert any(not r.passed for r in results)


def test_frontmatter_combined_constraints_all_pass():
    results = pred.check_frontmatter(
        fm={"status": "done"},
        field="status",
        spec={"required": True, "in": ["done", "paused"], "matches": "^d.*$"},
    )
    assert all(r.passed for r in results)


def test_frontmatter_combined_one_fails():
    results = pred.check_frontmatter(
        fm={"status": "done"},
        field="status",
        spec={"required": True, "in": ["paused"]},  # done not in set
    )
    assert any(not r.passed for r in results)


# ── check_frontmatter — datetime / date normalization ─────────────────────
# PyYAML auto-parses unquoted ISO 8601 strings into datetime.datetime /
# datetime.date instances. Default str() on a datetime uses a space separator
# (`2026-05-13 19:00:00+02:00`), which breaks T-separated ISO regexes and
# string-equals comparisons. Predicate must normalize via isoformat().


def test_frontmatter_matches_passes_on_yaml_parsed_datetime():
    import datetime as dt
    value = dt.datetime(2026, 5, 13, 19, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
    results = pred.check_frontmatter(
        fm={"started_at": value},
        field="started_at",
        spec={"matches": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"},
    )
    assert all(r.passed for r in results), [r.reason for r in results if not r.passed]


def test_frontmatter_equals_passes_on_yaml_parsed_date():
    import datetime as dt
    results = pred.check_frontmatter(
        fm={"date": dt.date(2026, 5, 13)},
        field="date",
        spec={"equals": "2026-05-13"},
    )
    assert all(r.passed for r in results), [r.reason for r in results if not r.passed]


def test_frontmatter_equals_passes_on_yaml_parsed_datetime_against_isoformat():
    import datetime as dt
    value = dt.datetime(2026, 5, 13, 19, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))
    results = pred.check_frontmatter(
        fm={"started_at": value},
        field="started_at",
        spec={"equals": "2026-05-13T19:00:00+02:00"},
    )
    assert all(r.passed for r in results), [r.reason for r in results if not r.passed]
