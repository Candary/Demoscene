// bloom_blur.frag — Separable Gaussian blur для multi-pass bloom.
// 9-tap Gaussian kernel, direction via uDirection uniform.
// Контракт: uInput (sampler2D), uDirection (vec2: (1,0)=horizontal, (0,1)=vertical).
#version 330 core
uniform float uTime; uniform float uClipTime; uniform float uProgress;
uniform float uGlobalTime; uniform vec2 uResolution; uniform int uSeed;
uniform float uBeat; uniform float uBeatPhase; uniform float uBarPhase; uniform float uEnergy;
uniform sampler2D uInput;
uniform vec2 uDirection;   // (1,0) = horizontal, (0,1) = vertical
out vec4 FragColor;

// 9-tap Gaussian weights (sum = 1.0)
const float w[5] = float[](0.227027, 0.1945946, 0.1216216, 0.07567568, 0.025);

void main() {
    vec2 uv = gl_FragCoord.xy / uResolution;
    vec2 texelSize = uDirection / uResolution;  // direction-aware texel offset

    // Center tap
    vec3 col = texture(uInput, uv).rgb * w[0];

    // Symmetric taps (offset ±1, ±2, ±3, ±4)
    for (int i = 1; i <= 4; i++) {
        vec2 offset = texelSize * float(i);
        col += texture(uInput, uv + offset).rgb * w[i];
        col += texture(uInput, uv - offset).rgb * w[i];
    }

    FragColor = vec4(col, 1.0);
}
