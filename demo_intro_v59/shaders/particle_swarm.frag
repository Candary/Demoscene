// ============================================================================
// particle_swarm.frag
// ----------------------------------------------------------------------------
// Эффект: рой частиц, реагирует на энергию (сценовый клип).
//
// Контракт (см. particle_swarm.effect.json):
//   uColor    vec3   — accent color (palette.accent, sRGB 0..1)
//   uSwarm    float  — swarm activity, 0..1 (default bind: clamp(energy, 0, 1))
//                      высокие значения = рой шире, движение активнее
//   uBeatKick float  — beat kick, 0..1 (default bind: pow(1 - beat_phase, 3))
//                      резкий пик в начале доли — рой "пульсирует" наружу
//
// Стандартные uniforms (задаёт рантайм Scene Manager):
//   uTime, uClipTime, uProgress, uGlobalTime, uResolution, uSeed,
//   uBeat, uBeatPhase, uBarPhase, uEnergy
//
// Архитектура:
//   16 частиц-метаболов в 3D пространстве. Каждая:
//     - base position на сфере (rng-детерминированная от uSeed)
//     - orbital motion (вращение вокруг центра)
//     - noise offset (curl-like, от uTime и uSwarm)
//     - beat kick: кратковременное расширение орбит при uBeatKick > 0
//   SDF: chain smin всех 16 сфер → единая "рой-поверхность"
//   Освещение: glow зависит от плотности (ближе к центру роя — ярче)
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

// --- Effect uniforms (из manifest particle_swarm.effect.json) ---------------
uniform vec3  uColor;      // palette.accent
uniform float uSwarm;      // 0..1 — активность роя
uniform float uBeatKick;   // 0..1 — beat kick

// --- Выход ------------------------------------------------------------------
out vec4 FragColor;

// ============================================================================
// Константы
// ============================================================================

const float PI  = 3.14159265359;
const float TAU = 6.28318530718;
const int   N_PARTICLES = 16;

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

// Value noise 3D — для flow-like движения частиц.
// Не высокое качество, но достаточно для "рой-движения".
float hash3(vec3 p) {
    p = fract(p * 0.3183099 + 0.1);
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

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

// SDF сферы.
float sdSphere(vec3 p, float r) {
    return length(p) - r;
}

// Smooth min — полиномиальное слияние (k=0.005 защита от вырождения).
float smin(float a, float b, float k) {
    float kk = max(k, 0.005);
    float h = clamp(0.5 + 0.5 * (b - a) / kk, 0.0, 1.0);
    return mix(b, a, h) - kk * h * (1.0 - h);
}

// ============================================================================
// Предвычисление позиций 16 частиц (один раз за пиксель, до raymarch)
// ----------------------------------------------------------------------------
// Глобальные массивы. Заполняются в main(), используются в mapScene().
// 16 частиц — компромисс: визуально rich рой, но 16×32=512 sdSphere на пиксель
// (с bounding sphere skip — фактически меньше).
// ============================================================================

vec3  gPos[N_PARTICLES];
float gRad[N_PARTICLES];

void precomputeParticles() {
    float t = uTime;
    float swarmScale = 0.3 + 0.7 * uSwarm;     // 0.3..1.0 — насколько рой разлетается
    float kickPush = uBeatKick * 0.8;          // beat kick向外 расширение

    for (int i = 0; i < N_PARTICLES; i++) {
        float fi = float(i);

        // Базовая позиция на сфере (rng-детерминированная).
        float theta = PI * rng(fi * 1.7 + 0.3);
        float phi   = TAU * rng(fi * 2.3 + 1.1);
        float rBase = 0.8 + 0.4 * rng(fi * 3.1 + 2.7);

        vec3 base = vec3(
            sin(theta) * cos(phi) * rBase,
            sin(theta) * sin(phi) * rBase,
            cos(theta) * rBase
        );

        // Орбитальное вращение — каждая частица со своей скоростью.
        float spinSpeed = 0.3 + 0.5 * rng(fi * 4.5 + 3.3);
        float a = t * spinSpeed;
        mat2 spin = mat2(cos(a), -sin(a), sin(a), cos(a));
        base.xz = spin * base.xz;

        // Noise offset — flow-like движение, масштабируется uSwarm.
        vec3 noiseInput = vec3(fi * 0.5, t * 0.4, fi * 0.3);
        vec3 offset;
        offset.x = noise3(noiseInput) - 0.5;
        offset.y = noise3(noiseInput + vec3(13.7, 0, 0)) - 0.5;
        offset.z = noise3(noiseInput + vec3(0, 17.3, 0)) - 0.5;
        offset *= swarmScale * 1.5;

        // Beat kick: расширение radially наружу.
        vec3 outwardDir = normalize(base + vec3(0.001));
        base += outwardDir * kickPush;

        gPos[i] = base + offset;
        gRad[i] = 0.18 + 0.08 * rng(fi * 5.7 + 4.1);
    }
}

// ============================================================================
// SDF сцены — chain smin 16 сфер
// ============================================================================
float mapScene(vec3 p) {
    float d = sdSphere(p - gPos[0], gRad[0]);
    for (int i = 1; i < N_PARTICLES; i++) {
        d = smin(d, sdSphere(p - gPos[i], gRad[i]), 0.20);
    }
    return d;
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
    // Bounding sphere R=3.5 — все частицы внутри (max radius ~2.0 + noise 1.5).
    vec3 oc = ro;
    float b = dot(oc, rd);
    float c = dot(oc, oc) - 12.25;  // 3.5^2
    float disc = b * b - c;
    if (disc < 0.0) return vec2(-1.0, 0.0);
    float tStart = max(0.0, -b - sqrt(disc));

    float t = tStart;
    const int STEPS = 48;       // 48 — metaballs требуют больше шагов (soft merge)
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
    float a = uTime * 0.5;
    return normalize(vec3(sin(a), 0.6, cos(a)));
}

// Фон: тёмный градиент + лёгкая tint от uColor (родственный палитре).
vec3 backgroundColor(vec3 rd) {
    float t = 0.5 + 0.5 * rd.y;
    vec3 base = mix(vec3(0.02, 0.02, 0.05), vec3(0.06, 0.07, 0.12), t);
    return base + uColor * 0.04 * (1.0 - t);
}

// ACES tonemap.
vec3 aces(vec3 c) {
    return (c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14);
}

// Плотность роя в точке — насколько близко к какой-либо частице.
// Используется для glow: точки около центра роя — ярче.
float swarmDensity(vec3 p) {
    float density = 0.0;
    for (int i = 0; i < N_PARTICLES; i++) {
        float d = length(p - gPos[i]);
        density += exp(-d * d * 4.0);  // gaussian falloff
    }
    return density / float(N_PARTICLES);
}

// ============================================================================
// Main
// ============================================================================
void main() {
    vec2 fragUv = gl_FragCoord.xy / uResolution;
    vec2 uv = (fragUv * 2.0 - 1.0) * vec2(uResolution.x / uResolution.y, 1.0);

    // Предвычислить позиции частиц ОДИН раз за пиксель (не в mapScene).
    precomputeParticles();

    // Камера: плавное вращение, слегка сверху.
    float cam_t = uTime * 0.15;
    vec3 ro = vec3(sin(cam_t) * 5.0, 1.5, cos(cam_t) * 5.0);
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
        float spec = pow(max(dot(n, halfDir), 0.0), 24.0);

        // Цвет: uColor + плотность роя усиливает glow.
        float density = swarmDensity(p);
        float glowMul = 0.5 + density * 1.5;     // плотные области — ярче

        // Beat kick усиливает emissive (мгновенная вспышка).
        glowMul += uBeatKick * 0.8;

        vec3 surfColor = uColor * glowMul;

        vec3 surface = surfColor * (amb + diff * 0.7) + vec3(1.0) * spec * 0.4;
        // Emissive component — рой сам светится.
        surface += uColor * (0.3 + 0.4 * uSwarm);

        // Fog: blend с фоном по глубине.
        float fog = 1.0 - exp(-hit.x * 0.06);
        col = mix(surface, bg, fog * 0.4);
    }

    // Виньетка.
    vec2 vd = fragUv - 0.5;
    col *= 1.0 - 0.35 * dot(vd, vd) * 2.0;

    // ACES + gamma.
    col = aces(col);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));

    FragColor = vec4(col, 1.0);
}
