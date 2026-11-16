// path: scripts/cyclic_dawn/shaders/fluid_dawn.frag
// Scene 1 "dawn" (0-35s). FBM + domain warp, warm palette.
// Pipeline uniforms: uPrimaryColor, uAccentColor, uIntensity, uMotionSpeed, uPulse.
#version 330 core

uniform float uTime;       uniform float uClipTime;  uniform float uProgress;
uniform float uGlobalTime; uniform vec2  uResolution; uniform int   uSeed;
uniform float uBeat;       uniform float uBeatPhase;  uniform float uBarPhase;  uniform float uEnergy;

uniform vec3  uPrimaryColor;  // warm base (deep orange)
uniform vec3  uAccentColor;   // hot yellow
uniform float uIntensity;     // 0..2
uniform float uMotionSpeed;   // 0..2
uniform float uPulse;         // 0..1

out vec4 FragColor;

const float TAU = 6.28318530718;

// v61.2: avoid reserved name `noise3`/`noise2` — use `vnoise*`.
float hash2(vec2 p) {
    uvec2 q = uvec2(floor(p)) + uvec2(0x9E3779B9u, 0x85EBCA6Bu);
    uint h = q.x ^ q.y ^ uint(uSeed);
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

float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 5; i++) { v += a * vnoise2(p); p = p * 2.03 + vec2(1.7, 9.2); a *= 0.5; }
    return v;
}

vec3 aces(vec3 c) { return (c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14); }

void main() {
    vec3  primary = max(uPrimaryColor, vec3(0.001));
    vec3  accent  = max(uAccentColor,  vec3(0.001));
    float intens  = max(uIntensity,    1.0);
    float speed   = max(uMotionSpeed,  0.0);
    float pulse   = max(uPulse,        0.0);

    vec2 uv = (gl_FragCoord.xy * 2.0 - uResolution) / uResolution.y;
    float t = uTime * speed * 0.15;

    // Domain warp (Inigo Quilez pattern).
    vec2 q = vec2(fbm(uv + t), fbm(uv + vec2(1.7, 9.2) + t));
    vec2 r = vec2(
        fbm(uv + 4.0 * q + vec2(8.3, 2.8) + t * 1.2),
        fbm(uv + 4.0 * q + vec2(1.7, 9.2) - t * 0.7)
    );
    float f = fbm(uv + 4.0 * r);

    // Hue mix: primary -> accent via fbm field; pulse boost on beat.
    vec3 col = mix(primary, accent, clamp(f * f * 4.0, 0.0, 1.0));
    col += accent * pulse * 0.4 * smoothstep(0.55, 0.95, f);
    col *= intens * 0.9;

    // Slow vignette + tonemap.
    vec2 vd = (gl_FragCoord.xy / uResolution) - 0.5;
    col *= 1.0 - 0.35 * dot(vd, vd) * 2.0;
    col = aces(col);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));

    FragColor = vec4(col, 1.0);
}
