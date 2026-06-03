"""Tests for _paperwork_engine — file-rule orchestration (T8)."""
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

import _paperwork_engine as engine  # noqa: E402


# ── evaluate_file_rule — must-exist ───────────────────────────────────────


def test_file_rule_must_exist_passes(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "2026-05-13-x.md").touch()
    failures = engine.evaluate_file_rule(
        rule={
            "path": "sessions/2026-05-13-x.md",
            "must-exist": True,
        },
        project_dir=tmp_path,
        edit_log=[],
    )
    assert failures == []


def test_file_rule_must_exist_fails(tmp_path):
    failures = engine.evaluate_file_rule(
        rule={
            "path": "sessions/missing.md",
            "must-exist": True,
        },
        project_dir=tmp_path,
        edit_log=[],
    )
    assert len(failures) == 1
    assert "no file matches" in failures[0].reason.lower()
    assert failures[0].rule_label == "[files] sessions/missing.md"


# ── evaluate_file_rule — must-be-modified ─────────────────────────────────


def test_file_rule_modified_passes_when_in_log(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "x.md").touch()
    failures = engine.evaluate_file_rule(
        rule={
            "path": "sessions/x.md",
            "must-exist": True,
            "must-be-modified-this-session": True,
        },
        project_dir=tmp_path,
        edit_log=[{"path": "sessions/x.md"}],
    )
    assert failures == []


def test_file_rule_modified_fails_when_absent(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "x.md").touch()
    failures = engine.evaluate_file_rule(
        rule={
            "path": "sessions/x.md",
            "must-exist": True,
            "must-be-modified-this-session": True,
        },
        project_dir=tmp_path,
        edit_log=[],
    )
    assert len(failures) == 1
    assert "not modified" in failures[0].reason.lower()


# ── evaluate_file_rule — frontmatter ──────────────────────────────────────


def test_file_rule_frontmatter_passes(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "x.md").write_text(
        "---\nstatus: done\nslug: x\n---\nbody\n"
    )
    failures = engine.evaluate_file_rule(
        rule={
            "path": "sessions/x.md",
            "must-exist": True,
            "frontmatter": {
                "status": {"required": True, "in": ["done", "paused"]},
            },
        },
        project_dir=tmp_path,
        edit_log=[],
    )
    assert failures == []


def test_file_rule_frontmatter_missing_required(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "x.md").write_text("---\nslug: x\n---\nbody\n")
    failures = engine.evaluate_file_rule(
        rule={
            "path": "sessions/x.md",
            "must-exist": True,
            "frontmatter": {"status": {"required": True}},
        },
        project_dir=tmp_path,
        edit_log=[],
    )
    assert len(failures) == 1
    assert "status" in failures[0].reason
    assert "missing" in failures[0].reason.lower()


def test_file_rule_frontmatter_multiple_failures(tmp_path):
    """One file with two failing fields produces two failure rows."""
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "x.md").write_text(
        "---\nstatus: in_progress\nslug: x\n---\nbody\n"
    )
    failures = engine.evaluate_file_rule(
        rule={
            "path": "sessions/x.md",
            "must-exist": True,
            "frontmatter": {
                "status": {"required": True, "in": ["done", "paused"]},
                "followups": {"required": True},
            },
        },
        project_dir=tmp_path,
        edit_log=[],
    )
    assert len(failures) == 2
    reasons = [f.reason for f in failures]
    assert any("status" in r for r in reasons)
    assert any("followups" in r for r in reasons)


def test_file_rule_frontmatter_per_match_when_glob(tmp_path):
    """Glob matches multiple files; each failing produces its own row."""
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "a.md").write_text("---\nslug: a\n---\nbody\n")
    (tmp_path / "sessions" / "b.md").write_text("---\nstatus: done\nslug: b\n---\n")
    failures = engine.evaluate_file_rule(
        rule={
            "path": "sessions/*.md",
            "must-exist": True,
            "frontmatter": {"status": {"required": True}},
        },
        project_dir=tmp_path,
        edit_log=[],
    )
    # only a.md fails
    assert len(failures) == 1
    assert "a.md" in failures[0].rule_label


def test_file_rule_skips_frontmatter_when_must_exist_fails(tmp_path):
    """If the file doesn't exist, frontmatter checks can't run."""
    failures = engine.evaluate_file_rule(
        rule={
            "path": "sessions/missing.md",
            "must-exist": True,
            "frontmatter": {"status": {"required": True}},
        },
        project_dir=tmp_path,
        edit_log=[],
    )
    # Only the must-exist failure; no spurious frontmatter rows.
    assert len(failures) == 1


def test_file_rule_corrupted_frontmatter(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "x.md").write_text("---\nstatus: [unclosed\n---\n")
    failures = engine.evaluate_file_rule(
        rule={
            "path": "sessions/x.md",
            "must-exist": True,
            "frontmatter": {"status": {"required": True}},
        },
        project_dir=tmp_path,
        edit_log=[],
    )
    assert len(failures) == 1
    assert "frontmatter" in failures[0].reason.lower()
    assert "malformed" in failures[0].reason.lower() or "parse" in failures[0].reason.lower()


def test_file_rule_no_frontmatter_in_target(tmp_path):
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "x.md").write_text("body only\n")
    failures = engine.evaluate_file_rule(
        rule={
            "path": "sessions/x.md",
            "must-exist": True,
            "frontmatter": {"status": {"required": True}},
        },
        project_dir=tmp_path,
        edit_log=[],
    )
    assert len(failures) == 1
    assert "status" in failures[0].reason


# ── when: gating ──────────────────────────────────────────────────────────


def test_when_clause_holds_true_when_log_has_matching_edit():
    log = [{"path": "src/foo.py"}, {"path": "docs/bar.md"}]
    assert engine.when_clause_holds(
        when={"when-files-modified-matching": "src/**"},
        edit_log=log,
    ) is True


def test_when_clause_holds_false_when_log_has_no_matching_edit():
    log = [{"path": "docs/bar.md"}]
    assert engine.when_clause_holds(
        when={"when-files-modified-matching": "src/**"},
        edit_log=log,
    ) is False


def test_when_clause_holds_true_when_no_when_clause():
    """No `when:` means always-run."""
    assert engine.when_clause_holds(when=None, edit_log=[]) is True


def test_file_rule_skipped_when_when_clause_false(tmp_path):
    """Rule body should not run if `when:` evaluates false."""
    failures = engine.evaluate_file_rule(
        rule={
            "path": "sessions/missing.md",
            "must-exist": True,  # would fail
            "when": {"when-files-modified-matching": "src/**"},
        },
        project_dir=tmp_path,
        edit_log=[{"path": "docs/elsewhere.md"}],  # no src/ edit → when false
    )
    assert failures == []


def test_file_rule_runs_when_when_clause_true(tmp_path):
    failures = engine.evaluate_file_rule(
        rule={
            "path": "sessions/missing.md",
            "must-exist": True,
            "when": {"when-files-modified-matching": "src/**"},
        },
        project_dir=tmp_path,
        edit_log=[{"path": "src/foo.py"}],
    )
    assert len(failures) == 1


# ── consistency rules ─────────────────────────────────────────────────────


def test_consistency_passes_when_all_captures_in_target(tmp_path):
    src = tmp_path / "session.md"
    src.write_text("---\ndate: x\n---\n\nF1 F2 found.\n")
    tgt = tmp_path / "TECHNICAL_DEBT.md"
    tgt.write_text("entries: F1, F2 noted.\n")
    failures = engine.evaluate_consistency_rule(
        rule={
            "name": "findings-tracked",
            "find": "F\\d+",
            "in": "session.md",
            "must-also-appear-in": ["TECHNICAL_DEBT.md"],
        },
        project_dir=tmp_path,
    )
    assert failures == []


def test_consistency_fails_when_capture_missing_in_target(tmp_path):
    src = tmp_path / "session.md"
    src.write_text("---\ndate: x\n---\n\nF1 F2 F3 found.\n")
    tgt = tmp_path / "TECHNICAL_DEBT.md"
    tgt.write_text("entries: F1, F2 noted.\n")  # F3 missing
    failures = engine.evaluate_consistency_rule(
        rule={
            "name": "findings-tracked",
            "find": "F\\d+",
            "in": "session.md",
            "must-also-appear-in": ["TECHNICAL_DEBT.md"],
        },
        project_dir=tmp_path,
    )
    assert len(failures) == 1
    assert "F3" in failures[0].reason
    assert "TECHNICAL_DEBT.md" in failures[0].reason
    assert "[consistency: findings-tracked]" in failures[0].rule_label


def test_consistency_ignores_captures_in_frontmatter(tmp_path):
    """find: should only match within body, not within source frontmatter."""
    src = tmp_path / "session.md"
    src.write_text("---\nsession_id: S99\ndate: x\n---\n\nBody has no S codes.\n")
    tgt = tmp_path / "INDEX.md"
    tgt.write_text("no S codes\n")
    failures = engine.evaluate_consistency_rule(
        rule={
            "name": "session-ids-cross-referenced",
            "find": "S\\d+",
            "in": "session.md",
            "must-also-appear-in": ["INDEX.md"],
        },
        project_dir=tmp_path,
    )
    # S99 was in frontmatter only — no captures expected.
    assert failures == []


def test_consistency_glob_target_passes_when_any_match_contains(tmp_path):
    src = tmp_path / "src.md"
    src.write_text("body F1 found\n")
    (tmp_path / "handoffs").mkdir()
    (tmp_path / "handoffs" / "a.md").write_text("nothing here\n")
    (tmp_path / "handoffs" / "b.md").write_text("F1 is here\n")
    failures = engine.evaluate_consistency_rule(
        rule={
            "name": "x",
            "find": "F\\d+",
            "in": "src.md",
            "must-also-appear-in": ["handoffs/*.md"],
        },
        project_dir=tmp_path,
    )
    assert failures == []


def test_consistency_glob_target_fails_when_no_match_contains(tmp_path):
    src = tmp_path / "src.md"
    src.write_text("body F9 found\n")
    (tmp_path / "handoffs").mkdir()
    (tmp_path / "handoffs" / "a.md").write_text("F1 only\n")
    failures = engine.evaluate_consistency_rule(
        rule={
            "name": "x",
            "find": "F\\d+",
            "in": "src.md",
            "must-also-appear-in": ["handoffs/*.md"],
        },
        project_dir=tmp_path,
    )
    assert len(failures) == 1
    assert "F9" in failures[0].reason


def test_consistency_source_glob_applies_per_match(tmp_path):
    """When `in:` is a glob, each matching source produces its own evaluation."""
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "a.md").write_text("F1\n")
    (tmp_path / "sessions" / "b.md").write_text("F2\n")
    tgt = tmp_path / "TD.md"
    tgt.write_text("F1\n")
    failures = engine.evaluate_consistency_rule(
        rule={
            "name": "tracked",
            "find": "F\\d+",
            "in": "sessions/*.md",
            "must-also-appear-in": ["TD.md"],
        },
        project_dir=tmp_path,
    )
    # b.md's F2 is missing in TD.md
    assert len(failures) == 1
    assert "F2" in failures[0].reason


def test_consistency_dedups_captures_within_source(tmp_path):
    """F1 mentioned three times in source = one capture per unique string."""
    src = tmp_path / "src.md"
    src.write_text("F1 F1 F1 F1 again\n")
    tgt = tmp_path / "TD.md"
    tgt.write_text("nothing\n")
    failures = engine.evaluate_consistency_rule(
        rule={
            "name": "x",
            "find": "F\\d+",
            "in": "src.md",
            "must-also-appear-in": ["TD.md"],
        },
        project_dir=tmp_path,
    )
    # Only one failure for the unique capture F1.
    assert len(failures) == 1


# ── run_all ───────────────────────────────────────────────────────────────


def test_run_all_combines_file_and_consistency_failures(tmp_path):
    src = tmp_path / "session.md"
    src.write_text("---\nslug: x\n---\n\nF1 mentioned\n")
    tgt = tmp_path / "TD.md"
    tgt.write_text("nothing\n")
    config = {
        "session-log-dir": "sessions",
        "files": [
            {"path": "session.md", "must-exist": True, "frontmatter": {"status": {"required": True}}},
        ],
        "consistency": [
            {"name": "tracked", "find": "F\\d+", "in": "session.md", "must-also-appear-in": ["TD.md"]},
        ],
    }
    failures = engine.run_all(config=config, project_dir=tmp_path, edit_log=[])
    # one file failure (missing status) + one consistency failure (F1 missing in TD)
    assert len(failures) == 2


def test_run_all_returns_empty_when_all_pass(tmp_path):
    src = tmp_path / "session.md"
    src.write_text("---\nslug: x\nstatus: done\n---\n")
    config = {
        "session-log-dir": "sessions",
        "files": [{"path": "session.md", "must-exist": True, "frontmatter": {"status": {"required": True}}}],
        "consistency": [],
    }
    assert engine.run_all(config=config, project_dir=tmp_path, edit_log=[]) == []


# ── format_report ─────────────────────────────────────────────────────────


def test_format_report_groups_failures_by_label():
    failures = [
        engine.Failure("[files] sessions/x.md", "frontmatter.status: required field missing"),
        engine.Failure("[files] sessions/x.md", "frontmatter.followups: required field missing"),
        engine.Failure("[consistency: findings]", '"F1" found in x but missing in y'),
    ]
    out = engine.format_report(failures)
    # Header reports total
    assert "3 rule(s) failed" in out
    # Both labels appear, each with their failures grouped
    assert "[files] sessions/x.md" in out
    assert out.count("[files] sessions/x.md") == 1  # de-duplicated header
    assert "[consistency: findings]" in out
    # All three reasons appear
    assert "frontmatter.status" in out
    assert "frontmatter.followups" in out
    assert "F1" in out
    # Helper closing line
    assert "fix each item" in out.lower()


def test_format_report_empty_when_no_failures():
    assert engine.format_report([]) == ""


# ── tier: annotation ──────────────────────────────────────────────────────


def test_failure_default_tier_is_one():
    f = engine.Failure("[files] x.md", "reason")
    assert f.tier == 1


def test_file_rule_failure_carries_rule_tier(tmp_path):
    failures = engine.evaluate_file_rule(
        rule={"path": "sessions/missing.md", "must-exist": True, "tier": 2},
        project_dir=tmp_path,
        edit_log=[],
    )
    assert len(failures) == 1
    assert failures[0].tier == 2


def test_consistency_failure_carries_rule_tier(tmp_path):
    (tmp_path / "src.md").write_text("F1 appears here\n")
    (tmp_path / "target.md").write_text("nothing relevant\n")
    failures = engine.evaluate_consistency_rule(
        rule={
            "name": "x", "find": "F1", "in": "src.md",
            "must-also-appear-in": ["target.md"], "tier": 2,
        },
        project_dir=tmp_path,
    )
    assert len(failures) == 1
    assert failures[0].tier == 2


def test_format_advisory_renders_deferred_without_blocking_footer():
    failures = [engine.Failure("[files] x.md", "frontmatter.note missing", tier=2)]
    out = engine.format_advisory(failures)
    assert "deferred" in out.lower()
    assert "frontmatter.note missing" in out
    # Must NOT carry the blocking call-to-action — these don't block the session.
    assert "end the session again" not in out.lower()
