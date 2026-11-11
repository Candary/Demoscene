// bloom_bright.frag — Bright-pass filter для multi-pass bloom.
// Выделяет яркие пиксели (> threshold), остальные → чёрные.
// Контракт: uInput (sampler2D), uThreshold (0..2), uIntensity (0..3).
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
    // Brightness по luminance (Rec. 709)
    float brightness = dot(col, vec3(0.2126, 0.7152, 0.0722));
    // Soft threshold: плавный переход вместо жёсткого step
    float contribution = smoothstep(uThreshold * 0.8, uThreshold * 1.2, brightness);
    col *= contribution * uIntensity;
    FragColor = vec4(col, 1.0);
}
