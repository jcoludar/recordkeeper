import importlib.util
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "substrate" / "session-manifest" / "hooks"


def _load(name):
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_read_pointer_missing_is_none(tmp_path):
    m = _load("_manifest_pointer")
    assert m.read_pointer(tmp_path) is None


def test_write_then_read_roundtrip(tmp_path):
    m = _load("_manifest_pointer")
    m.write_pointer(tmp_path, log="sessions/2026-06-03-x.md", slug="x", started_at="2026-06-03T08:00:00+02:00")
    p = m.read_pointer(tmp_path)
    assert p["log"] == "sessions/2026-06-03-x.md"
    assert p["slug"] == "x"
    assert p["started_at"] == "2026-06-03T08:00:00+02:00"


def test_read_pointer_corrupt_json_is_none(tmp_path):
    m = _load("_manifest_pointer")
    path = m.pointer_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not json")
    assert m.read_pointer(tmp_path) is None


def test_read_pointer_without_log_key_is_none(tmp_path):
    m = _load("_manifest_pointer")
    path = m.pointer_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text('{"slug": "x"}')
    assert m.read_pointer(tmp_path) is None


def test_clear_pointer_is_idempotent(tmp_path):
    m = _load("_manifest_pointer")
    m.write_pointer(tmp_path, log="sessions/a.md", slug="a", started_at="t")
    m.clear_pointer(tmp_path)
    m.clear_pointer(tmp_path)  # no error on already-absent
    assert m.read_pointer(tmp_path) is None
