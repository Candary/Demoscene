"""scene.bake — Scene Manager adapter: produces show JSON → bakes .smt.

This patch bridges Uroboros to the Scene Manager pipeline:
  Uro plan (geometry + palette + cozy) → show JSON → bake() → .smt

Inputs (from upstream nodes):
  - geometry: room layout (width, depth, footprints)
  - palette: color palette (roles, mood, source)
  - cozy: optional cozy room primitives (from cozy.plan_room)

Params:
  - scenes: list of scene effects (default: standard v58 lineup)
  - duration: total demo duration (default: 211)
  - resolution: [w, h] (default: [1280, 720])
  - fps: (default: 60)
  - seed: (default: 2026)
  - bpm: (default: 128)
  - output_dir: where to save .smt (default: "output")
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

OP = "scene.bake"

# Standard v58/v60 scene lineup
DEFAULT_SCENES = [
    ("s1", "nebula_raymarch", 0, 25, "scene"),
    ("s2", "sphere_scene", 25, 25, "scene"),
    ("s3", "particle_swarm", 50, 25, "scene"),
    ("s4", "anxiety_mist", 75, 25, "scene"),
    ("s5", "morph_grid", 100, 25, "scene"),
    ("s6", "cozy_room_sdf", 125, 55, "scene"),
    ("s7", "morphing_figures", 181, 30, "scene"),
]

# Transitions between scenes
DEFAULT_TRANSITIONS = [
    ("t1", "crossfade", 23, 4, "s1", "s2"),
    ("t2", "flash", 48, 4, "s2", "s3"),
    ("t3", "crossfade", 73, 4, "s3", "s4"),
    ("t4", "flash", 98, 4, "s4", "s5"),
    ("t5", "crossfade", 123, 4, "s5", "s6"),
    ("t6", "crossfade", 180, 1, "s6", "s7"),
]

# v58 energy curve (53 values @ rate 0.25)
V58_ENERGY = [
    0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.55,
    0.60, 0.70, 0.78, 0.82, 0.85, 0.88,
    0.92, 0.98, 1.00, 1.00, 0.98, 0.92, 0.85,
    0.90, 0.95, 0.92, 0.88, 0.85,
    0.92, 1.00, 1.00, 0.98, 0.92, 0.85,
    0.78, 0.70, 0.62, 0.55, 0.48, 0.40,
    0.33, 0.27, 0.22, 0.18, 0.15, 0.12, 0.10, 0.08,
    0.20, 0.30, 0.40, 0.50, 0.55, 0.50, 0.45, 0.40,
]

V58_SECTIONS = [{"start": 0.0}, {"start": 27.0}, {"start": 77.0}, {"start": 127.0}, {"start": 181.0}]

V58_SEEDS = {
    "s1": 11111, "s2": 22222, "s3": 33333, "s4": 44444,
    "s5": 55555, "s6": 66666, "s7": 77777,
    "t1": 10101, "t2": 20202, "t3": 30303, "t4": 40404,
    "t5": 50505, "t6": 60606,
}

# v58 hardcoded colors for volumetric scenes (Color Matrix doesn't work for these)
V58_COLORS = {
    "s1": {"uPrimaryColor": [0.05, 0.10, 0.30], "uAccentColor": [0.20, 0.60, 0.90]},
    "s4": {"uPrimaryColor": [0.25, 0.05, 0.10], "uAccentColor": [0.80, 0.15, 0.10]},
}

# v58 cozy room primitives (10 prims × 12 floats)
COZY_PRIMS = [
    0,0, 5.0,0.1,5.0, 0.0,-1.5, 0.0, 0.0, 0.80,0.70,0.50,
    0,0, 5.0,3.0,0.1, 0.0, 0.0,-2.5, 0.0, 0.40,0.30,0.25,
    0,0, 0.1,3.0,5.0,-2.5, 0.0, 0.0, 0.0, 0.50,0.35,0.25,
    0,0, 0.1,3.0,5.0, 2.5, 0.0, 0.0, 0.0, 0.50,0.35,0.25,
    0,0, 1.5,0.1,1.0, 0.0,-0.5, 0.0, 0.0, 0.40,0.25,0.15,
    1,0, 0.20,0.20,0.20, 0.0, 0.10, 0.0, 0.0, 1.00,0.85,0.40,
    2,0, 0.08,0.10,0.08, 0.5,-0.42, 0.3, 0.0, 0.90,0.90,0.95,
    0,0, 0.30,0.05,0.40,-0.4,-0.43, 0.2, 0.3, 0.70,0.20,0.20,
    2,0, 0.15,0.25,0.15,-1.8,-1.20, 1.5, 0.0, 0.55,0.30,0.20,
    0,0, 1.5,1.5,0.05, 2.4, 0.30,-1.0, 0.0, 0.70,0.85,1.00,
]


def apply(context, params):
    upstream = context.get("upstream", {})
    inputs = context.get("inputs", {})

    # v60-vlm: color overrides from feedback loop (e.g., {"s1.uPrimaryColor": [0.05, 0.10, 0.30]})
    color_overrides = params.get("color_overrides", {})

    # Extract palette from upstream (if available)
    palette_data = upstream.get("palette", {})
    palette = palette_data.get("palette", {})
    palette_source = palette_data.get("source", "fallback")

    # Extract cozy room data from upstream (if available)
    cozy_data = upstream.get("cozy", {})
    cozy_primitives = cozy_data.get("primitives", COZY_PRIMS)

    # Build show JSON
    duration = params.get("duration", 211)
    resolution = params.get("resolution", [1280, 720])
    fps = params.get("fps", 60)
    seed = params.get("seed", 2026)
    bpm = params.get("bpm", 128)

    # Use palette colors for direct-color scenes, v58 hardcoded for volumetric
    def get_color(scene_id, uniform_name, fallback):
        # v60-vlm: check color_overrides first (from feedback loop)
        override_key = f"{scene_id}.{uniform_name}"
        if override_key in color_overrides:
            return color_overrides[override_key]
        # Then check v58 hardcoded (for volumetric scenes)
        if scene_id in V58_COLORS and uniform_name in V58_COLORS[scene_id]:
            return V58_COLORS[scene_id][uniform_name]
        # Try palette — handle both dict and list formats
        if isinstance(palette, dict):
            roles = palette.get("roles", {})
        elif isinstance(palette, list):
            # palette is a list of color dicts: [{"role":"primary","hex":"#..."}, ...]
            roles = {p.get("role"): p for p in palette if isinstance(p, dict)}
        else:
            roles = {}
        if isinstance(roles, dict):
            if uniform_name == "uPrimaryColor" and "primary" in roles:
                r = roles["primary"]
                hex_val = r.get("hex", "#000000") if isinstance(r, dict) else str(r)
                return hex_to_rgb(hex_val)
            if uniform_name == "uAccentColor" and "accent" in roles:
                r = roles["accent"]
                hex_val = r.get("hex", "#ffffff") if isinstance(r, dict) else str(r)
                return hex_to_rgb(hex_val)
            if uniform_name == "uColor" and "primary" in roles:
                r = roles["primary"]
                hex_val = r.get("hex", "#000000") if isinstance(r, dict) else str(r)
                return hex_to_rgb(hex_val)
        return fallback

    def hex_to_rgb(h):
        h = h.lstrip("#")
        return [int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4)]

    clips = []

    # Scenes
    scene_configs = {
        "s1": {"uPrimaryColor": get_color("s1", "uPrimaryColor", [0.05, 0.10, 0.30]),
               "uAccentColor": get_color("s1", "uAccentColor", [0.20, 0.60, 0.90]),
               "uIntensity": 0.8, "uMotionSpeed": 1.0, "uPulse": 0.0},
        "s2": {"uColor": get_color("s2", "uColor", [0.1, 0.5, 0.8]),
               "uGlow": 1.2, "uOrbit": 0.0},
        "s3": {"uColor": get_color("s3", "uColor", [0.95, 0.2, 0.55]),
               "uSwarm": 0.7, "uBeatKick": 0.0},
        "s4": {"uPrimaryColor": get_color("s4", "uPrimaryColor", [0.25, 0.05, 0.10]),
               "uAccentColor": get_color("s4", "uAccentColor", [0.80, 0.15, 0.10]),
               "uIntensity": 1.2, "uMotionSpeed": 1.5, "uWarmth": 0.85},
        "s5": {"uColor": get_color("s5", "uColor", [0.30, 0.60, 0.90]),
               "uMorph": 0.5, "uSpeed": 1.0},
        "s6": {"uLightColor": get_color("s6", "uLightColor", [1.0, 0.85, 0.6]),
               "uCamAngle": 0.15},
        "s7": {},
    }

    for sid, effect, start, dur, kind in DEFAULT_SCENES:
        clip = {
            "id": sid, "track": "main", "kind": kind, "effect": effect,
            "start": start, "duration": dur, "palette": "p",
            "seed": V58_SEEDS.get(sid, 0),
            "map": scene_configs.get(sid, {}),
        }
        if sid == "s6":
            clip["arrays"] = {"uPrimitives": cozy_primitives}
        clips.append(clip)

    # Transitions
    for tid, effect, start, dur, a, b in DEFAULT_TRANSITIONS:
        clip = {
            "id": tid, "track": "main", "kind": "transition", "effect": effect,
            "start": start, "duration": dur, "between": [a, b],
            "palette": "p", "seed": V58_SEEDS.get(tid, 0),
            "map": {},
        }
        if effect == "flash":
            clip["map"] = {"uColor": [1.0, 1.0, 1.0], "uPeak": 1.0}
        clips.append(clip)

    # Post effects (multi-pass bloom)
    clips.extend([
        {"id": "blm_bright", "track": "post", "kind": "post", "effect": "bloom_bright",
         "start": 0, "duration": duration, "palette": "p", "seed": 77007,
         "map": {"uThreshold": 0.6, "uIntensity": 1.0}},
        {"id": "blm_blurh", "track": "post", "kind": "post", "effect": "bloom_blur",
         "start": 0, "duration": duration, "palette": "p", "seed": 77008,
         "map": {"uDirection": [1.0, 0.0]}},
        {"id": "blm_blurv", "track": "post", "kind": "post", "effect": "bloom_blur",
         "start": 0, "duration": duration, "palette": "p", "seed": 77009,
         "map": {"uDirection": [0.0, 1.0]}},
        {"id": "blm_add", "track": "post", "kind": "post", "effect": "passthrough",
         "start": 0, "duration": duration, "palette": "p", "seed": 77010, "map": {}},
        {"id": "vig", "track": "post", "kind": "post", "effect": "vignette",
         "start": 0, "duration": duration, "palette": "p", "seed": 99001,
         "map": {"uStrength": 0.35, "uSoftness": 0.5}},
        {"id": "grn", "track": "post", "kind": "post", "effect": "grain",
         "start": 0, "duration": duration, "palette": "p", "seed": 88008,
         "map": {"uAmount": 0.20}},
        {"id": "fin", "track": "evt", "kind": "event", "effect": "finish",
         "start": duration, "duration": 0, "palette": "p", "seed": 77777, "map": {}},
    ])

    show = {
        "format": "scene-manager/1",
        "meta": {
            "title": params.get("title", "Uroboros-generated demo"),
            "duration": duration,
            "resolution": resolution,
            "fps": fps,
            "seed": seed,
            "prewarm": 3.0,
        },
        "audio": {
            "bpm": float(bpm),
            "offset": 0.0,
            "beats_per_bar": 4,
            "markers": [],
            "energy": V58_ENERGY,
            "sections": V58_SECTIONS,
        },
        "palettes": {"p": {"primary": "#000000", "accent": "#ffffff"}},
        "looks": {},
        "tracks": [
            {"id": "main", "order": 10},
            {"id": "post", "order": 25},
            {"id": "evt", "order": 30},
        ],
        "clips": clips,
    }

    # Try to bake .smt using Scene Manager toolchain
    smt_text = None
    bake_error = None
    try:
        # Find scene_manager
        sm_paths = [
            Path("/home/z/my-project/scene_manager/output"),
            Path(__file__).resolve().parents[1] / "scene_manager" / "output",
            Path(__file__).resolve().parents[2] / "scene_manager" / "output",
        ]
        for sm_path in sm_paths:
            if (sm_path / "scene_manager").is_dir():
                sys.path.insert(0, str(sm_path))
                from scene_manager.effects import EffectCatalog
                from scene_manager.session import ShowSession
                from scene_manager.graph import plan
                from scene_manager.bake import bake, to_smt

                cat = EffectCatalog.from_dir(str(sm_path.parent / "examples" / "effects"))
                session = ShowSession(show, cat)
                resolved = session.compile()
                segs = plan(resolved, cat)
                baked = bake(resolved, cat, show, segs)
                smt_text = to_smt(baked)
                break
    except Exception as e:
        bake_error = str(e)

    return {
        "show_json": show,
        "smt": smt_text,
        "bake_error": bake_error,
        "source": "scene_manager" if smt_text else "show_json_only",
        "palette_source": palette_source,
        "scene_count": len(clips),
        "duration": duration,
    }
