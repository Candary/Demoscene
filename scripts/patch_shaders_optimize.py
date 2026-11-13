#!/usr/bin/env python3
"""Sync optimization patches to shaders.h (C++/OpenGL 3.3 version).

Same optimizations as preview.html:
A. Lazy SDF evaluation per morph phase.
B. Particle bounding-sphere skip in MapScene loop.
C. RayMarch 60 → 48 steps; Coarse 30 → 20.
D. DropletEffect 12 → 8 droplets.
(Q key + DPR cap are preview-only — main.cpp window size is the equivalent.)
"""
import re
import sys
from pathlib import Path

SHADERS_PATH = Path("/home/z/my-project/download/demo_intro/shaders.h")
src = SHADERS_PATH.read_text(encoding="utf-8")

# === A. Lazy SDF evaluation in MapScene ===
old_sdf_block = """    // Расстояния до девяти фигур.
    float d1 = sdSphere       (p, 1.0);
    float d2 = sdBox          (p, vec3(0.85));
    float d3 = sdTorus        (p, 0.8, 0.3);
    float d4 = sdOctahedron   (p, 1.0);
    float d5 = sdTriPrism     (p, vec2(1.0, 0.5));  // треугольник (новый)
    float d6 = sdCone         (p, 1.0, 0.9);
    float d7 = sdCapsule      (p, vec3(-0.8, -0.6, 0.0), vec3(0.8, 0.6, 0.0), 0.35);
    float d8 = sdTeapot       (p);
    float d9 = sdDodecahedron (p, 1.0);   // додекаэдр

    // Выбираем пару соседних фигур и плавно смешиваем между ними.
    float idx   = floor(phase);
    float frac_ = smoothstep(0.0, 1.0, phase - idx);

    float d_main;
    if      (idx < 0.5) d_main = mix(d1, d2, frac_);   // сфера → куб
    else if (idx < 1.5) d_main = mix(d2, d3, frac_);   // куб → тор
    else if (idx < 2.5) d_main = mix(d3, d4, frac_);   // тор → октаэдр
    else if (idx < 3.5) d_main = mix(d4, d5, frac_);   // октаэдр → треугольник
    else if (idx < 4.5) d_main = mix(d5, d6, frac_);   // треугольник → конус
    else if (idx < 5.5) d_main = mix(d6, d7, frac_);   // конус → капсула
    else if (idx < 6.5) d_main = mix(d7, d8, frac_);   // капсула → чайник
    else if (idx < 7.5) d_main = mix(d8, d9, frac_);   // чайник → додекаэдр
    else                d_main = mix(d9, d1, frac_);   // додекаэдр → сфера (петля)"""

new_sdf_block = """    // ОПТИМИЗАЦИЯ: вычисляем только 2 нужные фигуры (по текущей фазе),
    // а не все 9. Экономит 7 SDF-вызовов на каждый MapScene (× 48 шагов
    // raymarch + 4 CalcNormal = ~370 сэкономленных SDF-вызовов на пиксель).
    float idx   = floor(phase);
    float frac_ = smoothstep(0.0, 1.0, phase - idx);

    float d_main;
    if      (idx < 0.5) d_main = mix(sdSphere       (p, 1.0),
                                      sdBox          (p, vec3(0.85)), frac_);
    else if (idx < 1.5) d_main = mix(sdBox          (p, vec3(0.85)),
                                      sdTorus        (p, 0.8, 0.3), frac_);
    else if (idx < 2.5) d_main = mix(sdTorus        (p, 0.8, 0.3),
                                      sdOctahedron   (p, 1.0), frac_);
    else if (idx < 3.5) d_main = mix(sdOctahedron   (p, 1.0),
                                      sdTriPrism     (p, vec2(1.0, 0.5)), frac_);
    else if (idx < 4.5) d_main = mix(sdTriPrism     (p, vec2(1.0, 0.5)),
                                      sdCone         (p, 1.0, 0.9), frac_);
    else if (idx < 5.5) d_main = mix(sdCone         (p, 1.0, 0.9),
                                      sdCapsule      (p, vec3(-0.8, -0.6, 0.0), vec3(0.8, 0.6, 0.0), 0.35), frac_);
    else if (idx < 6.5) d_main = mix(sdCapsule      (p, vec3(-0.8, -0.6, 0.0), vec3(0.8, 0.6, 0.0), 0.35),
                                      sdTeapot       (p), frac_);
    else if (idx < 7.5) d_main = mix(sdTeapot       (p),
                                      sdDodecahedron (p, 1.0), frac_);
    else                d_main = mix(sdDodecahedron (p, 1.0),
                                      sdSphere       (p, 1.0), frac_);   // петля"""

if old_sdf_block not in src:
    print("ERROR: SDF block not found in shaders.h", file=sys.stderr); sys.exit(1)
src = src.replace(old_sdf_block, new_sdf_block)

# === B. Particle early-exit in MapScene loop ===
old_part_loop = """    for (int i = 0; i < 8; i++) {
        if (uFireMask[i] < 0.5) continue;  // частица горит — воду скрываем
        float ds = sdSphere(p - gParticlePos[i], gParticleRad[i]);
        if (ds < d_part) {
            d_part = ds;
            pid_nearest = float(i);
        }
    }"""

new_part_loop = """    for (int i = 0; i < 8; i++) {
        if (uFireMask[i] < 0.5) continue;  // частица горит — воду скрываем
        // ОПТИМИЗАЦИЯ: дешёвый квадрат расстояния перед sdSphere —
        // если частица далеко, sdSphere не нужна (length() = sqrt).
        vec3 dp = p - gParticlePos[i];
        float r = gParticleRad[i] + 0.3;
        if (dot(dp, dp) > r * r) continue;
        float ds = length(dp) - gParticleRad[i];
        if (ds < d_part) {
            d_part = ds;
            pid_nearest = float(i);
        }
    }"""

if old_part_loop not in src:
    print("ERROR: particle loop not found in shaders.h", file=sys.stderr); sys.exit(1)
src = src.replace(old_part_loop, new_part_loop)

# === C. RayMarch steps 60 → 48, Coarse 30 → 20 ===
src = src.replace(
    "    const int steps = 60;   // ОПТИМИЗАЦИЯ 3: 80 → 60 (на ~25% быстрее raymarch)\n    const float maxDist = 50.0;",
    "    const int steps = 48;   // ОПТИМИЗАЦИЯ: 60 → 48 шагов (с lazy SDF eval достаточно)\n    const float maxDist = 50.0;"
)
src = src.replace(
    "    const int steps = 30;   // вдвое меньше шагов\n    const float maxDist = 50.0;",
    "    const int steps = 20;   // ОПТИМИЗАЦИЯ: 30 → 20 шагов (преломление в каплях)\n    const float maxDist = 50.0;"
)

# === D. DropletEffect 12 → 8 droplets ===
src = src.replace(
    "    for (int i = 0; i < 12; i++) {",
    "    for (int i = 0; i < 8; i++) {   // ОПТИМИЗАЦИЯ: 12 → 8 капель"
)

SHADERS_PATH.write_text(src, encoding="utf-8")
print(f"Patched: {SHADERS_PATH} ({len(src)} bytes)")
