"""Tests for the store-write-approval substrate hooks."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

MASTERBOOK = Path(__file__).resolve().parent.parent
HOOK = MASTERBOOK / "substrate" / "store-write-approval" / "hooks" / "pre_store_write_protection.py"


def _run_hook(stdin_json: dict, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run the hook as a subprocess with the given stdin JSON. Return the completed process."""
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(stdin_json),
        capture_output=True,
        text=True,
        env=env or {},
        timeout=5,
    )


def test_write_to_protected_path_blocked_without_sentinel(tmp_path):
    """A Write to a protected path without a sentinel file should be blocked (exit 2)."""
    protected = tmp_path / "protected" / "data.csv"
    protected.parent.mkdir(parents=True)
    protected.write_text("existing\n")

    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(protected), "content": "new"},
    }
    env = {
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "STORE_WRITE_PROTECTED_PATHS": str(protected.parent),
        "PATH": os.environ.get("PATH", ""),
    }
    result = _run_hook(payload, env=env)
    assert result.returncode == 2, f"Expected exit 2, got {result.returncode}; stderr: {result.stderr}"


def test_write_to_protected_path_allowed_with_fresh_sentinel(tmp_path):
    """A Write to a protected path with a fresh sentinel should pass (exit 0)."""
    protected = tmp_path / "protected" / "data.csv"
    protected.parent.mkdir(parents=True)
    protected.write_text("existing\n")
    sentinel = tmp_path / ".store_write_approved"
    sentinel.write_text("")  # fresh: mtime = now

    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(protected), "content": "new"},
    }
    env = {
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "STORE_WRITE_PROTECTED_PATHS": str(protected.parent),
        "PATH": os.environ.get("PATH", ""),
    }
    result = _run_hook(payload, env=env)
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}; stderr: {result.stderr}"


def test_write_to_unprotected_path_always_allowed(tmp_path):
    """A Write to an unprotected path should pass even without sentinel."""
    other = tmp_path / "other" / "file.txt"
    other.parent.mkdir(parents=True)

    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(other), "content": "new"},
    }
    env = {
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "STORE_WRITE_PROTECTED_PATHS": str(tmp_path / "protected"),
        "PATH": os.environ.get("PATH", ""),
    }
    result = _run_hook(payload, env=env)
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}; stderr: {result.stderr}"


def test_expired_sentinel_blocks_write(tmp_path):
    """A sentinel older than the TTL should not authorize writes."""
    protected = tmp_path / "protected" / "data.csv"
    protected.parent.mkdir(parents=True)
    sentinel = tmp_path / ".store_write_approved"
    sentinel.write_text("")
    # Set mtime to 2 hours ago — older than 60-minute default TTL.
    old_time = time.time() - 7200
    os.utime(sentinel, (old_time, old_time))

    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(protected), "content": "new"},
    }
    env = {
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "STORE_WRITE_PROTECTED_PATHS": str(protected.parent),
        "PATH": os.environ.get("PATH", ""),
    }
    result = _run_hook(payload, env=env)
    assert result.returncode == 2, f"Expected exit 2 (expired), got {result.returncode}; stderr: {result.stderr}"


def test_non_write_tool_passes_through(tmp_path):
    """A tool that isn't Edit/Write should not be subject to the gate."""
    payload = {
        "tool_name": "Read",
        "tool_input": {"file_path": str(tmp_path / "anything")},
    }
    env = {
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "STORE_WRITE_PROTECTED_PATHS": str(tmp_path / "protected"),
        "PATH": os.environ.get("PATH", ""),
    }
    result = _run_hook(payload, env=env)
    assert result.returncode == 0


SELF_TOUCH_HOOK = MASTERBOOK / "substrate" / "store-write-approval" / "hooks" / "pre_sentinel_no_self_touch.py"


def _run_self_touch_hook(stdin_json: dict, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SELF_TOUCH_HOOK)],
        input=json.dumps(stdin_json),
        capture_output=True,
        text=True,
        env=env or {},
        timeout=5,
    )


def test_bash_touching_sentinel_is_blocked(tmp_path):
    """The agent must not be able to `touch` the sentinel file via Bash."""
    sentinel = tmp_path / ".store_write_approved"
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": f"touch {sentinel}"},
    }
    env = {
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "PATH": os.environ.get("PATH", ""),
    }
    result = _run_self_touch_hook(payload, env=env)
    assert result.returncode == 2, f"Expected exit 2, got {result.returncode}; stderr: {result.stderr}"


def test_bash_redirect_to_sentinel_is_blocked(tmp_path):
    """Redirect to sentinel path (echo ok > sentinel) is still blocked."""
    sentinel = tmp_path / ".store_write_approved"
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": f'echo "ok" > "{sentinel}"'},
    }
    env = {
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "PATH": os.environ.get("PATH", ""),
    }
    result = _run_self_touch_hook(payload, env=env)
    assert result.returncode == 2, f"Expected exit 2 for redirect, got {result.returncode}; stderr: {result.stderr}"


def test_bash_unrelated_command_passes(tmp_path):
    """Bash commands that don't touch the sentinel pass through."""
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "ls /tmp"},
    }
    env = {
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "PATH": os.environ.get("PATH", ""),
    }
    result = _run_self_touch_hook(payload, env=env)
    assert result.returncode == 0


def test_non_bash_tool_passes_through_self_touch_guard(tmp_path):
    """Non-Bash tools (Read, Write, etc.) are not subject to this hook."""
    payload = {
        "tool_name": "Read",
        "tool_input": {"file_path": str(tmp_path / "anything")},
    }
    env = {
        "CLAUDE_PROJECT_DIR": str(tmp_path),
        "PATH": os.environ.get("PATH", ""),
    }
    result = _run_self_touch_hook(payload, env=env)
    assert result.returncode == 0
