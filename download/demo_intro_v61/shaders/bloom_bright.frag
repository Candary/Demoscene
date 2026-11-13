// bloom_bright.frag — Bright-pass filter для multi-pass bloom.
#version 330 core
uniform float uTime; uniform float uClipTime; uniform float uProgress;
uniform float uGlobalTime; uniform vec2 uResolution; uniform int uSeed;
uniform float uBeat; uniform float uBeatPhase; uniform float uBarPhase; uniform float uEnergy;
uniform sampler2D uInput;
uniform float uThreshold;
uniform float uIntensity;
out vec4 FragColor;
void main() {
    vec2 uv = gl_FragCoord.xy / uResolution;
    vec3 col = texture(uInput, uv).rgb;
    float brightness = dot(col, vec3(0.2126, 0.7152, 0.0722));
    float contribution = smoothstep(uThreshold * 0.8, uThreshold * 1.2, brightness);
    col *= contribution * uIntensity;
    FragColor = vec4(col, 1.0);
}
