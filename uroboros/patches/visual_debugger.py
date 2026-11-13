"""Visual Debugger — Uroboros patch for automated screenshot capture.

This patch bridges Uroboros to a headless WebGL2 browser renderer:
  Input: .smt file (or direct scene + uniform list)
  Process: for each scene, navigate headless browser to visual_debug.html,
           wait for frameReady signal (+ 2s for full render), screenshot
  Output: list of screenshot paths + CV analysis (brightness, visible %, hue)

Architecture:
  Local HTTP server (Python http.server)
    ↓ serves /home/z/my-project over http://localhost:<port>/
    ↓ enables fetch() in visual_debug.html to load .frag files
  visual_debug.html (WebGL2 page)
    ↓ URL params: scene, t, uPrimaryColor, uAccentColor, ...
    ↓ fetch .frag file, compile, render ONE frame
    ↓ window.frameReady = true + postMessage('READY')
  visual_debugger.py (this patch)
    ↓ agent-browser open <url>
    ↓ agent-browser eval "window.frameReady"
    ↓ agent-browser screenshot <path>.png
    ↓ Python CV analysis (PIL)

Usage as Uroboros patch:
  apply(context, params):
    params.scenes = [{"id": "s1", "effect": "nebula_raymarch",
                      "t_capture": 7.0, "uniforms": {...}}, ...]
    returns: {"screenshots": [{"scene": "s1", "path": "/tmp/...png",
                                "analysis": {...}}], "summary": {...}}

Usage standalone:
  python3 visual_debugger.py --scene nebula_raymarch --t 7 \\
    --uPrimaryColor 0.05,0.10,0.30 --uAccentColor 0.20,0.60,0.90 \\
    --uIntensity 1.5 --output /tmp/shot.png
"""
from __future__ import annotations
import os
import sys
import json
import base64
import subprocess
import tempfile
import time
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any

OP = "visual.debug"

# Paths
PROJECT_ROOT = "/home/z/my-project"
URO_ROOT = f"{PROJECT_ROOT}/uroboros"
DEBUG_HTML = f"{URO_ROOT}/visual_debug.html"

# Default scene capture times (matching v60 demo.smt clip starts + 2s buffer)
# This implements the user's requirement: "screenshot when scene loads + 2 seconds"
DEFAULT_SCENE_TIMES = {
    "s1": 7.0,    # nebula starts at T=0, capture at T=2+5=7 (low quality + 2s)
    "s2": 27.0,   # sphere starts at T=25, capture at T=25+2=27
    "s3": 52.0,   # particles starts at T=50, capture at T=52
    "s4": 77.0,   # anxiety starts at T=75, capture at T=77
    "s5": 102.0,  # morph_grid starts at T=100, capture at T=102
    "s6": 129.0,  # cozy_room starts at T=127, capture at T=129
    "s7": 183.0,  # morphing_figures starts at T=181, capture at T=183
}

# Map scene IDs to effect names
SCENE_EFFECTS = {
    "s1": "nebula_raymarch",
    "s2": "sphere_scene",
    "s3": "particle_swarm",
    "s4": "anxiety_mist",
    "s5": "morph_grid",
    "s6": "cozy_room_sdf",
    "s7": "morphing_figures",
}


# ============================================================================
# Local HTTP server (in-process, serves PROJECT_ROOT for fetch())
# ============================================================================

import threading
import http.server
import socketserver
import urllib.request
import urllib.error

_HTTP_THREAD = None
_HTTP_PORT = None


class _SilentHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that suppresses logging."""
    def log_message(self, *args, **kwargs):
        pass


def _start_http_server_in_thread(port: int, directory: str) -> threading.Thread:
    """Start http.server in a background thread (lives as long as Python process)."""
    handler = lambda *a, **kw: _SilentHTTPRequestHandler(*a, directory=directory, **kw)
    httpd = socketserver.TCPServer(("0.0.0.0", port), handler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    thread._httpd = httpd  # store for shutdown
    return thread


def _ensure_http_server() -> int:
    """Start HTTP server in-process if not running. Returns port."""
    global _HTTP_THREAD, _HTTP_PORT
    if _HTTP_THREAD is not None and _HTTP_THREAD.is_alive():
        return _HTTP_PORT

    # Find a free port
    import socket
    for port in range(8765, 8785):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", port))
                _HTTP_PORT = port
                break
        except OSError:
            continue

    _HTTP_THREAD = _start_http_server_in_thread(_HTTP_PORT, PROJECT_ROOT)

    # Wait for server to be ready
    for _ in range(20):
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{_HTTP_PORT}/", timeout=0.5)
            return _HTTP_PORT
        except (urllib.error.URLError, ConnectionRefusedError):
            time.sleep(0.1)
    print(f"WARNING: HTTP server not ready on port {_HTTP_PORT}")
    return _HTTP_PORT


def _shutdown_http_server():
    """Shutdown the HTTP server."""
    global _HTTP_THREAD
    if _HTTP_THREAD is not None and hasattr(_HTTP_THREAD, '_httpd'):
        _HTTP_THREAD._httpd.shutdown()
    _HTTP_THREAD = None


# ============================================================================
# Browser driver
# ============================================================================

def _run_browser(args: List[str], timeout: int = 30) -> Dict:
    """Run agent-browser with args, return parsed output."""
    cmd = ["agent-browser"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = result.stdout.strip()
        try:
            return json.loads(out) if out else {}
        except json.JSONDecodeError:
            return {"raw": out, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except FileNotFoundError:
        return {"error": "agent-browser not installed"}


def _open_url(url: str, session: str = "visual_debug") -> bool:
    """Open URL in headless browser, return True on success."""
    result = _run_browser(["open", url, "--session", session], timeout=20)
    return "error" not in result


def _eval_js(expr: str, session: str = "visual_debug") -> Any:
    """Evaluate JavaScript in browser, return result."""
    # Use base64 for reliable execution
    b64 = base64.b64encode(expr.encode()).decode()
    result = _run_browser(["eval", "-b", b64, "--session", session, "--json"],
                          timeout=10)
    if "data" in result:
        return result["data"].get("result")
    if "result" in result:
        return result["result"]
    return None


def _screenshot(path: str, session: str = "visual_debug") -> bool:
    """Take screenshot to path."""
    result = _run_browser(["screenshot", path, "--session", session], timeout=15)
    return os.path.exists(path) and os.path.getsize(path) > 0


def _close(session: str = "visual_debug"):
    """Close browser session."""
    _run_browser(["close", "--session", session], timeout=5)


# ============================================================================
# Screenshot capture
# ============================================================================

def capture_scene_screenshot(
    scene_id: str,
    t: float,
    uniforms: Dict[str, Any],
    output_path: str,
    *,
    shader_path: Optional[str] = None,
    width: int = 1280,
    height: int = 720,
    extra_wait_s: float = 2.0,
    session: str = "visual_debug",
) -> Dict:
    """Capture one screenshot of a scene at time T.

    Args:
        scene_id: e.g. "s1" or effect name "nebula_raymarch"
        t: time T to render at
        uniforms: dict of uniform overrides {uPrimaryColor: [r,g,b], ...}
        output_path: where to save PNG
        shader_path: optional override for .frag file path
        width, height: canvas dimensions
        extra_wait_s: additional wait after frameReady (user requirement: +2s)
        session: agent-browser session name

    Returns:
        {scene, t, path, ready, analysis}
    """
    # Resolve scene_id → effect name
    effect = SCENE_EFFECTS.get(scene_id, scene_id)

    # Ensure HTTP server is running
    port = _ensure_http_server()

    # Build URL (http://localhost:port/...)
    url_params = {
        "scene": effect,
        "t": str(t),
        "width": str(width),
        "height": str(height),
        "shaderPath": shader_path or f"/demo_intro_v61/shaders/{effect}.frag",
    }
    for uname, val in uniforms.items():
        if isinstance(val, list):
            url_params[uname] = ",".join(str(v) for v in val)
        else:
            url_params[uname] = str(val)

    query = "&".join(f"{k}={v}" for k, v in url_params.items())
    url = f"http://127.0.0.1:{port}/uroboros/visual_debug.html?{query}"

    print(f"  [{scene_id}] opening {url[:120]}...")
    if not _open_url(url, session=session):
        return {"scene": scene_id, "t": t, "ready": False,
                "error": "failed to open URL"}

    # Poll for window.frameReady (max 15 seconds)
    deadline = time.time() + 15
    ready = False
    while time.time() < deadline:
        result = _eval_js("window.frameReady === true", session=session)
        if result is True or result == "true":
            ready = True
            break
        time.sleep(0.3)

    if not ready:
        # Check for error
        err = _eval_js("window.frameError || 'no error'", session=session)
        return {"scene": scene_id, "t": t, "ready": False,
                "error": f"frameReady timeout: {err}"}

    # Extra wait for full render (user requirement: scene loaded + 2s)
    if extra_wait_s > 0:
        # Re-render the same frame a few times to ensure full draw
        for _ in range(int(extra_wait_s * 10)):
            _eval_js("window.requestAnimationFrame(window.renderFrame || function(){})",
                     session=session)
            time.sleep(0.1)

    # Take screenshot
    if not _screenshot(output_path, session=session):
        return {"scene": scene_id, "t": t, "ready": True,
                "error": "screenshot failed"}

    # Analyze
    analysis = analyze_screenshot(output_path)

    return {
        "scene": scene_id,
        "effect": effect,
        "t": t,
        "path": output_path,
        "ready": True,
        "analysis": analysis,
    }


# ============================================================================
# CV analysis
# ============================================================================

def analyze_screenshot(path: str) -> Dict:
    """Analyze a PNG screenshot: brightness, visible %, dominant hue, max pixel.

    Returns:
        {avg_brightness, max_brightness, visible_pct, center_avg, hue_dominant,
         hue_distribution, verdict}
    """
    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
        pixels = list(img.getdata())
        w, h = img.size

        # Brightness stats
        brightness = [(r + g + b) / 3 for r, g, b in pixels]
        avg = sum(brightness) / len(brightness)
        mx = max(brightness)

        # Visible pixels (> 30/255)
        visible_count = sum(1 for b in brightness if b > 30)
        visible_pct = visible_count / len(brightness) * 100

        # Center region avg (center 30%)
        cx0, cy0 = int(w * 0.35), int(h * 0.35)
        cx1, cy1 = int(w * 0.65), int(h * 0.65)
        center_pixels = [img.getpixel((x, y)) for x in range(cx0, cx1)
                         for y in range(cy0, cy1)]
        center_avg = sum(sum(p) for p in center_pixels) / (len(center_pixels) * 3)

        # Hue distribution (only for visible pixels)
        hue_buckets = {"red": 0, "yellow": 0, "green": 0,
                       "cyan": 0, "blue": 0, "purple": 0, "gray": 0}
        for r, g, b in pixels:
            if max(r, g, b) < 30:
                continue  # skip dark pixels
            mx_c = max(r, g, b)
            mn_c = min(r, g, b)
            if mx_c - mn_c < 20:
                hue_buckets["gray"] += 1
                continue
            if mx_c == r:
                if g > b:
                    hue_buckets["yellow"] += 1 if g > 100 else hue_buckets["red"]
                else:
                    hue_buckets["red"] += 1
            elif mx_c == g:
                if r > b:
                    hue_buckets["yellow"] += 1
                else:
                    hue_buckets["cyan"] += 1
            else:  # mx_c == b
                if r > g:
                    hue_buckets["purple"] += 1
                else:
                    hue_buckets["blue"] += 1

        total_visible = sum(hue_buckets.values()) or 1
        hue_dist = {k: v / total_visible for k, v in hue_buckets.items()}
        dominant = max(hue_dist, key=hue_dist.get)

        # Verdict
        if avg < 5:
            verdict = "pitch_black"
        elif avg < 15:
            verdict = "too_dark"
        elif avg < 30:
            verdict = "dark"
        elif avg > 200:
            verdict = "too_bright"
        elif avg > 100:
            verdict = "bright"
        else:
            verdict = "ok"

        return {
            "avg_brightness": round(avg, 2),
            "max_brightness": round(mx, 2),
            "visible_pct": round(visible_pct, 2),
            "center_avg": round(center_avg, 2),
            "hue_dominant": dominant,
            "hue_distribution": {k: round(v, 3) for k, v in hue_dist.items()},
            "verdict": verdict,
            "resolution": [w, h],
        }
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# Batch capture (all scenes)
# ============================================================================

def capture_all_scenes(
    scenes_config: List[Dict],
    output_dir: str,
    *,
    width: int = 1280,
    height: int = 720,
    session: str = "visual_debug",
) -> Dict:
    """Capture screenshots for multiple scenes.

    Args:
        scenes_config: [{"id": "s1", "t": 7.0, "uniforms": {...}}, ...]
        output_dir: where to save PNGs
        width, height: canvas size

    Returns:
        {screenshots: [...], summary: {...}}
    """
    os.makedirs(output_dir, exist_ok=True)
    screenshots = []

    print(f"=== Visual Debugger: capturing {len(scenes_config)} scenes ===")

    for cfg in scenes_config:
        sid = cfg["id"]
        t = cfg.get("t", DEFAULT_SCENE_TIMES.get(sid, 5.0))
        uniforms = cfg.get("uniforms", {})

        out_path = f"{output_dir}/debug_{sid}_{SCENE_EFFECTS.get(sid, sid)}.png"

        result = capture_scene_screenshot(
            sid, t, uniforms, out_path,
            width=width, height=height, session=session,
        )
        screenshots.append(result)

        if result.get("ready"):
            a = result.get("analysis", {})
            print(f"  [{sid}] OK avg={a.get('avg_brightness','?')} "
                  f"visible={a.get('visible_pct','?')}% "
                  f"verdict={a.get('verdict','?')} "
                  f"hue={a.get('hue_dominant','?')}")
        else:
            print(f"  [{sid}] FAIL: {result.get('error', 'unknown')}")

    # Summary
    verdicts = [s.get("analysis", {}).get("verdict", "error") for s in screenshots]
    avg_brights = [s.get("analysis", {}).get("avg_brightness", 0) for s in screenshots]
    summary = {
        "total": len(screenshots),
        "succeeded": sum(1 for s in screenshots if s.get("ready")),
        "failed": sum(1 for s in screenshots if not s.get("ready")),
        "verdicts": dict((s["scene"], v) for s, v in zip(screenshots, verdicts) if "scene" in s),
        "avg_brightness_by_scene": dict(
            (s["scene"], b) for s, b in zip(screenshots, avg_brights) if "scene" in s
        ),
        "dark_scenes": [s["scene"] for s, v in zip(screenshots, verdicts)
                        if "scene" in s and v in ("pitch_black", "too_dark", "dark")],
        "bright_scenes": [s["scene"] for s, v in zip(screenshots, verdicts)
                          if "scene" in s and v in ("bright", "too_bright")],
    }

    return {"screenshots": screenshots, "summary": summary}


# ============================================================================
# Parse .smt to extract scene configs
# ============================================================================

def parse_smt_for_scenes(smt_path: str) -> List[Dict]:
    """Parse .smt file, extract per-scene uniforms and capture times.

    Returns list of {id, effect, t_capture, uniforms}
    """
    scenes = []
    current_clip = None
    current_uniform = None

    with open(smt_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("clip ") and " scene " in line:
                parts = line.split()
                clip_id = parts[1]
                effect = parts[4] if len(parts) > 4 else ""
                start_str = parts[5] if len(parts) > 5 else "0"
                try:
                    start_t = float(start_str)
                except ValueError:
                    start_t = 0.0
                # Capture time = start + 2s (user requirement)
                t_capture = start_t + 2.0
                current_clip = {
                    "id": clip_id,
                    "effect": effect,
                    "t_capture": t_capture,
                    "uniforms": {},
                }
                scenes.append(current_clip)
            elif line.startswith("uni ") and current_clip:
                parts = line.split()
                current_uniform = parts[1]
            elif line.startswith("prog 1 n:") and current_clip and current_uniform:
                val_str = line.split("n:")[1].strip()
                try:
                    val = float(val_str)
                    current_clip["uniforms"].setdefault(current_uniform, []).append(val)
                except ValueError:
                    pass
            elif line.startswith("endclip"):
                current_clip = None
                current_uniform = None

    # Convert lists of 3 floats to vec3 uniforms
    for s in scenes:
        for uname, vals in list(s["uniforms"].items()):
            if len(vals) == 3:
                s["uniforms"][uname] = vals
            elif len(vals) == 1:
                s["uniforms"][uname] = vals[0]

    return scenes


# ============================================================================
# Uroboros patch interface
# ============================================================================

def apply(context, params):
    """Uroboros patch entry point.

    Params:
      scenes: list of {id, t, uniforms} (optional — defaults to all 7)
      smt_path: path to .smt file (optional — extract scenes from here)
      output_dir: where to save PNGs (default /tmp/visual_debug_shots)
      width, height: canvas dimensions

    Returns:
      {screenshots, summary, source}
    """
    output_dir = params.get("output_dir", "/tmp/visual_debug_shots")
    width = params.get("width", 1280)
    height = params.get("height", 720)

    # Get scene configs
    if "scenes" in params:
        scenes_config = params["scenes"]
        source = "param"
    elif "smt_path" in params:
        scenes_config = parse_smt_for_scenes(params["smt_path"])
        # Convert to expected format
        scenes_config = [
            {"id": s["id"], "t": s["t_capture"], "uniforms": s["uniforms"]}
            for s in scenes_config if s["id"].startswith("s") and not s["id"].startswith("s_")
        ]
        source = f"smt:{params['smt_path']}"
    else:
        # Default: all 7 scenes, no uniform overrides
        scenes_config = [
            {"id": sid, "t": t, "uniforms": {}}
            for sid, t in DEFAULT_SCENE_TIMES.items()
        ]
        source = "default"

    result = capture_all_scenes(
        scenes_config, output_dir,
        width=width, height=height,
    )

    return {
        "source": source,
        "output_dir": output_dir,
        "screenshots": result["screenshots"],
        "summary": result["summary"],
    }


# ============================================================================
# CLI standalone mode
# ============================================================================

def _cli():
    import argparse
    parser = argparse.ArgumentParser(description="Uroboros Visual Debugger")
    parser.add_argument("--scene", help="Scene ID (s1..s7) or effect name")
    parser.add_argument("--t", type=float, default=5.0, help="Time T (seconds)")
    parser.add_argument("--uPrimaryColor", help="r,g,b (0..1)")
    parser.add_argument("--uAccentColor", help="r,g,b (0..1)")
    parser.add_argument("--uColor", help="r,g,b (0..1)")
    parser.add_argument("--uLightColor", help="r,g,b (0..1)")
    parser.add_argument("--uIntensity", type=float, help="float")
    parser.add_argument("--uMotionSpeed", type=float, help="float")
    parser.add_argument("--uWarmth", type=float, help="float")
    parser.add_argument("--uPulse", type=float, help="float")
    parser.add_argument("--uSeed", type=int, default=2026, help="int")
    parser.add_argument("--smt", help="Path to .smt file (capture all scenes)")
    parser.add_argument("--output-dir", default="/tmp/visual_debug_shots",
                        help="Output directory for PNGs")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()

    if args.smt:
        # Batch mode from .smt
        result = apply({}, {
            "smt_path": args.smt,
            "output_dir": args.output_dir,
            "width": args.width,
            "height": args.height,
        })
        print("\n=== Summary ===")
        print(json.dumps(result["summary"], indent=2))
    elif args.scene:
        # Single scene
        uniforms = {}
        for arg_name in ["uPrimaryColor", "uAccentColor", "uColor",
                         "uLightColor"]:
            val = getattr(args, arg_name)
            if val:
                uniforms[arg_name] = [float(x) for x in val.split(",")]
        for arg_name in ["uIntensity", "uMotionSpeed", "uWarmth",
                         "uPulse", "uSeed"]:
            val = getattr(args, arg_name)
            if val is not None:
                uniforms[arg_name] = val

        out_path = f"{args.output_dir}/debug_{args.scene}.png"
        os.makedirs(args.output_dir, exist_ok=True)
        result = capture_scene_screenshot(
            args.scene, args.t, uniforms, out_path,
            width=args.width, height=args.height,
        )
        print(json.dumps(result, indent=2, default=str))
    else:
        # Default: all 7 scenes
        result = apply({}, {
            "output_dir": args.output_dir,
            "width": args.width,
            "height": args.height,
        })
        print("\n=== Summary ===")
        print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    _cli()
