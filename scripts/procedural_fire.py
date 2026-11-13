#!/usr/bin/env python3
"""Replace texture-based fire with procedural particle fire in preview.html.

Approach (from Chinedufn tutorial, but procedural — no texture):
- Per fire source: N=30 particles, each with own lifetime/velocity/offset/phase.
- Time loops with mod(uTime + aPhase, aLifetime) — particles recycle.
- Velocity mostly along uFireUp (= normalize(uFirePos)) — radial outward.
- Color: white-yellow (born) -> orange -> red (dying), procedurally.
- Size shrinks quadratically with age (vLife^2).
- Soft circular alpha falloff (exp(-d^2 * 2.5)).
- Additive blending, fire-level fade in/out.
"""
import re
import sys
from pathlib import Path

HTML_PATH = Path("/home/z/my-project/download/demo_intro/preview.html")
html = HTML_PATH.read_text(encoding="utf-8")

# === 1. Replace fire-vertex-shader ===
NEW_FIRE_VS = '''<script id="fire-vertex-shader" type="x-shader/x-vertex">#version 300 es
// Процедурный огонь: каждый источник = N мелких частиц со своими
// lifetime/velocity/offset/phase. Время зациклено через mod(t+phase, lifetime),
// частицы рециклятся — непрерывная анимация. Билборд через right/up камеры
// (как в основной сцене). Подход из урока Chinedufn (particle billboard),
// но без текстуры — цвет и форма частицы процедурные во фрагментном шейдере.
precision highp float;

layout(location = 0) in vec2  aTriCorner;     // угол квада (-1..1)
layout(location = 1) in vec3  aCenterOffset;  // стартовое смещение партикла (мир)
layout(location = 2) in vec3  aVelocity;      // скорость партикла (мир)
layout(location = 3) in float aLifetime;      // длительность жизни (сек)
layout(location = 4) in float aPhase;          // фазовый сдвиг 0..aLifetime

uniform float uTime;        // локальное время с момента старта огня (сек)
uniform vec3  uFirePos;    // позиция источника в мире
uniform vec3  uFireUp;     // «вверх» для партиклов (= normalize(uFirePos))
uniform float uFireSize;   // базовый размер партикла
uniform vec3  uCamPos;
uniform vec3  uCamFwd;
uniform vec3  uCamRight;
uniform vec3  uCamUp;
uniform float uAspect;

out vec2  vLocalUV;  // -1..1 (для фрагментного шейдера)
out float vLife;     // 1 = только что родился, 0 = умирает

void main() {
    // Локальное время циклит — частица рециклится.
    float t = mod(uTime + aPhase, aLifetime);
    float normT = t / aLifetime;
    vLife = 1.0 - normT;

    // Скорость: в основном вдоль uFireUp + лёгкий случайный разброс.
    vec3 velocity = uFireUp * (0.35 + aLifetime * 0.15) + aVelocity * 0.15;
    vec3 worldPos = uFirePos + aCenterOffset + t * velocity;

    // Билборд: смещение по right/up камеры * размер * угол квада.
    // Размер падает квадратично с возрастом (как в уроке Chinedufn).
    float size = uFireSize * (vLife * vLife * 0.7 + 0.3);
    worldPos += (uCamRight * aTriCorner.x + uCamUp * aTriCorner.y) * size;

    // Проекция в clip space (повторяет логику raymarch-камеры).
    vec3 view = worldPos - uCamPos;
    float z = dot(view, uCamFwd);
    float invZ = 1.0 / max(z, 0.001);
    vec2 screenUV = vec2(dot(view, uCamRight) * invZ, dot(view, uCamUp) * invZ);
    gl_Position = vec4(vec2(screenUV.x / uAspect, screenUV.y) * 2.0, 0.0, 1.0);

    vLocalUV = aTriCorner;  // -1..1
}
</script>'''

# Match from <script id="fire-vertex-shader" to </script>
pattern_vs = re.compile(
    r'<script id="fire-vertex-shader"[^>]*>.*?</script>',
    re.DOTALL
)
html = pattern_vs.sub(NEW_FIRE_VS, html, count=1)

# === 2. Replace fire-fragment-shader ===
NEW_FIRE_FS = '''<script id="fire-fragment-shader" type="x-shader/x-fragment">#version 300 es
// Процедурная частица огня (без текстуры): мягкий круг с цветовым
// градиентом по возрасту: бело-жёлтый (родился) -> жёлтый -> оранжевый
// -> красный (умирает). Аддитивный блендинг даёт неоновое свечение.
precision highp float;

in vec2  vLocalUV;  // -1..1
in float vLife;     // 1 = молодая, 0 = умирающая

uniform float uFadeAlpha;  // fade-in/out на уровне источника (0..1)

out vec4 FragColor;

// Цвет огня по возрасту (age = 1 - vLife, 0 = родился, 1 = умирает).
vec3 fireColor(float age) {
    vec3 whiteYellow = vec3(1.00, 0.95, 0.70);
    vec3 yellow      = vec3(1.00, 0.80, 0.25);
    vec3 orange      = vec3(1.00, 0.40, 0.10);
    vec3 red         = vec3(0.70, 0.12, 0.05);
    if (age < 0.20) return mix(whiteYellow, yellow, age / 0.20);
    if (age < 0.55) return mix(yellow, orange, (age - 0.20) / 0.35);
    return mix(orange, red, (age - 0.55) / 0.45);
}

void main() {
    vec2 uv = vLocalUV;
    float d2 = dot(uv, uv);   // 0..2
    if (d2 > 1.0) discard;   // вне круга — не пишем

    // Мягкое круглое затухание (гауссоподобное).
    float alpha = exp(-d2 * 2.5);
    alpha *= vLife * uFadeAlpha;

    // Цвет по возрасту + лёгкое усиление молодых частиц («горячее ядро»).
    float age = 1.0 - vLife;
    vec3 col = fireColor(age);
    col *= 1.0 + (1.0 - age) * 0.4;

    FragColor = vec4(col, alpha);
}
</script>'''

pattern_fs = re.compile(
    r'<script id="fire-fragment-shader"[^>]*>.*?</script>',
    re.DOTALL
)
html = pattern_fs.sub(NEW_FIRE_FS, html, count=1)

# === 3. Replace fire JS setup block (program/uniforms/VAO/texture/helpers) ===
# Anchor: from "// --- Компиляция программы огня ---" through end of fireImg.src line
NEW_FIRE_SETUP = '''// --- Компиляция программы огня (процедурная, без текстуры) ---
const fireVS = document.getElementById('fire-vertex-shader').textContent;
const fireFS = document.getElementById('fire-fragment-shader').textContent;
const fireProg = (function() {
    const vs2 = compileShader(gl.VERTEX_SHADER, fireVS);
    const fs2 = compileShader(gl.FRAGMENT_SHADER, fireFS);
    const p = gl.createProgram();
    gl.attachShader(p, vs2);
    gl.attachShader(p, fs2);
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
        throw new Error('Fire program link failed: ' + gl.getProgramInfoLog(p));
    }
    return p;
})();

const fireU = {
    uCamPos:    gl.getUniformLocation(fireProg, 'uCamPos'),
    uCamFwd:    gl.getUniformLocation(fireProg, 'uCamFwd'),
    uCamRight:  gl.getUniformLocation(fireProg, 'uCamRight'),
    uCamUp:     gl.getUniformLocation(fireProg, 'uCamUp'),
    uAspect:    gl.getUniformLocation(fireProg, 'uAspect'),
    uTime:      gl.getUniformLocation(fireProg, 'uTime'),
    uFirePos:   gl.getUniformLocation(fireProg, 'uFirePos'),
    uFireUp:    gl.getUniformLocation(fireProg, 'uFireUp'),
    uFireSize:  gl.getUniformLocation(fireProg, 'uFireSize'),
    uFadeAlpha: gl.getUniformLocation(fireProg, 'uFadeAlpha'),
};

// --- VBO с шаблоном партиклов (один на все источники огня) ---
// 30 партиклов × 6 вершин = 180 вершин. На партикл: triCorner(2) +
// centerOffset(3) + velocity(3) + lifetime(1) + phase(1) = 10 float'ов.
const FIRE_PARTICLES = 30;
const FIRE_VERTS_PER_PARTICLE = 6;
const FIRE_TOTAL_VERTS = FIRE_PARTICLES * FIRE_VERTS_PER_PARTICLE;
const FIRE_FLOATS_PER_VERT = 10;
const FIRE_STRIDE = FIRE_FLOATS_PER_VERT * 4;  // байты

const fireVBO = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, fireVBO);
(function buildFireVBO() {
    const data = new Float32Array(FIRE_TOTAL_VERTS * FIRE_FLOATS_PER_VERT);
    const corners = [
        [-1, -1], [1, -1], [-1, 1], [-1, 1], [1, -1], [1, 1]
    ];
    for (let p = 0; p < FIRE_PARTICLES; p++) {
        // Случайные параметры партикла (фиксируем один раз — все источники
        // используют один и тот же шаблон, отличаясь только позицией).
        const cx = (Math.random() - 0.5) * 0.10;
        const cy = (Math.random() - 0.5) * 0.05 - 0.02;
        const cz = (Math.random() - 0.5) * 0.10;
        const vx = (Math.random() - 0.5) * 0.30;
        const vy = (Math.random() - 0.5) * 0.20;
        const vz = (Math.random() - 0.5) * 0.30;
        const lt = 0.6 + Math.random() * 1.2;   // 0.6..1.8 с
        const phase = Math.random() * lt;
        for (let v = 0; v < FIRE_VERTS_PER_PARTICLE; v++) {
            const i = (p * FIRE_VERTS_PER_PARTICLE + v) * FIRE_FLOATS_PER_VERT;
            data[i + 0] = corners[v][0];
            data[i + 1] = corners[v][1];
            data[i + 2] = cx;
            data[i + 3] = cy;
            data[i + 4] = cz;
            data[i + 5] = vx;
            data[i + 6] = vy;
            data[i + 7] = vz;
            data[i + 8] = lt;
            data[i + 9] = phase;
        }
    }
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    console.log('Fire VBO built:', FIRE_TOTAL_VERTS, 'verts', FIRE_PARTICLES, 'particles');
})();

// VAO огня с атрибутами: 5 атрибутов, stride 10 float.
const fireVAO = gl.createVertexArray();
gl.bindVertexArray(fireVAO);
gl.bindBuffer(gl.ARRAY_BUFFER, fireVBO);
gl.enableVertexAttribArray(0);
gl.vertexAttribPointer(0, 2, gl.FLOAT, false, FIRE_STRIDE, 0);              // aTriCorner
gl.enableVertexAttribArray(1);
gl.vertexAttribPointer(1, 3, gl.FLOAT, false, FIRE_STRIDE, 2 * 4);          // aCenterOffset
gl.enableVertexAttribArray(2);
gl.vertexAttribPointer(2, 3, gl.FLOAT, false, FIRE_STRIDE, 5 * 4);          // aVelocity
gl.enableVertexAttribArray(3);
gl.vertexAttribPointer(3, 1, gl.FLOAT, false, FIRE_STRIDE, 8 * 4);          // aLifetime
gl.enableVertexAttribArray(4);
gl.vertexAttribPointer(4, 1, gl.FLOAT, false, FIRE_STRIDE, 9 * 4);         // aPhase
gl.bindVertexArray(null);
gl.bindBuffer(gl.ARRAY_BUFFER, null);'''

# Match from "// --- Компиляция программы огня" through "fireImg.src = '<anything>';"
# (the data URI contains ';' chars — match to closing quote + semicolon)
pattern_setup = re.compile(
    r'// --- Компиляция программы огня.*?fireImg\.src = \'[^\']*\';',
    re.DOTALL
)
new_html, n = pattern_setup.subn(NEW_FIRE_SETUP, html, count=1)
if n != 1:
    print(f"ERROR: setup block not found (substitutions={n})", file=sys.stderr)
    sys.exit(1)
html = new_html

# === 4. Replace fire render block ===
# Find the fire rendering block: from "// === Проход огня" to "// FPS" before FPS counter.
NEW_FIRE_RENDER = '''    // === Проход огня (поверх основной сцены, аддитивный блендинг) ===
    // Процедурный мультипартикльный огонь: на каждый активный источник —
    // 30 частиц со своими lifetime/velocity/phase. Без текстуры — цвет и
    // форма полностью процедурные.
    if (fireEnabled && fires.length > 0) {
        gl.useProgram(fireProg);
        gl.bindVertexArray(fireVAO);
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE);

        // Камера (повторяет логику raymarch-сцены).
        const cam_t = timeAccum * 0.3;
        const _dist = 3.5 / Math.max(zoom, 0.001);
        const ro = [Math.sin(cam_t) * _dist,
                    Math.sin(cam_t * 0.7) * (_dist * 0.35),
                    Math.cos(cam_t) * _dist];
        const fwd   = normalize3(sub3([0,0,0], ro));
        const right = normalize3(cross3([0,1,0], fwd));
        const up    = cross3(fwd, right);
        const aspect = canvas.width / canvas.height;

        gl.uniform3f(fireU.uCamPos,   ro[0], ro[1], ro[2]);
        gl.uniform3f(fireU.uCamFwd,   fwd[0], fwd[1], fwd[2]);
        gl.uniform3f(fireU.uCamRight, right[0], right[1], right[2]);
        gl.uniform3f(fireU.uCamUp,    up[0], up[1], up[2]);
        gl.uniform1f(fireU.uAspect, aspect);

        for (const f of fires) {
            const elapsed = timeAccum - f.startTime;
            if (elapsed < 0 || elapsed > FIRE_LIFETIME) continue;

            // Позиция частицы-источника в мире.
            const wp = particleWorldPos(f.particleIdx, timeAccum, rotYaw, rotPitch);
            gl.uniform3f(fireU.uFirePos, wp[0], wp[1], wp[2]);

            // uFireUp = normalize(uFirePos) — партиклы летят радиально наружу.
            const upLen = Math.hypot(wp[0], wp[1], wp[2]) || 1e-9;
            gl.uniform3f(fireU.uFireUp, wp[0]/upLen, wp[1]/upLen, wp[2]/upLen);

            // Размер = радиус частицы × коэфф (видимая частица воды).
            const radius = 0.08 + 0.04 * Math.sin(timeAccum * 2.0 + f.particleIdx * 1.5);
            gl.uniform1f(fireU.uFireSize, radius * 3.0);

            // Локальное время огня (с момента зажигания).
            gl.uniform1f(fireU.uTime, elapsed);

            // Fade in (0.4 с) → hold → fade out (0.5 с).
            let fadeAlpha;
            if (elapsed < 0.4) fadeAlpha = elapsed / 0.4;
            else if (elapsed > FIRE_LIFETIME - 0.5) fadeAlpha = (FIRE_LIFETIME - elapsed) / 0.5;
            else fadeAlpha = 1.0;
            gl.uniform1f(fireU.uFadeAlpha, fadeAlpha);

            // Рисуем все 30 партиклов одним draw call'ом.
            gl.drawArrays(gl.TRIANGLES, 0, FIRE_TOTAL_VERTS);
        }

        gl.disable(gl.BLEND);
        gl.useProgram(prog);       // восстановить основную программу
        gl.bindVertexArray(vao);
    }

    // FPS'''

pattern_render = re.compile(
    r'    // === Проход огня \(поверх основной сцены, аддитивный блендинг\) ===.*?// FPS',
    re.DOTALL
)
new_html, n = pattern_render.subn(NEW_FIRE_RENDER, html, count=1)
if n != 1:
    print(f"ERROR: render block not found (substitutions={n})", file=sys.stderr)
    sys.exit(1)
html = new_html

# === 5. Remove unused reference to fireTexReady (was in if condition) ===
# Already handled by NEW_FIRE_RENDER which doesn't use fireTexReady.
# But the if statement still references it. Let me check.
# (We'll see — the regex replaced the whole block, so it should be gone.)

HTML_PATH.write_text(html, encoding="utf-8")
print(f"Wrote: {HTML_PATH} ({len(html)} bytes)")
