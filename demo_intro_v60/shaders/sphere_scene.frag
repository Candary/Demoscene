// ============================================================================
// sphere_scene.frag
// ----------------------------------------------------------------------------
// Эффект: светящаяся сфера с орбитами (сценовый клип).
//
// Контракт (см. sphere_scene.effect.json):
//   uColor   vec3   — primary color (palette.primary, sRGB 0..1)
//   uGlow    float  — emissive intensity, 0..2 (default bind: 0.5 + energy)
//   uOrbit   float  — orbit angle, 0..2π (default bind: mod(t * 0.3, 6.2832))
//
// Стандартные uniforms (задаёт рантайм Scene Manager, в manifest их нет):
//   uTime, uClipTime, uProgress, uGlobalTime, uResolution, uSeed,
//   uBeat, uBeatPhase, uBarPhase, uEnergy
//
// Вывод: vec4 FragColor (линейный RGB, alpha = 1; alpha из prog opacity
// применяет рантайм через blend mode — нам premultiply НЕ нужен, мы пишем
// прямо в цель согласно op RENDER).
//
// Совместимость: OpenGL 3.3 core, GLSL 330 es — никаких extension'ов.
// Тотальность: деление защищено max(), sqrt/clamp от NaN, fin() не нужен —
// нет операций, способных выдать NaN при корректных входах.
// ============================================================================

#version 330 core

// --- Стандартные uniforms (от Scene Manager рантайма) ----------------------
uniform float uTime;          // время от eff_start клипа, всегда >= 0
uniform float uClipTime;      // t = T - nom_start, может быть < 0 на подводке
uniform float uProgress;      // clamp(p, 0, 1) — прогресс клипа
uniform float uGlobalTime;    // абсолютное время показа T
uniform vec2  uResolution;    // (width, height) в пикселях
uniform int   uSeed;          // crc32("{meta.seed}:{id}") & 0xFFFFFF — детерминированный seed
uniform float uBeat;          // audio.beat — номер доли (растёт)
uniform float uBeatPhase;     // audio.beat_phase — 0..1 внутри доли
uniform float uBarPhase;      // audio.bar_phase — 0..1 внутри такта
uniform float uEnergy;        // audio.energy — огибающая энергии трека

// --- Effect uniforms (из manifest sphere_scene.effect.json) -----------------
uniform vec3  uColor;         // primary color (palette.primary, sRGB 0..1)
uniform float uGlow;          // emissive intensity, 0..2
uniform float uOrbit;         // orbit angle, 0..2π

// --- Входы ------------------------------------------------------------------
// gl_FragCoord используется напрямую — шейдер работает со стандартным
// fullscreen quad vertex shader (без vUV varying). Это делает эффект
// самодостаточным: рантайм подаёт лишь вершины quad и uniforms.

// --- Выход ------------------------------------------------------------------
out vec4 FragColor;

// ============================================================================
// Константы и утилиты
// ============================================================================

const float PI  = 3.14159265359;
const float TAU = 6.28318530718;

// Защита от деления на 0 — для total-semantic (хотя в этом шейдере нет
// опасных операций, привыкаем к стилю, совместимому с SMT RPN fin()).
float safeDiv(float a, float b) {
    return b != 0.0 ? a / b : 0.0;
}

// LCG для детерминированной случайности — seed приходит из uSeed.
// Возвращает [0, 1).
float rng(float n) {
    uint i = floatBitsToUint(n) ^ uint(uSeed) * 0x9E3779B1u;
    i ^= i >> 16u;
    i *= 0x85ebca6bu;
    i ^= i >> 13u;
    i *= 0xc2b2ae35u;
    i ^= i >> 16u;
    return float(i) * (1.0 / 4294967296.0);
}

// ============================================================================
// SDF primitives
// ============================================================================

// Сфера радиуса r в начале координат.
float sdSphere(vec3 p, float r) {
    return length(p) - r;
}

// Полиномиальное smooth-объединение (как в shaders.h).
// k = 0.005 — защита от вырождения в min(a, b).
float smin(float a, float b, float k) {
    float kk = max(k, 0.005);
    float h = clamp(0.5 + 0.5 * (b - a) / kk, 0.0, 1.0);
    return mix(b, a, h) - kk * h * (1.0 - h);
}

// ============================================================================
// Сцена: центральная сфера + 4 орбитальных
// ----------------------------------------------------------------------------
// Главная сфера в центре (радиус 1.0, плавно "дышит" с uBeat).
// 4 малых сферы на орбитах разных радиусов и наклонов (uOrbit управляет
// вращением). Каждая имеет свою фазу и радиус (детерминированный через rng).
// ============================================================================

// Глобальные позиции орбитальных сфер — вычисляются один раз в main,
// не в каждом вызове MapScene.
vec3 gOrbitPos[4];
float gOrbitRad[4];

// Возвращает расстояние SDF до ближайшей поверхности сцены.
// p — точка в мире (после камеры).
float mapScene(vec3 p) {
    // Главная сфера: лёгкое пульсирование по доле.
    float beatPulse = 1.0 + 0.05 * pow(1.0 - uBeatPhase, 4.0);
    float dMain = sdSphere(p, beatPulse);

    // Орбитальные сферы — берём из предвычисленных глобальных массивов.
    float dOrbit = 1e9;
    for (int i = 0; i < 4; i++) {
        float ds = sdSphere(p - gOrbitPos[i], gOrbitRad[i]);
        dOrbit = min(dOrbit, ds);
    }

    // Soft-merge главной и орбитальных — единая поверхность.
    return smin(dMain, dOrbit, 0.15);
}

// Tetrahedron trick — 4 вызова MapScene вместо 6 для расчёта нормали.
vec3 calcNormal(vec3 p) {
    const vec2 k = vec2(1.0, -1.0);
    const float e = 0.001;
    return normalize(
        k.xyy * mapScene(p + k.xyy * e) +
        k.yyx * mapScene(p + k.yyx * e) +
        k.yxy * mapScene(p + k.yxy * e) +
        k.xxx * mapScene(p + k.xxx * e)
    );
}

// ============================================================================
// Raymarching
// ============================================================================

// 48 шагов — достаточно для гладких SDF (как в shaders.h после оптимизации).
// maxDist = 30 — сцена компактная, лучи быстро выходят за пределы.
// Порог 0.001 — для гладкого освещения.
vec2 rayMarch(vec3 ro, vec3 rd) {
    float t = 0.0;
    const int STEPS = 48;
    const float MAX_DIST = 30.0;
    for (int i = 0; i < STEPS; i++) {
        vec3 p = ro + rd * t;
        float d = mapScene(p);
        if (d < 0.001) return vec2(t, 1.0);  // hit
        if (t > MAX_DIST) break;
        t += d;
    }
    return vec2(-1.0, 0.0);  // miss
}

// ============================================================================
// Освещение и фон
// ============================================================================

// Динамический свет: вращается с uOrbit (синхронно с орбитами).
// Возвращает направление на источник.
vec3 lightDir() {
    float a = uOrbit * 0.7;
    return normalize(vec3(sin(a), 0.7, cos(a)));
}

// Простой фон: радиальный градиент от тёмного центра к ещё более тёмным краям.
// Цвет подмешивает uColor — фон "тонирован" основным цветом сцены для единства.
vec3 backgroundColor(vec3 rd) {
    float t = 0.5 + 0.5 * rd.y;  // 0..1, верх = ярче
    vec3 base = mix(vec3(0.02, 0.02, 0.04), vec3(0.08, 0.10, 0.14), t);
    // Лёгкая подмешка основного цвета — сцена "дышит" вместе с палитрой.
    return base + uColor * 0.05 * (1.0 - t);
}

// ACES tonemap — как в shaders.h.
vec3 aces(vec3 c) {
    return (c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14);
}

// ============================================================================
// Main — точка входа
// ============================================================================
void main() {
    // --- UV: [0, 1] из gl_FragCoord; затем [-aspect, +aspect] × [-1, 1] -------
    vec2 fragUv = gl_FragCoord.xy / uResolution;
    vec2 uv = (fragUv * 2.0 - 1.0) * vec2(uResolution.x / uResolution.y, 1.0);

    // --- Предвычисление орбит (один раз за кадр, не в MapScene) ---------------
    // 4 орбитальные сферы. Каждая:
    //   - радиус орбиты 1.5..2.5 (rng, детерминированно от uSeed)
    //   - наклон орбиты 0..π (rng)
    //   - фаза 0..2π (rng)
    //   - радиус сферы 0.15..0.30 (rng)
    // uOrbit вращает все орбиты синхронно.
    for (int i = 0; i < 4; i++) {
        float fi = float(i);
        float rOrbit = 1.5 + 1.0 * rng(fi * 1.7 + 0.3);
        float inclin = PI * rng(fi * 2.3 + 1.1);
        float phase  = TAU * rng(fi * 3.1 + 2.7);
        float rSphere = 0.15 + 0.15 * rng(fi * 4.5 + 3.3);

        float a = uOrbit + phase;
        // Орбита в плоскости, наклонённой на inclin к экватору.
        vec3 orbitLocal = vec3(cos(a) * rOrbit, sin(a) * rOrbit * sin(inclin),
                               sin(a) * rOrbit * cos(inclin));
        gOrbitPos[i] = orbitLocal;
        gOrbitRad[i] = rSphere;
    }

    // --- Камера: слегка вращается для "живости" --------------------------------
    float cam_t = uTime * 0.2;
    vec3 ro = vec3(sin(cam_t) * 4.0, 1.5, cos(cam_t) * 4.0);
    vec3 ta = vec3(0.0);
    vec3 fwd = normalize(ta - ro);
    vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), fwd));
    vec3 up = cross(fwd, right);
    vec3 rd = normalize(fwd + uv.x * right + uv.y * up);

    // --- Фон (считаем сразу — пригодится и для miss, и для fog blend) ----------
    vec3 bg = backgroundColor(rd);

    // --- Raymarch -------------------------------------------------------------
    vec2 hit = rayMarch(ro, rd);
    vec3 col;
    if (hit.x < 0.0) {
        // Miss — только фон.
        col = bg;
    } else {
        vec3 p = ro + rd * hit.x;
        vec3 n = calcNormal(p);

        // --- Свет -----------------------------------------------------------
        vec3 ld = lightDir();
        float diff = max(dot(n, ld), 0.0);
        float amb  = 0.15 + 0.15 * max(dot(n, vec3(0.0, 1.0, 0.0)), 0.0);

        // Specular — по half-vector.
        vec3 viewDir = -rd;
        vec3 halfDir = normalize(ld + viewDir);
        float spec = pow(max(dot(n, halfDir), 0.0), 32.0);

        // --- Базовый цвет поверхности --------------------------------------
        // uColor — sRGB 0..1. Лёгкая вариация по позиции для "объёмности".
        vec3 surfColor = uColor * (0.9 + 0.1 * sin(p.y * 4.0 + uTime));

        // --- Emissive glow: орбитальные сферы светятся сильнее ------------
        // Ближайшая орбитальная даёт свечение, если мы рядом с ней.
        float glowBoost = 0.0;
        for (int i = 0; i < 4; i++) {
            float dist = length(p - gOrbitPos[i]);
            float near = 1.0 - smoothstep(gOrbitRad[i], gOrbitRad[i] + 0.3, dist);
            glowBoost += near * uGlow;
        }
        glowBoost = clamp(glowBoost, 0.0, 2.0);

        // --- Финальный цвет: diffuse + ambient + spec + glow --------------
        vec3 surface = surfColor * (amb + diff * 0.8) + vec3(1.0) * spec * 0.5;
        surface += surfColor * glowBoost * 0.4;

        // --- Fog: blend с фоном по глубине --------------------------------
        float fog = 1.0 - exp(-hit.x * 0.08);
        col = mix(surface, bg, fog * 0.5);
    }

    // --- Виньетка (мягкая) ----------------------------------------------------
    vec2 vd = fragUv - 0.5;
    col *= 1.0 - 0.3 * dot(vd, vd) * 2.0;

    // --- ACES tonemap + gamma 2.2 --------------------------------------------
    col = aces(col);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));

    FragColor = vec4(col, 1.0);
}
