// vignette.frag — Затемнение краёв. Post-processing, cost=1.
// Контракт: uInput (sampler2D), uStrength (0..1), uSoftness (0.05..1).
#version 330 core
uniform float uTime; uniform float uClipTime; uniform float uProgress;
uniform float uGlobalTime; uniform vec2 uResolution; uniform int uSeed;
uniform float uBeat; uniform float uBeatPhase; uniform float uBarPhase; uniform float uEnergy;
uniform sampler2D uInput;
uniform float uStrength; uniform float uSoftness;
out vec4 FragColor;
void main() {
    vec2 uv = gl_FragCoord.xy / uResolution;
    vec4 col = texture(uInput, uv);
    // Vignette: darken edges based on distance from center.
    vec2 d = uv - 0.5;
    float dist = length(d);
    float vignette = 1.0 - uStrength * smoothstep(0.5 - uSoftness * 0.5, 0.5, dist);
    FragColor = vec4(col.rgb * vignette, col.a);
}
