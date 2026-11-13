#!/usr/bin/env python3
"""
Patch preview.html and shaders.h: replace the gradient+stars background
with a domain-warped FBM nebula background matching the user's reference image.

Reference (per VLM analysis):
  - Palette: deep void (0.05, 0.02, 0.15), vibrant purple (0.6, 0.1, 0.9),
    hot pink (0.9, 0.1, 0.5), electric cyan (0.1, 0.8, 1.0),
    neon orange (1.0, 0.6, 0.1), highlight white
  - Layout: flow bottom-right -> top-left, focal cyan node ~(0.6, 0.5),
    orange glow at mid-left, pink glow at bottom-right, deep indigo bg
  - Shape: domain-warped FBM ribbons (5-octave fbm called twice for warp + once
    for value, totals ~15 noise2D calls per pixel = manageable since bg is
    computed only once per pixel except in refraction passes).
  - No stars (reference has no stars).
  - Vignette retained.
"""

from pathlib import Path

# Block of new GLSL code: helpers + NebulaBackground function.
# This text is inserted right before "vec3 RenderSceneInner" in both files.
# IMPORTANT: indentation matches existing 0-col top-level functions (no indent).
NEBULA_BLOCK = '''// --- НЕБУЛА-ФОН: domain-warped FBM, неоновые ленты -------------------
// Референс: фиолетово-синий фон с яркими циан/оранжевым/розовым световыми
// лентами, плавно текущими снизу-справа вверх-влево. Без звёзд (как на
// референсном изображении). Используется в обоих местах, где раньше был
// градиент+звёзды.
float hash21(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise2D(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm4(vec2 p) {
    // 4-октавный FBM — компромисс между детализацией и скоростью.
    // На фоне (один выз на пиксель в основном проходе) это приемлемо.
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
        v += a * noise2D(p);
        p = p * 2.02 + vec2(13.7, 5.1);
        a *= 0.5;
    }
    return v;
}

vec3 NebulaBackground(vec3 rd) {
    // 2D-проекция направления луча в экранные UV (похоже на панораму).
    // atan(z,x) -> azimuth, asin(y) -> elevation.
    vec2 uv = vec2(atan(rd.z, rd.x), asin(clamp(rd.y, -1.0, 1.0)));
    uv *= 0.6;                  // масштаб: 1 ед = ~57° поля зрения
    uv += vec2(uTime * 0.025, uTime * 0.018);  // медленный дрейф

    // Domain warping: первое FBM искажает координаты для второго FBM.
    vec2 q = uv * 1.3 + vec2(2.5, -1.5);
    vec2 warp = vec2(fbm4(q), fbm4(q + vec2(4.7, 2.1)));
    vec2 r = vec2(
        fbm4(q + warp * 1.5 + vec2(1.7, 9.2)),
        fbm4(q + warp * 1.5 + vec2(8.3, 2.8))
    );
    float f = fbm4(q + r * 1.2);

    // --- Палитра (по VLM-анализу референса) ---
    vec3 deepVoid    = vec3(0.05, 0.02, 0.15);  // тёмно-индиго в "долинах"
    vec3 vibrantPurp = vec3(0.45, 0.10, 0.70);  // доминирует слева-сверху
    vec3 hotPink    = vec3(0.90, 0.15, 0.55);  // снизу-справа
    vec3 electricCy = vec3(0.15, 0.75, 1.00);  // центр, ленты
    vec3 neonOrang  = vec3(1.00, 0.55, 0.10);  // хвост ленты слева

    // Многослойная сборка цвета
    vec3 col = deepVoid;
    col = mix(col, vibrantPurp, smoothstep(0.20, 0.55, f));
    col = mix(col, electricCy,  smoothstep(0.55, 0.80, f) * 0.85);
    col = mix(col, hotPink,    smoothstep(0.50, 0.75, length(r)) * 0.6);
    col = mix(col, neonOrang,  smoothstep(0.45, 0.60, warp.x + warp.y * 0.4) * 0.55);

    // Диагональная лента: синусоидальные "волны" вдоль направления потока
    // (снизу-справа вверх-влево = сумма координат растёт).
    float ribbon = sin((uv.x + uv.y) * 2.5 + f * 5.0 + uTime * 0.2);
    ribbon = smoothstep(0.0, 1.0, ribbon) * smoothstep(1.5, 0.5, abs(f - 0.55));
    col += electricCy * ribbon * 0.45;
    col += vec3(1.0) * pow(ribbon, 4.0) * 0.25;  // белые пики

    // --- Световые узлы (glow) ---
    // Яркий циан-узел чуть правее центра (~0.6, 0.3) — где лента изгибается
    vec2 focal1 = uv - vec2(0.6, 0.3);
    col += electricCy * exp(-dot(focal1, focal1) * 3.5) * 0.70;

    // Оранжевый хвост слева-середине
    vec2 focal2 = uv - vec2(-0.7, -0.1);
    col += neonOrang * exp(-dot(focal2, focal2) * 4.5) * 0.55;

    // Розовое свечение снизу-справа
    vec2 focal3 = uv - vec2(0.9, -0.7);
    col += hotPink * exp(-dot(focal3, focal3) * 3.5) * 0.45;

    // Пурпурное свечение сверху-слева
    vec2 focal4 = uv - vec2(-0.8, 0.6);
    col += vibrantPurp * exp(-dot(focal4, focal4) * 3.5) * 0.40;

    // Виньетка (как в оригинале)
    vec2 qv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.x;
    col *= 1.0 - 0.45 * dot(qv, qv);

    // Слегка приглушить, чтобы фигуры/частицы хорошо читались на фоне.
    col *= 0.85;

    return col;
}

'''

# Block A replacement (bounding-sphere miss case).
OLD_BS_MISS_PH = '''        float bgGrad0 = 0.5 + 0.5 * rd.y;
        vec3 bgTop0    = Palette(uTime * 0.05 + 0.0);
        vec3 bgBot0    = Palette(uTime * 0.05 + 0.4);
        vec3 bg0 = mix(bgBot0, bgTop0, bgGrad0) * 0.6;
        bg0 += vec3(StarField(rd));

        vec2 q0 = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.x;
        bg0 *= 1.0 - 0.5 * dot(q0, q0);

        return bg0;'''
NEW_BS_MISS = '''        return NebulaBackground(rd);'''

# Block B replacement (main bg, before raymarch).
OLD_BG_MAIN = '''    float bgGrad = 0.5 + 0.5 * rd.y;
    vec3 bgColTop    = Palette(uTime * 0.05 + 0.0);
    vec3 bgColBottom = Palette(uTime * 0.05 + 0.4);
    vec3 bg = mix(bgColBottom, bgColTop, bgGrad) * 0.6;
    float stars = StarField(rd);
    bg += vec3(stars);'''
NEW_BG_MAIN = '''    vec3 bg = NebulaBackground(rd);'''


def patch_file(path: Path) -> None:
    src = path.read_text(encoding='utf-8')
    orig = src

    # 1) Inject NebulaBackground helpers right before RenderSceneInner
    marker = 'vec3 RenderSceneInner(vec2 uv, bool isCoarse) {'
    if marker not in src:
        raise RuntimeError(f'{path}: RenderSceneInner marker not found')
    if 'vec3 NebulaBackground(vec3 rd) {' not in src:
        src = src.replace(marker, NEBULA_BLOCK + marker, 1)

    # 2) Replace bounding-sphere miss block
    if OLD_BS_MISS_PH not in src:
        raise RuntimeError(f'{path}: bs-miss block not found')
    src = src.replace(OLD_BS_MISS_PH, NEW_BS_MISS, 1)

    # 3) Replace main bg block
    if OLD_BG_MAIN not in src:
        raise RuntimeError(f'{path}: main bg block not found')
    src = src.replace(OLD_BG_MAIN, NEW_BG_MAIN, 1)

    if src == orig:
        raise RuntimeError(f'{path}: no changes made (logic error)')

    path.write_text(src, encoding='utf-8')
    print(f'OK {path}  (+{len(NEBULA_BLOCK)} chars injected, '
          f'{-len(OLD_BS_MISS_PH) - len(OLD_BG_MAIN) + len(NEW_BS_MISS) + len(NEW_BG_MAIN)} net bg)')


if __name__ == '__main__':
    base = Path('/home/z/my-project/download/demo_intro')
    for name in ('preview.html', 'shaders.h'):
        patch_file(base / name)
    print('Done.')
