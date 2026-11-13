// grain.frag — Плёночное зерно. Post-processing, cost=1, uses_random.
// Контракт: uInput (sampler2D), uAmount (0..0.5).
#version 330 core
uniform float uTime; uniform float uClipTime; uniform float uProgress;
uniform float uGlobalTime; uniform vec2 uResolution; uniform int uSeed;
uniform float uBeat; uniform float uBeatPhase; uniform float uBarPhase; uniform float uEnergy;
uniform sampler2D uInput;
uniform float uAmount;
// v61: глобальная экспозиция в ЛИНЕЙНОМ пространстве (1.0 = без изменений).
// Нужна потому, что все цвета сцен были подобраны при баге зерна, которое
// вычитало 0.5*uAmount*2 из каждого кадра.
uniform float uExposure;
out vec4 FragColor;

// v61: целочисленный hash вместо fract-от-произведения.
// Старая версия складывала seed с координатой ДО умножения на 17: при seed >= 2e4
// произведение уходило в ~1e8, где float32 теряет дробную часть, и fract(...)
// возвращал ровно 0 — зерно «умирало» и вычитало 0.5*uAmount*2 из каждого кадра.
float hash3(vec3 p) {
    // v61.1: целочисленный hash (fract-версия давала ~64 уровня шума).
    ivec3 i = ivec3(floor(p));
    uint h = uint(i.x) * 0x8da6b343u ^ uint(i.y) * 0xd8163841u
           ^ uint(i.z) * 0xcb1ab31fu ^ uint(uSeed);
    h ^= h >> 13; h *= 0x5bd1e995u; h ^= h >> 15;
    return float(h & 0xFFFFFFu) / 16777216.0;
}

void main() {
    vec2 uv = gl_FragCoord.xy / uResolution;
    vec4 col = texture(uInput, uv);
    // v61: экспозиция до зерна — в линейном пространстве, чтобы чёрное оставалось чёрным.
    vec3 lin = pow(max(col.rgb, 0.0), vec3(2.2)) * max(uExposure, 0.0);
    col.rgb = pow(lin, vec3(1.0 / 2.2));
    // Animated grain: hash by pixel position + time (changes each frame, like real film).
    float n = hash3(vec3(gl_FragCoord.xy, uTime * 60.0));
    // Center noise around 0: -0.5..+0.5, then scale by uAmount.
    col.rgb += (n - 0.5) * uAmount * 2.0;
    FragColor = col;
}
