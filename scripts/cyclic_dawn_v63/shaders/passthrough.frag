// passthrough.frag — texture copy for COMPOSITE with additive blend.
#version 330 core
uniform float uTime; uniform float uClipTime; uniform float uProgress;
uniform float uGlobalTime; uniform vec2 uResolution; uniform int uSeed;
uniform float uBeat; uniform float uBeatPhase; uniform float uBarPhase; uniform float uEnergy;
uniform sampler2D uInput;
uniform float uIntensity;

out vec4 FragColor;
void main() {
    // v61.2 fix: removed duplicate `float intensity` declaration
    // (was GLSL compile error: 'intensity' redefinition — silently rejected
    // by NVIDIA driver, breaking the entire post-processing chain).
    float intensity = max(uIntensity, 1.0);
    vec2 uv = gl_FragCoord.xy / uResolution;
    FragColor = texture(uInput, uv);
}
