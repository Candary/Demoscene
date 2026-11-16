// path: cyclic_drown_v63/shaders/fall.frag
// Scene 3 "fall" (33-45s). 6-layer stratified ember field + smoke FBM bg + twinkle.
#version 330 core

uniform float uTime;       uniform float uClipTime;  uniform float uProgress;
uniform float uGlobalTime; uniform vec2  uResolution; uniform int   uSeed;
uniform float uBeat;       uniform float uBeatPhase;  uniform float uBarPhase;  uniform float uEnergy;

uniform vec3  uPrimaryColor;   // smoke base (dark gray)
uniform vec3  uAccentColor;    // ember orange
uniform float uIntensity;
uniform float uMotionSpeed;
uniform float uPulse;

out vec4 FragColor;

// Integer hash — v61.2 style (no reserved name clash).
float hash3(vec3 p) {
    ivec3 i = ivec3(floor(p));
    uint h = uint(i.x) * 0x8da6b343u ^ uint(i.y) * 0xd8163841u
           ^ uint(i.z) * 0xcb1ab31fu ^ uint(uSeed);
    h ^= h >> 13; h *= 0x5bd1e995u; h ^= h >> 15;
    return float(h & 0xFFFFFFu) / 16777216.0;
}

// Stratified ember field — 6 layers with per-layer cell density & speed.
// Risk #1 mitigation: bounded loop, mediump accumulator.
mediump float emberField(vec2 uv, float t) {
    mediump float acc = 0.0;
    const int LAYERS = 6;
    for (int i = 0; i < LAYERS; i++) {
        float fi = float(i);
        float fallSpeed = 0.4 + fi * 0.18;
        float drift     = 0.10 + fi * 0.05;
        vec2  cell      = vec2(8.0 + fi * 3.0, 5.0 + fi * 2.0);
        vec2  g = uv * cell;
        g.x += sin(t * drift + fi * 1.7) * 0.8;
        g.y += t * fallSpeed;
        vec2 i_g = floor(g);
        vec2 f_g = fract(g);
        float h = hash3(vec3(i_g, fi));
        // Sparse embers: only where hash > 0.86 (≈14% of cells per layer).
        if (h < 0.86) continue;
        float d = length(f_g - 0.5);
        float glow = smoothstep(0.5, 0.0, d);
        // Twinkle: per-ember phase from hash.
        float tw = 0.6 + 0.4 * sin(t * 6.0 + h * 50.0);
        acc += glow * tw * (1.0 - fi * 0.10);
    }
    return acc;
}

// 3-octave FBM for smoke bg — kept cheap (inline hash).
mediump float smokeFbm(vec2 p) {
    mediump float v = 0.0, a = 0.5;
    for (int i = 0; i < 3; i++) {
        vec3 pp = vec3(p, float(i));
        float n0 = hash3(floor(pp));
        float n1 = hash3(floor(pp) + ivec3(1,0,0));
        float n2 = hash3(floor(pp) + ivec3(0,1,0));
        float n3 = hash3(floor(pp) + ivec3(1,1,0));
        vec2 fr = fract(pp.xy);
        fr = fr * fr * (3.0 - 2.0 * fr);
        float nn = mix(mix(n0,n1,fr.x), mix(n2,n3,fr.x), fr.y);
        v += a * nn;
        p *= 2.07;
        a *= 0.5;
    }
    return v;
}

vec3 aces_safe(vec3 c) {
    c = max(c, vec3(0.0));
    return (c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14);
}

void main() {
    vec3  primary = max(uPrimaryColor, vec3(0.001));
    vec3  accent  = max(uAccentColor,  vec3(0.001));
    float intens  = max(uIntensity,    1.0);
    float speed   = max(uMotionSpeed,  0.0);
    float pulse   = max(uPulse,        0.0);

    vec2 uv = (gl_FragCoord.xy * 2.0 - uResolution) / uResolution.y;
    float t = uTime * speed;

    // Smoke background.
    float smoke = smokeFbm(uv * 1.5 + vec2(0.0, t * 0.05));
    vec3  bg = primary * (0.2 + 0.5 * smoke);

    // Embers + beat kick.
    float embers = emberField(uv * 1.2, t);
    embers *= 1.0 + 0.6 * pow(1.0 - uBeatPhase, 4.0) + 0.3 * pulse;

    vec3 col = bg + accent * embers * intens * 1.4;
    col = mix(col, primary * 0.3, 0.25);  // wash towards smoke

    // Vignette (darker than dawn — moody).
    vec2 vd = (gl_FragCoord.xy / uResolution) - 0.5;
    col *= 1.0 - 0.45 * dot(vd, vd) * 2.0;

    col = aces_safe(col);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));
    FragColor = vec4(col, 1.0);
}
