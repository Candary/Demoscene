// grain.frag — Плёночное зерно. Post-processing, cost=1, uses_random.
// Контракт: uInput (sampler2D), uAmount (0..0.5).
#version 330 core
uniform float uTime; uniform float uClipTime; uniform float uProgress;
uniform float uGlobalTime; uniform vec2 uResolution; uniform int uSeed;
uniform float uBeat; uniform float uBeatPhase; uniform float uBarPhase; uniform float uEnergy;
uniform sampler2D uInput;
uniform float uAmount;
out vec4 FragColor;

float hash3(vec3 p) {
    p = fract(p * 0.3183099 + 0.1) + float(uSeed) * 0.0001;
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

void main() {
    vec2 uv = gl_FragCoord.xy / uResolution;
    vec4 col = texture(uInput, uv);
    // Animated grain: hash by pixel position + time (changes each frame, like real film).
    float n = hash3(vec3(gl_FragCoord.xy, uTime * 60.0));
    // Center noise around 0: -0.5..+0.5, then scale by uAmount.
    col.rgb += (n - 0.5) * uAmount * 2.0;
    FragColor = col;
}
