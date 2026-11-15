// ============================================================================
// lava_cracks.frag — процедурный шейдер вулканической лавы
// ----------------------------------------------------------------------------
// Эффект: тёмная вулканическая порода с трещинами, из которых пробивается
// яркое оранжево-красное свечение расплавленной лавы.
// Центральная часть — наиболее интенсивное свечение, расходится к краям.
// Пульсация: синусоидальная модуляция интенсивности свечения (10с цикл).
//
// Контракт:
//   uPrimaryColor vec3  — базовый цвет породы (тёмно-серый/чёрный)
//   uAccentColor  vec3  — цвет лавы (оранжево-красный)
//   uIntensity    float — общая яркость свечения (0..2)
//   uMotionSpeed  float — скорость движения лавы (0..2)
//   uPulse        float — дополнительная пульсация (0..1)
//
// Стандартные uniforms (от Scene Manager runtime):
//   uTime, uClipTime, uProgress, uGlobalTime, uResolution, uSeed,
//   uBeat, uBeatPhase, uBarPhase, uEnergy
//
// Совместимость: OpenGL 3.3 core, GLSL 330
// ============================================================================

#version 330 core

// --- Стандартные uniforms ---------------------------------------------------
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

// --- Effect uniforms --------------------------------------------------------
uniform vec3  uPrimaryColor;   // базовый цвет породы
uniform vec3  uAccentColor;    // цвет лавы
uniform float uIntensity;      // яркость свечения
uniform float uMotionSpeed;    // скорость движения
uniform float uPulse;          // дополнительная пульсация

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

// Целочисленный hash (v61 style — без квантования при больших seed)
float hash3(vec3 p) {
    ivec3 i = ivec3(floor(p));
    uint h = uint(i.x) * 0x8da6b343u ^ uint(i.y) * 0xd8163841u ^ uint(i.z) * 0xcb1ab31fu;
    h ^= h >> 16;
    h *= 0x7feb352du;
    h ^= h >> 15;
    h *= 0x846ca68bu;
    h ^= h >> 16;
    return float(h & 0x00FFFFFFu) / float(0x01000000);
}

// Value noise 3D — trilinear interpolation
// v61.2 fix: renamed noise3 -> vnoise3 (GLSL reserved built-in name clash).
float vnoise3(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float na = hash3(i + vec3(0.0, 0.0, 0.0));
    float nb = hash3(i + vec3(1.0, 0.0, 0.0));
    float nc = hash3(i + vec3(0.0, 1.0, 0.0));
    float nd = hash3(i + vec3(1.0, 1.0, 0.0));
    float ne = hash3(i + vec3(0.0, 0.0, 1.0));
    float nf = hash3(i + vec3(1.0, 0.0, 1.0));
    float ng = hash3(i + vec3(0.0, 1.0, 1.0));
    float nh = hash3(i + vec3(1.0, 1.0, 1.0));
    return mix(mix(mix(na, nb, f.x), mix(nc, nd, f.x), f.y),
               mix(mix(ne, nf, f.x), mix(ng, nh, f.x), f.y), f.z);
}

// 4-octave FBM
float fbm(vec3 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
        v += a * vnoise3(p);
        p = p * 2.0 + vec3(1.7, 2.3, 3.1);
        a *= 0.5;
    }
    return v;
}

// ============================================================================
// Voronoi — для генерации трещин
// ----------------------------------------------------------------------------
// Возвращает vec2: x = distance to nearest cell, y = cell ID hash
// ============================================================================
vec2 voronoi(vec3 p) {
    vec3 b = floor(p);
    vec3 f = fract(p);
    float minDist = 1.0;
    float cellID = 0.0;
    for (int z = -1; z <= 1; z++) {
        for (int y = -1; y <= 1; y++) {
            for (int x = -1; x <= 1; x++) {
                vec3 cell = vec3(float(x), float(y), float(z));
                vec3 point = cell + vec3(hash3(b + cell),
                                         hash3(b + cell + vec3(1.0)),
                                         hash3(b + cell + vec3(2.0)));
                vec3 diff = cell + point - f;
                float dist = dot(diff, diff);
                if (dist < minDist) {
                    minDist = dist;
                    cellID = hash3(b + cell + vec3(3.0));
                }
            }
        }
    }
    return vec2(sqrt(minDist), cellID);
}

// ============================================================================
// Текстура вулканической породы
// ----------------------------------------------------------------------------
// Многослойный FBM с domain warping — даёт rugged rock surface.
// ============================================================================
float rockTexture(vec2 uv, float t) {
    vec3 p = vec3(uv * 3.0, t * 0.05 * uMotionSpeed);
    // Domain warp для органической деформации
    float warp = fbm(p + vec3(5.2, 1.3, 0.0));
    float rock = fbm(p + vec3(2.0 * warp, 2.0 * warp, 0.0));
    // Второй слой — мелкие детали
    float detail = fbm(p * 4.0 + vec3(3.1, 7.2, 1.5));
    return mix(rock, detail, 0.3);
}

// ============================================================================
// Трещины (cracks) — FBM-based, без тяжёлого Voronoi
// ----------------------------------------------------------------------------
// Использует thresholded FBM derivatives для создания органических трещин.
// Быстрее Voronoi (4 octaves vs 27 cells), лучше читается на SwiftShader.
// ============================================================================
float crackPattern(vec2 uv, float t) {
    vec3 p = vec3(uv * 3.0, t * 0.03 * uMotionSpeed);
    // Domain warp для органической формы
    float warp = fbm(p + vec3(5.2, 1.3, 0.0));
    float cracks = fbm(p + vec3(2.0 * warp, 2.0 * warp, 0.0));

    // Threshold: низкие значения FBM = трещины (dark areas become lava)
    float crackMask = 1.0 - smoothstep(0.2, 0.5, cracks);

    // Второй слой — мелкие трещины под другим углом
    vec3 p2 = vec3(uv * 6.0, t * 0.05 * uMotionSpeed);
    float fineCracks = 1.0 - smoothstep(0.15, 0.35, fbm(p2));

    // Третий слой — широкие потоки лавы
    vec3 p3 = vec3(uv * 1.5, t * 0.01 * uMotionSpeed);
    float rivers = 1.0 - smoothstep(0.3, 0.6, fbm(p3 + vec3(warp)));

    return clamp(crackMask * 0.5 + fineCracks * 0.3 + rivers * 0.4, 0.0, 1.0);
}

// ============================================================================
// Пульсация свечения
// ----------------------------------------------------------------------------
// 10-секундный цикл: нарастание → пик → затухание.
// Дополнительно: быстрая пульсация от uPulse + beat-sync.
// ============================================================================
float glowPulse(float t) {
    // Медленный цикл (10с): sin с периодом 10
    float slowCycle = 0.5 + 0.5 * sin(t * TAU / 10.0);

    // Быстрая пульсация (beat-sync)
    float beatPulse = pow(1.0 - uBeatPhase, 3.0) * 0.3;

    // Дополнительная модуляция от uPulse
    float extraPulse = uPulse * 0.5 * sin(t * 3.0);

    return clamp(slowCycle * 0.6 + beatPulse + extraPulse, 0.0, 1.5);
}

// ============================================================================
// Цветовая палитра лавы
// ----------------------------------------------------------------------------
// Температурная шкала: тёмная порода → тёмно-красный → оранжевый → жёлтый
// ============================================================================
vec3 lavaColor(float temperature) {
    // temperature: 0 = холодная порода, 1 = максимально горячая
    vec3 dark   = uPrimaryColor;                    // тёмная порода
    vec3 deep   = vec3(0.3, 0.05, 0.02);           // тёмно-красный
    vec3 orange = uAccentColor;                     // оранжевый
    vec3 hot    = vec3(1.0, 0.85, 0.3);            // жёлто-белый

    vec3 col = mix(dark, deep, smoothstep(0.0, 0.3, temperature));
    col = mix(col, orange, smoothstep(0.2, 0.6, temperature));
    col = mix(col, hot, smoothstep(0.5, 0.9, temperature));
    return col;
}

// ============================================================================
// Радиальное затухание от центра
// ----------------------------------------------------------------------------
// Центр — наиболее интенсивное свечение, к краям — затухание.
// ============================================================================
float centerGlow(vec2 uv) {
    vec2 center = vec2(0.5, 0.5);
    float dist = length(uv - center);
    // Два центра свечения (по референсу: центр + левый-нижний)
    // Менее крутой falloff → больше площади освещено
    float c1 = exp(-dist * 1.5);
    float c2 = exp(-length(uv - vec2(0.3, 0.35)) * 2.0);
    return max(c1, c2 * 0.8);
}

// ============================================================================
// ACES tonemap
// ============================================================================
vec3 aces(vec3 c) {
    return (c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14);
}

// ============================================================================
// Main
// ============================================================================
void main() {

    // --- Pipeline defaults: guard against unset uniforms (0 in GLSL) ---
    vec3  primaryColor = max(uPrimaryColor, vec3(0.001));
    float intensity    = max(uIntensity, 1.0);
    float motionSpeed  = max(uMotionSpeed, 0.0);
    float pulse        = max(uPulse, 0.0);

    vec2 fragUv = gl_FragCoord.xy / uResolution;
    vec2 uv = fragUv * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;

    float t = uTime;

    // --- Текстура породы ----------------------------------------------------
    float rock = rockTexture(fragUv * 2.0, t);
    // Базовый цвет породы: тёмно-серый с вариацией
    vec3 rockCol = uPrimaryColor * (0.3 + rock * 0.5);

    // --- Трещины ------------------------------------------------------------
    float cracks = crackPattern(fragUv * 2.0, t);

    // --- Пульсация свечения -------------------------------------------------
    float glow = glowPulse(t);
    float effectiveIntensity = intensity * glow;

    // --- Радиальное затухание (центр ярче) ----------------------------------
    float centerFalloff = centerGlow(fragUv);

    // --- Температура лавы в трещинах ----------------------------------------
    // Комбинация: ширина трещины × пульсация × центральное затухание
    float temperature = cracks * effectiveIntensity * (0.3 + centerFalloff * 0.7);
    temperature = clamp(temperature, 0.0, 1.0);

    // --- Цвет лавы ----------------------------------------------------------
    vec3 lava = lavaColor(temperature);

    // --- Композитинг: порода + свечение из трещин --------------------------
    vec3 col = rockCol;
    // Свечение добавляется аддитивно там, где есть трещины
    float glowAmount = cracks * effectiveIntensity * centerFalloff;
    col += lava * glowAmount * 3.0;

    // Дополнительное свечение вокруг горячих точек (bloom-подобный эффект)
    float hotSpot = pow(centerFalloff * cracks * effectiveIntensity, 1.5);
    col += lavaColor(0.9) * hotSpot * 0.5;

    // --- Виньетка (тёмные края) ---------------------------------------------
    vec2 vd = fragUv - 0.5;
    col *= 1.0 - 0.4 * dot(vd, vd) * 2.0;

    // --- Тонмаппинг + gamma -------------------------------------------------
    col = aces(col);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));

    FragColor = vec4(col, 1.0);
}
