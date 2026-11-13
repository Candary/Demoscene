// cozy_room_sdf.frag — SDF-комната из примитивов Cozy Engine.
// Контракт: uPrimitives (farray: shape,axis,sx,sy,sz,px,py,pz,rot_y,r,g,b × N),
//           uPrimitivesCount (int), uLightColor (vec3), uCamAngle (float).
// kind: scene, cost: 4.
#version 330 core

uniform float uTime; uniform float uClipTime; uniform float uProgress;
uniform float uGlobalTime; uniform vec2 uResolution; uniform int uSeed;
uniform float uBeat; uniform float uBeatPhase; uniform float uBarPhase; uniform float uEnergy;

uniform float uPrimitives[384]; // 32 prims × 12 floats (runtime задаёт actual count через uPrimitivesCount)
uniform int   uPrimitivesCount;
uniform vec3  uLightColor;
uniform float uCamAngle;

out vec4 FragColor;

const float PI = 3.14159265359;
const int   MAX_PRIMS = 32;
const int   STRIDE = 12;

float sdSphere(vec3 p, float r) { return length(p) - r; }
float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}
float sdCylinder(vec3 p, float r, float h) {
    vec2 d = vec2(length(p.xz) - r, abs(p.y) - h);
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
}

// Global: color of closest primitive (set by mapScene).
vec3 gHitColor;

float mapScene(vec3 p) {
    float minDist = 1e9;
    gHitColor = vec3(0.5);
    for (int i = 0; i < MAX_PRIMS; i++) {
        if (i >= uPrimitivesCount) break;
        int b = i * STRIDE;
        float shape = uPrimitives[b + 0];
        vec3 size = vec3(uPrimitives[b+2], uPrimitives[b+3], uPrimitives[b+4]);
        vec3 pos = vec3(uPrimitives[b+5], uPrimitives[b+6], uPrimitives[b+7]);
        float rotY = uPrimitives[b+8];
        vec3 color = vec3(uPrimitives[b+9], uPrimitives[b+10], uPrimitives[b+11]);

        // Transform to primitive local space.
        vec3 lp = p - pos;
        float c = cos(-rotY), s = sin(-rotY);
        lp.xz = mat2(c, -s, s, c) * lp.xz;

        // SDF by shape type: 0=box, 1=sphere, 2=cylinder.
        float d;
        if (shape < 0.5) {
            d = sdBox(lp, size * 0.5);
        } else if (shape < 1.5) {
            d = sdSphere(lp, size.x);
        } else {
            d = sdCylinder(lp, size.x, size.y * 0.5);
        }

        if (d < minDist) {
            minDist = d;
            gHitColor = color;
        }
    }
    return minDist;
}

vec3 calcNormal(vec3 p) {
    const vec2 k = vec2(1.0, -1.0);
    const float e = 0.001;
    return normalize(
        k.xyy * mapScene(p + k.xyy * e) +
        k.yyx * mapScene(p + k.yyx * e) +
        k.yxy * mapScene(p + k.yxy * e) +
        k.xxx * mapScene(p + k.xxx * e));
}

vec2 rayMarch(vec3 ro, vec3 rd) {
    // Bounding sphere R=8 — room fits inside.
    vec3 oc = ro;
    float b = dot(oc, rd);
    float c = dot(oc, oc) - 64.0;
    float disc = b * b - c;
    if (disc < 0.0) return vec2(-1.0, 0.0);
    float t = max(0.0, -b - sqrt(disc));
    const int STEPS = 48;
    for (int i = 0; i < STEPS; i++) {
        vec3 p = ro + rd * t;
        float d = mapScene(p);
        if (d < 0.001) return vec2(t, 1.0);
        if (t > 30.0) break;
        t += d;
    }
    return vec2(-1.0, 0.0);
}

vec3 backgroundColor(vec3 rd) {
    float t = 0.5 + 0.5 * rd.y;
    return mix(vec3(0.02, 0.02, 0.03), vec3(0.05, 0.06, 0.08), t);
}

vec3 aces(vec3 c) {
    return (c * (2.51 * c + 0.03)) / (c * (2.43 * c + 0.59) + 0.14);
}

void main() {
    vec2 fragUv = gl_FragCoord.xy / uResolution;
    vec2 uv = (fragUv * 2.0 - 1.0) * vec2(uResolution.x / uResolution.y, 1.0);

    // Camera: orbits via uCamAngle.
    float a = uCamAngle;
    float dist = 6.0;
    vec3 ro = vec3(sin(a) * dist, 2.5, cos(a) * dist);
    vec3 ta = vec3(0.0, 1.0, 0.0);
    vec3 fwd = normalize(ta - ro);
    vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), fwd));
    vec3 up = cross(fwd, right);
    vec3 rd = normalize(fwd + uv.x * right + uv.y * up);

    vec3 bg = backgroundColor(rd);
    vec2 hit = rayMarch(ro, rd);
    vec3 col;
    if (hit.x < 0.0) {
        col = bg;
    } else {
        vec3 p = ro + rd * hit.x;
        vec3 n = calcNormal(p);
        // Light from above-front, tinted with uLightColor.
        vec3 ld = normalize(vec3(0.3, 0.8, 0.5));
        float diff = max(dot(n, ld), 0.0);
        float amb = 0.2 + 0.15 * max(dot(n, vec3(0.0, 1.0, 0.0)), 0.0);
        vec3 viewDir = -rd;
        vec3 halfDir = normalize(ld + viewDir);
        float spec = pow(max(dot(n, halfDir), 0.0), 32.0);
        // Surface color from closest primitive + light color tint.
        vec3 surface = gHitColor * (amb + diff * 0.7) + uLightColor * spec * 0.4;
        // Warm ambient from light color.
        surface += uLightColor * 0.1 * diff;
        float fog = 1.0 - exp(-hit.x * 0.06);
        col = mix(surface, bg, fog * 0.4);
    }

    vec2 vd = fragUv - 0.5;
    col *= 1.0 - 0.25 * dot(vd, vd) * 2.0;
    col = aces(col);
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));
    FragColor = vec4(col, 1.0);
}
