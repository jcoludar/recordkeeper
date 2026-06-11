# masterbook/tests/test_manifest_atomic.py
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


def test_atomic_write_creates_parent_and_content(tmp_path):
    m = _load("_manifest_atomic")
    target = tmp_path / "sub" / "f.txt"
    m.atomic_write_text(target, "hello")
    assert target.read_text() == "hello"


def test_atomic_write_leaves_no_tempfiles(tmp_path):
    m = _load("_manifest_atomic")
    target = tmp_path / "f.txt"
    m.atomic_write_text(target, "x")
    assert [p.name for p in tmp_path.iterdir()] == ["f.txt"]


def test_read_counter_missing_is_zero(tmp_path):
    m = _load("_manifest_atomic")
    assert m.read_counter(tmp_path / "counter") == 0


def test_bump_counter_is_sequential(tmp_path):
    m = _load("_manifest_atomic")
    c = tmp_path / "counter"
    assert m.bump_counter(c) == 1
    assert m.bump_counter(c) == 2
    assert m.read_counter(c) == 2


def test_read_counter_corrupt_is_zero(tmp_path):
    m = _load("_manifest_atomic")
    c = tmp_path / "counter"
    c.write_text("not-a-number")
    assert m.read_counter(c) == 0
