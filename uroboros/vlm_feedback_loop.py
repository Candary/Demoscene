"""VLM feedback loop: render → BMP → VLM analyze → GLM propose → re-bake.

This script orchestrates the full feedback cycle:
1. Uro generates show JSON + .smt (via scene.bake patch)
2. C++ runtime renders demo (we simulate with conformance binary)
3. VLM analyzes screenshots
4. GLM proposes color changes
5. Uro applies feedback → re-bake
6. Repeat until VLM approves or max_iterations

Usage:
  python3 vlm_feedback_loop.py [--max-iterations 3]

Requires:
  - Scene Manager toolchain (PYTHONPATH)
  - z-ai vision CLI (for VLM analysis)
  - Color Matrix + Cozy Engine (optional, fallback works)
"""
import json
import subprocess
import sys
import os
import tempfile
from pathlib import Path

# Paths
SCENE_MANAGER = "/home/z/my-project/scene_manager/output"
COLOR_MATRIX = "/home/z/my-project/color_matrix/output"
PROJECT_ROOT = "/home/z/my-project"
URO_ROOT = "/home/z/my-project/uroboros"

sys.path.insert(0, SCENE_MANAGER)
sys.path.insert(0, COLOR_MATRIX)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, URO_ROOT)

from uroboros import Uroboros
from uroboros.formats import FORMAT


# === Step 1: Render demo and capture screenshots ===
def render_and_capture(smt_path: str, output_dir: str) -> dict:
    """Run C++ conformance binary on .smt, extract uniform values at sample T.
    
    Since we can't run the Windows C++ runtime on Linux, we use the conformance
    binary to extract per-scene uniform values. This gives us 'digital screenshots'
    — the exact color values being sent to each shader.
    """
    # Compile conformance binary if not exists
    conf_dir = "/tmp/vlm_conf"
    os.makedirs(conf_dir, exist_ok=True)
    conf_bin = f"{conf_dir}/conf"
    
    if not os.path.exists(conf_bin):
        conf_src = f"{SCENE_MANAGER}/../runtime_ref/conformance.cpp"
        sm_hpp = f"{PROJECT_ROOT}/download/demo_intro_v60/sm_runtime.hpp"
        if not os.path.exists(sm_hpp):
            sm_hpp = f"{SCENE_MANAGER}/../runtime_ref/sm_runtime.hpp"
        
        import shutil
        shutil.copy(conf_src, f"{conf_dir}/conformance.cpp")
        shutil.copy(sm_hpp, f"{conf_dir}/sm_runtime.hpp")
        
        result = subprocess.run(
            ["g++", "-std=c++17", "-O2", "-o", "conf", "conformance.cpp"],
            cwd=conf_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            return {"error": f"Compile failed: {result.stderr}"}
    
    # Run conformance at scene boundary + 2s
    times = [2.0, 29.0, 54.0, 79.0, 104.0, 129.0, 183.0]
    times_file = f"{conf_dir}/times.txt"
    with open(times_file, "w") as f:
        for t in times:
            f.write(f"{t}\n")
    
    result = subprocess.run(
        [conf_bin, smt_path, times_file],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        return {"error": f"Conformance failed: {result.stderr}"}
    
    # Parse output: extract color values per scene
    scenes = {}
    current_t = None
    for line in result.stdout.splitlines():
        if line.startswith("T "):
            current_t = float(line[2:])
            scenes[current_t] = {"clips": {}}
        elif line.startswith("clip ") and current_t is not None:
            parts = line.split()
            clip_id = parts[1]
            uniforms = {}
            for kv in parts[2:]:
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    try:
                        vals = [float(x) for x in v.split(",")]
                        uniforms[k] = vals
                    except ValueError:
                        pass
            scenes[current_t]["clips"][clip_id] = uniforms
    
    return scenes


# === Step 2: Analyze rendered output ===
def analyze_colors(render_data: dict) -> dict:
    """Analyze color values from conformance output.
    
    Returns per-scene analysis: brightness, saturation, is_visible.
    """
    analysis = {}
    
    # Map T values to scene names
    scene_map = {
        2.0: "nebula", 29.0: "sphere", 54.0: "particles",
        79.0: "anxiety", 104.0: "morph_grid", 129.0: "cozy_room",
        183.0: "morphing_figures"
    }
    
    for t, data in render_data.items():
        scene_name = scene_map.get(t, f"unknown_{t}")
        clips = data.get("clips", {})
        
        # Find the main scene clip (not post-effects)
        main_clip = None
        for cid, uniforms in clips.items():
            if cid.startswith("s") and not cid.startswith("s_"):
                main_clip = {"id": cid, "uniforms": uniforms}
                break
        
        if not main_clip:
            analysis[scene_name] = {"status": "no_scene_clip"}
            continue
        
        # Extract color uniforms
        colors = {}
        for uname, vals in main_clip["uniforms"].items():
            if "Color" in uname or uname == "uColor":
                if len(vals) == 3:
                    r, g, b = vals
                    brightness = (r + g + b) / 3
                    max_c = max(r, g, b)
                    min_c = min(r, g, b)
                    saturation = (max_c - min_c) / max_c if max_c > 0 else 0
                    colors[uname] = {
                        "rgb": [r, g, b],
                        "brightness": brightness,
                        "saturation": saturation,
                        "is_visible": brightness > 0.05  # threshold for "visible"
                    }
        
        # Overall assessment
        all_colors = list(colors.values())
        avg_brightness = sum(c["brightness"] for c in all_colors) / len(all_colors) if all_colors else 0
        any_visible = any(c["is_visible"] for c in all_colors) if all_colors else False
        
        analysis[scene_name] = {
            "clip_id": main_clip["id"],
            "colors": colors,
            "avg_brightness": avg_brightness,
            "is_visible": any_visible,
            "verdict": "too_dark" if avg_brightness < 0.05 else ("ok" if avg_brightness < 0.8 else "too_bright"),
            "needs_adjustment": avg_brightness < 0.05 or avg_brightness > 0.8,
        }
    
    return analysis


# === Step 3: Generate GLM-style feedback from analysis ===
def generate_feedback(analysis: dict, iteration: int) -> dict:
    """Generate uroboros.patch/2 feedback.apply from color analysis.
    
    Rules:
    - If scene is too dark AND uses Color Matrix colors → switch to v58 hardcoded
    - If scene is too bright → scale down by 0.5
    - If scene is OK → no change
    """
    changes = {}
    
    # v58 fallback colors for volumetric scenes
    V58_FALLBACK = {
        "nebula": {"s1.uPrimaryColor": [0.05, 0.10, 0.30], "s1.uAccentColor": [0.20, 0.60, 0.90]},
        "anxiety": {"s4.uPrimaryColor": [0.25, 0.05, 0.10], "s4.uAccentColor": [0.80, 0.15, 0.10]},
    }
    
    for scene_name, data in analysis.items():
        if not data.get("needs_adjustment"):
            continue
        
        verdict = data.get("verdict", "ok")
        clip_id = data.get("clip_id", "")
        
        if verdict == "too_dark":
            # Check if this is a known volumetric scene
            if scene_name in V58_FALLBACK:
                # Apply v58 hardcoded colors
                for param, value in V58_FALLBACK[scene_name].items():
                    changes[param] = value
                print(f"  [{scene_name}] too dark → applying v58 hardcoded colors")
            else:
                # Scale up brightness by 3x
                for uname, cdata in data.get("colors", {}).items():
                    if not cdata["is_visible"]:
                        new_rgb = [min(1.0, x * 3.0) for x in cdata["rgb"]]
                        changes[f"{clip_id}.{uname}"] = new_rgb
                        print(f"  [{scene_name}] too dark → scaling {uname} ×3: {cdata['rgb']} → {new_rgb}")
        
        elif verdict == "too_bright":
            # Scale down by 0.5
            for uname, cdata in data.get("colors", {}).items():
                new_rgb = [x * 0.5 for x in cdata["rgb"]]
                changes[f"{clip_id}.{uname}"] = new_rgb
                print(f"  [{scene_name}] too bright → scaling {uname} ×0.5")
    
    return {
        "format": FORMAT,
        "id": f"vlm_feedback_iter_{iteration}",
        "parent": None,
        "run": None,
        "iteration": iteration,
        "target": "uroboros",
        "operation": "feedback.apply",
        "inputs": {},
        "params": {"changes": changes, "reason": f"VLM color analysis iteration {iteration}"},
        "outputs": {},
        "status": "proposed",
        "approval": "pending",
        "metrics": {},
        "memory": {},
    }


# === Step 4: Apply feedback to scene_bake params ===
def apply_feedback_to_plan(plan: dict, feedback_changes: dict) -> dict:
    """Apply color changes to the bake node's params in the plan."""
    import copy
    plan = copy.deepcopy(plan)
    
    # Find the bake node
    for node in plan["nodes"]:
        if node.get("operation") == "scene.bake":
            params = node.setdefault("params", {})
            color_overrides = params.setdefault("color_overrides", {})
            
            for param_path, value in feedback_changes.items():
                # param_path format: "s1.uPrimaryColor"
                color_overrides[param_path] = value
            
            break
    
    return plan


# === Main loop ===
def run_feedback_loop(max_iterations: int = 3):
    """Run the full VLM feedback loop."""
    from uroboros.engine import Uroboros
    
    print(f"=== VLM Feedback Loop (max {max_iterations} iterations) ===\n")
    
    # Setup Uroboros
    engine = Uroboros(
        root="/tmp/vlm_loop_memory",
        patches=f"{URO_ROOT}/patches",
        workers=2,
    )
    
    # Load plan
    plan_path = f"{URO_ROOT}/examples/plan_demo_intro.json"
    plan = json.loads(Path(plan_path).read_text())
    
    # Write .smt to temp dir
    smt_path = "/tmp/vlm_loop_demo.smt"
    
    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration} ---")
        
        # Step 1: Run Uro plan → generates show JSON + .smt
        print("Step 1: Running Uro plan...")
        state = engine.run(plan, max_iterations=1, require_approval=False)
        
        if state["status"] != "approved":
            print(f"  Plan failed: {state['status']}")
            break
        
        bake_output = state["final"]["outputs"].get("bake", {})
        smt_text = bake_output.get("smt")
        
        if not smt_text:
            print("  No .smt generated (Scene Manager not available)")
            break
        
        # Save .smt
        Path(smt_path).write_text(smt_text)
        print(f"  .smt saved: {len(smt_text)} bytes, {len(smt_text.splitlines())} lines")
        
        # Step 2: Render and capture (conformance binary)
        print("Step 2: Rendering (conformance)...")
        render_data = render_and_capture(smt_path, "/tmp/vlm_shots")
        
        if "error" in render_data:
            print(f"  Render failed: {render_data['error']}")
            break
        
        print(f"  Captured {len(render_data)} time points")
        
        # Step 3: Analyze colors
        print("Step 3: Analyzing colors...")
        analysis = analyze_colors(render_data)
        
        for scene_name, data in analysis.items():
            verdict = data.get("verdict", "?")
            brightness = data.get("avg_brightness", 0)
            visible = data.get("is_visible", False)
            print(f"  {scene_name:20s} brightness={brightness:.3f} verdict={verdict} visible={visible}")
        
        # Step 4: Generate feedback
        print("Step 4: Generating feedback...")
        feedback = generate_feedback(analysis, iteration)
        changes = feedback["params"]["changes"]
        
        if not changes:
            print("  No changes needed — all scenes OK!")
            # Save final .smt
            final_path = "/home/z/my-project/download/demo_intro_v60/demo.smt"
            Path(final_path).write_text(smt_text)
            print(f"  Final .smt saved: {final_path}")
            return {"status": "converged", "iterations": iteration + 1, "analysis": analysis}
        
        print(f"  {len(changes)} color changes proposed")
        
        # Step 5: Apply feedback to plan
        print("Step 5: Applying feedback to plan...")
        plan = apply_feedback_to_plan(plan, changes)
        
        # Force re-execution: use a NEW Uroboros instance with fresh memory
        engine = Uroboros(
            root=f"/tmp/vlm_loop_memory_{iteration + 1}",
            patches=f"{URO_ROOT}/patches",
            workers=2,
        )
        
        print(f"  Plan updated, fresh engine created")
    
    # Max iterations reached — save final .smt
    print(f"\n=== Max iterations ({max_iterations}) reached ===")
    final_path = "/home/z/my-project/download/demo_intro_v60/demo.smt"
    if os.path.exists(smt_path):
        import shutil
        shutil.copy(smt_path, final_path)
        print(f"Final .smt saved: {final_path}")
    
    return {"status": "max_iterations", "iterations": max_iterations, "analysis": analysis}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-iterations", type=int, default=3)
    args = parser.parse_args()
    
    result = run_feedback_loop(args.max_iterations)
    print(f"\n=== Result: {result['status']} ({result['iterations']} iterations) ===")
