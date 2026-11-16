// path: scripts/cyclic_dawn/shaders/ember_fall.frag
// Scene 3 "fall" (70-90s). Procedural ember particles + dark smoky bg.
#version 330 core

uniform float uTime;       uniform float uClipTime;  uniform float uProgress;
uniform float uGlobalTime; uniform vec2  uResolution; uniform int   uSeed;
uniform float uBeat;       uniform float uBeatPhase;  uniform float uBarPhase;  uniform float uEnergy;

uniform vec3  uPrimaryColor;   // smoke base (dark gray)
uniform vec3  uAccentColor;    // ember (orange)
uniform float uIntensity;
uniform float uMotionSpeed;
uniform float uPulse;

out vec4 FragColor;

// Integer hash — v61.2 style (no reserved name clash).
float hash3(vec3 p) {
    ivec3 i = ivec3(floor(p));
    uint h = uint(i.x) * 0x8da6b343u ^ uint(i.y) * 0xd8163841u
           ^ uint(i.z) * 0xcb1ab31fu ^ uint(uSeed);
    h ^= h >> 13; h *= 0x5bd1e995u; h ^= h >> 15;
    return float(h & 0xFFFFFFu) / 16777216.0;
}

// Stratified ember field: N layers of falling points.
float emberField(vec2 uv, float t) {
    float acc = 0.0;
    const int LAYERS = 6;
    for (int i = 0; i < LAYERS; i++) {
        float fi = float(i);
        // Per-layer fall speed + horizontal drift.
        float speed = 0.4 + fi * 0.18;
        float drift = 0.10 + fi * 0.05;
        vec2 cell = vec2(8.0 + fi * 3.0, 5.0 + fi * 2.0);
        vec2 g = uv * cell;
        g.x += sin(t * drift + fi * 1.7) * 0.8;
        g.y += t * speed;
        vec2 i_g = floor(g);
        vec2 f_g = fract(g);
        float h = hash3(vec3(i_g, fi));
        // Ember exists only where hash > threshold (sparse).
        float threshold = 0.86;
        if (h < threshold) continue;
        // Distance to ember center.
        float d = length(f_g - 0.5);
        float glow = smoothstep(0.5, 0.0, d);
        // Twinkle.
        float tw = 0.6 + 0.4 * sin(t * 6.0 + h * 50.0);
        acc += glow * tw * (1.0 - fi * 0.1);
    }
    return acc;
}

vec3 aces(vec3 c) { return (c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14); }

void main() {
    vec3  primary = max(uPrimaryColor, vec3(0.001));
    vec3  accent  = max(uAccentColor,  vec3(0.001));
    float intens  = max(uIntensity,    1.0);
    float speed   = max(uMotionSpeed,  0.0);
    float pulse   = max(uPulse,        0.0);

    vec2 uv = (gl_FragCoord.xy * 2.0 - uResolution) / uResolution.y;
    float t = uTime * speed;

    // Smoke background: low-frequency FBM-tinted primary.
    float smoke = 0.0;
    {
        vec2 q = uv * 1.5 + vec2(0.0, t * 0.05);
        // 3-octave FBM inline.
        float a = 0.5;
        vec2 p = q;
        float v = 0.0;
        for (int i = 0; i < 3; i++) {
            // 2-tap cheap noise from hash3.
            vec3 pp = vec3(p, float(i));
            float n0 = hash3(floor(pp));
            float n1 = hash3(floor(pp) + ivec3(1,0,0));
            float n2 = hash3(floor(pp) + ivec3(0,1,0));
            float n3 = hash3(floor(pp) + ivec3(1,1,0));
            vec2 fr = fract(pp.xy);
            fr = fr * fr * (3.0 - 2.0 * fr);
            float nn = mix(mix(n0,n1,fr.x), mix(n2,n3,fr.x), fr.y);
            v += a * nn;
            p *= 2.07;
            a *= 0.5;
        }
        smoke = v;
    }
    vec3 bg = primary * (0.2 + 0.5 * smoke);

    // Embers.
    float embers = emberField(uv * 1.2, t);
    // Beat kick: brighter embers on beat.
    embers *= 1.0 + 0.6 * pow(1.0 - uBeatPhase, 4.0) + 0.3 * pulse;

    vec3 col = bg + accent * embers * intens * 1.4;
    col = mix(col, primary * 0.3, 0.25);  // wash towards smoke

    // Vignette + tonemap.
    vec2 vd = (gl_FragCoord.xy / uResolution) - 0.5;
    col *= 1.0 - 0.45 * dot(vd, vd) * 2.0;
    col = aces(col);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));

    FragColor = vec4(col, 1.0);
}
