// passthrough.frag — Simple texture copy for COMPOSITE with additive blend.
// Used as the final bloom pass: reads bloom texture, outputs it,
// GL additive blending (GL_ONE, GL_ONE) adds it to the destination.
// Контракт: uInput (sampler2D).
#version 330 core
uniform float uTime; uniform float uClipTime; uniform float uProgress;
uniform float uGlobalTime; uniform vec2 uResolution; uniform int uSeed;
uniform float uBeat; uniform float uBeatPhase; uniform float uBarPhase; uniform float uEnergy;
uniform sampler2D uInput;
out vec4 FragColor;

void main() {
    vec2 uv = gl_FragCoord.xy / uResolution;
    FragColor = texture(uInput, uv);
}
