"""Tests for P1 fixes from external review (2026-11-12).

Covers:
- P1.1: PNG byte order (source inspection — C++ test in scripts/test_png_v2.cpp)
- P1.2: Hot reload timestamp initialization (source inspection)
- P1.3: Opacity application in setBlendMode (source inspection)
- P1.4: strict mode rejects fallback outputs
- P1.5: cache key includes data_dependencies (replacing file → cache miss)
"""
import os
import json
import sys
import shutil
import tempfile
import pytest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
sys.path.insert(0, str(PROJECT_ROOT))

from uroboros import Uroboros
from uroboros.formats import FORMAT, PatchError


# ============================================================================
# P1.4: Strict mode rejects fallback outputs
# ============================================================================

FALLBACK_PATCH_SRC = '''
OP = "fallback.test"
def apply(context, params):
    return {"result": "default", "_fallback": True, "_fallback_reason": "no matrix"}
'''

LOOSE_FALLBACK_PATCH_SRC = '''
OP = "fallback.loose"
def apply(context, params):
    return {"result": "default", "_fallback": True, "_fallback_reason": "no matrix"}
'''

# ============================================================================
# P1.5: data_dependencies test patch (used in fixture)
# ============================================================================

DATA_DEPS_PATCH_SRC = '''
OP = "data.test"
import os
def apply(context, params):
    deps = params.get("data_dependencies", [])
    path = deps[0] if deps else None
    content = ""
    if path and os.path.exists(path):
        with open(path) as f:
            content = f.read().strip()
    return {"content": content}
'''


@pytest.fixture
def isolated_patches_dir(tmp_path):
    """Create a temp patches dir with all real patches + isolated state
    AND pre-populated test patches (fallback + data.test).

    Note: PatchRegistry skips files starting with '_', so test patches
    must use a different prefix.
    """
    src_patches = PROJECT_ROOT / "patches"
    dst_patches = tmp_path / "patches"
    shutil.copytree(src_patches, dst_patches)
    # Pre-populate test patches so they're loaded at registry __init__
    (dst_patches / "zz_test_fb_strict.py").write_text(FALLBACK_PATCH_SRC)
    (dst_patches / "zz_test_fb_loose.py").write_text(LOOSE_FALLBACK_PATCH_SRC)
    (dst_patches / "zz_test_data_deps.py").write_text(DATA_DEPS_PATCH_SRC)
    return dst_patches


@pytest.fixture
def uroboros_strict(tmp_path, isolated_patches_dir):
    """Uroboros in strict mode with isolated patches dir + test patches."""
    return Uroboros(
        root=tmp_path / "data",
        patches=isolated_patches_dir,
        workers=2,
        strict=True,
    )


@pytest.fixture
def uroboros_loose(tmp_path, isolated_patches_dir):
    """Uroboros in demo (loose) mode + test patches."""
    return Uroboros(
        root=tmp_path / "data",
        patches=isolated_patches_dir,
        workers=2,
        strict=False,
    )


class TestStrictMode:
    def test_strict_flag_default_false(self, tmp_path, isolated_patches_dir):
        """Default Uroboros instance has strict=False (back-compat)."""
        u = Uroboros(root=tmp_path / "data", patches=isolated_patches_dir)
        assert u.strict is False

    def test_strict_flag_explicit_true(self, tmp_path, isolated_patches_dir):
        """Uroboros(strict=True) sets the flag."""
        u = Uroboros(root=tmp_path / "data", patches=isolated_patches_dir, strict=True)
        assert u.strict is True

    def test_strict_rejects_fallback_output(self, uroboros_strict):
        """Strict mode: patch returning _fallback:True raises PatchError."""
        plan = {
            "format": FORMAT,
            "name": "test_strict_fallback",
            "nodes": [
                {"id": "fb", "target": "test", "operation": "fallback.test", "params": {}}
            ],
        }
        with pytest.raises(PatchError, match="fallback"):
            uroboros_strict.run(plan, max_iterations=1, require_approval=False)

    def test_loose_allows_fallback_output(self, uroboros_loose):
        """Loose mode (default): _fallback outputs are accepted (back-compat)."""
        plan = {
            "format": FORMAT,
            "name": "test_loose_fallback",
            "nodes": [
                {"id": "fb", "target": "test", "operation": "fallback.loose", "params": {}}
            ],
        }
        state = uroboros_loose.run(plan, max_iterations=1, require_approval=False)
        # In loose mode, the fallback output is accepted (status approved)
        assert state["status"] == "approved"
        assert state["final"]["outputs"]["fb"]["_fallback"] is True


# ============================================================================
# P1.5: Cache key includes data_dependencies
# ============================================================================

class TestDataDependencies:
    def test_cache_key_changes_when_data_file_changes(
        self, uroboros_loose, tmp_path
    ):
        """Replacing a data_dependencies file should cause cache miss."""
        data_file = tmp_path / "data_v1.txt"
        data_file.write_text("version 1\n")

        plan = {
            "format": FORMAT,
            "name": "test_data_deps",
            "nodes": [
                {"id": "d", "target": "test", "operation": "data.test",
                 "params": {"data_dependencies": [str(data_file)]}}
            ],
        }

        # First run — executes (cache miss)
        s1 = uroboros_loose.run(plan, max_iterations=1, require_approval=False)
        out1 = s1["final"]["outputs"]["d"]["content"]
        assert out1 == "version 1"

        # Second run — should hit cache (file unchanged)
        s2 = uroboros_loose.run(plan, max_iterations=1, require_approval=False)
        out2 = s2["final"]["outputs"]["d"]["content"]
        assert out2 == "version 1"
        cache_hits_2 = s2["iterations"][0]["checklist"]["cache_hits"]
        assert cache_hits_2 >= 1, "Second run with unchanged data should hit cache"

        # Modify the data file
        data_file.write_text("version 2\n")

        # Third run — should MISS cache (data_deps hash changed)
        s3 = uroboros_loose.run(plan, max_iterations=1, require_approval=False)
        out3 = s3["final"]["outputs"]["d"]["content"]
        assert out3 == "version 2", \
            f"Data file changed but cached old result: {out3}"
        exec_count_3 = s3["iterations"][0]["checklist"]["execution_count"]
        assert exec_count_3 >= 1, \
            "Data file change should cause cache miss and re-execution"


# ============================================================================
# P1.1: PNG byte order — verified via scripts/test_png_v2.cpp (C++ test)
# ============================================================================

def _find_demo_runtime():
    for p in [
        PROJECT_ROOT.parent / "download" / "demo_intro_v61" / "demo_runtime.cpp",
        PROJECT_ROOT / "download" / "demo_intro_v61" / "demo_runtime.cpp",
    ]:
        if p.exists():
            return p
    return None


def _find_gl_executor():
    for p in [
        PROJECT_ROOT.parent / "download" / "demo_intro_v61" / "gl_executor.hpp",
        PROJECT_ROOT / "download" / "demo_intro_v61" / "gl_executor.hpp",
    ]:
        if p.exists():
            return p
    return None


class TestPNGByteOrder:
    """P1.1 is verified via the standalone C++ test in scripts/test_png_v2.cpp.
    The test compiles writePNG with the P1.1 fix (writeBE32 for chunk length
    and CRC) and verifies that Pillow can decode the resulting PNG file.
    """

    def test_png_test_source_exists(self):
        """The C++ test for writePNG exists."""
        candidates = [
            PROJECT_ROOT.parent / "scripts" / "test_png_v2.cpp",
            PROJECT_ROOT / "scripts" / "test_png_v2.cpp",
        ]
        assert any(p.exists() for p in candidates), \
            f"PNG test source not found at any of: {candidates}"

    def test_png_byte_order_fix_in_demo_runtime(self):
        """demo_runtime.cpp writes PNG chunk length and CRC in big-endian (P1.1).

        Implementation-agnostic: accepts either `writeBE32` or `putBE32`
        helper name (different code reviewers used different names for the
        same fix). The semantic requirement is: chunk length and CRC are
        NOT written via raw `fwrite(&val, 4, 1, f)` (which would use
        machine byte order = little-endian on x86).
        """
        cpp_path = _find_demo_runtime()
        if cpp_path is None:
            pytest.skip("demo_runtime.cpp not found")

        src = cpp_path.read_text()
        # P1.1: a big-endian 32-bit writer helper exists (either name OK)
        be_helper_found = ("writeBE32" in src) or ("putBE32" in src)
        assert be_helper_found, \
            "No big-endian 32-bit writer helper (writeBE32 or putBE32) found — P1.1 not applied"

        # Strip C++ comments, then verify no raw fwrite(&clen/crc) calls remain
        import re
        code_only = re.sub(r'/\*.*?\*/', '', src, flags=re.DOTALL)  # block comments
        code_only = re.sub(r'//[^\n]*', '', code_only)               # line comments
        assert "fwrite(&clen" not in code_only, \
            "fwrite(&clen, ...) still in code (P1.1 regression)"
        assert "fwrite(&crc" not in code_only, \
            "fwrite(&crc, ...) still in code (P1.1 regression)"


# ============================================================================
# P1.2: Hot reload — NOT APPLICABLE in hardcode v61 baseline
# ============================================================================
# The hardcode v61 baseline (from user 2026-11-13) does NOT implement hot
# reload feature: no checkReload(), no reloadProgram(), no fileTimes_ member,
# no getFileTime() method in ShaderCache class, no F4 key handler.
#
# The original P1.2 fix (added 2026-11-12) targeted a different codebase that
# HAD these symbols but didn't initialize fileTimes_ on first load. That fix
# is moot here — there's nothing to initialize because the feature doesn't exist.
#
# Applying the fix blindly (as I did) caused compile errors:
#   error C2065: fileTimes_: undeclared identifier
#   error C3861: getFileTime: identifier not found
#
# This was a violation of static analysis protocol. The broken line has been
# removed from gl_executor.hpp. If hot reload is desired, it must be
# implemented as a complete feature (fileTimes_ member + getFileTime method +
# checkReload + reloadProgram + F4 handler), not a one-line fix.


# ============================================================================
# P1.3: Opacity application
# ============================================================================

class TestOpacityApplication:
    """P1.3: setBlendMode must use the opacity parameter (via glBlendColor +
    glBlendFuncSeparate with GL_CONSTANT_ALPHA).
    """

    def test_setblendmode_uses_opacity(self):
        hpp_path = _find_gl_executor()
        if hpp_path is None:
            pytest.skip("gl_executor.hpp not found")

        src = hpp_path.read_text()
        # P1.3: glBlendColor is called with opacity
        assert "glBlendColor" in src, "glBlendColor missing (P1.3 not applied)"
        # P1.3: glBlendFuncSeparate used (separate alpha for opacity)
        assert "glBlendFuncSeparate" in src, \
            "glBlendFuncSeparate missing (P1.3 not applied)"
        # P1.3: GL_CONSTANT_ALPHA used to apply opacity
        assert "GL_CONSTANT_ALPHA" in src, \
            "GL_CONSTANT_ALPHA missing (P1.3 not applied)"


if __name__ == "__main__":
    import traceback
    test_classes = [
        TestStrictMode,
        TestDataDependencies,
        TestPNGByteOrder,
        TestOpacityApplication,
    ]
    total = passed = failed = 0
    for cls in test_classes:
        instance = cls()
        methods = [m for m in dir(instance) if m.startswith("test_")]
        for method_name in methods:
            total += 1
            try:
                # Skip tests requiring fixtures — they need pytest
                import inspect
                sig = inspect.signature(getattr(instance, method_name))
                if any(p.default is inspect.Parameter.empty for p in sig.parameters.values()):
                    print(f"  SKIP  {cls.__name__}.{method_name} (requires pytest fixtures)")
                    continue
                method = getattr(instance, method_name)
                method()
                passed += 1
                print(f"  PASS  {cls.__name__}.{method_name}")
            except Exception as e:
                failed += 1
                print(f"  FAIL  {cls.__name__}.{method_name}: {e}")
                traceback.print_exc()
    print(f"\n=== Tests: {passed}/{total} passed, {failed} failed ===")
    sys.exit(1 if failed > 0 else 0)

