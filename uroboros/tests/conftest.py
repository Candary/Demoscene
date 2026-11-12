import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def patches_dir(project_root) -> Path:
    return project_root / "patches"


@pytest.fixture
def uroboros_instance(tmp_path, patches_dir):
    from uroboros import Uroboros
    return Uroboros(root=tmp_path / "data", patches=patches_dir, workers=2)