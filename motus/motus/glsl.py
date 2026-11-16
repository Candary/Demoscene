"""Опциональные шейдеры GLSL 330 core. Ядро их не использует — это адаптер.

ВНИМАНИЕ: в этой сессии шейдеры не прогонялись через glslangValidator.
Перед встраиванием проверьте: glslangValidator -S vert particle.vert и т.п.
Для GL_POINTS нужен glEnable(GL_PROGRAM_POINT_SIZE).
"""

PARTICLE_VS = """#version 330 core
layout(location=0) in vec3 aPos;
layout(location=1) in vec4 aColor;
layout(location=2) in float aSize;
uniform mat4 uViewProj;
uniform float uViewportH;
out vec4 vColor;
void main() {
    vec4 clip = uViewProj * vec4(aPos, 1.0);
    gl_Position = clip;
    gl_PointSize = max(1.0, aSize * uViewportH / max(0.0001, clip.w));
    vColor = aColor;
}
"""

PARTICLE_FS = """#version 330 core
in vec4 vColor;
out vec4 fragColor;
void main() {
    vec2 d = gl_PointCoord * 2.0 - 1.0;
    float r = dot(d, d);
    if (r > 1.0) discard;
    float a = vColor.a * (1.0 - r);
    fragColor = vec4(vColor.rgb * a, a);   // premultiplied, additive-friendly
}
"""

POST_FS = """#version 330 core
in vec2 vUv;
uniform sampler2D uScene;
uniform float uTime;
uniform float uVignette;
uniform float uGrain;
uniform vec3  uWave;      // x=radius, y=width, z=strength
uniform vec2  uWaveCenter;
out vec4 fragColor;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

void main() {
    vec2 uv = vUv;
    vec2 d = uv - uWaveCenter;
    float dist = length(d);
    float ring = exp(-pow((dist - uWave.x) / max(1e-4, uWave.y), 2.0));
    uv += normalize(d + 1e-6) * ring * uWave.z;
    vec3 c = texture(uScene, uv).rgb;
    c *= 1.0 - uVignette * smoothstep(0.35, 0.95, length(vUv - 0.5) * 1.4142);
    c += (hash(vUv * 1024.0 + uTime) - 0.5) * uGrain;
    fragColor = vec4(c, 1.0);
}
"""