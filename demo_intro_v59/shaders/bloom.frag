// bloom.frag — Свечение ярких областей. Post-processing, cost=3.
// Контракт: uInput (sampler2D), uThreshold (0..2), uIntensity (0..3), uRadius (0.1..4).
// Single-pass approximation: circular sampling для cheap blur bright areas.
#version 330 core
uniform float uTime; uniform float uClipTime; uniform float uProgress;
uniform float uGlobalTime; uniform vec2 uResolution; uniform int uSeed;
uniform float uBeat; uniform float uBeatPhase; uniform float uBarPhase; uniform float uEnergy;
uniform sampler2D uInput;
uniform float uThreshold; uniform float uIntensity; uniform float uRadius;
out vec4 FragColor;
const float PI = 3.14159265359;

void main() {
    vec2 uv = gl_FragCoord.xy / uResolution;
    vec4 center = texture(uInput, uv);

    // Single-pass bloom: sample 12 points in circle, extract bright, average.
    vec3 bloomAccum = vec3(0.0);
    const int SAMPLES = 12;
    for (int i = 0; i < SAMPLES; i++) {
        float a = float(i) * (2.0 * PI / float(SAMPLES));
        vec2 offset = vec2(cos(a), sin(a)) * uRadius / uResolution;
        vec3 s = texture(uInput, uv + offset).rgb;
        // Bright pass: extract pixels above threshold.
        bloomAccum += max(s - uThreshold, 0.0);
    }
    bloomAccum /= float(SAMPLES);

    // Composite: original + blurred bright areas.
    vec3 col = center.rgb + bloomAccum * uIntensity;
    FragColor = vec4(col, center.a);
}
