# tests/test_plugin_schema_valid.py
"""Guard the plugin/marketplace manifests against Claude Code's real schema.

Our unit tests only assert field *presence*; they cannot catch schema-shape
bugs (e.g. `repository` must be a string, the marketplace needs a `name` and no
numeric `version`). Those only surface when Claude Code actually loads the
plugin. `claude plugin validate` runs that same schema check offline, so we
wire it in as a regression guard. Skipped where the `claude` CLI is unavailable
(e.g. CI without Claude Code installed).
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = shutil.which("claude")
requires_claude = pytest.mark.skipif(CLAUDE is None, reason="claude CLI not on PATH")


@requires_claude
def test_marketplace_manifest_validates():
    proc = subprocess.run(
        [CLAUDE, "plugin", "validate", str(ROOT)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@requires_claude
def test_plugin_manifest_validates(tmp_path):
    # The repo-root validate only checks the marketplace (both manifests live in
    # .claude-plugin/), so validate the plugin manifest in isolation to catch
    # plugin-shape regressions like a non-string `repository`.
    pdir = tmp_path / ".claude-plugin"
    pdir.mkdir()
    shutil.copy(ROOT / ".claude-plugin" / "plugin.json", pdir / "plugin.json")
    proc = subprocess.run(
        [CLAUDE, "plugin", "validate", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
