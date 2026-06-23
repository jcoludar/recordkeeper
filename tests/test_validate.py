import subprocess
import sys
from pathlib import Path

import pytest

from validate import validate_module, validate_index, ValidationError


def test_validate_module_ok(mini_masterbook):
    p = mini_masterbook / "tier-1" / "example.md"
    validate_module(p, masterbook_root=mini_masterbook, max_words=200)  # no exception


def test_validate_module_id_path_mismatch(tmp_path):
    p = tmp_path / "tier-1" / "wrong.md"
    p.parent.mkdir(parents=True)
    p.write_text("---\nid: tier-1/different\nname: x\ntier: 1\ndefault: true\nsummary: y\n---\nbody\n")
    with pytest.raises(ValidationError) as exc:
        validate_module(p, masterbook_root=tmp_path, max_words=200)
    assert "id" in str(exc.value)


def test_validate_module_too_long(tmp_path):
    p = tmp_path / "tier-1" / "long.md"
    p.parent.mkdir(parents=True)
    body = "word " * 1000
    p.write_text(f"---\nid: tier-1/long\nname: x\ntier: 1\ndefault: true\nsummary: y\n---\n{body}\n")
    with pytest.raises(ValidationError) as exc:
        validate_module(p, masterbook_root=tmp_path, max_words=200)
    assert "exceeds" in str(exc.value)


def test_validate_module_tier_requires_full_field_set(tmp_path):
    """tier-1/tier-2 modules must carry the full 8-field frontmatter convention."""
    from validate import REQUIRED_TIER_MODULE_FIELDS

    p = tmp_path / "tier-1" / "thin.md"
    p.parent.mkdir(parents=True)
    # 5 fields only — missing applies_when / conflicts_with / requires.
    p.write_text("---\nid: tier-1/thin\nname: x\ntier: 1\ndefault: true\nsummary: y\n---\nbody\n")
    with pytest.raises(ValidationError, match="missing required"):
        validate_module(
            p, masterbook_root=tmp_path, max_words=200,
            required_fields=REQUIRED_TIER_MODULE_FIELDS,
        )


def test_validate_module_substrate_five_fields_ok(tmp_path):
    """Substrate modules use a leaner 5-field schema (no applies_when/conflicts_with)."""
    p = tmp_path / "substrate" / "demo" / "module.md"
    p.parent.mkdir(parents=True)
    p.write_text(
        "---\nid: substrate/demo\nname: x\ntier: substrate\ndefault: false\nsummary: y\n---\nbody\n"
    )
    validate_module(p, masterbook_root=tmp_path, max_words=200)  # default 5-field set


def test_validate_index_accepts_fragment_links(mini_masterbook):
    """A `#fragment` in an INDEX link must not break module-reference matching."""
    idx = mini_masterbook / "INDEX.md"
    idx.write_text(
        "# INDEX\n\n"
        "- [tier-1/example](tier-1/example.md#overview)\n"
        "- [tier-2/optional](tier-2/optional.md)\n"
    )
    validate_index(mini_masterbook)  # no exception


def test_validate_index_ok(tmp_path, mini_masterbook):
    idx = mini_masterbook / "INDEX.md"
    idx.write_text(
        "# INDEX\n\n"
        "- [tier-1/example](tier-1/example.md)\n"
        "- [tier-2/optional](tier-2/optional.md)\n"
    )
    validate_index(mini_masterbook)


def test_validate_index_missing_reference(mini_masterbook):
    idx = mini_masterbook / "INDEX.md"
    idx.write_text("# INDEX\n\n- [tier-1/example](tier-1/example.md)\n")
    with pytest.raises(ValidationError) as exc:
        validate_index(mini_masterbook)
    assert "tier-2/optional" in str(exc.value)


def test_validate_index_orphan_reference(mini_masterbook):
    idx = mini_masterbook / "INDEX.md"
    idx.write_text(
        "# INDEX\n\n"
        "- [tier-1/example](tier-1/example.md)\n"
        "- [tier-2/optional](tier-2/optional.md)\n"
        "- [tier-1/ghost](tier-1/ghost.md)\n"
    )
    with pytest.raises(ValidationError) as exc:
        validate_index(mini_masterbook)
    assert "ghost" in str(exc.value)


from validate import validate_settings_fragments, validate_hooks, validate_commands


def test_validate_settings_fragments_ok(mini_masterbook):
    validate_settings_fragments(mini_masterbook)


def test_validate_settings_fragments_bad_json(mini_masterbook):
    bad = mini_masterbook / "settings-fragments" / "bad.json"
    bad.write_text("{not valid json")
    with pytest.raises(ValidationError):
        validate_settings_fragments(mini_masterbook)


def test_validate_hooks_ok(mini_masterbook):
    h = mini_masterbook / "hooks"
    h.mkdir(exist_ok=True)
    (h / "good.py").write_text("import sys\nsys.exit(0)\n")
    validate_hooks(mini_masterbook)


def test_validate_hooks_bad_syntax(mini_masterbook):
    h = mini_masterbook / "hooks"
    h.mkdir(exist_ok=True)
    (h / "bad.py").write_text("def broken(:\n")
    with pytest.raises(ValidationError):
        validate_hooks(mini_masterbook)


VALIDATE = Path(__file__).resolve().parent.parent / "tools" / "validate.py"


def test_validate_cli_runs_against_fixture(mini_masterbook):
    (mini_masterbook / "INDEX.md").write_text(
        "# INDEX\n\n"
        "- [tier-1/example](tier-1/example.md)\n"
        "- [tier-2/optional](tier-2/optional.md)\n"
    )
    result = subprocess.run(
        [sys.executable, str(VALIDATE), str(mini_masterbook)],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_validate_cli_fails_on_bad_module(mini_masterbook):
    bad = mini_masterbook / "tier-1" / "broken.md"
    bad.write_text("no frontmatter")
    (mini_masterbook / "INDEX.md").write_text(
        "# INDEX\n\n"
        "- [tier-1/example](tier-1/example.md)\n"
        "- [tier-1/broken](tier-1/broken.md)\n"
        "- [tier-2/optional](tier-2/optional.md)\n"
    )
    result = subprocess.run(
        [sys.executable, str(VALIDATE), str(mini_masterbook)],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "broken.md" in result.stderr or "broken.md" in result.stdout


def test_validate_cli_walks_substrate_modules(mini_masterbook):
    """validate.py walks masterbook/substrate/<name>/module.md too."""
    # Create a valid substrate
    sub = mini_masterbook / "substrate" / "demo-sub"
    sub.mkdir(parents=True)
    (sub / "module.md").write_text(
        "---\n"
        "id: substrate/demo-sub\n"
        "name: Demo Sub\n"
        "tier: substrate\n"
        "default: false\n"
        "summary: A demo substrate for tests\n"
        "---\n\n"
        "Body text here.\n"
    )
    # Index references only tier modules — validate_index doesn't check substrates.
    (mini_masterbook / "INDEX.md").write_text(
        "# INDEX\n\n"
        "- [tier-1/example](tier-1/example.md)\n"
        "- [tier-2/optional](tier-2/optional.md)\n"
    )
    result = subprocess.run(
        [sys.executable, str(VALIDATE), str(mini_masterbook)],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_validate_cli_fails_on_bad_substrate_module(mini_masterbook):
    """A substrate module with mismatched id fails validation."""
    sub = mini_masterbook / "substrate" / "bad-sub"
    sub.mkdir(parents=True)
    (sub / "module.md").write_text(
        "---\n"
        "id: substrate/different-name\n"
        "name: Bad Sub\n"
        "tier: substrate\n"
        "default: false\n"
        "summary: id mismatch on purpose\n"
        "---\n\n"
        "Body.\n"
    )
    (mini_masterbook / "INDEX.md").write_text(
        "# INDEX\n\n"
        "- [tier-1/example](tier-1/example.md)\n"
        "- [tier-2/optional](tier-2/optional.md)\n"
    )
    result = subprocess.run(
        [sys.executable, str(VALIDATE), str(mini_masterbook)],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "bad-sub" in (result.stderr + result.stdout)


def test_validate_hooks_walks_substrate(mini_masterbook):
    """validate_hooks AST-parses substrate/*/hooks/*.py too."""
    sub_hooks = mini_masterbook / "substrate" / "demo-sub" / "hooks"
    sub_hooks.mkdir(parents=True)
    (sub_hooks / "bad.py").write_text("def broken(:\n")
    with pytest.raises(ValidationError):
        validate_hooks(mini_masterbook)


def test_validate_hooks_substrate_ok(mini_masterbook):
    """A syntactically valid substrate hook passes."""
    sub_hooks = mini_masterbook / "substrate" / "demo-sub" / "hooks"
    sub_hooks.mkdir(parents=True)
    (sub_hooks / "good.py").write_text("print('hi')\n")
    validate_hooks(mini_masterbook)  # no exception


def test_validate_settings_fragments_walks_substrate(mini_masterbook):
    """JSON parse errors in substrate/<name>/settings-fragment.json are caught."""
    sub = mini_masterbook / "substrate" / "demo-sub"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "settings-fragment.json").write_text("{not valid json")
    with pytest.raises(ValidationError):
        validate_settings_fragments(mini_masterbook)


def test_validate_settings_fragments_substrate_ok(mini_masterbook):
    """A valid substrate fragment passes."""
    sub = mini_masterbook / "substrate" / "demo-sub"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "settings-fragment.json").write_text('{"hooks": {}}')
    validate_settings_fragments(mini_masterbook)  # no exception


def test_validate_commands_ok(mini_masterbook):
    """A well-formed top-level command + a well-formed substrate command both pass."""
    # Top-level: mini_masterbook/commands/rebuild.md already exists from the fixture.
    # Add a substrate command.
    sub_cmds = mini_masterbook / "substrate" / "demo-paper" / "commands"
    sub_cmds.mkdir(parents=True)
    (sub_cmds / "debrief.md").write_text(
        "---\ndescription: end-of-session checklist\n---\n\n# /debrief\n\nBody.\n"
    )
    validate_commands(mini_masterbook)  # no exception


def test_validate_commands_missing_description(mini_masterbook):
    """A command file without `description:` frontmatter fails."""
    sub_cmds = mini_masterbook / "substrate" / "demo-paper" / "commands"
    sub_cmds.mkdir(parents=True)
    (sub_cmds / "bad.md").write_text(
        "---\nname: bad\n---\n\nBody.\n"
    )
    with pytest.raises(ValidationError, match="description"):
        validate_commands(mini_masterbook)


def test_validate_commands_empty_body(mini_masterbook):
    """A command file with empty body fails."""
    sub_cmds = mini_masterbook / "substrate" / "demo-paper" / "commands"
    sub_cmds.mkdir(parents=True)
    (sub_cmds / "empty.md").write_text(
        "---\ndescription: a thing\n---\n\n"
    )
    with pytest.raises(ValidationError, match="empty body"):
        validate_commands(mini_masterbook)


def test_validate_commands_bad_filename(mini_masterbook):
    """A command file with invalid filename pattern fails."""
    sub_cmds = mini_masterbook / "substrate" / "demo-paper" / "commands"
    sub_cmds.mkdir(parents=True)
    (sub_cmds / "Bad_Filename.md").write_text(
        "---\ndescription: x\n---\n\nBody.\n"
    )
    with pytest.raises(ValidationError, match="filename"):
        validate_commands(mini_masterbook)


def test_validate_commands_description_exactly_100_chars(mini_masterbook):
    """A description with exactly 100 chars is accepted (boundary inclusive)."""
    cmd = mini_masterbook / "commands" / "boundary.md"
    cmd.write_text(f"---\ndescription: {'a' * 100}\n---\n\nBody.\n")
    validate_commands(mini_masterbook)  # no exception


def test_validate_commands_description_101_chars_fails(mini_masterbook):
    """A description with 101 chars is rejected."""
    cmd = mini_masterbook / "commands" / "toolong.md"
    cmd.write_text(f"---\ndescription: {'a' * 101}\n---\n\nBody.\n")
    with pytest.raises(ValidationError, match="100 chars"):
        validate_commands(mini_masterbook)


def _write_budget_version(root, *, per_module, per_substrate):
    (root / "VERSION").write_text(
        "---\nversion: 0.0.0\nlength_budget:\n"
        f"  global_words: 4000\n  per_module_words: {per_module}\n"
        f"  per_substrate_module_words: {per_substrate}\n---\n"
    )


def _write_index_tier_only(root):
    (root / "INDEX.md").write_text(
        "# INDEX\n\n"
        "- [tier-1/example](tier-1/example.md)\n"
        "- [tier-2/optional](tier-2/optional.md)\n"
    )


def test_validate_cli_substrate_module_gets_higher_budget(mini_masterbook):
    """A substrate module.md over the tier per_module_words but under
    per_substrate_module_words passes — substrate docs get the looser budget."""
    _write_budget_version(mini_masterbook, per_module=50, per_substrate=200)
    sub = mini_masterbook / "substrate" / "wordy"
    sub.mkdir(parents=True)
    body = "word " * 120  # > tier per_module (50), < per_substrate (200)
    (sub / "module.md").write_text(
        "---\nid: substrate/wordy\nname: Wordy\ntier: substrate\ndefault: false\n"
        "summary: a wordy substrate\n---\n\n" + body + "\n"
    )
    _write_index_tier_only(mini_masterbook)
    result = subprocess.run(
        [sys.executable, str(VALIDATE), str(mini_masterbook)],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_validate_cli_substrate_module_over_substrate_budget_fails(mini_masterbook):
    """A substrate module.md above per_substrate_module_words still fails."""
    _write_budget_version(mini_masterbook, per_module=50, per_substrate=200)
    sub = mini_masterbook / "substrate" / "toolong"
    sub.mkdir(parents=True)
    body = "word " * 250  # > per_substrate (200)
    (sub / "module.md").write_text(
        "---\nid: substrate/toolong\nname: Too Long\ntier: substrate\ndefault: false\n"
        "summary: an over-budget substrate\n---\n\n" + body + "\n"
    )
    _write_index_tier_only(mini_masterbook)
    result = subprocess.run(
        [sys.executable, str(VALIDATE), str(mini_masterbook)],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "exceeds" in (result.stderr + result.stdout)
