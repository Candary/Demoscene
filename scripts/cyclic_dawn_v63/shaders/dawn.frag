// path: cyclic_dawn_v63/shaders/dawn.frag
// Scene 1 "dawn" (0-12s). FBM domain warp, amber→yellow gradient, ACES tonemap.
// Target mean luminance ~0.4 sRGB.
// Pipeline uniforms (Color Matrix + motus + cyclic):
//   uPrimaryColor (deep amber base), uAccentColor (hot yellow),
//   uIntensity, uMotionSpeed, uPulse.
#version 330 core

uniform float uTime;       uniform float uClipTime;  uniform float uProgress;
uniform float uGlobalTime; uniform vec2  uResolution; uniform int   uSeed;
uniform float uBeat;       uniform float uBeatPhase;  uniform float uBarPhase;  uniform float uEnergy;

uniform vec3  uPrimaryColor;
uniform vec3  uAccentColor;
uniform float uIntensity;
uniform float uMotionSpeed;
uniform float uPulse;

out vec4 FragColor;

// v61.2: avoid reserved GLSL built-in names (noise2/noise3).
// Inline uint hash — no function-call overhead in FBM inner loop.
float hash2(vec2 p) {
    uvec2 q = uvec2(floor(p)) + uvec2(0x9E3779B9u, 0x85EBCA6Bu) + uint(uSeed) * 0x9E3779B1u;
    uint h = q.x ^ q.y;
    h ^= h >> 16; h *= 0x7feb352du; h ^= h >> 15;
    h *= 0x846ca68bu; h ^= h >> 16;
    return float(h & 0x00FFFFFFu) / float(0x01000000);
}

float vnoise2(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash2(i),               b = hash2(i + vec2(1.0, 0.0));
    float c = hash2(i + vec2(0.0,1.0)), d = hash2(i + vec2(1.0,1.0));
    return mix(mix(a,b,f.x), mix(c,d,f.x), f.y);
}

// Risk #1 mitigation: cap at 4 octaves (5+ spills registers on GTX 750).
float fbm4(vec2 p) {
    mediump float v = 0.0;
    mediump float a = 0.5;
    for (int i = 0; i < 4; i++) {
        v += a * vnoise2(p);
        p = p * 2.03 + vec2(1.7, 9.2);
        a *= 0.5;
    }
    return v;
}

// Risk #2 mitigation: pre-clamp input to ACES to avoid NaN on negative channels.
vec3 aces_safe(vec3 c) {
    c = max(c, vec3(0.0));
    return (c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14);
}

void main() {
    // Pipeline guards: max() prevents ×0 if uniform unset.
    vec3  primary = max(uPrimaryColor, vec3(0.001));
    vec3  accent  = max(uAccentColor,  vec3(0.001));
    float intens  = max(uIntensity,    1.0);
    float speed   = max(uMotionSpeed,  0.0);
    float pulse   = max(uPulse,        0.0);

    vec2 uv = (gl_FragCoord.xy * 2.0 - uResolution) / uResolution.y;
    float t = uTime * speed * 0.18;

    // Domain warp (Inigo Quilez pattern, 2 FBM taps for warp + 1 for field).
    vec2 q = vec2(fbm4(uv + t), fbm4(uv + vec2(1.7, 9.2) + t));
    vec2 r = vec2(
        fbm4(uv + 3.5 * q + vec2(8.3, 2.8) + t * 1.1),
        fbm4(uv + 3.5 * q + vec2(1.7, 9.2) - t * 0.7)
    );
    float f = fbm4(uv + 3.5 * r);

    // Hue mix: primary → accent via fbm² — pushes hue towards accent in dense regions.
    vec3 col = mix(primary, accent, clamp(f * f * 4.0, 0.0, 1.0));
    // Beat/pulse boost on brightest fbm regions.
    col += accent * pulse * 0.45 * smoothstep(0.55, 0.95, f);
    // Target mean ~0.4 sRGB after ACES+gamma: pre-ACES linear ~0.18.
    col *= intens * 0.55;

    // Vignette (spec: 0.35 strength).
    vec2 vd = (gl_FragCoord.xy / uResolution) - 0.5;
    col *= 1.0 - 0.35 * dot(vd, vd) * 2.0;

    col = aces_safe(col);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));
    FragColor = vec4(col, 1.0);
}
