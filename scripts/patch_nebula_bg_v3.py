#!/usr/bin/env python3
"""
V3 patch for nebula background.
V2 was washed out because focal points were in ray-angle UV space which
doesn't match screen layout — focal2 (orange) covered most of the screen
because its uv-range was offset by atan(z,x) ≈ -pi/2 at center.

V3 uses SCREEN-SPACE UV for focal points and bright color thresholds,
and uses ray-angle UV only for the FBM noise pattern.
"""
from pathlib import Path

OLD_FUNC = '''vec3 NebulaBackground(vec3 rd) {
    // 2D-проекция направления луча в панораму.
    vec2 uv = vec2(atan(rd.z, rd.x), asin(clamp(rd.y, -1.0, 1.0)));
    uv *= 0.7;                            // немного больше поля
    uv += vec2(uTime * 0.030, uTime * 0.020);

    // Domain warping — многослойный: warp -> r -> f
    vec2 q = uv * 1.4 + vec2(2.5, -1.5);
    vec2 warp = vec2(fbm4(q), fbm4(q + vec2(4.7, 2.1)));
    vec2 r = vec2(
        fbm4(q + warp * 1.8 + vec2(1.7, 9.2)),
        fbm4(q + warp * 1.8 + vec2(8.3, 2.8))
    );
    float f = fbm4(q + r * 1.5);
    float fw = warp.x + warp.y * 0.5;
    float rl = length(r);

    // --- Палитра (тёмная база, яркие акценты) ---
    vec3 deepVoid    = vec3(0.025, 0.010, 0.060);  // ОЧЕНЬ тёмное индиго
    vec3 vibrantPurp = vec3(0.30,  0.06,  0.55);   // мягкий пурпур для тонов
    vec3 hotPink    = vec3(0.95,  0.18,  0.55);   // яркое розовое
    vec3 electricCy = vec3(0.20,  0.85, 1.00);     // насыщенный циан
    vec3 neonOrang  = vec3(1.00,  0.55,  0.10);   // неоновый оранжевый
    vec3 deepBlue   = vec3(0.05,  0.12,  0.40);   // тёмно-синий

    // База — тёмный цвет, яркие акценты только в зонах высокого FBM
    vec3 col = mix(deepVoid, deepBlue, smoothstep(0.30, 0.60, f) * 0.7);
    col = mix(col, vibrantPurp, smoothstep(0.55, 0.75, f) * 0.5);
    col = mix(col, electricCy, smoothstep(0.72, 0.88, f) * 0.95);
    col = mix(col, hotPink,    smoothstep(0.70, 0.85, rl) * 0.55);
    col = mix(col, neonOrang,  smoothstep(0.70, 0.85, fw) * 0.45);

    // Диагональная лента — узкая и яркая (вдоль направления снизу-справа
    // вверх-влево, где сумма координат растёт).
    float ribbon = sin((uv.x + uv.y) * 3.0 + f * 6.0 + uTime * 0.25);
    ribbon = pow(smoothstep(-0.2, 1.0, ribbon), 2.5);
    ribbon *= smoothstep(0.55, 0.78, f);     // лента только в ярких зонах FBM
    col += electricCy * ribbon * 0.85;
    col += vec3(1.0) * pow(ribbon, 8.0) * 0.6;  // узкие белые пики

    // --- Световые узлы — узкие и яркие (HDR, чтобы ACES bloom'ил) ---
    vec2 focal1 = uv - vec2(0.6, 0.25);     // циан в центре-справа
    col += electricCy * exp(-dot(focal1, focal1) * 6.0) * 1.8;

    vec2 focal2 = uv - vec2(-0.6, -0.15);    // оранжевый слева-середине
    col += neonOrang * exp(-dot(focal2, focal2) * 7.0) * 1.4;

    vec2 focal3 = uv - vec2(0.85, -0.6);     // розовый снизу-справа
    col += hotPink * exp(-dot(focal3, focal3) * 6.0) * 1.2;

    vec2 focal4 = uv - vec2(-0.7, 0.55);     // пурпурный сверху-слева
    col += vibrantPurp * exp(-dot(focal4, focal4) * 6.0) * 1.0;

    // Лёгкая виньетка
    vec2 qv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.x;
    col *= 1.0 - 0.40 * dot(qv, qv);

    return col;
}'''

NEW_FUNC = '''vec3 NebulaBackground(vec3 rd) {
    // ---- A. Шумовой паттерн: в координатах угла луча (ray-angle UV) ----
    vec2 ruv = vec2(atan(rd.z, rd.x), asin(clamp(rd.y, -1.0, 1.0)));
    ruv *= 0.7;
    ruv += vec2(uTime * 0.030, uTime * 0.020);

    // Domain warping — многослойный.
    vec2 q = ruv * 1.4 + vec2(2.5, -1.5);
    vec2 warp = vec2(fbm4(q), fbm4(q + vec2(4.7, 2.1)));
    vec2 r = vec2(
        fbm4(q + warp * 1.8 + vec2(1.7, 9.2)),
        fbm4(q + warp * 1.8 + vec2(8.3, 2.8))
    );
    float f = fbm4(q + r * 1.5);
    float fw = warp.x + warp.y * 0.5;
    float rl = length(r);

    // ---- B. Палитра: тёмная база + редкие яркие акценты ----
    vec3 deepVoid    = vec3(0.015, 0.005, 0.040);   // почти чёрное индиго
    vec3 deepBlue   = vec3(0.020, 0.050, 0.180);   // тёмно-синий
    vec3 vibrantPurp = vec3(0.200, 0.040, 0.350);   // мягкий пурпур
    vec3 hotPink    = vec3(0.900, 0.180, 0.500);   // яркое розовое
    vec3 electricCy = vec3(0.150, 0.750, 1.000);    // насыщенный циан
    vec3 neonOrang  = vec3(1.000, 0.540, 0.080);    // неоновый оранжевый

    // База — глубокая тёмная, яркие акценты только в зонах высокого FBM.
    vec3 col = mix(deepVoid, deepBlue, smoothstep(0.35, 0.70, f) * 0.6);
    col = mix(col, vibrantPurp, smoothstep(0.60, 0.82, f) * 0.35);
    col = mix(col, electricCy, smoothstep(0.78, 0.92, f) * 0.8);
    col = mix(col, hotPink,    smoothstep(0.75, 0.90, rl) * 0.30);
    col = mix(col, neonOrang,  smoothstep(0.75, 0.90, fw) * 0.25);

    // ---- C. Screen-space UV для лент и узлов ----
    vec2 suv = (gl_FragCoord.xy / uResolution.xy - 0.5) * 2.0;
    suv.x *= uResolution.x / uResolution.y;

    // Диагональная лента — узкая, появляется только в зонах высокого FBM.
    float ribbon = sin((suv.x + suv.y) * 1.8 + f * 5.0 + uTime * 0.4);
    ribbon = pow(smoothstep(-0.4, 1.0, ribbon), 4.0);
    ribbon *= smoothstep(0.62, 0.85, f);
    col += electricCy * ribbon * 0.6;
    col += vec3(1.0) * pow(ribbon, 12.0) * 0.5;

    // ---- D. Световые узлы — в SCREEN-SPACE, очень узкие ----
    // Точку делаем ОЧЕНЬ узкой (высокий коэф. у exp), чтобы яркий HDR-пик
    // не разливался по всему экрану. Только в центре узла — пик >1.0,
    // дальше быстро падает.
    vec2 f1 = suv - vec2( 0.45,  0.05);
    float g1 = exp(-dot(f1, f1) * 22.0);
    col += electricCy * g1 * 1.5;

    vec2 f2 = suv - vec2(-0.75, -0.10);
    float g2 = exp(-dot(f2, f2) * 25.0);
    col += neonOrang * g2 * 1.3;

    vec2 f3 = suv - vec2( 0.70, -0.55);
    float g3 = exp(-dot(f3, f3) * 22.0);
    col += hotPink * g3 * 1.2;

    vec2 f4 = suv - vec2(-0.65,  0.55);
    float g4 = exp(-dot(f4, f4) * 22.0);
    col += vibrantPurp * g4 * 1.0;

    vec2 f5 = suv - vec2( 0.10, -0.70);
    float g5 = exp(-dot(f5, f5) * 20.0);
    col += deepBlue * g5 * 0.8;

    // ---- E. Виньетка ----
    col *= 1.0 - 0.30 * dot(suv, suv);

    return col;
}'''


def patch(path: Path) -> None:
    src = path.read_text(encoding='utf-8')
    if OLD_FUNC not in src:
        raise RuntimeError(f'{path}: old NebulaBackground body not found')
    src = src.replace(OLD_FUNC, NEW_FUNC, 1)
    path.write_text(src, encoding='utf-8')
    print(f'OK {path}')


if __name__ == '__main__':
    base = Path('/home/z/my-project/download/demo_intro')
    for name in ('preview.html', 'shaders.h'):
        patch(base / name)
    print('Done.')
