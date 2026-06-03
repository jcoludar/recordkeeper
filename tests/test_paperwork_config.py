"""Tests for _paperwork_config."""
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

import _paperwork_config as cfg  # noqa: E402


# ── tier: annotation ──────────────────────────────────────────────────────


def test_file_rule_tier_2_accepted(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text("files:\n  - path: 'a.md'\n    must-exist: true\n    tier: 2\n")
    result = cfg.load_and_validate(path)
    assert result["files"][0]["tier"] == 2


def test_consistency_rule_tier_2_accepted(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text(
        "consistency:\n  - name: x\n    find: 'foo'\n    in: a.md\n"
        "    must-also-appear-in: [b.md]\n    tier: 2\n"
    )
    result = cfg.load_and_validate(path)
    assert result["consistency"][0]["tier"] == 2


def test_tier_value_out_of_range_rejected(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text("files:\n  - path: 'a.md'\n    must-exist: true\n    tier: 3\n")
    with pytest.raises(cfg.ConfigError, match="tier"):
        cfg.load_and_validate(path)


# ── consistency find: regex validated at load ─────────────────────────────


def test_consistency_invalid_regex_rejected_at_load(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text(
        "consistency:\n  - name: x\n    find: '[unclosed'\n    in: a.md\n"
        "    must-also-appear-in: [b.md]\n"
    )
    with pytest.raises(cfg.ConfigError, match="find"):
        cfg.load_and_validate(path)


def test_consistency_multigroup_regex_rejected_at_load(tmp_path):
    """re.findall returns tuples for >1 capturing group, which the engine's
    `capture in text` check cannot handle — reject at load, not at Stop time."""
    path = tmp_path / "paperwork.yaml"
    path.write_text(
        "consistency:\n  - name: x\n    find: '(a)(b)'\n    in: a.md\n"
        "    must-also-appear-in: [b.md]\n"
    )
    with pytest.raises(cfg.ConfigError, match="group"):
        cfg.load_and_validate(path)


def test_consistency_single_group_regex_ok(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text(
        "consistency:\n  - name: x\n    find: 'F(\\d+)'\n    in: a.md\n"
        "    must-also-appear-in: [b.md]\n"
    )
    result = cfg.load_and_validate(path)
    assert result["consistency"][0]["find"] == "F(\\d+)"


# ── load_and_validate ─────────────────────────────────────────────────────


def test_load_minimal_config(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text("files: []\n")
    result = cfg.load_and_validate(path)
    assert result["files"] == []
    assert result["consistency"] == []
    assert result["session-log-dir"] == "sessions"


def test_load_full_config(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text(
        "session-log-dir: docs/sessions\n"
        "files:\n"
        "  - path: 'sessions/{today}-*.md'\n"
        "    must-exist: true\n"
        "    must-be-modified-this-session: true\n"
        "    frontmatter:\n"
        "      status: {required: true, in: [done, paused]}\n"
        "    when:\n"
        "      when-files-modified-matching: 'src/**'\n"
        "consistency:\n"
        "  - name: every-finding-tracked\n"
        "    find: 'F\\d+'\n"
        "    in: 'sessions/{today}-*.md'\n"
        "    must-also-appear-in: ['TECHNICAL_DEBT.md']\n"
    )
    result = cfg.load_and_validate(path)
    assert result["session-log-dir"] == "docs/sessions"
    assert len(result["files"]) == 1
    assert result["files"][0]["must-exist"] is True
    assert result["consistency"][0]["name"] == "every-finding-tracked"


def test_missing_config_file_raises(tmp_path):
    with pytest.raises(cfg.ConfigError) as exc_info:
        cfg.load_and_validate(tmp_path / "missing.yaml")
    assert "does not exist" in str(exc_info.value).lower()


def test_malformed_yaml_raises_with_line_hint(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text("files: [\n  - path: 'unclosed\n")
    with pytest.raises(cfg.ConfigError) as exc_info:
        cfg.load_and_validate(path)
    msg = str(exc_info.value).lower()
    assert "yaml" in msg or "parse" in msg
    assert "line" in msg


def test_unknown_top_level_key_did_you_mean(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text("fles: []\n")  # typo: fles instead of files
    with pytest.raises(cfg.ConfigError) as exc_info:
        cfg.load_and_validate(path)
    msg = str(exc_info.value)
    assert "unknown key" in msg.lower()
    assert "fles" in msg
    assert "files" in msg  # did-you-mean suggestion


def test_unknown_file_entry_key_did_you_mean(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text(
        "files:\n  - path: x\n    must-exsit: true\n"  # typo: must-exsit
    )
    with pytest.raises(cfg.ConfigError) as exc_info:
        cfg.load_and_validate(path)
    msg = str(exc_info.value)
    assert "must-exsit" in msg
    assert "must-exist" in msg


def test_file_entry_missing_path_raises(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text("files:\n  - must-exist: true\n")
    with pytest.raises(cfg.ConfigError) as exc_info:
        cfg.load_and_validate(path)
    assert "path" in str(exc_info.value).lower()
    assert "required" in str(exc_info.value).lower()


def test_consistency_entry_missing_name_raises(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text(
        "consistency:\n"
        "  - find: 'F\\d+'\n"
        "    in: 'x.md'\n"
        "    must-also-appear-in: ['y.md']\n"
    )
    with pytest.raises(cfg.ConfigError) as exc_info:
        cfg.load_and_validate(path)
    assert "name" in str(exc_info.value).lower()


def test_consistency_entry_missing_find_raises(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text(
        "consistency:\n"
        "  - name: x\n"
        "    in: 'x.md'\n"
        "    must-also-appear-in: ['y.md']\n"
    )
    with pytest.raises(cfg.ConfigError):
        cfg.load_and_validate(path)


def test_frontmatter_field_unknown_key_did_you_mean(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text(
        "files:\n"
        "  - path: x\n"
        "    frontmatter:\n"
        "      status: {requird: true}\n"  # typo
    )
    with pytest.raises(cfg.ConfigError) as exc_info:
        cfg.load_and_validate(path)
    msg = str(exc_info.value)
    assert "requird" in msg
    assert "required" in msg


def test_when_unknown_key_did_you_mean(tmp_path):
    path = tmp_path / "paperwork.yaml"
    path.write_text(
        "files:\n"
        "  - path: x\n"
        "    when:\n"
        "      when-files-modifed-matching: 'src/**'\n"  # typo: modifed
    )
    with pytest.raises(cfg.ConfigError) as exc_info:
        cfg.load_and_validate(path)
    msg = str(exc_info.value)
    assert "when-files-modifed-matching" in msg
    assert "when-files-modified-matching" in msg


def test_validate_config_cli_returns_zero_on_valid(tmp_path, capsys):
    path = tmp_path / "paperwork.yaml"
    path.write_text("files: []\n")
    assert cfg.validate_config_cli(path) == 0


def test_validate_config_cli_returns_two_on_invalid(tmp_path, capsys):
    path = tmp_path / "paperwork.yaml"
    path.write_text("fles: []\n")
    assert cfg.validate_config_cli(path) == 2
    captured = capsys.readouterr()
    assert "unknown key" in captured.err.lower()


def test_files_or_consistency_absent_is_legal(tmp_path):
    """Empty config is legal (substrate becomes a no-op for the project)."""
    path = tmp_path / "paperwork.yaml"
    path.write_text("session-log-dir: sessions\n")
    result = cfg.load_and_validate(path)
    assert result["files"] == []
    assert result["consistency"] == []
