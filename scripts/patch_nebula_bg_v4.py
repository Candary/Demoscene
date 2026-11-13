#!/usr/bin/env python3
"""
V4 patch — replace the entire NebulaBackground function body.
Strategy: find `vec3 NebulaBackground(vec3 rd) {` ... `}` (matching braces)
and replace the entire function. This is robust to small variations in
prior patches.
"""
import re
from pathlib import Path

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


def replace_nebula(src: str) -> str:
    """Find NebulaBackground function and replace it (balanced-brace match)."""
    start = src.find('vec3 NebulaBackground(vec3 rd) {')
    if start < 0:
        raise RuntimeError('NebulaBackground signature not found')
    # Find matching closing brace.
    depth = 0
    i = start
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
    else:
        raise RuntimeError('Could not find matching brace')
    return src[:start] + NEW_FUNC + src[end:]


def main() -> None:
    base = Path('/home/z/my-project/download/demo_intro')
    for name in ('preview.html', 'shaders.h'):
        p = base / name
        src = p.read_text(encoding='utf-8')
        new = replace_nebula(src)
        if new == src:
            print(f'{name}: no change (already v4?)')
        else:
            p.write_text(new, encoding='utf-8')
            print(f'OK {name}')


if __name__ == '__main__':
    main()
