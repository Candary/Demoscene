// ============================================================================
// anxiety_mist.frag
// ----------------------------------------------------------------------------
// Эффект: тёмный туман с красными вспышками (сценовый клип).
//
// Контракт (см. anxiety_mist.effect.json):
//   uPrimaryColor vec3  — palette.primary (тёмно-красный/пурпурный — anxiety mood)
//   uAccentColor  vec3  — palette.accent (красные вспышки)
//   uIntensity    float — 0..2 (default bind: energy) — общая яркость
//   uMotionSpeed  float — 0..3 (default bind: 0.8 + energy*0.8) — скорость тумана
//   uWarmth       float — 0..1 (default bind: temperature/4) — тёплый (1) / холодный (0)
//
// Стандартные uniforms (от Scene Manager рантайма):
//   uTime, uClipTime, uProgress, uGlobalTime, uResolution, uSeed,
//   uBeat, uBeatPhase, uBarPhase, uEnergy
//
// Архитектура:
//   2D screen-space FBM (4 октавы) с domain warping. Не raymarching —
//   это "объёмный туман" в 2D, подходит для intro-mood сцен.
//   Красные вспышки — периодические острые пики, модулированные uBeat
//   и отдельным "panic" осциллятором (каждые ~3-5с).
//
// Производительность: ~8 noise3 calls per pixel — должно быть 60+ FPS
// даже на Intel HD 4000.
//
// Совместимость: OpenGL 3.3 core, GLSL 330. Total-semantic (нет NaN-операций).
// ============================================================================

#version 330 core

// --- Стандартные uniforms (от Scene Manager рантайма) ----------------------
uniform float uTime;
uniform float uClipTime;
uniform float uProgress;
uniform float uGlobalTime;
uniform vec2  uResolution;
uniform int   uSeed;
uniform float uBeat;
uniform float uBeatPhase;
uniform float uBarPhase;
uniform float uEnergy;

// --- Effect uniforms (из manifest anxiety_mist.effect.json) -----------------
uniform vec3  uPrimaryColor;   // palette.primary
uniform vec3  uAccentColor;    // palette.accent
uniform float uIntensity;      // 0..2
uniform float uMotionSpeed;    // 0..3
uniform float uWarmth;         // 0..1

// --- Выход ------------------------------------------------------------------
out vec4 FragColor;

// ============================================================================
// Константы
// ============================================================================

const float PI  = 3.14159265359;
const float TAU = 6.28318530718;

// ============================================================================
// Hash и noise
// ============================================================================

// 3D hash — для FBM в uv-time пространстве.
float hash3(vec3 p) {
    // uSeed подмешивается для per-show вариации.
    p = fract(p * 0.3183099 + 0.1) + float(uSeed) * 0.0001;
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

// Value noise 3D — trilinear interpolation.
float noise3(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float na = hash3(i + vec3(0,0,0));
    float nb = hash3(i + vec3(1,0,0));
    float nc = hash3(i + vec3(0,1,0));
    float nd = hash3(i + vec3(1,1,0));
    float ne = hash3(i + vec3(0,0,1));
    float nf = hash3(i + vec3(1,0,1));
    float ng = hash3(i + vec3(0,1,1));
    float nh = hash3(i + vec3(1,1,1));
    return mix(mix(mix(na, nb, f.x), mix(nc, nd, f.x), f.y),
               mix(mix(ne, nf, f.x), mix(ng, nh, f.x), f.y), f.z);
}

// 4-octave FBM с spectral weight 0.5.
float fbm(vec3 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
        v += a * noise3(p);
        p = p * 2.0 + vec3(1.7, 2.3, 3.1);
        a *= 0.5;
    }
    return v;
}

// ============================================================================
// Красные вспышки — острые пики
// ----------------------------------------------------------------------------
// Два механизма:
//   1. Beat-synced: каждый beat даёт короткую вспышку (pow для остроты).
//   2. "Panic" oscillator: каждые ~3-5с более длинная вспышка.
// Сумма даёт непредсказуемый ритм — чувство anxiety.
// ============================================================================

float beatFlash() {
    // Острый пик в начале каждой доли.
    return pow(1.0 - uBeatPhase, 6.0);
}

float panicFlash() {
    // Нерегулярные вспышки — каждые ~3-5 секунд, длительность 0.3-0.6с.
    // Используем floor(time / period) для переключения периода.
    float t = uTime;
    // Период зависит от uSeed — каждый show имеет свой ритм panic.
    float period = 3.0 + 2.0 * fract(float(uSeed) * 0.137);
    float phase = mod(t, period) / period;  // 0..1 внутри цикла
    // Без early return — для совместимости со старыми ANGLE/D3D11.
    // 'active' — reserved word в GLSL, используем 'flashMask'.
    float flashMask = step(phase, 0.7);       // 1.0 если phase <= 0.7, иначе 0.0
    float localPhase = phase / 0.7;           // 0..1 внутри вспышки
    // Острый пик + быстрый спад.
    return pow(1.0 - localPhase, 3.0) * 0.8 * flashMask;
}

// Сумма вспышек, ограниченная 0..1.5.
float totalFlash() {
    return clamp(beatFlash() * 0.5 + panicFlash(), 0.0, 1.5);
}

// ============================================================================
// Main — точка входа
// ============================================================================
void main() {
    // UV в screen-space, нормализованный.
    vec2 fragUv = gl_FragCoord.xy / uResolution;
    vec2 uv = fragUv * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;

    // --- Туман: domain-warped FBM --------------------------------------------
    // p — 3D: 2D screen coords + time axis (для анимации).
    float t = uTime * uMotionSpeed * 0.3;
    vec3 p = vec3(uv * 1.5, t);

    // Domain warp: FBM от FBM-ом.
    float warp = fbm(p + vec3(5.2, 1.3, 0.0));
    // Смещение по x,y на 2*warp, z (time) — без изменений.
    float mist = fbm(p + vec3(2.0 * warp, 2.0 * warp, 0.0));

    // --- Цвет тумана --------------------------------------------------------
    // Базовый тёмный цвет (deep indigo / dark purple).
    vec3 darkBase = vec3(0.04, 0.03, 0.06);
    // uPrimaryColor — тёмно-красный/пурпурный для anxiety mood.
    // uWarmth двигает смесь между cold purple и warm red.
    vec3 primaryMod = mix(
        uPrimaryColor * vec3(0.7, 0.3, 1.0),  // cold purple shift
        uPrimaryColor * vec3(1.3, 0.5, 0.3),  // warm red shift
        uWarmth
    );

    // Туманная компонента: primaryMod, усиливается где mist > порог.
    // v61: multiplier raised 0.4 → 0.8 (primary был невидим; eff_L было 0.05,
    // поднимаем до ~0.10 — заметный туман вместо почти-чёрного).
    vec3 col = darkBase;
    col = mix(col, primaryMod * 0.8, smoothstep(0.3, 0.7, mist));

    // --- Красные вспышки: uAccentColor усиливается вспышкой ------------------
    float flash = totalFlash();
    // Base flash: всегда видимый (не зависит от mist), слабее.
    col += uAccentColor * flash * uIntensity * 0.6;
    // Mist-masked flash: сильнее, только в плотных областях тумана.
    float flashMask = smoothstep(0.2, 0.5, mist);
    col += uAccentColor * flash * flashMask * uIntensity * 1.0;  // вспышка — additive, ярче фона

    // --- Дополнительная тёмная виньетка по краям ----------------------------
    // Anxiety часто использует "tunnel vision" — края затемнены.
    vec2 vd = fragUv - 0.5;
    float vig = 1.0 - 0.6 * dot(vd, vd) * 2.0;
    col *= vig;

    // --- Дрожание камеры — лёгкое, чувствуётся不安 ---------------------------
    // Очень subtle shake: 1-2 пикселя дрожания.
    // (через uniform uv offset, не position — иначе артефакты)
    float shake = (noise3(vec3(t * 8.0, 0.0, 0.0)) - 0.5) * 0.005 * uIntensity;
    col *= 1.0 + shake * 2.0;

    // --- ACES tonemap + gamma 2.2 --------------------------------------------
    col = (col * (2.51 * col + 0.03)) / (col * (2.43 * col + 0.59) + 0.14);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));

    FragColor = vec4(col, 1.0);
}
