"""Tests for pre_tool_use_secrets.py."""
import json
import subprocess
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "pre_tool_use_secrets.py"


def _run(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/usr/bin/env", "python3", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def test_blocks_env_file_read():
    r = _run({"tool_name": "Read", "tool_input": {"file_path": "/x/.env"}})
    assert r.returncode == 2
    assert ".env" in r.stderr


def test_blocks_credentials_json_write():
    r = _run({"tool_name": "Write", "tool_input": {"file_path": "/x/credentials.json"}})
    assert r.returncode == 2


def test_blocks_pem_edit():
    r = _run({"tool_name": "Edit", "tool_input": {"file_path": "/x/server.key.pem"}})
    assert r.returncode == 2


def test_allows_normal_file():
    r = _run({"tool_name": "Edit", "tool_input": {"file_path": "/x/foo.py"}})
    assert r.returncode == 0


def test_passes_through_non_file_tools():
    r = _run({"tool_name": "Bash", "tool_input": {"command": "ls"}})
    assert r.returncode == 0
