import pytest

from uroboros.formats import PatchError
from uroboros.registry import PatchRegistry


def test_load_patches(patches_dir):
    r = PatchRegistry(patches_dir)
    for op in ("geometry.generate", "color.palette", "scene.compose", "validate.scene"):
        assert op in r.ops, op


def test_unknown_op_raises(patches_dir):
    r = PatchRegistry(patches_dir)
    with pytest.raises(PatchError):
        r.apply("does.not.exist", {}, {})


def test_duplicate_op_raises(tmp_path):
    (tmp_path / "a.py").write_text("OP='x'\ndef apply(c,p): return {}\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("OP='x'\ndef apply(c,p): return {}\n", encoding="utf-8")
    with pytest.raises(PatchError):
        PatchRegistry(tmp_path)