"""Cyclic pipeline: forward → evaluate → decide → delta → repeat.

Phase 1: Python-side loop using Uroboros engine + motus adapter + CV analysis.
No C++ runtime involvement — operates on JSON snapshots from motus.scene.
"""
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .feedback import ConvergenceChecker, ConvergenceConfig, FeedbackProposer, SceneMetric
from .intro_cache import IntroCache, IterationRecord


@dataclass
class CyclicConfig:
    """Configuration for cyclic pipeline."""
    max_iterations: int = 5
    tolerance: float = 0.005
    damping: float = 0.5
    targets: Dict[str, float] = field(default_factory=dict)  # scene → target brightness
    enable_visual_debug: bool = False  # Phase 1: disabled by default
    cache_root: str = ".uroboros"


@dataclass
class CyclicResult:
    """Final result of cyclic pipeline run."""
    approved: bool
    iterations: int
    final_params: Dict[str, Any] = field(default_factory=dict)
    final_metrics: List[SceneMetric] = field(default_factory=list)
    decision: str = "abort"
    convergence_info: Dict[str, Any] = field(default_factory=dict)
    cache_path: str = ""


class CyclicPipeline:
    """Orchestrates the cyclic feedback loop.

    Usage:
        pipe = CyclicPipeline(config)
        result = pipe.run(
            forward_fn=my_forward_function,
            evaluate_fn=my_evaluate_function,
            initial_params={"s4.uIntensity": 1.8},
        )
    """

    def __init__(self, config: Optional[CyclicConfig] = None):
        self.config = config or CyclicConfig()
        self.cache = IntroCache(self.config.cache_root)
        conv_cfg = ConvergenceConfig(
            tolerance=self.config.tolerance,
            max_iterations=self.config.max_iterations,
            damping=self.config.damping,
        )
        self.checker = ConvergenceChecker(conv_cfg)
        self.proposer = FeedbackProposer(self.config.damping)

    def run(
        self,
        *,
        forward_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        evaluate_fn: Callable[[Dict[str, Any]], List[SceneMetric]],
        initial_params: Dict[str, Any],
        run_id: str = "",
    ) -> CyclicResult:
        """Run the cyclic pipeline to convergence or abort.

        Args:
            forward_fn: params → state dict (scene graph, frames, etc.)
            evaluate_fn: state → List[SceneMetric]
            initial_params: starting param values
            run_id: unique run identifier for cache

        Returns:
            CyclicResult with final decision and params
        """
        if not run_id:
            run_id = datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y%m%dT%H%M%SZ")

        current_params = dict(initial_params)
        self.checker.reset()

        for iteration in range(self.config.max_iterations):
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # 1. FORWARD: generate state with current params
            try:
                state = forward_fn(current_params)
            except Exception as exc:
                return self._fail(run_id, iteration, current_params,
                                  f"forward failed: {type(exc).__name__}: {exc}")

            # 2. EVALUATE: compute metrics
            try:
                metrics = evaluate_fn(state)
            except Exception as exc:
                return self._fail(run_id, iteration, current_params,
                                  f"evaluate failed: {type(exc).__name__}: {exc}")

            # 3. DECIDE: convergence check
            decision, conv_info = self.checker.check(metrics, iteration)

            # 4. CACHE: save iteration record
            record = IterationRecord(
                iteration=iteration, run_id=run_id, timestamp=timestamp,
                decision=decision, params=dict(current_params),
                convergence=conv_info,
                metrics={m.scene: {
                    "brightness": m.brightness,
                    "target": m.target_brightness,
                    "delta": round(m.delta, 6),
                    "verdict": m.verdict,
                    "within_tol": m.within_tolerance,
                } for m in metrics},
            )
            self.cache.save_iteration(record)

            if decision == "approve":
                return CyclicResult(
                    approved=True, iterations=iteration + 1,
                    final_params=current_params, final_metrics=metrics,
                    decision=decision, convergence_info=conv_info,
                    cache_path=str(self.cache.cache_dir),
                )

            if decision == "abort":
                return CyclicResult(
                    approved=False, iterations=iteration + 1,
                    final_params=current_params, final_metrics=metrics,
                    decision=decision, convergence_info=conv_info,
                    cache_path=str(self.cache.cache_dir),
                )

            # 5. DELTA: compute param changes for next iteration
            deltas = self.proposer.propose(metrics, current_params)
            record.delta = deltas
            # Re-save with delta
            self.cache.save_iteration(record)
            current_params = self.proposer.apply_deltas(current_params, deltas)

        # Should not reach here (checker handles max_iterations), but safety
        return CyclicResult(
            approved=False, iterations=self.config.max_iterations,
            final_params=current_params,
            decision="abort",
            convergence_info={"reason": "exhausted iterations without convergence"},
            cache_path=str(self.cache.cache_dir),
        )

    def _fail(self, run_id: str, iteration: int,
              params: Dict, error: str) -> CyclicResult:
        record = IterationRecord(
            iteration=iteration, run_id=run_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            decision="abort", params=dict(params),
            convergence={"reason": error},
        )
        self.cache.save_iteration(record)
        return CyclicResult(
            approved=False, iterations=iteration + 1,
            final_params=params, decision="abort",
            convergence_info={"reason": error},
            cache_path=str(self.cache.cache_dir),
        )
