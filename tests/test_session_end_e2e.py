# tests/test_session_end_e2e.py
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "session_end_stamp.py"


def test_end_to_end_stamps_via_stdin_cwd(tmp_path):
    sdir = tmp_path / "sessions"
    sdir.mkdir()
    log = sdir / "2026-06-05-demo.md"
    started = "2026-06-05T10:00:00+02:00"
    log.write_text(
        f"---\nslug: demo\nstarted_at: {started}\nstatus: done\n---\nbody\n"
    )
    event = json.dumps(
        {"cwd": str(tmp_path), "session_id": "abc", "why_session_ended": "exit"}
    )
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=event,
        text=True,
        capture_output=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    text = log.read_text()
    match = re.search(r"^ended_at:\s*(\S+)", text, re.MULTILINE)
    assert match, text
    # the stamped end-time is a real ISO-8601 value, never before started_at
    assert dt.datetime.fromisoformat(match.group(1)) >= dt.datetime.fromisoformat(started)
