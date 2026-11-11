// ============================================================================
// nebula_raymarch.frag
// ----------------------------------------------------------------------------
// Эффект: рэймарчинг туманности — volumetric 3D noise accumulation.
// (Основной эффект интро v49, в новой архитектуре Scene Manager.)
//
// Контракт (см. nebula_raymarch.effect.json):
//   uPrimaryColor vec3  — palette.primary (deep indigo base)
//   uAccentColor  vec3  — palette.accent (vibrant cyan/magenta highlights)
//   uIntensity    float — 0..2 (default bind: 0.4 + energy) — общая яркость
//   uMotionSpeed  float — 0..3 (default bind: 0.6 + energy*0.8) — скорость дрейфа
//   uPulse        float — 0..1 (default bind: pow(1-beat_phase, 4) * 0.4) — beat pulse
//
// Стандартные uniforms:
//   uTime, uClipTime, uProgress, uGlobalTime, uResolution, uSeed,
//   uBeat, uBeatPhase, uBarPhase, uEnergy
//
// Архитектура:
//   Volumetric raymarching через 3D noise field.
//   Для каждого пикселя: cast ray, march 40 шагов, на каждом шаге sample 3D FBM,
//   accumulate density × color. Не SDF — нет поверхности, только accumulation.
//
// Производительность: cost=4 (самый тяжёлый). 40 шагов × FBM (4 octaves) = heavy.
//   На GTX 480 @ 1080p — ожидаемо 30-50 FPS (vs 60+ для lighter shaders).
//
// Совместимость: OpenGL 3.3 core, GLSL 330. Total-semantic.
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

// --- Effect uniforms (из manifest nebula_raymarch.effect.json) --------------
uniform vec3  uPrimaryColor;   // palette.primary — deep indigo
uniform vec3  uAccentColor;    // palette.accent — vibrant highlight
uniform float uIntensity;      // 0..2
uniform float uMotionSpeed;    // 0..3
uniform float uPulse;          // 0..1 — beat pulse

// --- Выход ------------------------------------------------------------------
out vec4 FragColor;

// ============================================================================
// Константы
// ============================================================================

const float PI  = 3.14159265359;
const float TAU = 6.28318530718;

// Volumetric raymarch parameters.
uniform int uVolumeSteps;             // adaptive: 40 default, 24 low quality (set by runtime)
const int   MAX_VOLUME_STEPS = 40;    // GLSL 330: max bound for loop
const float VOLUME_NEAR  = 1.0;       // начать raymarch с t=1
const float VOLUME_FAR   = 20.0;      // заканчиваем на t=20
const float DENSITY_SCALE = 0.6;      // масштаб плотности (visual)

// ============================================================================
// Hash и noise
// ============================================================================

float hash3(vec3 p) {
    // uSeed подмешивается для per-show вариации.
    p = fract(p * 0.3183099 + 0.1) + float(uSeed) * 0.0001;
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

// Value noise 3D — trilinear.
float noise3(vec3 p) {
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

// 4-octave FBM.
float fbm(vec3 p) {
    float v = 0.0;
    float a = 0.5;
    v += a * noise3(p);          p = p * 2.0 + vec3(1.7, 2.3, 3.1); a *= 0.5;
    v += a * noise3(p);          p = p * 2.0 + vec3(1.7, 2.3, 3.1); a *= 0.5;
    v += a * noise3(p);          p = p * 2.0 + vec3(1.7, 2.3, 3.1); a *= 0.5;
    v += a * noise3(p);
    return v;
}

// ============================================================================
// Volumetric density field
// ----------------------------------------------------------------------------
// Возвращает density (0..1) в точке p. Использует domain-warped FBM.
// ============================================================================

float densityField(vec3 p) {
    // Анимация: медленный дрейф со временем + uMotionSpeed.
    vec3 anim = vec3(0.0, 0.0, uTime * uMotionSpeed * 0.1);

    // Domain warp: FBM от FBM — даёт "облака" структуры.
    vec3 q = p + anim;
    float warp = fbm(q + vec3(5.2, 1.3, 0.0));
    float mist = fbm(q + vec3(2.0 * warp, 2.0 * warp, 0.0));

    // Threshold: только плотные области дают visible mist.
    // smoothstep даёт мягкий край.
    return smoothstep(0.4, 0.75, mist);
}

// ============================================================================
// Volumetric raymarch — accumulate color along ray
// ============================================================================
vec4 volumetricMarch(vec3 ro, vec3 rd) {
    // OPTIMIZATION: mediump для accumulation storage.
    // highp остаётся для ray position (точность важна), mediump для color accumulation.
    mediump vec3 totalColor = vec3(0.0);
    mediump float totalAlpha = 0.0;

    // OPTIMIZATION: Adaptive step size — larger steps in empty regions.
    // В плотных областях шаг нормальный (точность), в пустых — 2.5× (speed).
    float baseStepSize = (VOLUME_FAR - VOLUME_NEAR) / float(uVolumeSteps);

    float t = VOLUME_NEAR;
    for (int i = 0; i < MAX_VOLUME_STEPS; i++) {
        if (i >= uVolumeSteps) break;  // adaptive step count
        if (t >= VOLUME_FAR) break;
        vec3 p = ro + rd * t;

        float density = densityField(p) * DENSITY_SCALE;

        if (density > 0.001) {
            // Цвет: mix primary и accent в зависимости от density.
            float colorMix = smoothstep(0.2, 0.8, density);
            mediump vec3 localColor = mix(uPrimaryColor, uAccentColor, colorMix);

            // Brightness modulation: distance fade + uIntensity + uPulse.
            float distFade = 1.0 / (1.0 + t * 0.1);
            float brightness = uIntensity * distFade * (1.0 + uPulse * 0.5);

            // Front-to-back accumulation.
            mediump float sampleAlpha = density * baseStepSize * 0.3;
            mediump vec3 sampleColor = localColor * brightness;

            totalColor += (1.0 - totalAlpha) * sampleColor * sampleAlpha;
            totalAlpha += (1.0 - totalAlpha) * sampleAlpha;

            // Early exit if fully opaque.
            if (totalAlpha > 0.95) break;
        }

        // ADAPTIVE STEP: 2.5× larger step in empty regions (density < 0.01),
        // normal step in dense regions. Эффективно покрывает больше empty space
        // тем же числом iterations.
        float stepMult = (density < 0.01) ? 2.5 : 1.0;
        t += baseStepSize * stepMult;
    }

    return vec4(totalColor, totalAlpha);
}

// ============================================================================
// Background + post-processing
// ============================================================================

// Тёмный фон с лёгкой tint от primary color.
vec3 backgroundColor(vec3 rd) {
    float t = 0.5 + 0.5 * rd.y;
    vec3 base = mix(vec3(0.02, 0.02, 0.04), vec3(0.05, 0.06, 0.10), t);
    return base + uPrimaryColor * 0.03 * (1.0 - t);
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

    // Камера: статичная (или лёгкое вращение), смотрит вдоль +Z.
    float cam_t = uTime * 0.05 * uMotionSpeed;
    vec3 ro = vec3(sin(cam_t) * 1.5, 0.0, -6.0);
    vec3 ta = vec3(0.0, 0.0, 0.0);
    vec3 fwd = normalize(ta - ro);
    vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), fwd));
    vec3 up = cross(fwd, right);
    vec3 rd = normalize(fwd + uv.x * right + uv.y * up);

    // Volumetric march.
    vec4 vol = volumetricMarch(ro, rd);

    // Background (виден там, где volumetric alpha < 1).
    vec3 bg = backgroundColor(rd);
    vec3 col = mix(bg, vol.rgb, vol.a);

    // Pulse brightness boost.
    col += uAccentColor * uPulse * 0.2;

    // Vignette.
    vec2 vd = fragUv - 0.5;
    col *= 1.0 - 0.35 * dot(vd, vd) * 2.0;

    // ACES + gamma.
    col = aces(col);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));

    FragColor = vec4(col, 1.0);
}
