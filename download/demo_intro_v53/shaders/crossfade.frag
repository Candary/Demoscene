// crossfade.frag — Плавное смешивание A и B. Transition, cost=1.
// Контракт: uA, uB (sampler2D), uProgress (0..1). Без кастомных uniforms.
#version 330 core
uniform float uTime; uniform float uClipTime; uniform float uProgress;
uniform float uGlobalTime; uniform vec2 uResolution; uniform int uSeed;
uniform float uBeat; uniform float uBeatPhase; uniform float uBarPhase; uniform float uEnergy;
uniform sampler2D uA; uniform sampler2D uB;
out vec4 FragColor;
void main() {
    vec2 uv = gl_FragCoord.xy / uResolution;
    vec4 a = texture(uA, uv);
    vec4 b = texture(uB, uv);
    FragColor = mix(a, b, uProgress);
}
