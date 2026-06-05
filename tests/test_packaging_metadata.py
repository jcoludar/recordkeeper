# tests/test_packaging_metadata.py
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _declared_version() -> str:
    """The `version:` field from the YAML-frontmatter VERSION file.

    VERSION is a structured doc (it also carries the assembler's length_budget),
    so we read the version field rather than the whole file.
    """
    text = (ROOT / "VERSION").read_text()
    match = re.search(r"^version:\s*(\S+)", text, re.MULTILINE)
    assert match, "VERSION must declare a `version:` field"
    return match.group(1)


def test_version_matches_manifest():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["version"] == _declared_version()


def test_readme_has_plugin_install_commands():
    readme = (ROOT / "README.md").read_text()
    assert "/plugin marketplace add" in readme
    assert "/plugin install recordkeeper" in readme
