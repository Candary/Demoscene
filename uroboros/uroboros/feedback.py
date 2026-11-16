"""Convergence checker and feedback proposer for cyclic pipeline.

ConvergenceChecker: decides approve/feedback/abort based on metrics vs targets.
FeedbackProposer: computes param deltas from metrics (brightness → uIntensity).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SceneMetric:
    """Per-scene evaluation result."""
    scene: str
    brightness: float = 0.0
    target_brightness: float = 0.18
    visible_pct: float = 0.0
    verdict: str = "ok"  # ok | too_dark | too_bright | error

    @property
    def delta(self) -> float:
        return self.brightness - self.target_brightness

    @property
    def within_tolerance(self) -> bool:
        return abs(self.delta) < 0.005


@dataclass
class ConvergenceConfig:
    """Tuning parameters for convergence detection."""
    tolerance: float = 0.005        # |metric - target| < tol → converged
    max_iterations: int = 5         # hard stop
    damping: float = 0.5            # delta = (target - current) * damping
    oscillation_window: int = 3     # check last N deltas for sign flips
    min_improvement: float = 0.001  # delta must improve by this or abort


class ConvergenceChecker:
    """Decides: approve (converged) | feedback_apply (not converged) | abort."""

    def __init__(self, config: Optional[ConvergenceConfig] = None):
        self.config = config or ConvergenceConfig()
        self._history: List[float] = []  # max_delta per iteration

    def check(self, metrics: List[SceneMetric], iteration: int) -> Tuple[str, Dict]:
        """Returns (decision, convergence_info)."""
        max_delta = max(abs(m.delta) for m in metrics) if metrics else 0.0
        all_converged = all(m.within_tolerance for m in metrics) if metrics else True
        self._history.append(max_delta)

        info = {
            "iteration": iteration,
            "max_delta": round(max_delta, 6),
            "all_converged": all_converged,
            "iterations_remaining": max(0, self.config.max_iterations - iteration - 1),
        }

        if all_converged:
            info["reason"] = "all metrics within tolerance"
            return "approve", info

        if iteration + 1 >= self.config.max_iterations:
            info["reason"] = "max_iterations reached"
            return "abort", info

        if self._is_oscillating():
            info["reason"] = "oscillation detected (sign flips in last deltas)"
            return "abort", info

        if len(self._history) >= 2:
            improvement = self._history[-2] - self._history[-1]
            info["improvement"] = round(improvement, 6)
            if improvement < self.config.min_improvement and iteration > 0:
                info["reason"] = f"insufficient improvement ({improvement:.6f} < {self.config.min_improvement})"
                return "abort", info

        info["reason"] = "metrics outside tolerance, continuing"
        return "feedback_apply", info

    def _is_oscillating(self) -> bool:
        """True if last N deltas show ≥2 sign flips (bouncing)."""
        if len(self._history) < self.config.oscillation_window + 1:
            return False
        recent = self._history[-(self.config.oscillation_window + 1):]
        flips = sum(1 for i in range(1, len(recent))
                    if recent[i] * recent[i-1] < 0)
        return flips >= 2

    def reset(self) -> None:
        self._history.clear()


class FeedbackProposer:
    """Maps scene metrics to param deltas for next iteration.

    Rules (deterministic, no ML):
      too_dark  → boost uIntensity by (target-current)/current * damping
      too_bright → reduce uExposure by (current-target)/current * damping
    """

    def __init__(self, damping: float = 0.5):
        self.damping = max(0.1, min(0.9, damping))

    def propose(self, metrics: List[SceneMetric],
                current_params: Dict[str, Any]) -> Dict[str, Any]:
        """Returns delta dict: {param_path: {from, to, reason}}."""
        deltas: Dict[str, Any] = {}
        for m in metrics:
            if m.within_tolerance:
                continue
            scene_prefix = m.scene.split("_")[0]  # "s4_anxiety" → "s4"
            if m.verdict == "too_dark":
                param_key = f"{scene_prefix}.uIntensity"
                current_val = float(current_params.get(param_key, 1.0))
                if current_val <= 0:
                    continue
                adjustment = (m.target_brightness - m.brightness) / m.brightness
                new_val = current_val * (1.0 + adjustment * self.damping)
                new_val = max(0.1, min(5.0, new_val))  # clamp
                deltas[param_key] = {
                    "from": round(current_val, 4),
                    "to": round(new_val, 4),
                    "reason": f"brightness {m.brightness:.3f} < target {m.target_brightness:.3f}",
                }
            elif m.verdict == "too_bright":
                param_key = f"{scene_prefix}.uExposure"
                current_val = float(current_params.get(param_key, 0.55))
                if current_val <= 0:
                    continue
                adjustment = (m.brightness - m.target_brightness) / m.brightness
                new_val = current_val * (1.0 - adjustment * self.damping)
                new_val = max(0.05, min(2.0, new_val))  # clamp
                deltas[param_key] = {
                    "from": round(current_val, 4),
                    "to": round(new_val, 4),
                    "reason": f"brightness {m.brightness:.3f} > target {m.target_brightness:.3f}",
                }
        return deltas

    def apply_deltas(self, params: Dict[str, Any],
                     deltas: Dict[str, Any]) -> Dict[str, Any]:
        """Returns new params dict with deltas applied."""
        out = dict(params)
        for key, change in deltas.items():
            if isinstance(change, dict) and "to" in change:
                out[key] = change["to"]
        return out
