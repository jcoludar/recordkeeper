"""Sanity checks for the cross-repo-orientation substrate's files."""
import json
import sys
from pathlib import Path

MASTERBOOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MASTERBOOK / "tools"))
from assemble import parse_frontmatter  # noqa: E402

SUBSTRATE = MASTERBOOK / "substrate" / "cross-repo-orientation"


def test_module_md_frontmatter_complete():
    text = (SUBSTRATE / "module.md").read_text()
    fm, _ = parse_frontmatter(text)
    for key in ("id", "name", "tier", "default", "applies_when", "conflicts_with", "requires", "summary"):
        assert key in fm, f"missing key: {key}"
    assert fm["id"] == "substrate/cross-repo-orientation"
    assert fm["requires"] == []


def test_settings_fragment_is_valid_json():
    text = (SUBSTRATE / "settings-fragment.json").read_text()
    data = json.loads(text)
    assert "hooks" in data
    assert data["hooks"]["SessionStart"][0]["matcher"] == "startup"
    cmd = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "/usr/bin/env" not in cmd, "should be bare $CLAUDE_PROJECT_DIR/..."
    assert cmd.startswith("$CLAUDE_PROJECT_DIR/")


def test_commands_have_required_frontmatter():
    for name in ("begin-session.md", "debrief.md"):
        text = (SUBSTRATE / "commands" / name).read_text()
        fm, body = parse_frontmatter(text)
        assert "description" in fm
        assert fm["description"].startswith("Use when "), \
            f"{name} description must start with 'Use when '"
        assert body.strip(), f"{name} has empty body"


def test_hooks_executable_and_have_shebang():
    import os
    for name in ("session_start_orient.py", "session_stop_log_timing.py", "discover_repos.py"):
        path = SUBSTRATE / "hooks" / name
        assert path.exists(), f"missing hook: {name}"
        first_line = path.read_text().splitlines()[0]
        assert first_line == "#!/usr/bin/env python3", \
            f"{name} missing shebang"
        assert os.access(path, os.X_OK), f"{name} not executable"


def test_claude_md_template_present():
    template = SUBSTRATE / "CLAUDE.md.template"
    assert template.exists()
    text = template.read_text()
    assert "example-tool dev workspace" in text
    assert "Cross-repo data contract" in text


def test_debrief_snippet_present():
    snippet = SUBSTRATE / "debrief_repo_state_section.md"
    assert snippet.exists()
    assert "Repo state at close" in snippet.read_text()


def test_vendored_stop_hook_matches_source():
    """session_stop_log_timing.py is vendored from session-paperwork; only docstring may differ."""
    source = MASTERBOOK / "substrate" / "session-paperwork" / "hooks" / "session_stop_log_timing.py"
    vendored = SUBSTRATE / "hooks" / "session_stop_log_timing.py"
    src_lines = source.read_text().splitlines()
    ven_lines = vendored.read_text().splitlines()

    def strip_docstring(lines: list[str]) -> list[str]:
        if not lines or not lines[0].startswith("#!"):
            return lines
        try:
            start = next(i for i, l in enumerate(lines) if l.strip().startswith('"""'))
        except StopIteration:
            return lines
        try:
            end = next(i for i, l in enumerate(lines[start + 1:], start + 1)
                       if l.strip().endswith('"""'))
        except StopIteration:
            return lines
        return lines[: start] + lines[end + 1:]

    assert strip_docstring(src_lines) == strip_docstring(ven_lines), (
        "Vendored copy has drifted from source outside the docstring. "
        "If the source was intentionally updated, port the change here and "
        "update both docstrings."
    )
