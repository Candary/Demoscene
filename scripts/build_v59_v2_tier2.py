"""v59-v2: v58 demo rebuilt with FULL Tier 2 pipeline.

Uses:
- Color Matrix: query colors by mood for each scene (instead of hardcoded hex)
- Cozy Engine: auto-generate room primitives (instead of manual 120 floats)
- Python Scene Manager toolchain: bake show JSON → .smt
- v58 timing/structure: 7 scenes + 6 transitions + 3 post, 211s

Output: /home/z/my-project/download/demo_intro_v59_v2/
"""
import sys, os, shutil, json
sys.path.insert(0, '/home/z/my-project/scene_manager/output')
sys.path.insert(0, '/home/z/my-project/color_matrix/output')
sys.path.insert(0, '/home/z/my-project')

from color_matrix_python.reader import FullRGBMatrixReader
from color_matrix_python.tools import ColorToolbox
from cozy_engine.tools import CozyToolbox
from scene_manager.effects import EffectCatalog
from scene_manager.session import ShowSession
from scene_manager.graph import plan
from scene_manager.bake import bake, to_smt

# ============================================================================
# 1. Setup: load all toolboxes
# ============================================================================
print("=== Loading toolboxes ===")

# Color Matrix
V11 = '/home/z/my-project/color_matrix/output/color-matrix-full-rgb-v11.npz'
color_tb = ColorToolbox(FullRGBMatrixReader(V11))
print(f"Color Matrix: loaded ({V11})")

# Cozy Engine
COZY_DIR = '/home/z/my-project/cozy_engine/data'
cozy_tb = CozyToolbox.from_dir(COZY_DIR, color_tb)
print(f"Cozy Engine: loaded ({COZY_DIR})")

# Scene Manager catalog
cat = EffectCatalog.from_dir('/home/z/my-project/scene_manager/examples/effects')
print(f"Effect catalog: {len(cat.effects)} effects")

# ============================================================================
# 2. Query Color Matrix for mood-driven colors per scene
# ============================================================================
print("\n=== Querying Color Matrix for scene palettes ===")

SCENE_MOODS = {
    "s1": "anxiety",      # nebula — dark, tense intro
    "s2": "warmth",       # sphere — warm, inviting
    "s3": "delight",      # particle_swarm — energetic, bright
    "s4": "anxiety",      # anxiety_mist — dark, anxious
    "s5": "warmth",       # morph_grid — warm, morphing
    "s6": "warmth",       # cozy_room — warm, cozy
    "s7": "delight",      # morphing_figures — bright, playful
}

scene_colors = {}
for sid, mood in SCENE_MOODS.items():
    r = color_tb.dispatch("find_colors", {"feel": mood, "count": 2})
    if "error" in r or r.get("ok") is False:
        print(f"  {sid} ({mood}): FALLBACK to v58 values")
        scene_colors[sid] = None
    else:
        primary = r["candidates"][0]["rgb"]
        accent = r["candidates"][1]["rgb"]
        scene_colors[sid] = {"primary": primary, "accent": accent}
        print(f"  {sid} ({mood}): primary={[round(x,3) for x in primary]} "
              f"accent={[round(x,3) for x in accent]} "
              f"empathy={r['candidates'][0].get('empathy', '?')}")

# ============================================================================
# 3. Generate cozy_room primitives via Cozy Engine
# ============================================================================
print("\n=== Generating cozy_room primitives via Cozy Engine ===")

cozy_result = cozy_tb.dispatch("build_cozy_asset", {
    "name": "room",
    "placements": [
        {"item": "sofa", "pos": [0, -1.0, -1.5]},
        {"item": "coffee_table", "pos": [0, -0.8, 0.5]},
        {"item": "lamp", "pos": [-1.5, 0.5, -1.5]},
        {"item": "armchair", "pos": [1.5, -0.8, -1.0]},
        {"item": "artwork", "pos": [0, 1.0, -2.4]},
    ],
    "room_size": [5, 3.0],
    "slot_colors": {"upholstery": "#8b4513"}
})

if "error" in cozy_result:
    print(f"  FALLBACK: using v58 hardcoded primitives")
    cozy_prims = None
else:
    # Extract primitive data
    lay = cozy_result.get("layout", cozy_result.get("primitives", []))
    if isinstance(lay, list) and len(lay) > 0:
        # Try to flatten the layout into uPrimitives format
        cozy_prims = []
        for item in lay:
            if isinstance(item, dict):
                # Each item has: shape, size, pos, rot, color
                shape = item.get("shape", 0)  # 0=box, 1=sphere, 2=cylinder
                axis = 0
                sx, sy, sz = item.get("size", [1, 1, 1])
                px, py, pz = item.get("pos", [0, 0, 0])
                rot = item.get("rot", 0)
                r, g, b = item.get("color", [0.5, 0.5, 0.5])
                cozy_prims.extend([shape, axis, sx, sy, sz, px, py, pz, rot, r, g, b])
            elif isinstance(item, (list, tuple)) and len(item) == 12:
                cozy_prims.extend(item)
        print(f"  Generated {len(cozy_prims)//12} primitives ({len(cozy_prims)} floats)")
    else:
        print(f"  Unexpected format: {type(lay)}")
        cozy_prims = None

# Fallback: v58 primitives if Cozy Engine didn't produce usable data
V58_COZY_PRIMS = [
    0,0, 5.0,0.1,5.0,    0.0,-1.5, 0.0, 0.0, 0.80,0.70,0.50,
    0,0, 5.0,3.0,0.1,    0.0, 0.0,-2.5, 0.0, 0.40,0.30,0.25,
    0,0, 0.1,3.0,5.0,   -2.5, 0.0, 0.0, 0.0, 0.50,0.35,0.25,
    0,0, 0.1,3.0,5.0,    2.5, 0.0, 0.0, 0.0, 0.50,0.35,0.25,
    0,0, 1.5,0.1,1.0,    0.0,-0.5, 0.0, 0.0, 0.40,0.25,0.15,
    1,0, 0.20,0.20,0.20, 0.0, 0.10,0.0, 0.0, 1.00,0.85,0.40,
    2,0, 0.08,0.10,0.08, 0.5,-0.42,0.3, 0.0, 0.90,0.90,0.95,
    0,0, 0.30,0.05,0.40,-0.4,-0.43,0.2, 0.3, 0.70,0.20,0.20,
    2,0, 0.15,0.25,0.15,-1.8,-1.20,1.5, 0.0, 0.55,0.30,0.20,
    0,0, 1.5,1.5,0.05,   2.4, 0.30,-1.0,0.0, 0.70,0.85,1.00,
]

if not cozy_prims or len(cozy_prims) < 12:
    print("  Using v58 fallback primitives (10 prims × 12 floats)")
    cozy_prims = V58_COZY_PRIMS

assert len(cozy_prims) % 12 == 0, f"primitives not multiple of 12: {len(cozy_prims)}"
print(f"  Final: {len(cozy_prims)//12} primitives, {len(cozy_prims)} floats")

# ============================================================================
# 4. Build show JSON with auto-generated colors
# ============================================================================
print("\n=== Building show JSON ===")

def get_color(sid, role, fallback):
    """Get color from Color Matrix (0-255 → 0-1 conversion) or fallback to v58 value."""
    sc = scene_colors.get(sid)
    if sc:
        rgb = sc.get(role, fallback)
        # Color Matrix returns 0-255, shader expects 0-1
        return [x / 255.0 for x in rgb]
    return fallback

show = {
    "format": "scene-manager/1",
    "meta": {
        "title": "v59-v2: v58 with Color Matrix + Cozy Engine",
        "duration": 211,
        "resolution": [1280, 720],
        "fps": 60,
        "seed": 2026,
        "prewarm": 3.0,
    },
    "audio": {"bpm": 128.0, "offset": 0.0, "beats_per_bar": 4, "markers": []},
    "palettes": {"p": {"primary": "#000000", "accent": "#ffffff"}},
    "looks": {},
    "tracks": [
        {"id": "main", "order": 10},
        {"id": "post", "order": 25},
        {"id": "evt", "order": 30},
    ],
    "clips": [
        # === 7 scenes with Color Matrix colors ===
        {"id": "s1", "track": "main", "kind": "scene", "effect": "nebula_raymarch",
         "start": 0, "duration": 25, "palette": "p",
         "map": {"uPrimaryColor": get_color("s1", "primary", [0.05, 0.10, 0.30]),
                 "uAccentColor":  get_color("s1", "accent",  [0.20, 0.60, 0.90]),
                 "uIntensity":    0.8, "uMotionSpeed": 1.0, "uPulse": 0.0}},
        {"id": "s2", "track": "main", "kind": "scene", "effect": "sphere_scene",
         "start": 25, "duration": 25, "palette": "p",
         "map": {"uColor": get_color("s2", "primary", [0.1, 0.5, 0.8]),
                 "uGlow": 1.2, "uOrbit": 0.0}},
        {"id": "s3", "track": "main", "kind": "scene", "effect": "particle_swarm",
         "start": 50, "duration": 25, "palette": "p",
         "map": {"uColor": get_color("s3", "primary", [0.95, 0.2, 0.55]),
                 "uSwarm": 0.7, "uBeatKick": 0.0}},
        {"id": "s4", "track": "main", "kind": "scene", "effect": "anxiety_mist",
         "start": 75, "duration": 25, "palette": "p",
         "map": {"uPrimaryColor": get_color("s4", "primary", [0.25, 0.05, 0.10]),
                 "uAccentColor":  get_color("s4", "accent",  [0.80, 0.15, 0.10]),
                 "uIntensity": 1.2, "uMotionSpeed": 1.5, "uWarmth": 0.85}},
        {"id": "s5", "track": "main", "kind": "scene", "effect": "morph_grid",
         "start": 100, "duration": 25, "palette": "p",
         "map": {"uColor": get_color("s5", "primary", [0.30, 0.60, 0.90]),
                 "uMorph": 0.5, "uSpeed": 1.0}},
        {"id": "s6", "track": "main", "kind": "scene", "effect": "cozy_room_sdf",
         "start": 125, "duration": 55, "palette": "p",
         "map": {"uLightColor": get_color("s6", "primary", [1.0, 0.85, 0.6]),
                 "uCamAngle": 0.4},
         "arrays": {"uPrimitives": cozy_prims}},
        {"id": "s7", "track": "main", "kind": "scene", "effect": "morphing_figures",
         "start": 181, "duration": 30, "palette": "p", "map": {}},

        # === 6 transitions (flash with visible uColor/uPeak) ===
        {"id": "t1", "track": "main", "kind": "transition", "effect": "crossfade",
         "start": 23, "duration": 4, "between": ["s1", "s2"], "palette": "p", "map": {}},
        {"id": "t2", "track": "main", "kind": "transition", "effect": "flash",
         "start": 48, "duration": 4, "between": ["s2", "s3"], "palette": "p",
         "map": {"uColor": [1.0, 1.0, 1.0], "uPeak": 1.0}},
        {"id": "t3", "track": "main", "kind": "transition", "effect": "crossfade",
         "start": 73, "duration": 4, "between": ["s3", "s4"], "palette": "p", "map": {}},
        {"id": "t4", "track": "main", "kind": "transition", "effect": "flash",
         "start": 98, "duration": 4, "between": ["s4", "s5"], "palette": "p",
         "map": {"uColor": [1.0, 1.0, 1.0], "uPeak": 1.0}},
        {"id": "t5", "track": "main", "kind": "transition", "effect": "crossfade",
         "start": 123, "duration": 4, "between": ["s5", "s6"], "palette": "p", "map": {}},
        {"id": "t6", "track": "main", "kind": "transition", "effect": "crossfade",
         "start": 180, "duration": 1, "between": ["s6", "s7"], "palette": "p", "map": {}},

        # === 3 post ===
        {"id": "blm", "track": "post", "kind": "post", "effect": "bloom",
         "start": 0, "duration": 211, "palette": "p",
         "map": {"uThreshold": 0.6, "uIntensity": 1.0, "uRadius": 4.0}},
        {"id": "vig", "track": "post", "kind": "post", "effect": "vignette",
         "start": 0, "duration": 211, "palette": "p",
         "map": {"uStrength": 0.35, "uSoftness": 0.5}},
        {"id": "grn", "track": "post", "kind": "post", "effect": "grain",
         "start": 0, "duration": 211, "palette": "p",
         "map": {"uAmount": 0.20}},

        {"id": "fin", "track": "evt", "kind": "event", "effect": "finish",
         "start": 211, "duration": 0, "palette": "p", "map": {}},
    ],
}

# ============================================================================
# 5. Bake
# ============================================================================
print("\n=== Baking .smt ===")
session = ShowSession(show, cat)
resolved = session.compile()
print(f"Resolved: {len(resolved.clips)} clips, errors={len(resolved.errors)}")
if resolved.errors:
    for e in resolved.errors[:5]:
        print(f"  ERROR: {e}")
    sys.exit(1)

segs = plan(resolved, cat)
baked = bake(resolved, cat, show, segs)
smt_text = to_smt(baked)
print(f"Baked: {len(smt_text.splitlines())} lines, {len(smt_text)} bytes")

# ============================================================================
# 6. Post-process: patch audio + sections + seeds
# ============================================================================
print("\n=== Post-processing ===")

# v58 energy curve (53 values)
V58_ENERGY = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.55, 0.60, 0.70, 0.78, 0.82, 0.85, 0.88,
              0.92, 0.98, 1.00, 1.00, 0.98, 0.92, 0.85, 0.90, 0.95, 0.92, 0.88, 0.85,
              0.92, 1.00, 1.00, 0.98, 0.92, 0.85, 0.78, 0.70, 0.62, 0.55, 0.48, 0.40,
              0.33, 0.27, 0.22, 0.18, 0.15, 0.12, 0.10, 0.08,
              0.20, 0.30, 0.40, 0.50, 0.55, 0.50, 0.45, 0.40]

# v58 seeds
V58_SEEDS = {
    "s1": "11111", "s2": "22222", "s3": "33333", "s4": "44444",
    "s5": "55555", "s6": "66666", "s7": "77777",
    "t1": "10101", "t2": "20202", "t3": "30303", "t4": "40404",
    "t5": "50505", "t6": "60606",
    "blm": "77007", "vig": "99001", "grn": "88008", "fin": "77777",
}

lines = smt_text.splitlines()
patched = []
for line in lines:
    # Patch audio line
    if line.startswith("audio "):
        patched.append(f"audio 128.0 0.0 4 0.25 53 " + " ".join(f"{e:.2f}" for e in V58_ENERGY))
        continue
    # Patch sections line
    if line.startswith("sections "):
        patched.append("sections 5 0.0 27.0 77.0 127.0 181.0")
        continue
    # Patch seeds
    if line.startswith("clip "):
        parts = line.split()
        clip_id = parts[1]
        if clip_id in V58_SEEDS:
            parts[10] = V58_SEEDS[clip_id]
            line = " ".join(parts)
    patched.append(line)
smt_text = "\n".join(patched) + "\n"
print(f"Patched: audio (53 values), sections (5), seeds (17 clips)")

# Post-process: add uPrimitives array to cozy_room_sdf (s6) clip
# Python baker doesn't include arrays field — add manually
COZY_PRIMS_STR = " ".join(f"{x:.4f}" for x in cozy_prims)
ARR_LINE = f"arr uPrimitives {len(cozy_prims)} {COZY_PRIMS_STR}"

lines = smt_text.splitlines()
with_array = []
in_s6 = False
for line in lines:
    if line.startswith("clip s6 "):
        in_s6 = True
    if in_s6 and line == "endclip":
        with_array.append(ARR_LINE)
        in_s6 = False
    with_array.append(line)
smt_text = "\n".join(with_array) + "\n"
print(f"Added uPrimitives array ({len(cozy_prims)} floats, {len(cozy_prims)//12} prims)")

# ============================================================================
# 7. Save to v59_v2 directory
# ============================================================================
DST = '/home/z/my-project/download/demo_intro_v59_v2'
if os.path.exists(DST):
    shutil.rmtree(DST)

# Copy from v58 milestone (same C++ code + shaders)
SRC = '/home/z/my-project/download/milestone_v58_stable'
if not os.path.exists(SRC):
    # If v58 milestone gone, use GitHub clone
    SRC = '/home/z/demo-runtime-publish/milestone_v58_stable'
shutil.copytree(SRC, DST)
if os.path.exists(os.path.join(DST, 'demo.smt')):
    os.remove(os.path.join(DST, 'demo.smt'))
if os.path.exists(os.path.join(DST, 'MILESTONE.txt')):
    os.remove(os.path.join(DST, 'MILESTONE.txt'))

with open(os.path.join(DST, 'demo.smt'), 'w') as f:
    f.write(smt_text)
print(f"\nSaved: {DST}/demo.smt ({len(smt_text.splitlines())} lines)")

# Update demo_runtime.cpp version
with open(os.path.join(DST, 'demo_runtime.cpp')) as f:
    src = f.read()
src = src.replace('Demo Runtime v58', 'Demo Runtime v59v2')
src = src.replace('Demo Runtime v59', 'Demo Runtime v59v2')
with open(os.path.join(DST, 'demo_runtime.cpp'), 'w') as f:
    f.write(src)
print(f"Updated: demo_runtime.cpp (version → v59v2)")

# Save show JSON for reference
with open(os.path.join(DST, 'demo.show.json'), 'w') as f:
    json.dump(show, f, indent=2, ensure_ascii=False)
print(f"Saved: demo.show.json (source spec)")

# Summary
print(f"\n{'='*60}")
print(f"v59-v2 BUILT — v58 with Color Matrix + Cozy Engine")
print(f"{'='*60}")
print(f"Colors: Color Matrix ({sum(1 for v in scene_colors.values() if v)}/7 scenes auto)")
print(f"Primitives: Cozy Engine ({len(cozy_prims)//12} prims) + v58 fallback")
print(f"Energy: v58 curve (53 values)")
print(f"Seeds: v58 exact (11111, 22222, ...)")
print(f".smt: {len(smt_text.splitlines())} lines, Python-generated")
