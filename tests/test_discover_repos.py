"""Tests for discover_repos.py — locates the two example-tool clones on disk."""
import json
import subprocess
import sys
from pathlib import Path

HOOK = (
    Path(__file__).resolve().parent.parent
    / "substrate"
    / "cross-repo-orientation"
    / "hooks"
    / "discover_repos.py"
)

sys.path.insert(0, str(HOOK.parent))
import discover_repos


def _init_git_repo(path: Path, origin_url: str) -> None:
    """Create a bare-ish git repo at `path` with `origin` pointing at `origin_url`."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", origin_url], check=True
    )


def test_validate_repo_path_accepts_matching_origin(tmp_path):
    repo = tmp_path / "example-tool"
    _init_git_repo(repo, "https://github.com/collaborator/example-tool.git")
    assert discover_repos.validate_repo_path(repo, "collaborator/example-tool") is True


def test_validate_repo_path_accepts_origin_without_dot_git(tmp_path):
    repo = tmp_path / "example-tool"
    _init_git_repo(repo, "https://github.com/collaborator/example-tool")
    assert discover_repos.validate_repo_path(repo, "collaborator/example-tool") is True


def test_validate_repo_path_accepts_ssh_origin(tmp_path):
    repo = tmp_path / "example-tool"
    _init_git_repo(repo, "git@github.com:collaborator/example-tool.git")
    assert discover_repos.validate_repo_path(repo, "collaborator/example-tool") is True


def test_validate_repo_path_rejects_wrong_origin(tmp_path):
    repo = tmp_path / "example-tool"
    _init_git_repo(repo, "https://github.com/other/example-tool.git")
    assert discover_repos.validate_repo_path(repo, "collaborator/example-tool") is False


def test_validate_repo_path_rejects_non_git_dir(tmp_path):
    repo = tmp_path / "not-a-repo"
    repo.mkdir()
    assert discover_repos.validate_repo_path(repo, "collaborator/example-tool") is False


def test_validate_repo_path_rejects_missing_dir(tmp_path):
    assert discover_repos.validate_repo_path(tmp_path / "nope", "collaborator/example-tool") is False


def test_validate_repo_path_rejects_non_github_host(tmp_path):
    """Regression: https://notgithub.com/... must not falsely match github.com."""
    repo = tmp_path / "example-tool"
    _init_git_repo(repo, "https://notgithub.com/collaborator/example-tool.git")
    assert discover_repos.validate_repo_path(repo, "collaborator/example-tool") is False


def test_validate_repo_path_rejects_gitlab_host(tmp_path):
    """Wrong host (gitlab.com instead of github.com) is rejected."""
    repo = tmp_path / "example-tool"
    _init_git_repo(repo, "https://gitlab.com/collaborator/example-tool.git")
    assert discover_repos.validate_repo_path(repo, "collaborator/example-tool") is False


def test_find_candidates_locates_repo_in_search_root(tmp_path):
    """find_candidates finds a matching repo in one of the given search roots."""
    search_root = tmp_path / "code"
    repo = search_root / "example-tool"
    _init_git_repo(repo, "https://github.com/collaborator/example-tool.git")
    candidates = discover_repos.find_candidates(
        expected_slug="collaborator/example-tool", search_roots=[search_root], max_depth=2
    )
    assert repo in candidates


def test_find_candidates_finds_nested_repo(tmp_path):
    """find_candidates searches up to max_depth nested directories."""
    repo = tmp_path / "a" / "b" / "example-tool"
    _init_git_repo(repo, "https://github.com/collaborator/example-tool.git")
    candidates = discover_repos.find_candidates(
        expected_slug="collaborator/example-tool", search_roots=[tmp_path], max_depth=3
    )
    assert repo in candidates


def test_find_candidates_skips_wrong_origin(tmp_path):
    """find_candidates excludes repos with a different origin."""
    repo = tmp_path / "example-tool"
    _init_git_repo(repo, "https://github.com/other/example-tool.git")
    candidates = discover_repos.find_candidates(
        expected_slug="collaborator/example-tool", search_roots=[tmp_path], max_depth=2
    )
    assert candidates == []


def test_find_candidates_ignores_missing_search_root(tmp_path):
    """find_candidates ignores non-existent search roots without erroring."""
    candidates = discover_repos.find_candidates(
        expected_slug="collaborator/example-tool",
        search_roots=[tmp_path / "missing"],
        max_depth=2,
    )
    assert candidates == []


def test_find_candidates_skips_symlinks(tmp_path):
    """find_candidates does not follow symlinks (macOS home dirs have recursive links)."""
    real_repo = tmp_path / "real" / "example-tool"
    _init_git_repo(real_repo, "https://github.com/collaborator/example-tool.git")
    link_root = tmp_path / "linkroot"
    link_root.mkdir()
    (link_root / "example-tool").symlink_to(real_repo)
    candidates = discover_repos.find_candidates(
        expected_slug="collaborator/example-tool", search_roots=[link_root], max_depth=2
    )
    assert candidates == []


def test_find_candidates_skips_noise_dirs(tmp_path):
    """find_candidates skips node_modules / __pycache__ / .git etc."""
    repo = tmp_path / "node_modules" / "example-tool"
    _init_git_repo(repo, "https://github.com/collaborator/example-tool.git")
    candidates = discover_repos.find_candidates(
        expected_slug="collaborator/example-tool", search_roots=[tmp_path], max_depth=3
    )
    assert candidates == []


def test_write_paths_config_creates_file(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    paths = {
        "example-tool": tmp_path / "example-tool",
        "example-tool_web": tmp_path / "example-tool_web",
    }
    discover_repos.write_paths_config(workspace, paths)
    config_file = workspace / ".example-tool-paths.json"
    assert config_file.exists()
    data = json.loads(config_file.read_text())
    assert data["example-tool"] == str(tmp_path / "example-tool")
    assert data["example-tool_web"] == str(tmp_path / "example-tool_web")
    assert "discovered_at" in data


def test_read_paths_config_returns_dict(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".example-tool-paths.json").write_text(json.dumps({
        "example-tool": "/path/to/example-tool",
        "example-tool_web": "/path/to/example-tool_web",
        "discovered_at": "2026-05-27T10:00:00+02:00",
    }))
    data = discover_repos.read_paths_config(workspace)
    assert data["example-tool"] == "/path/to/example-tool"


def test_read_paths_config_missing_returns_none(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    assert discover_repos.read_paths_config(workspace) is None


import os


def _run_cli(args: list[str], cwd: Path, stdin_text: str = "") -> subprocess.CompletedProcess:
    env = os.environ.copy()
    return subprocess.run(
        ["/usr/bin/env", "python3", str(HOOK), *args],
        cwd=str(cwd),
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_writes_config_on_unique_auto_resolve(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    repo1 = tmp_path / "code" / "example-tool"
    repo2 = tmp_path / "code" / "example-tool_web"
    _init_git_repo(repo1, "https://github.com/collaborator/example-tool.git")
    _init_git_repo(repo2, "https://github.com/collaborator/example-tool_web.git")
    r = _run_cli(
        ["--workspace", str(workspace), "--search-root", str(tmp_path / "code")],
        cwd=tmp_path,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads((workspace / ".example-tool-paths.json").read_text())
    assert data["example-tool"] == str(repo1.resolve())
    assert data["example-tool_web"] == str(repo2.resolve())


def test_cli_errors_on_ambiguous_without_interactive(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    repo1a = tmp_path / "a" / "example-tool"
    repo1b = tmp_path / "b" / "example-tool"
    repo2 = tmp_path / "a" / "example-tool_web"
    _init_git_repo(repo1a, "https://github.com/collaborator/example-tool.git")
    _init_git_repo(repo1b, "https://github.com/collaborator/example-tool.git")
    _init_git_repo(repo2, "https://github.com/collaborator/example-tool_web.git")
    r = _run_cli(
        ["--workspace", str(workspace),
         "--search-root", str(tmp_path / "a"),
         "--search-root", str(tmp_path / "b")],
        cwd=tmp_path,
    )
    assert r.returncode != 0
    assert "ambiguous" in r.stderr.lower() or "multiple" in r.stderr.lower()


def test_cli_interactive_accepts_first_candidate(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    repo1a = tmp_path / "a" / "example-tool"
    repo1b = tmp_path / "b" / "example-tool"
    repo2 = tmp_path / "a" / "example-tool_web"
    _init_git_repo(repo1a, "https://github.com/collaborator/example-tool.git")
    _init_git_repo(repo1b, "https://github.com/collaborator/example-tool.git")
    _init_git_repo(repo2, "https://github.com/collaborator/example-tool_web.git")
    r = _run_cli(
        ["--workspace", str(workspace), "--interactive",
         "--search-root", str(tmp_path / "a"),
         "--search-root", str(tmp_path / "b")],
        cwd=tmp_path,
        stdin_text="1\n1\n",
    )
    assert r.returncode == 0, r.stderr
    data = json.loads((workspace / ".example-tool-paths.json").read_text())
    assert Path(data["example-tool"]).name == "example-tool"


def test_cli_skips_when_config_already_exists(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    existing = workspace / ".example-tool-paths.json"
    existing.write_text(json.dumps({
        "example-tool": str(tmp_path / "p"),
        "example-tool_web": str(tmp_path / "pw"),
        "discovered_at": "2026-05-27T10:00:00+02:00",
    }))
    r = _run_cli(
        ["--workspace", str(workspace), "--search-root", str(tmp_path)],
        cwd=tmp_path,
    )
    assert r.returncode == 0
    assert "already exists" in r.stderr.lower() or "exists" in r.stderr.lower()
