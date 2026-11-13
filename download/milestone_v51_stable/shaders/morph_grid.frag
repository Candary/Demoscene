// ============================================================================
// morph_grid.frag
// ----------------------------------------------------------------------------
// Эффект: сетка, морфящаяся между формами (куб <-> сфера).
//
// Контракт (см. morph_grid.effect.json):
//   uColor vec3   — palette.primary (базовый цвет)
//   uMorph float  — 0..1 (default bind: smoothstep(0,1,p)) — глобальный прогресс морфа
//                   0 = все кубы, 1 = все сферы
//   uSpeed float  — 0..3 (default bind: 0.5 + energy) — скорость анимации
//
// Стандартные uniforms (от Scene Manager рантайма):
//   uTime, uClipTime, uProgress, uGlobalTime, uResolution, uSeed,
//   uBeat, uBeatPhase, uBarPhase, uEnergy
//
// Архитектура:
//   3D raymarched grid 5x5x5 ячеек (cellSize=1.5, total region [-3.75, 3.75]).
//   Periodic repeat через mod() — каждый cell имеет один SDF (не итерируем cells).
//   Per-cell morph: глобальный uMorph + синусоидальная вариация от cellId + time.
//   Каждый cell морфит между sdBox (куб) и sdSphere (сфера).
//
// Производительность: 1 SDF per ray step (периодичность!), 32 шага → очень лёгкий.
// Cost: 2 (легче sphere_scene и particle_swarm).
//
// Совместимость: OpenGL 3.3 core, GLSL 330. Total-semantic (нет NaN-операций).
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

// --- Effect uniforms (из manifest morph_grid.effect.json) -------------------
uniform vec3  uColor;        // palette.primary
uniform float uMorph;        // 0..1 — глобальный прогресс морфа
uniform float uSpeed;        // 0..3 — скорость анимации

// --- Выход ------------------------------------------------------------------
out vec4 FragColor;

// ============================================================================
// Константы
// ============================================================================

const float PI  = 3.14159265359;
const float TAU = 6.28318530718;

// Размер ячейки сетки и общая граница.
const vec3  CELL_SIZE = vec3(1.5);
const float GRID_BOUND = 3.75;   // |q| <= 3.75 → 5x5x5 ячеек

// ============================================================================
// Утилиты
// ============================================================================

// LCG с uint — детерминированный от uSeed.
float rng(float n) {
    uint i = floatBitsToUint(n) ^ (uint(uSeed) * 0x9E3779B1u);
    i ^= i >> 16u; i *= 0x85ebca6bu;
    i ^= i >> 13u; i *= 0xc2b2ae35u;
    i ^= i >> 16u;
    return float(i) * (1.0 / 4294967296.0);
}

// ============================================================================
// SDF primitives
// ============================================================================

float sdSphere(vec3 p, float r) {
    return length(p) - r;
}

// Box SDF (iq formula) — exact distance.
float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}

// ============================================================================
// Сцена — periodic grid of morphing cells
// ----------------------------------------------------------------------------
// Используем mod() для periodic repeat — каждый cell имеет ОДИН SDF,
// не итерируем 125 cells. Это даёт огромную экономию GPU.
// ============================================================================

// Возвращает расстояние SDF до ближайшей поверхности grid'а.
float mapScene(vec3 q) {
    // Bounding: вне сетки возвращаем SDF bounding box (не 1e9!),
    // чтобы raymarch приближался к grid'у, а не пропускал его.
    vec3 absq = abs(q);
    float maxComp = max(max(absq.x, absq.y), absq.z);
    float outsideMask = step(GRID_BOUND, maxComp);   // 1.0 если вне grid'а

    // SDF bounding box — negative внутри, positive снаружи.
    // Когда луч вне grid'а, это направляет его к grid'у.
    float boundSDF = sdBox(q, vec3(GRID_BOUND));

    // Periodic repeat: cell-local coordinates в [-CELL_SIZE/2, +CELL_SIZE/2].
    vec3 p = mod(q + CELL_SIZE * 0.5, CELL_SIZE) - CELL_SIZE * 0.5;

    // Cell ID — для per-cell вариации.
    vec3 cellId = floor((q + CELL_SIZE * 0.5) / CELL_SIZE);
    float cellHash = rng(cellId.x * 1.7 + cellId.y * 2.3 + cellId.z * 3.1 + 0.5);

    // Per-cell morph.
    float perCellMorph = uMorph + 0.3 * sin(cellHash * TAU + uTime * uSpeed * 0.5);
    perCellMorph = clamp(perCellMorph, 0.0, 1.0);

    // SDF: mix между кубом и сферой.
    float dCube   = sdBox(p, vec3(0.32));     // куб half-size 0.32
    float dSphere = sdSphere(p, 0.40);        // сфера радиус 0.40
    float dInside = mix(dCube, dSphere, perCellMorph);

    // Вне grid'а: boundSDF (advance toward grid).
    // Внутри grid'а: dInside (фактический SDF ячейки).
    return mix(dInside, boundSDF, outsideMask);
}

// Tetrahedron trick для нормали (4 вызова mapScene вместо 6).
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
vec2 rayMarch(vec3 ro, vec3 rd) {
    // Bounding sphere R=6 — все ячейки внутри.
    vec3 oc = ro;
    float b = dot(oc, rd);
    float c = dot(oc, oc) - 36.0;   // 6^2
    float disc = b * b - c;
    if (disc < 0.0) return vec2(-1.0, 0.0);   // miss bounding sphere
    float tStart = max(0.0, -b - sqrt(disc));

    float t = tStart;
    const int STEPS = 32;             // 32 — для SDF сетки достаточно
    const float MAX_DIST = 30.0;
    for (int i = 0; i < STEPS; i++) {
        vec3 p = ro + rd * t;
        float d = mapScene(p);
        if (d < 0.001) return vec2(t, 1.0);
        if (t > MAX_DIST) break;
        t += d;
    }
    return vec2(-1.0, 0.0);
}

// ============================================================================
// Освещение + фон
// ============================================================================

vec3 lightDir() {
    float a = uTime * 0.3;
    return normalize(vec3(sin(a), 0.7, cos(a)));
}

// Фон: тёмный градиент + лёгкая tint от uColor.
vec3 backgroundColor(vec3 rd) {
    float t = 0.5 + 0.5 * rd.y;
    vec3 base = mix(vec3(0.03, 0.03, 0.05), vec3(0.08, 0.09, 0.13), t);
    return base + uColor * 0.04 * (1.0 - t);
}

// ACES tonemap.
vec3 aces(vec3 c) {
    return (c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14);
}

// ============================================================================
// Main
// ============================================================================
void main() {
    vec2 fragUv = gl_FragCoord.xy / uResolution;
    vec2 uv = (fragUv * 2.0 - 1.0) * vec2(uResolution.x / uResolution.y, 1.0);

    // Камера: вращается вокруг grid'а, слегка сверху.
    float cam_t = uTime * 0.1 * uSpeed;
    vec3 ro = vec3(sin(cam_t) * 8.0, 3.5, cos(cam_t) * 8.0);
    vec3 ta = vec3(0.0);
    vec3 fwd = normalize(ta - ro);
    vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), fwd));
    vec3 up = cross(fwd, right);
    vec3 rd = normalize(fwd + uv.x * right + uv.y * up);

    vec3 bg = backgroundColor(rd);
    vec2 hit = rayMarch(ro, rd);

    vec3 col;
    if (hit.x < 0.0) {
        col = bg;
    } else {
        vec3 p = ro + rd * hit.x;
        vec3 n = calcNormal(p);

        // Освещение.
        vec3 ld = lightDir();
        float diff = max(dot(n, ld), 0.0);
        float amb = 0.18 + 0.12 * max(dot(n, vec3(0.0, 1.0, 0.0)), 0.0);
        vec3 viewDir = -rd;
        vec3 halfDir = normalize(ld + viewDir);
        float spec = pow(max(dot(n, halfDir), 0.0), 32.0);

        // Per-cell цветовая вариация: uColor + лёгкая modulation от cellHash.
        vec3 cellId = floor((p + CELL_SIZE * 0.5) / CELL_SIZE);
        float cellHash = rng(cellId.x * 1.7 + cellId.y * 2.3 + cellId.z * 3.1 + 0.5);
        vec3 surfColor = uColor * (0.85 + 0.30 * cellHash);

        // Rim light для объёмности — особенно на sphere-fases.
        float rim = pow(1.0 - abs(dot(n, viewDir)), 2.5);
        surfColor += uColor * rim * 0.4;

        vec3 surface = surfColor * (amb + diff * 0.8) + vec3(1.0) * spec * 0.5;

        // Fog: blend с фоном по глубине.
        float fog = 1.0 - exp(-hit.x * 0.07);
        col = mix(surface, bg, fog * 0.5);
    }

    // Виньетка.
    vec2 vd = fragUv - 0.5;
    col *= 1.0 - 0.30 * dot(vd, vd) * 2.0;

    // ACES + gamma.
    col = aces(col);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));

    FragColor = vec4(col, 1.0);
}
