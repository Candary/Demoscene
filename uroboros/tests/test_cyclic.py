"""Tests for cyclic pipeline: convergence, oscillation, abort, cache GC."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from uroboros.feedback import (
    ConvergenceChecker, ConvergenceConfig, FeedbackProposer, SceneMetric,
)
from uroboros.intro_cache import IntroCache, IterationRecord
from uroboros.cyclic import CyclicConfig, CyclicPipeline, CyclicResult


# ============================================================================
# Helpers: simulated forward/evaluate functions
# ============================================================================

def make_metric(scene: str, brightness: float, target: float = 0.18) -> SceneMetric:
    verdict = "ok"
    if brightness < target - 0.005:
        verdict = "too_dark"
    elif brightness > target + 0.005:
        verdict = "too_bright"
    return SceneMetric(scene=scene, brightness=brightness,
                       target_brightness=target, verdict=verdict)


def make_forward(target_brightness: dict, convergence_rate: float = 0.5):
    """Returns a forward_fn that simulates params → state with brightness."""
    def forward_fn(params: dict) -> dict:
        state = {"params": dict(params), "frames": []}
        return state
    return forward_fn


def make_evaluator(brightness_sequence: list, targets: dict):
    """Returns evaluate_fn that yields brightness from a sequence per call."""
    call_count = [0]
    def evaluate_fn(state: dict) -> list:
        idx = min(call_count[0], len(brightness_sequence) - 1)
        call_count[0] += 1
        metrics = []
        for scene, brightness in brightness_sequence[idx].items():
            target = targets.get(scene, 0.18)
            metrics.append(make_metric(scene, brightness, target))
        return metrics
    return evaluate_fn


# ============================================================================
# IntroCache tests
# ============================================================================

class TestIntroCache:
    def test_save_and_load(self, tmp_path):
        cache = IntroCache(tmp_path)
        record = IterationRecord(
            iteration=0, run_id="test", timestamp="2026-01-01T00:00:00Z",
            decision="feedback_apply",
            metrics={"s1": {"brightness": 0.1}},
        )
        path = cache.save_iteration(record)
        assert os.path.exists(path)

        loaded = cache.load_iteration(0)
        assert loaded is not None
        assert loaded.iteration == 0
        assert loaded.decision == "feedback_apply"
        assert loaded.metrics["s1"]["brightness"] == 0.1

    def test_list_iterations(self, tmp_path):
        cache = IntroCache(tmp_path)
        for i in range(3):
            cache.save_iteration(IterationRecord(
                iteration=i, run_id="test", timestamp="t"))
        assert cache.list_iterations() == [0, 1, 2]

    def test_final_iteration_marked(self, tmp_path):
        cache = IntroCache(tmp_path)
        cache.save_iteration(IterationRecord(
            iteration=0, run_id="t", timestamp="t", decision="feedback_apply"))
        cache.save_iteration(IterationRecord(
            iteration=1, run_id="t", timestamp="t", decision="approve"))
        assert cache.final_iteration == 1

    def test_prune(self, tmp_path):
        cache = IntroCache(tmp_path)
        for i in range(5):
            cache.save_iteration(IterationRecord(
                iteration=i, run_id="t", timestamp="t"))
        deleted = cache.prune(keep_last=2)
        assert deleted == 3
        remaining = cache.list_iterations()
        assert len(remaining) == 2

    def test_load_nonexistent(self, tmp_path):
        cache = IntroCache(tmp_path)
        assert cache.load_iteration(999) is None

    def test_frames_blob(self, tmp_path):
        cache = IntroCache(tmp_path)
        blob = b"\x00" * 100
        record = IterationRecord(iteration=0, run_id="t", timestamp="t")
        cache.save_iteration(record, frames_blob=blob)
        loaded = cache.load_frames(0)
        assert loaded == blob


# ============================================================================
# ConvergenceChecker tests
# ============================================================================

class TestConvergenceChecker:
    def test_approve_when_all_within_tolerance(self):
        checker = ConvergenceChecker()
        metrics = [make_metric("s1", 0.18), make_metric("s2", 0.181)]
        decision, info = checker.check(metrics, 0)
        assert decision == "approve"
        assert info["all_converged"] is True

    def test_feedback_when_outside_tolerance(self):
        checker = ConvergenceChecker()
        metrics = [make_metric("s1", 0.10), make_metric("s2", 0.25)]
        decision, info = checker.check(metrics, 0)
        assert decision == "feedback_apply"
        assert info["all_converged"] is False

    def test_abort_on_max_iterations(self):
        cfg = ConvergenceConfig(max_iterations=2)
        checker = ConvergenceChecker(cfg)
        metrics = [make_metric("s1", 0.01)]
        d0, _ = checker.check(metrics, 0)
        assert d0 == "feedback_apply"
        d1, info1 = checker.check(metrics, 1)
        assert d1 == "abort"
        assert "max_iterations" in info1["reason"]

    def test_oscillation_detection(self):
        cfg = ConvergenceConfig(max_iterations=10, oscillation_window=3)
        checker = ConvergenceChecker(cfg)
        # Simulate bouncing deltas: +0.05, -0.05, +0.05, -0.05
        deltas = [0.05, -0.05, 0.05, -0.05]
        decisions = []
        for i, d in enumerate(deltas):
            m = SceneMetric("s1", brightness=0.18 + d, target_brightness=0.18)
            # Manually push to history to simulate
            checker._history.append(d)
            decision, _ = checker.check([m], i)
            decisions.append(decision)
        assert "abort" in decisions  # should abort due to oscillation

    def test_insufficient_improvement(self):
        cfg = ConvergenceConfig(max_iterations=10, min_improvement=0.01)
        checker = ConvergenceChecker(cfg)
        # First iteration: delta = 0.05
        checker._history.append(0.05)
        m1 = make_metric("s1", 0.13)
        d1, _ = checker.check([m1], 0)
        assert d1 == "feedback_apply"
        # Second: improvement only 0.001
        checker._history.append(0.049)
        d2, info2 = checker.check([m1], 1)
        assert d2 == "abort"
        assert "insufficient" in info2["reason"]


# ============================================================================
# FeedbackProposer tests
# ============================================================================

class TestFeedbackProposer:
    def test_too_dark_boosts_intensity(self):
        proposer = FeedbackProposer(damping=0.5)
        metrics = [make_metric("s4_anxiety", 0.117, target=0.15)]
        params = {"s4.uIntensity": 1.8}
        deltas = proposer.propose(metrics, params)
        assert "s4.uIntensity" in deltas
        assert deltas["s4.uIntensity"]["to"] > 1.8  # boosted

    def test_too_bright_reduces_exposure(self):
        proposer = FeedbackProposer(damping=0.5)
        metrics = [make_metric("s5_morph_grid", 0.220, target=0.18)]
        params = {"s5.uExposure": 0.55}
        deltas = proposer.propose(metrics, params)
        assert "s5.uExposure" in deltas
        assert deltas["s5.uExposure"]["to"] < 0.55  # reduced

    def test_ok_metric_no_delta(self):
        proposer = FeedbackProposer()
        metrics = [make_metric("s1", 0.18)]  # within tolerance
        deltas = proposer.propose(metrics, {"s1.uIntensity": 1.0})
        assert deltas == {}

    def test_apply_deltas(self):
        proposer = FeedbackProposer()
        params = {"s4.uIntensity": 1.8}
        deltas = {"s4.uIntensity": {"from": 1.8, "to": 2.16, "reason": "test"}}
        result = proposer.apply_deltas(params, deltas)
        assert result["s4.uIntensity"] == 2.16
        # Original unchanged
        assert params["s4.uIntensity"] == 1.8

    def test_clamp_values(self):
        proposer = FeedbackProposer(damping=1.0)  # max damping
        # Extreme brightness difference → should clamp
        metrics = [make_metric("s1", 0.001, target=0.5)]
        params = {"s1.uIntensity": 1.0}
        deltas = proposer.propose(metrics, params)
        assert deltas["s1.uIntensity"]["to"] <= 5.0  # clamped


# ============================================================================
# CyclicPipeline integration tests
# ============================================================================

class TestCyclicPipeline:
    def test_converges_in_one_iteration(self, tmp_path):
        """All metrics already within tolerance → approve on iter 0."""
        config = CyclicConfig(
            max_iterations=5, tolerance=0.005,
            cache_root=str(tmp_path),
        )
        pipe = CyclicPipeline(config)

        forward = make_forward({}, 0.5)
        evaluate = make_evaluator(
            [{"s1": 0.18, "s2": 0.181}],  # already at target
            {"s1": 0.18, "s2": 0.18},
        )
        result = pipe.run(
            forward_fn=forward, evaluate_fn=evaluate,
            initial_params={"s1.uIntensity": 1.0},
        )
        assert result.approved is True
        assert result.iterations == 1
        assert result.decision == "approve"

    def test_converges_in_two_iterations(self, tmp_path):
        """First iteration off-target, second converges after feedback."""
        config = CyclicConfig(
            max_iterations=5, tolerance=0.005, damping=0.8,
            cache_root=str(tmp_path),
        )
        pipe = CyclicPipeline(config)

        forward = make_forward({}, 0.8)
        evaluate = make_evaluator(
            [{"s1": 0.10}, {"s1": 0.179}],  # iter0: dark, iter1: near target
            {"s1": 0.18},
        )
        result = pipe.run(
            forward_fn=forward, evaluate_fn=evaluate,
            initial_params={"s1.uIntensity": 1.0},
        )
        assert result.approved is True
        assert result.iterations == 2

    def test_aborts_on_max_iterations(self, tmp_path):
        """Never converges → abort after max_iterations."""
        config = CyclicConfig(
            max_iterations=3, tolerance=0.001, damping=0.1,
            cache_root=str(tmp_path),
        )
        pipe = CyclicPipeline(config)

        forward = make_forward({}, 0.1)
        evaluate = make_evaluator(
            [{"s1": 0.001}] * 5,  # always way off
            {"s1": 0.18},
        )
        result = pipe.run(
            forward_fn=forward, evaluate_fn=evaluate,
            initial_params={"s1.uIntensity": 0.1},
        )
        assert result.approved is False
        assert result.decision == "abort"
        assert result.iterations <= 3

    def test_forward_failure_aborts(self, tmp_path):
        """Exception in forward_fn → abort with error."""
        config = CyclicConfig(cache_root=str(tmp_path))
        pipe = CyclicPipeline(config)

        def failing_forward(params):
            raise RuntimeError("simulated crash")

        evaluate = make_evaluator([{"s1": 0.18}], {"s1": 0.18})
        result = pipe.run(
            forward_fn=failing_forward, evaluate_fn=evaluate,
            initial_params={},
        )
        assert result.approved is False
        assert result.decision == "abort"
        assert "forward failed" in result.convergence_info.get("reason", "")

    def test_cache_records_all_iterations(self, tmp_path):
        """Cache should have iteration records for each step."""
        config = CyclicConfig(
            max_iterations=5, tolerance=0.005,
            cache_root=str(tmp_path),
        )
        pipe = CyclicPipeline(config)

        forward = make_forward({}, 0.5)
        evaluate = make_evaluator(
            [{"s1": 0.10}, {"s1": 0.179}], {"s1": 0.18},
        )
        result = pipe.run(
            forward_fn=forward, evaluate_fn=evaluate,
            initial_params={"s1.uIntensity": 1.0}, run_id="test_cache",
        )
        iterations = pipe.cache.list_iterations()
        assert len(iterations) == result.iterations
        assert pipe.cache.final_iteration is not None

    def test_params_updated_between_iterations(self, tmp_path):
        """Feedback proposer should adjust params between iterations."""
        config = CyclicConfig(
            max_iterations=5, tolerance=0.005, damping=0.5,
            cache_root=str(tmp_path),
        )
        pipe = CyclicPipeline(config)

        forward = make_forward({}, 0.5)
        evaluate = make_evaluator(
            [{"s1": 0.10}, {"s1": 0.179}], {"s1": 0.18},
        )
        result = pipe.run(
            forward_fn=forward, evaluate_fn=evaluate,
            initial_params={"s1.uIntensity": 1.0},
        )
        # Final params should differ from initial
        assert result.final_params["s1.uIntensity"] != 1.0
