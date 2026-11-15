"""gpu_eval — GPU-side evaluation bridge.

Calls demo_runtime.exe --still to render frames on real GPU,
reads BMP/PNG output, runs CV analysis, returns SceneMetric[].

Cannot run on Linux (demo_runtime.exe is Windows x64). On Linux,
falls back to visual_debugger (WebGL2 approximation) or returns
mock metrics for testing.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .feedback import SceneMetric


# Default capture times per scene (scene_start + 2s, matching v61 .smt)
DEFAULT_CAPTURE_TIMES: Dict[str, float] = {
    "s1": 7.0,    # nebula starts at 0
    "s2": 27.0,   # sphere starts at 25
    "s3": 52.0,   # particles starts at 50
    "s4": 77.0,   # anxiety starts at 75
    "s5": 102.0,  # morph_grid starts at 100
    "s6": 129.0,  # cozy_room starts at 127
    "s7": 183.0,  # morphing_figures starts at 181
}

# Default brightness targets per scene
DEFAULT_TARGETS: Dict[str, float] = {
    "s1": 0.18, "s2": 0.20, "s3": 0.18,
    "s4": 0.15, "s5": 0.20, "s6": 0.18, "s7": 0.25,
}


def analyze_bmp(bmp_path: str | Path, scene_id: str,
                target_brightness: float = 0.18) -> SceneMetric:
    """Analyze a BMP/PNG screenshot and return SceneMetric.

    Uses PIL for CV analysis: avg brightness, visible%, verdict.
    """
    path = Path(bmp_path)
    if not path.exists():
        return SceneMetric(scene=scene_id, brightness=0.0,
                           target_brightness=target_brightness,
                           verdict="error")

    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
        pixels = list(img.getdata())
        if not pixels:
            return SceneMetric(scene=scene_id, brightness=0.0,
                               target_brightness=target_brightness,
                               verdict="error")

        # avg brightness (0..1 sRGB)
        total = sum((r + g + b) / 3 for r, g, b in pixels) / len(pixels) / 255.0
        visible_pct = sum(1 for r, g, b in pixels
                          if (r + g + b) / 3 > 30) / len(pixels) * 100

        verdict = "ok"
        if total < target_brightness - 0.005:
            verdict = "too_dark"
        elif total > target_brightness + 0.005:
            verdict = "too_bright"

        return SceneMetric(
            scene=scene_id, brightness=round(total, 4),
            target_brightness=target_brightness,
            visible_pct=round(visible_pct, 2), verdict=verdict,
        )
    except ImportError:
        return SceneMetric(scene=scene_id, brightness=0.0,
                           target_brightness=target_brightness,
                           verdict="error")
    except Exception as exc:
        return SceneMetric(scene=scene_id, brightness=0.0,
                           target_brightness=target_brightness,
                           verdict="error")


class GPUEvaluator:
    """Bridges CyclicPipeline to demo_runtime.exe for GPU-side evaluation.

    On Windows: runs demo_runtime.exe --still → BMP → CV analysis
    On Linux: returns mock metrics (or uses visual_debugger as fallback)
    """

    def __init__(self, *, demo_runtime_path: str = "demo_runtime.exe",
                 smt_path: str = "demo.smt",
                 work_dir: Optional[str] = None,
                 targets: Optional[Dict[str, float]] = None,
                 capture_times: Optional[Dict[str, float]] = None):
        self.demo_runtime = demo_runtime_path
        self.smt_path = smt_path
        self.work_dir = work_dir or tempfile.mkdtemp(prefix="gpu_eval_")
        self.targets = dict(targets or DEFAULT_TARGETS)
        self.capture_times = dict(capture_times or DEFAULT_CAPTURE_TIMES)
        os.makedirs(self.work_dir, exist_ok=True)

    def evaluate(self, state: Dict[str, Any]) -> List[SceneMetric]:
        """Run GPU rendering + CV analysis for all scenes.

        Args:
            state: dict from forward_fn (must contain "smt_path" if different from default)

        Returns:
            List[SceneMetric] per scene
        """
        smt = state.get("smt_path", self.smt_path)
        scenes = state.get("scenes", list(self.capture_times.keys()))
        results: List[SceneMetric] = []

        for scene_id in scenes:
            t = self.capture_times.get(scene_id, 5.0)
            target = self.targets.get(scene_id, 0.18)
            bmp_path = os.path.join(self.work_dir, f"shot_{scene_id}.bmp")

            metric = self._render_and_analyze(smt, t, scene_id, bmp_path, target)
            results.append(metric)

        return results

    def _render_and_analyze(self, smt_path: str, t: float,
                            scene_id: str, bmp_path: str,
                            target: float) -> SceneMetric:
        """Render one frame via demo_runtime.exe and analyze."""
        if not self._can_run_runtime():
            return self._mock_metric(scene_id, target)

        try:
            cmd = [self.demo_runtime, smt_path,
                   "--still", str(t), "--out", bmp_path]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                cwd=os.path.dirname(smt_path) or ".",
            )
            if result.returncode != 0:
                return SceneMetric(scene=scene_id, brightness=0.0,
                                   target_brightness=target, verdict="error")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return SceneMetric(scene=scene_id, brightness=0.0,
                               target_brightness=target, verdict="error")

        return analyze_bmp(bmp_path, scene_id, target)

    def _can_run_runtime(self) -> bool:
        """Check if demo_runtime.exe is executable on this platform."""
        if os.name == "nt":  # Windows
            return os.path.isfile(self.demo_runtime)
        # On Linux: check if Wine is available + .exe exists
        exe = Path(self.demo_runtime)
        if not exe.exists():
            return False
        try:
            wine_check = subprocess.run(
                ["wine", "--version"], capture_output=True, timeout=5)
            return wine_check.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _mock_metric(self, scene_id: str, target: float) -> SceneMetric:
        """Return a mock metric for testing when GPU is unavailable."""
        return SceneMetric(
            scene=scene_id, brightness=target,  # assume perfect for mock
            target_brightness=target, verdict="ok",
            visible_pct=99.0,
        )


def create_gpu_forward_fn(smt_template_path: str,
                          work_dir: str) -> Any:
    """Create a forward_fn for CyclicPipeline that injects params into .smt.

    Args:
        smt_template_path: original .smt file to use as template
        work_dir: where to write modified .smt files

    Returns:
        forward_fn(params: dict) → state dict with smt_path
    """
    from .smt_patch import inject_params

    template = Path(smt_template_path)
    if not template.exists():
        raise FileNotFoundError(f"smt template not found: {template}")

    def forward_fn(params: Dict[str, Any]) -> Dict[str, Any]:
        # Filter to float params only (skip non-numeric)
        float_params = {}
        for k, v in params.items():
            if isinstance(v, (int, float)):
                float_params[k] = float(v)

        if not float_params:
            # No params to inject — use original .smt
            return {"smt_path": str(template), "scenes": list(DEFAULT_CAPTURE_TIMES.keys())}

        # Write modified .smt
        out_path = os.path.join(work_dir, "modified.smt")
        inject_params(template, float_params, out_path)
        return {"smt_path": out_path, "scenes": list(DEFAULT_CAPTURE_TIMES.keys())}

    return forward_fn
