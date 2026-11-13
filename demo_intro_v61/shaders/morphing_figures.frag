// ============================================================================
// morphing_figures.frag — v58: неинтерактивный шейдер из preview.html
// ----------------------------------------------------------------------------
// Эффект: 9 морфящихся SDF-фигур (сфера → куб → тор → октаэдр → треугольник →
//         конус → капсула → чайник → додекаэдр) с орбитальной камерой,
//         звёздным фоном и 8 объёмными частицами. Neon magenta-cyan-lime палитра.
//
// Контракт: только стандартные uniforms от Scene Manager рантайма.
//   uTime, uClipTime, uProgress, uGlobalTime, uResolution, uSeed,
//   uBeat, uBeatPhase, uBarPhase, uEnergy
//
// Неинтерактивные параметры (зашиты в шейдер):
//   zoom = 1.0 (фиксированная дистанция камеры)
//   mouseRot = (0, 0) (без вращения мышью)
//   fireMask = all 1.0 (без огня на частицах)
//   applyToneMap = 1 (всегда ACES)
//   droplets = 0 (без эффекта капель)
//
// Совместимость: OpenGL 3.3 core, GLSL 330.
// Производительность: 48 шагов raymarch + 8 частиц, ~30-50 FPS на GTX 750.
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

out vec4 FragColor;

const float PI  = 3.14159265359;
const float TAU = 6.28318530718;

// --- Палитра: неоновая магента-циан-лайм (как в preview.html) --------------
vec3 Palette(float t) {
    vec3 a = vec3(0.5, 0.5, 0.5);
    vec3 b = vec3(0.5, 0.5, 0.5);
    vec3 c = vec3(2.0, 1.0, 1.5);
    vec3 d = vec3(0.0, 0.25, 0.5);
    return a + b * cos(TAU * (c * t + d));
}

mat2 Rot2D(float angle) {
    float s = sin(angle);
    float c = cos(angle);
    return mat2(c, -s, s, c);
}

// --- SDF примитивы (как в preview.html) ------------------------------------
float sdSphere(vec3 p, float r) { return length(p) - r; }

float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}

float sdTorus(vec3 p, float R, float r) {
    vec2 q = vec2(length(p.xz) - R, p.y);
    return length(q) - r;
}

float sdOctahedron(vec3 p, float r) {
    p = abs(p);
    return (p.x + p.y + p.z - r) * 0.57735027;
}

float sdTriPrism(vec3 p, vec2 h) {
    vec3 q = abs(p);
    float d1 = q.z - h.y;
    float d2 = max(q.x * 0.866025 + p.y * 0.5, -p.y) - h.x * 0.5;
    return length(max(vec2(d1, d2), 0.0)) + min(max(d1, d2), 0.0);
}

float sdCone(vec3 p, float h, float r) {
    vec2 q = vec2(length(p.xz), p.y);
    float d_side = (q.x * h + q.y * r - h * r) / sqrt(h * h + r * r);
    float d_base = -q.y;
    return max(d_base, d_side);
}

float sdCapsule(vec3 p, vec3 a, vec3 b, float r) {
    vec3 pa = p - a;
    vec3 ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h) - r;
}

float smin(float a, float b, float k) {
    float kk = max(k, 0.005);
    float h = clamp(0.5 + 0.5 * (b - a) / kk, 0.0, 1.0);
    return mix(b, a, h) - kk * h * (1.0 - h);
}

float sdTeapot(vec3 p) {
    vec3 bodyP = p;
    bodyP.y /= 1.3;
    float body = sdSphere(bodyP, 0.5);
    float lid = sdSphere(p - vec3(0.0, 0.65, 0.0), 0.10);
    float knob = sdSphere(p - vec3(0.0, 0.78, 0.0), 0.04);
    float spout = sdCapsule(p, vec3(0.40, 0.05, 0.0), vec3(0.85, 0.45, 0.0), 0.07);
    vec3 handleP = (p - vec3(-0.45, 0.15, 0.0)).xzy;
    float handle = sdTorus(handleP, 0.20, 0.04);
    float d = body;
    d = smin(d, spout, 0.04);
    d = smin(d, handle, 0.04);
    d = smin(d, lid, 0.05);
    d = smin(d, knob, 0.02);
    return d;
}

float sdDodecahedron(vec3 p, float r) {
    const float PHI  = 1.61803398875;
    const float NORM = 0.525731112119134;
    float d1 = abs(dot(p, vec3(0.0, 1.0,  PHI) * NORM));
    float d2 = abs(dot(p, vec3(0.0, 1.0, -PHI) * NORM));
    float d3 = abs(dot(p, vec3(1.0,  PHI, 0.0) * NORM));
    float d4 = abs(dot(p, vec3(1.0, -PHI, 0.0) * NORM));
    float d5 = abs(dot(p, vec3(PHI, 0.0, 1.0)  * NORM));
    float d6 = abs(dot(p, vec3(PHI, 0.0, -1.0) * NORM));
    float d = max(max(d1, d2), max(d3, d4));
    d = max(d, max(d5, d6));
    return d - r;
}

// --- Материалы -------------------------------------------------------------
const float MAT_NONE     = 0.0;
const float MAT_MAIN     = 1.0;
const float MAT_PARTICLE = 2.0;

float hash(float n) {
    uint i = floatBitsToUint(n) ^ 0x12345678u;
    i = (i ^ (i >> 16u)) * 0x85ebca6bu;
    i = (i ^ (i >> 13u)) * 0xc2b2ae35u;
    i = i ^ (i >> 16u);
    return float(i) * (1.0 / 4294967296.0);
}

// --- Предвычисленные матрицы и позиции частиц ------------------------------
mat2 gRotXZ = mat2(1.0);
mat2 gRotYZ = mat2(1.0);
mat2 gRotXY = mat2(1.0);

vec3 gParticlePos[8];
float gParticleRad[8];

vec2 MapScene(vec3 p) {
    float t = uTime;

    // Без вращения мышью (неинтерактивный режим).

    p.xz = gRotXZ * p.xz;
    p.yz = gRotYZ * p.yz;
    p.xy = gRotXY * p.xy;

    float phase = mod(t * 0.25, 9.0);
    float idx   = floor(phase);
    float frac_ = smoothstep(0.0, 1.0, phase - idx);

    float d_main;
    if      (idx < 0.5) d_main = mix(sdSphere       (p, 1.0),
                                      sdBox          (p, vec3(0.85)), frac_);
    else if (idx < 1.5) d_main = mix(sdBox          (p, vec3(0.85)),
                                      sdTorus        (p, 0.8, 0.3), frac_);
    else if (idx < 2.5) d_main = mix(sdTorus        (p, 0.8, 0.3),
                                      sdOctahedron   (p, 1.0), frac_);
    else if (idx < 3.5) d_main = mix(sdOctahedron   (p, 1.0),
                                      sdTriPrism     (p, vec2(1.0, 0.5)), frac_);
    else if (idx < 4.5) d_main = mix(sdTriPrism     (p, vec2(1.0, 0.5)),
                                      sdCone         (p, 1.0, 0.9), frac_);
    else if (idx < 5.5) d_main = mix(sdCone         (p, 1.0, 0.9),
                                      sdCapsule      (p, vec3(-0.8, -0.6, 0.0), vec3(0.8, 0.6, 0.0), 0.35), frac_);
    else if (idx < 6.5) d_main = mix(sdCapsule      (p, vec3(-0.8, -0.6, 0.0), vec3(0.8, 0.6, 0.0), 0.35),
                                      sdTeapot       (p), frac_);
    else if (idx < 7.5) d_main = mix(sdTeapot       (p),
                                      sdDodecahedron (p, 1.0), frac_);
    else                d_main = mix(sdDodecahedron (p, 1.0),
                                      sdSphere       (p, 1.0), frac_);

    float d_part = 1e9;
    float pid_nearest = 0.0;
    for (int i = 0; i < 8; i++) {
        // Без fire mask — все частицы видны.
        float ds = sdSphere(p - gParticlePos[i], gParticleRad[i]);
        if (ds < d_part) {
            d_part = ds;
            pid_nearest = float(i);
        }
    }

    float d_combined = smin(d_main, d_part, 0.15);
    float matID = (d_main < d_part) ? MAT_MAIN : MAT_PARTICLE + pid_nearest * 0.1;
    return vec2(d_combined, matID);
}

vec3 CalcNormal(vec3 p) {
    const vec2 k = vec2(1.0, -1.0);
    const float e = 0.001;
    return normalize(
        k.xyy * MapScene(p + k.xyy * e).x +
        k.yyx * MapScene(p + k.yyx * e).x +
        k.yxy * MapScene(p + k.yxy * e).x +
        k.xxx * MapScene(p + k.xxx * e).x
    );
}

vec2 RayMarch(vec3 ro, vec3 rd) {
    float t = 0.0;
    const int steps = 48;
    const float maxDist = 50.0;
    for (int i = 0; i < steps; i++) {
        vec3 p = ro + rd * t;
        vec2 hit = MapScene(p);
        if (hit.x < 0.001) return vec2(t, hit.y);
        if (t > maxDist) return vec2(-1.0, MAT_NONE);
        t += hit.x;
    }
    return vec2(-1.0, MAT_NONE);
}

float StarField(vec3 dir) {
    vec3 p = dir * 8.0;
    vec3 id = floor(p);
    vec3 f = fract(p) - 0.5;
    float rnd = hash(dot(id, vec3(12.9898, 78.233, 37.719)));
    float d = length(f);
    float star = smoothstep(0.5, 0.0, d) * rnd;
    star *= 0.6 + 0.4 * sin(uTime * 3.0 + rnd * 100.0);
    return star * 0.7;
}

vec3 RenderScene(vec2 uv) {
    // Предвычисление матриц вращения.
    gRotXZ = Rot2D(uTime * 0.5);
    gRotYZ = Rot2D(uTime * 0.3);
    gRotXY = Rot2D(uTime * 0.2);

    // Предвычисление позиций частиц.
    for (int i = 0; i < 8; i++) {
        float fi = float(i);
        float angle = uTime * (0.4 + fi * 0.06) + fi * 0.78;
        float radius = 1.6 + 0.4 * sin(fi * 1.7 + uTime * 0.2);
        float yOff  = 0.8 * sin(fi * 0.9 + uTime * 0.3 + fi);
        gParticlePos[i] = vec3(cos(angle) * radius, yOff, sin(angle) * radius);
        gParticleRad[i] = 0.08 + 0.04 * sin(uTime * 2.0 + fi * 1.5);
    }

    // Камера: zoom=1.0 (зафиксировано).
    float cam_t = uTime * 0.3;
    float baseDist = 3.5;
    float dist = baseDist;  // zoom=1.0
    vec3 ro = vec3(
        sin(cam_t) * dist,
        sin(cam_t * 0.7) * (dist * 0.35),
        cos(cam_t) * dist
    );
    vec3 ta = vec3(0.0);
    vec3 forward = normalize(ta - ro);
    vec3 right   = normalize(cross(vec3(0.0, 1.0, 0.0), forward));
    vec3 up      = cross(forward, right);
    vec3 rd = normalize(forward + uv.x * right + uv.y * up);

    // Bounding sphere check.
    float bsRadius = 2.2;
    float bsB = dot(ro, rd);
    float bsC = dot(ro, ro) - bsRadius * bsRadius;
    float bsDisc = bsB * bsB - bsC;
    if (bsDisc < 0.0) {
        float bgGrad0 = 0.5 + 0.5 * rd.y;
        vec3 bgTop0    = Palette(uTime * 0.05 + 0.0);
        vec3 bgBot0    = Palette(uTime * 0.05 + 0.4);
        vec3 bg0 = mix(bgBot0, bgTop0, bgGrad0) * 0.6;
        bg0 += vec3(StarField(rd));
        vec2 q0 = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.x;
        bg0 *= 1.0 - 0.5 * dot(q0, q0);
        return bg0;
    }

    // Фон: градиентное небо + звёзды.
    float bgGrad = 0.5 + 0.5 * rd.y;
    vec3 bgColTop    = Palette(uTime * 0.05 + 0.0);
    vec3 bgColBottom = Palette(uTime * 0.05 + 0.4);
    vec3 bg = mix(bgColBottom, bgColTop, bgGrad) * 0.6;
    bg += vec3(StarField(rd));

    // Raymarching.
    vec2 hit = RayMarch(ro, rd);
    vec3 col = bg;

    if (hit.x > 0.0) {
        vec3 p = ro + rd * hit.x;
        vec3 n = CalcNormal(p);

        vec3 lightDir = normalize(vec3(
            sin(uTime * 0.7), 0.8, cos(uTime * 0.7)
        ));
        float diff = max(dot(n, lightDir), 0.0);
        float amb = 0.15 + 0.15 * max(dot(n, vec3(0.0, 1.0, 0.0)), 0.0);
        vec3 viewDir = -rd;
        vec3 halfDir = normalize(lightDir + viewDir);
        float spec = pow(max(dot(n, halfDir), 0.0), 32.0);

        if (hit.y >= MAT_PARTICLE) {
            float pid = (hit.y - MAT_PARTICLE) * 10.0;
            float rndType  = hash(pid * 7.3 + 1.0);
            float rndColor = hash(pid * 3.7 + 5.0);
            float pulse = 0.5 + 0.5 * sin(uTime * (1.5 + rndType * 2.0) + pid * 0.7);
            vec3 particleCol = Palette(pid * 0.13 + rndColor + uTime * 0.1);

            if (rndType > 0.5) {
                float glow = 1.5 + 1.0 * pulse;
                col = particleCol * glow;
                col += vec3(1.0) * pow(pulse, 3.0) * 0.4;
            } else {
                float alpha = 0.25 + 0.35 * pulse;
                float rim = pow(1.0 - abs(dot(n, viewDir)), 2.5);
                vec3 surface = particleCol * (amb * 0.7 + diff * 0.5);
                surface += particleCol * rim * 1.2;
                surface += vec3(1.0) * spec * 0.3;
                col = mix(bg, surface, alpha);
            }
        } else {
            vec3 objCol = Palette(p.x * 0.5 + p.y * 0.3 + p.z * 0.2 + uTime * 0.1);
            vec3 surface = objCol * (amb + diff * 0.8) + vec3(1.0) * spec * 0.5;
            float fog = 1.0 - exp(-hit.x * 0.08);
            col = mix(surface, bg, fog * 0.5);
            col += surface * 0.15;
        }
    }

    // Виньетирование.
    vec2 q = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.x;
    float vignette = 1.0 - 0.5 * dot(q, q);
    col *= vignette;

    return col;
}

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;
    vec3 col = RenderScene(uv);

    // ACES tonemap + gamma 2.2 (всегда включено).
    col = (col * (2.51 * col + 0.03)) / (col * (2.43 * col + 0.59) + 0.14);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));

    FragColor = vec4(col, 1.0);
}
