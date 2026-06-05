"""Shared pytest fixtures for masterbook tests."""
import sys
from pathlib import Path

# Make masterbook/tools importable as a package-ish path.
MASTERBOOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MASTERBOOK / "tools"))
sys.path.insert(0, str(MASTERBOOK / "hooks"))
sys.path.insert(0, str(MASTERBOOK / "baseline-hooks"))

import pytest


@pytest.fixture
def mini_masterbook(tmp_path):
    """Copy the bundled fixture masterbook into a tmp dir for write-tests."""
    import shutil
    src = MASTERBOOK / "tests" / "fixtures" / "mini_masterbook"
    dst = tmp_path / "masterbook"
    shutil.copytree(src, dst)
    return dst


@pytest.fixture
def sample_project(tmp_path):
    """Copy the fixture project into a tmp dir."""
    import shutil
    src = MASTERBOOK / "tests" / "fixtures" / "sample_project"
    dst = tmp_path / "project"
    shutil.copytree(src, dst)
    return dst
