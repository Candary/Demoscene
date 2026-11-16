// path: cyclic_dawn_v63/shaders/bloom_transition.frag
// Transition between spire (scene 2) and fall (scene 3) — bloom-intensity flash.
// uA = spire texture, uB = fall texture.
// uProgress 0→1:
//   0.00-0.30: bloom grows on uA (spire becomes overexposed)
//   0.30-0.70: peak white-out, uA and uB mixed at ~0.5
//   0.70-1.00: bloom recedes, uB (fall) emerges
#version 330 core

uniform float uTime;       uniform float uClipTime;  uniform float uProgress;
uniform float uGlobalTime; uniform vec2  uResolution; uniform int   uSeed;
uniform float uBeat;       uniform float uBeatPhase;  uniform float uBarPhase;  uniform float uEnergy;

uniform sampler2D uA;       // outgoing scene (spire)
uniform sampler2D uB;       // incoming scene (fall)
uniform vec3  uColor;       // bloom tint (default white)
uniform float uPeak;        // peak bloom intensity (1.0)

out vec4 FragColor;

vec3 aces_safe(vec3 c) {
    c = max(c, vec3(0.0));
    return (c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14);
}

void main() {
    vec2 uv = gl_FragCoord.xy / uResolution;

    // Smoothstep uProgress for cinematic curve.
    float p = clamp(uProgress, 0.0, 1.0);
    p = p * p * (3.0 - 2.0 * p);

    // Three-phase bloom envelope (smoothstep segments).
    float bloomIntensity;
    if (p < 0.3) {
        bloomIntensity = smoothstep(0.0, 0.3, p) * uPeak;
    } else if (p < 0.7) {
        bloomIntensity = uPeak;  // peak hold
    } else {
        bloomIntensity = (1.0 - smoothstep(0.7, 1.0, p)) * uPeak;
    }

    // Crossfade mix: at p=0 → uA only; at p=1 → uB only; at p=0.5 → 50/50.
    float mixA = 1.0 - p;
    float mixB = p;

    vec3 colA = texture(uA, uv).rgb;
    vec3 colB = texture(uB, uv).rgb;

    // Additive bloom on the dominant scene + tint.
    vec3 bloomTint = max(uColor, vec3(0.001)) * bloomIntensity * 1.5;
    vec3 col = colA * mixA + colB * mixB + bloomTint;

    // Slight desaturation at peak (white-out feel).
    float lum = dot(col, vec3(0.2126, 0.7152, 0.0722));
    float desat = bloomIntensity * 0.5;
    col = mix(col, vec3(lum), desat);

    col = aces_safe(col);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));
    FragColor = vec4(col, 1.0);
}
