#!/usr/bin/env python3
"""
V2 patch for nebula background: darker base, sharper streaks.
V1 was too washed out (mix() thresholds too low → vibrantPurp dominated
everywhere, colors went pastel after ACES+gamma).
"""
from pathlib import Path

OLD_FUNC_BODY = '''vec3 NebulaBackground(vec3 rd) {
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
}'''

NEW_FUNC = '''vec3 NebulaBackground(vec3 rd) {
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


def patch(path: Path) -> None:
    src = path.read_text(encoding='utf-8')
    if OLD_FUNC_BODY not in src:
        raise RuntimeError(f'{path}: old NebulaBackground body not found')
    src = src.replace(OLD_FUNC_BODY, NEW_FUNC, 1)
    path.write_text(src, encoding='utf-8')
    print(f'OK {path}')


if __name__ == '__main__':
    base = Path('/home/z/my-project/download/demo_intro')
    for name in ('preview.html', 'shaders.h'):
        patch(base / name)
    print('Done.')
