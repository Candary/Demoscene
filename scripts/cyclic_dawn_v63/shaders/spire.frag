// path: cyclic_dawn_v63/shaders/spire.frag
// Scene 2 "spire" (16.5-28.5s). Rotating triangle grid, acid-green edge glow,
// scanlines + chromatic aberration.
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

// SDF: equilateral triangle centered at origin (Inigo Quilez).
float sdEquilateralTriangle(vec2 p, float r) {
    const float k = 1.7320508; // sqrt(3)
    p.x = abs(p.x) - r;
    p.y = p.y + r / k;
    if (p.x + k * p.y > 0.0) p = vec2(p.x - k * p.y, -k * p.x - p.y) / 2.0;
    p.x -= clamp(p.x, -2.0 * r, 0.0);
    return -length(p) * sign(p.y);
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
    uv *= 3.5;

    // Rotating grid.
    float a = uTime * speed * 0.28;
    mat2 rot = mat2(cos(a), -sin(a), sin(a), cos(a));
    vec2 p = rot * uv;

    // Strategy #4 (procedural grid atom): mod-repeat + lattice.
    vec2 id = floor(p + 0.5);
    vec2 fp = fract(p + 0.5) - 0.5;

    float d = sdEquilateralTriangle(fp * 2.0, 0.85);
    float edge = smoothstep(0.025, 0.0, abs(d));

    // Per-cell hash for varied brightness (jitter).
    uvec2 q = uvec2(id) + uvec2(0x9E3779B9u, 0x85EBCA6Bu) + uint(uSeed);
    uint h = q.x ^ q.y;
    h ^= h >> 16; h *= 0x7feb352du; h ^= h >> 15;
    float cellHash = float(h & 0x00FFFFFFu) / float(0x01000000);

    // Strategy #5: runtime parameterization — beat & pulse drive glow intensity.
    float beatGlow = 0.6 + 0.8 * pulse + 0.4 * pow(1.0 - uBeatPhase, 4.0);

    vec3 col = primary;
    col += accent * edge * beatGlow * (0.5 + 0.7 * cellHash);
    col += primary * edge * 0.15;

    // Scanlines + chromatic aberration on edges (spec).
    col *= 0.85 + 0.15 * sin(gl_FragCoord.y * 1.6);
    // Random per-cell chromatic shift.
    float ca = 0.004 * (1.0 + pulse + cellHash);
    col.r = mix(col.r, col.r * 1.25, edge * ca * 80.0);
    col.b = mix(col.b, col.b * 0.85, edge * ca * 60.0);

    col *= intens;
    col = aces_safe(col);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));
    FragColor = vec4(col, 1.0);
}
