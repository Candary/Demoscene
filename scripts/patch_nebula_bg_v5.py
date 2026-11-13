#!/usr/bin/env python3
"""
V5 patch — layout matches the reference image precisely:
- 60-70% dark blue/purple base
- Cyan focal at CENTER (apex of ribbon)
- Orange/yellow band on LEFT-CENTER
- Pink/magenta glow at TOP-RIGHT
- Pink/violet crescent at BOTTOM-RIGHT
- More prominent flowing ribbon streams
- Saturated colors (not pastel)
"""
from pathlib import Path

NEW_FUNC = '''vec3 NebulaBackground(vec3 rd) {
    // ---- A. Шумовой паттерн (ray-angle UV) ----
    vec2 ruv = vec2(atan(rd.z, rd.x), asin(clamp(rd.y, -1.0, 1.0)));
    ruv *= 0.7;
    ruv += vec2(uTime * 0.030, uTime * 0.020);

    // Domain warping.
    vec2 q = ruv * 1.4 + vec2(2.5, -1.5);
    vec2 warp = vec2(fbm4(q), fbm4(q + vec2(4.7, 2.1)));
    vec2 r = vec2(
        fbm4(q + warp * 1.8 + vec2(1.7, 9.2)),
        fbm4(q + warp * 1.8 + vec2(8.3, 2.8))
    );
    float f = fbm4(q + r * 1.5);
    float fw = warp.x + warp.y * 0.5;
    float rl = length(r);

    // ---- B. Screen-space UV для лент и узлов ----
    vec2 suv = (gl_FragCoord.xy / uResolution.xy - 0.5) * 2.0;
    suv.x *= uResolution.x / uResolution.y;

    // ---- C. Палитра: насыщенные неоновые цвета ----
    vec3 deepBase   = vec3(0.020, 0.015, 0.075);    // тёмно-сине-фиолетовая база
    vec3 deepBlue   = vec3(0.025, 0.060, 0.220);    // тёмно-синий
    vec3 vibrantPurp = vec3(0.260, 0.060, 0.500);    // насыщенный пурпур
    vec3 hotPink    = vec3(0.950, 0.180, 0.520);    // яркое розовое
    vec3 electricCy = vec3(0.180, 0.780, 1.000);    // насыщенный циан
    vec3 neonOrang  = vec3(1.000, 0.580, 0.090);    // неоновый оранжевый
    vec3 neonYell   = vec3(1.000, 0.820, 0.250);    // неоновый жёлтый

    // База — глубокий сине-фиолетовый, пурпур проступает в средних FBM-зонах.
    vec3 col = mix(deepBase, deepBlue, smoothstep(0.30, 0.65, f) * 0.55);
    col = mix(col, vibrantPurp, smoothstep(0.50, 0.78, f) * 0.40);

    // ---- D. Flowing RIBBON — главная визуальная черта (как на референсе) ----
    // Лента — синусоида вдоль диагонали снизу-справа вверх-влево.
    // Сдвигаем ленту координатами FBM чтобы она извивалась.
    float ribbonT = sin((suv.x + suv.y) * 1.6 + f * 6.0 + uTime * 0.35);
    float ribbonW = pow(smoothstep(-0.3, 1.0, ribbonT), 2.5);
    // Лента видна в средних и ярких зонах FBM.
    ribbonW *= smoothstep(0.45, 0.85, f);
    // Основной цвет ленты — циан, к краю переходит в фиолетовый.
    col += electricCy * ribbonW * 0.85;
    col += neonYell * pow(ribbonW, 2.0) * 0.15;          // жёлтое свечение в пиках
    col += vec3(1.0) * pow(ribbonW, 10.0) * 0.6;         // белые HDR-пики

    // Вторая лента — тоньше, диагональ в другую сторону, для глубины.
    float ribbon2 = sin((suv.x - suv.y) * 2.0 + f * 4.0 - uTime * 0.25);
    ribbon2 = pow(smoothstep(0.2, 1.0, ribbon2), 3.0);
    ribbon2 *= smoothstep(0.55, 0.85, f) * 0.4;
    col += vibrantPurp * ribbon2 * 0.55;

    // ---- E. Световые узлы — в SCREEN-SPACE, по референсу ----
    // 1. ЦИАН В ЦЕНТРЕ — апекс ленты.
    vec2 f1 = suv - vec2( 0.05,  0.10);
    float g1 = exp(-dot(f1, f1) * 18.0);
    col += electricCy * g1 * 1.4;

    // 2. ОРАНЖЕВО-ЖЁЛТАЯ ПОЛОСА слева-центр, вытянутая по горизонтали.
    vec2 f2 = (suv - vec2(-0.65, -0.05)) * vec2(0.4, 1.0);  // 2.5× уже по X
    float g2 = exp(-dot(f2, f2) * 16.0);
    col += neonOrang * g2 * 1.1;
    col += neonYell * pow(g2, 4.0) * 0.6;                  // жёлтое ядро

    // 3. РОЗОВЫЙ СВЕТ сверху-справа.
    vec2 f3 = suv - vec2( 0.55,  0.55);
    float g3 = exp(-dot(f3, f3) * 14.0);
    col += hotPink * g3 * 1.0;

    // 4. РОЗОВО-ФИОЛЕТОВЫЙ СЕРП снизу-справа.
    vec2 f4 = suv - vec2( 0.65, -0.55);
    float g4 = exp(-dot(f4, f4) * 15.0);
    col += mix(vibrantPurp, hotPink, 0.5) * g4 * 0.9;

    // 5. ПУРПУРНЫЙ СВЕТ сверху-слева (для баланса).
    vec2 f5 = suv - vec2(-0.55,  0.45);
    float g5 = exp(-dot(f5, f5) * 16.0);
    col += vibrantPurp * g5 * 0.7;

    // 6. СИНИЙ СВЕТ снизу-центр (для глубины).
    vec2 f6 = suv - vec2( 0.0,  -0.65);
    float g6 = exp(-dot(f6, f6) * 18.0);
    col += deepBlue * g6 * 0.7;

    // ---- F. Виньетка — концентрирует внимание в центре ----
    col *= 1.0 - 0.32 * dot(suv, suv);

    return col;
}'''


def replace_nebula(src: str) -> str:
    start = src.find('vec3 NebulaBackground(vec3 rd) {')
    if start < 0:
        raise RuntimeError('NebulaBackground signature not found')
    depth = 0
    i = start
    end = None
    while i < len(src):
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    if end is None:
        raise RuntimeError('matching brace not found')
    return src[:start] + NEW_FUNC + src[end:]


def main() -> None:
    base = Path('/home/z/my-project/download/demo_intro')
    for name in ('preview.html', 'shaders.h'):
        p = base / name
        src = p.read_text(encoding='utf-8')
        new = replace_nebula(src)
        p.write_text(new, encoding='utf-8')
        print(f'OK {name}')


if __name__ == '__main__':
    main()
