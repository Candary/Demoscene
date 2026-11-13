#!/usr/bin/env python3
"""Patch procedural fire: spread particles more, smaller size, more orange/red
gradient, less white boost (was over-saturating to flat yellow blob)."""
import re
from pathlib import Path

HTML_PATH = Path("/home/z/my-project/download/demo_intro/preview.html")
html = HTML_PATH.read_text(encoding="utf-8")

# === 1. VBO: spread particles wider, more velocity variation ===
old_vbo_loop = """    for (let p = 0; p < FIRE_PARTICLES; p++) {
        // Случайные параметры партикла (фиксируем один раз — все источники
        // используют один и тот же шаблон, отличаясь только позицией).
        const cx = (Math.random() - 0.5) * 0.10;
        const cy = (Math.random() - 0.5) * 0.05 - 0.02;
        const cz = (Math.random() - 0.5) * 0.10;
        const vx = (Math.random() - 0.5) * 0.30;
        const vy = (Math.random() - 0.5) * 0.20;
        const vz = (Math.random() - 0.5) * 0.30;
        const lt = 0.6 + Math.random() * 1.2;   // 0.6..1.8 с
        const phase = Math.random() * lt;"""

new_vbo_loop = """    for (let p = 0; p < FIRE_PARTICLES; p++) {
        // Случайные параметры партикла. Широкий разброс по стартовой позиции
        // и скорости — частицы должны выглядеть как отдельные угольки, а не
        // как один монолитный блоб.
        const ang = Math.random() * Math.PI * 2;
        const r = Math.sqrt(Math.random()) * 0.18;   // диск радиуса 0.18
        const cx = Math.cos(ang) * r;
        const cy = (Math.random() - 0.5) * 0.06;     // небольшое вертикальное смещение
        const cz = Math.sin(ang) * r;
        const spAng = Math.random() * Math.PI * 2;
        const spMag = 0.15 + Math.random() * 0.30;   // 0.15..0.45 — боковой разброс
        const vx = Math.cos(spAng) * spMag;
        const vy = (Math.random() - 0.5) * 0.25;     // лёгкий вертикальный шум
        const vz = Math.sin(spAng) * spMag;
        const lt = 0.5 + Math.random() * 1.6;   // 0.5..2.1 с — широкий разброс
        const phase = Math.random() * lt;"""

if old_vbo_loop not in html:
    raise SystemExit("ERROR: VBO loop anchor not found")
html = html.replace(old_vbo_loop, new_vbo_loop)

# === 2. Vertex shader: smaller particles, less quadratic shrink ===
old_size = "    float size = uFireSize * (vLife * vLife * 0.7 + 0.3);"
new_size = "    float size = uFireSize * (vLife * vLife * 0.5 + 0.15);"
html = html.replace(old_size, new_size)

# === 3. Fragment shader: more orange/red gradient, less white boost ===
old_firecol = """vec3 fireColor(float age) {
    vec3 whiteYellow = vec3(1.00, 0.95, 0.70);
    vec3 yellow      = vec3(1.00, 0.80, 0.25);
    vec3 orange      = vec3(1.00, 0.40, 0.10);
    vec3 red         = vec3(0.70, 0.12, 0.05);
    if (age < 0.20) return mix(whiteYellow, yellow, age / 0.20);
    if (age < 0.55) return mix(yellow, orange, (age - 0.20) / 0.35);
    return mix(orange, red, (age - 0.55) / 0.45);
}"""

new_firecol = """vec3 fireColor(float age) {
    // Насыщенный огонь: жёлто-белое ядро (родился) -> жёлтый -> оранжевый
    // -> тёмно-красный. Градиент более выраженный, чем у монохромного
    // жёлтого блоба — должны быть видны красные «хвосты».
    vec3 hotCore  = vec3(1.00, 0.85, 0.40);   // родился: тёплое жёлто-белое
    vec3 yellow   = vec3(1.00, 0.65, 0.15);
    vec3 orange   = vec3(1.00, 0.30, 0.05);
    vec3 deepRed  = vec3(0.55, 0.08, 0.02);   // умирает: тёмно-красный
    if (age < 0.15) return mix(hotCore, yellow, age / 0.15);
    if (age < 0.50) return mix(yellow, orange, (age - 0.15) / 0.35);
    return mix(orange, deepRed, (age - 0.50) / 0.50);
}"""
html = html.replace(old_firecol, new_firecol)

old_boost = "    col *= 1.0 + (1.0 - age) * 0.4;"
new_boost = "    col *= 1.0 + (1.0 - age) * 0.15;   // лёгкое усиление ядра (без перевала в белый)"
html = html.replace(old_boost, new_boost)

# === 4. Alpha falloff: tighter, less overlap between particles ===
old_alpha = "    float alpha = exp(-d2 * 2.5);"
new_alpha = "    float alpha = exp(-d2 * 4.0);   // tighter edge — меньше перекрытия"
html = html.replace(old_alpha, new_alpha)

# === 5. Render loop: smaller uFireSize multiplier ===
old_size_uniform = "            gl.uniform1f(fireU.uFireSize, radius * 3.0);"
new_size_uniform = "            gl.uniform1f(fireU.uFireSize, radius * 2.0);"
html = html.replace(old_size_uniform, new_size_uniform)

HTML_PATH.write_text(html, encoding="utf-8")
print(f"Patched: {HTML_PATH} ({len(html)} bytes)")
