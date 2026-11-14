"""Tests for smt_patch (param injection) and gpu_eval (evaluation bridge)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from uroboros.smt_patch import parse_smt, inject_params, extract_params
from uroboros.gpu_eval import analyze_bmp, GPUEvaluator, create_gpu_forward_fn
from uroboros.feedback import SceneMetric


# ============================================================================
# smt_patch tests
# ============================================================================

# Minimal .smt for testing
TEST_SMT = """SMT 1
meta 4.0 60 640 360 2026
clip s1 10 scene nebula_raymarch 0.0 4.0 0.0 4.0 normal 11111 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uPrimaryColor vec3 3
prog 1 n:0.05
prog 1 n:0.1
prog 1 n:0.3
uni uAccentColor vec3 3
prog 1 n:0.2
prog 1 n:0.6
prog 1 n:0.9
uni uIntensity float 1
prog 1 n:0.8
uni uMotionSpeed float 1
prog 1 n:1.0
endclip
clip s2 10 scene sphere_scene 3.0 4.0 3.0 1.0 normal 22222 - - 2.0
prog opacity 1 n:1.0
uni uColor vec3 3
prog 1 n:0.1
prog 1 n:0.5
prog 1 n:0.8
uni uGlow float 1
prog 1 n:1.2
endclip
"""


@pytest.fixture
def test_smt_file(tmp_path):
    p = tmp_path / "test.smt"
    p.write_text(TEST_SMT)
    return p


class TestSmtParse:
    def test_parse_finds_clips(self, test_smt_file):
        records = parse_smt(test_smt_file)
        clips = [r for r in records if r["type"] == "clip"]
        assert len(clips) == 2
        assert clips[0]["clip_id"] == "s1"
        assert clips[0]["effect"] == "nebula_raymarch"
        assert clips[1]["clip_id"] == "s2"

    def test_parse_finds_uniforms(self, test_smt_file):
        records = parse_smt(test_smt_file)
        unis = [r for r in records if r["type"] == "uni"]
        names = [u["name"] for u in unis]
        assert "uIntensity" in names
        assert "uPrimaryColor" in names
        assert "uGlow" in names

    def test_parse_finds_prog_values(self, test_smt_file):
        records = parse_smt(test_smt_file)
        progs = [r for r in records if r["type"] == "prog" and "value" in r]
        values = [p["value"] for p in progs]
        assert 0.8 in values  # uIntensity in s1
        assert 1.2 in values  # uGlow in s2


class TestExtractParams:
    def test_extract_float_uniforms(self, test_smt_file):
        params = extract_params(test_smt_file)
        assert "s1.uIntensity" in params
        assert params["s1.uIntensity"] == 0.8
        assert "s1.uMotionSpeed" in params
        assert params["s1.uMotionSpeed"] == 1.0
        assert "s2.uGlow" in params
        assert params["s2.uGlow"] == 1.2

    def test_extract_skips_vec3(self, test_smt_file):
        params = extract_params(test_smt_file)
        # Vec3 uniforms should NOT appear (only count=1 floats)
        assert "s1.uPrimaryColor" not in params
        assert "s2.uColor" not in params


class TestInjectParams:
    def test_inject_single_float(self, test_smt_file):
        out = inject_params(test_smt_file, {"s1.uIntensity": 1.5})
        # Re-parse and verify
        params = extract_params(out)
        assert params["s1.uIntensity"] == 1.5
        # Other params unchanged
        assert params["s1.uMotionSpeed"] == 1.0

    def test_inject_multiple_params(self, test_smt_file):
        out = inject_params(test_smt_file, {
            "s1.uIntensity": 2.0,
            "s2.uGlow": 0.5,
        })
        params = extract_params(out)
        assert params["s1.uIntensity"] == 2.0
        assert params["s2.uGlow"] == 0.5

    def test_inject_to_new_file(self, test_smt_file, tmp_path):
        out_path = tmp_path / "modified.smt"
        inject_params(test_smt_file, {"s1.uIntensity": 1.5}, out_path)
        # Original unchanged
        orig_params = extract_params(test_smt_file)
        assert orig_params["s1.uIntensity"] == 0.8
        # Modified file has new value
        new_params = extract_params(out_path)
        assert new_params["s1.uIntensity"] == 1.5

    def test_inject_nonexistent_param_no_crash(self, test_smt_file):
        """Injecting a param that doesn't exist in .smt should not crash."""
        out = inject_params(test_smt_file, {"s99.nonexistent": 1.0})
        # Should still work, just no injection happened
        params = extract_params(out)
        assert params["s1.uIntensity"] == 0.8  # unchanged

    def test_inject_preserves_structure(self, test_smt_file):
        """Injected .smt should have same line count (no lines added/removed)."""
        original_lines = test_smt_file.read_text().splitlines()
        out = inject_params(test_smt_file, {"s1.uIntensity": 1.5})
        modified_lines = Path(out).read_text().splitlines()
        assert len(original_lines) == len(modified_lines)


# ============================================================================
# gpu_eval tests
# ============================================================================

class TestAnalyzeBmp:
    def test_analyze_missing_file(self, tmp_path):
        metric = analyze_bmp(tmp_path / "nonexistent.bmp", "s1", 0.18)
        assert metric.verdict == "error"
        assert metric.brightness == 0.0

    def test_analyze_real_bmp(self, tmp_path):
        """Create a simple BMP and analyze it."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not available")

        # Create 10x10 gray image (brightness ~0.5)
        img = Image.new("RGB", (10, 10), (128, 128, 128))
        bmp_path = tmp_path / "test.bmp"
        img.save(str(bmp_path))

        metric = analyze_bmp(bmp_path, "s1", target_brightness=0.18)
        assert metric.verdict == "too_bright"  # 0.5 > 0.18
        assert 0.4 < metric.brightness < 0.6

    def test_analyze_dark_image(self, tmp_path):
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not available")

        img = Image.new("RGB", (10, 10), (5, 5, 5))  # very dark
        bmp_path = tmp_path / "dark.bmp"
        img.save(str(bmp_path))

        metric = analyze_bmp(bmp_path, "s4", target_brightness=0.15)
        assert metric.verdict == "too_dark"
        assert metric.brightness < 0.05


class TestGPUEvaluator:
    def test_mock_mode_on_linux(self, tmp_path):
        """On Linux without Wine, evaluator returns mock metrics."""
        ev = GPUEvaluator(
            smt_path=str(tmp_path / "dummy.smt"),
            work_dir=str(tmp_path),
        )
        # _can_run_runtime should return False on Linux without Wine
        if not ev._can_run_runtime():
            metric = ev._mock_metric("s1", 0.18)
            assert metric.verdict == "ok"
            assert metric.brightness == 0.18

    def test_evaluate_returns_metrics(self, tmp_path):
        """evaluate() should return SceneMetric for each scene."""
        ev = GPUEvaluator(
            smt_path=str(tmp_path / "dummy.smt"),
            work_dir=str(tmp_path),
            capture_times={"s1": 5.0, "s2": 10.0},
        )
        state = {"smt_path": str(tmp_path / "dummy.smt"), "scenes": ["s1", "s2"]}
        metrics = ev.evaluate(state)
        assert len(metrics) == 2
        assert all(isinstance(m, SceneMetric) for m in metrics)


class TestCreateGpuForwardFn:
    def test_forward_fn_no_params(self, tmp_path):
        """With no float params, forward_fn returns original smt path."""
        # Create dummy .smt
        smt = tmp_path / "demo.smt"
        smt.write_text("SMT 1\n")
        fn = create_gpu_forward_fn(str(smt), str(tmp_path))
        state = fn({"non_numeric": "hello"})
        assert state["smt_path"] == str(smt)

    def test_forward_fn_with_params(self, tmp_path):
        """With float params, forward_fn creates modified .smt."""
        smt = tmp_path / "demo.smt"
        smt.write_text(TEST_SMT)
        fn = create_gpu_forward_fn(str(smt), str(tmp_path))
        state = fn({"s1.uIntensity": 1.5})
        assert state["smt_path"] != str(smt)  # modified path
        assert os.path.exists(state["smt_path"])

    def test_forward_fn_missing_template(self, tmp_path):
        """Missing template file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            create_gpu_forward_fn(str(tmp_path / "nonexistent.smt"), str(tmp_path))
