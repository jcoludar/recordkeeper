"""Tests for assemble_kit.py — substrate → share/example-tool-dev-kit/ assembler."""
import json
import os
import subprocess
import sys
from pathlib import Path

MASTERBOOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MASTERBOOK / "tools"))
import assemble_kit  # noqa: E402

REPO_ROOT = MASTERBOOK.parent
SUBSTRATE = MASTERBOOK / "substrate" / "cross-repo-orientation"


def test_copies_commands(tmp_path):
    target = tmp_path / "kit"
    assemble_kit.assemble(SUBSTRATE, target)
    for name in ("begin-session.md", "debrief.md"):
        assert (target / ".claude" / "commands" / name).exists()


def test_copies_hooks_with_exec_bit(tmp_path):
    target = tmp_path / "kit"
    assemble_kit.assemble(SUBSTRATE, target)
    for name in ("session_start_orient.py", "session_stop_log_timing.py", "discover_repos.py"):
        hook = target / ".claude" / "hooks" / name
        assert hook.exists()
        assert os.access(hook, os.X_OK), f"{name} not executable in kit"


def test_writes_settings_json_from_fragment(tmp_path):
    target = tmp_path / "kit"
    assemble_kit.assemble(SUBSTRATE, target)
    settings = json.loads((target / ".claude" / "settings.json").read_text())
    assert settings["hooks"]["SessionStart"][0]["matcher"] == "startup"


def test_copies_claude_md_from_template(tmp_path):
    target = tmp_path / "kit"
    assemble_kit.assemble(SUBSTRATE, target)
    text = (target / "CLAUDE.md").read_text()
    assert "example-tool dev workspace" in text


def test_overwrite_does_not_wipe_unknown_files(tmp_path):
    target = tmp_path / "kit"
    target.mkdir()
    (target / ".claude").mkdir()
    custom = target / ".claude" / "user-custom-file.md"
    custom.write_text("user content")
    assemble_kit.assemble(SUBSTRATE, target)
    assert custom.exists(), "user file was wiped"
    assert custom.read_text() == "user content"


def test_idempotent(tmp_path):
    target = tmp_path / "kit"
    assemble_kit.assemble(SUBSTRATE, target)
    text1 = (target / ".claude" / "commands" / "begin-session.md").read_text()
    assemble_kit.assemble(SUBSTRATE, target)
    text2 = (target / ".claude" / "commands" / "begin-session.md").read_text()
    assert text1 == text2


def test_copies_install_sh_executable(tmp_path):
    target = tmp_path / "kit"
    assemble_kit.assemble(SUBSTRATE, target)
    install = target / "install.sh"
    assert install.exists()
    assert os.access(install, os.X_OK)
    r = subprocess.run(["bash", "-n", str(install)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_install_sh_against_tmpdir(tmp_path):
    """Smoke-test the installer end-to-end with synthetic example-tool clones."""
    kit = tmp_path / "kit"
    assemble_kit.assemble(SUBSTRATE, kit)
    # Re-run to materialize install.sh from the substrate template.
    assemble_kit.assemble(SUBSTRATE, kit)

    clones = tmp_path / "clones"
    for name, slug in (
        ("example-tool", "collaborator/example-tool"),
        ("example-tool_web", "collaborator/example-tool_web"),
    ):
        path = clones / name
        path.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(path)], check=True)
        subprocess.run(
            ["git", "-C", str(path), "remote", "add", "origin", f"https://github.com/{slug}.git"],
            check=True,
        )

    workspace = tmp_path / "ws"
    workspace.mkdir()
    paths_config = {
        "example-tool": str((clones / "example-tool").resolve()),
        "example-tool_web": str((clones / "example-tool_web").resolve()),
        "discovered_at": "2026-05-27T10:00:00+02:00",
    }
    (workspace / ".example-tool-paths.json").write_text(json.dumps(paths_config))

    env = os.environ.copy()
    r = subprocess.run(
        ["bash", str(kit / "install.sh"), str(workspace)],
        input="n\n",
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0, f"stderr:\n{r.stderr}\nstdout:\n{r.stdout}"

    assert (workspace / ".claude" / "settings.json").is_file()
    assert (workspace / ".claude" / "hooks" / "session_start_orient.py").is_file()
    assert os.access(workspace / ".claude" / "hooks" / "session_start_orient.py", os.X_OK)
    assert (workspace / "CLAUDE.md").is_file()
    assert (workspace / "sessions" / "README.md").is_file()

    (workspace / "CLAUDE.md").write_text("# example-user custom note")
    r2 = subprocess.run(
        ["bash", str(kit / "install.sh"), str(workspace)],
        input="n\n",
        capture_output=True,
        text=True,
        env=env,
    )
    assert r2.returncode == 0
    assert (workspace / "CLAUDE.md").read_text() == "# example-user custom note"
