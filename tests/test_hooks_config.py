import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sessionend_hook_registered_in_exec_form():
    cfg = json.loads((ROOT / "hooks" / "hooks.json").read_text())
    entries = cfg["hooks"]["SessionEnd"]
    hook = entries[0]["hooks"][0]
    assert hook["command"] == "python3"
    assert hook["args"] == ["${CLAUDE_PLUGIN_ROOT}/hooks/session_end_stamp.py"]
