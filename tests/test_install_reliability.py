# tests/test_install_reliability.py
import json
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERPRETERS = {"python3", "python", "bash", "sh", "/usr/bin/env"}


def test_no_bare_path_hook_invocations():
    """Every hook must run via an explicit interpreter so a missing +x bit
    cannot cause exit 126 on a fresh plugin install."""
    cfg = json.loads((ROOT / "hooks" / "hooks.json").read_text())
    for event, entries in cfg["hooks"].items():
        for entry in entries:
            for hook in entry["hooks"]:
                assert hook["command"] in INTERPRETERS, (
                    f"{event}: '{hook['command']}' is a bare-path invocation "
                    f"(exit-126 risk); use an interpreter + args"
                )
                assert hook.get("args"), f"{event}: interpreter with no script arg"


def test_hook_script_compiles():
    py_compile.compile(str(ROOT / "hooks" / "session_end_stamp.py"), doraise=True)
