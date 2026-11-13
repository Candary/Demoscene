#!/usr/bin/env python3
"""Patch main.cpp: replace texture-based fire with procedural particle fire.

Mirror of preview.html procedural fire: VBO with 30 particle template,
5 attributes per vertex (aTriCorner/aCenterOffset/aVelocity/aLifetime/aPhase),
uFireUp = normalize(uFirePos), uTime = elapsed (local fire time), uFadeAlpha,
procedural color/alpha in fragment shader.
"""
import re
import sys
from pathlib import Path

CPP_PATH = Path("/home/z/my-project/download/demo_intro/main.cpp")
src = CPP_PATH.read_text(encoding="utf-8")

# === 1. Remove #include "fire_texture.h" ===
src = src.replace(
    '#include "shaders.h"\n#include "fire_texture.h"  // декодированные RGB-байты fire_spritesheet.png\n',
    '#include "shaders.h"\n'
)

# === 2. Replace globals: remove g_fireTex, add new uniform locations, add particle constants ===
old_globals = """static bool   g_fireEnabled   = true;
static GLuint g_fireProgram   = 0;
static GLuint g_fireVAO       = 0;
static GLuint g_fireTex       = 0;
struct FireInstance { int particleIdx; double startTime; };
static FireInstance g_fires[8];   // массив активных огней (слот для запаса)
static int          g_fireCount = 0;
static double       g_nextSpawnAt = 2.0;
static const int    kFireCols = 4;
static const int    kFireRows = 6;
static const int    kFireFrames = 24;
static const double kFireFPS = 12.0;
static const double kFireLifetime = 3.5;
static const double kFireMinInterval = 2.0;
static const double kFireMaxInterval = 4.0;
static const int    kFireMaxConcurrent = 3;"""

new_globals = """static bool   g_fireEnabled   = true;
static GLuint g_fireProgram   = 0;
static GLuint g_fireVAO       = 0;
static GLuint g_fireVBO       = 0;
struct FireInstance { int particleIdx; double startTime; };
static FireInstance g_fires[8];   // массив активных огней (слот для запаса)
static int          g_fireCount = 0;
static double       g_nextSpawnAt = 2.0;
static const int    kFireParticles = 30;
static const int    kFireVertsPerParticle = 6;
static const int    kFireTotalVerts = kFireParticles * kFireVertsPerParticle;  // 180
static const int    kFireFloatsPerVert = 10;   // triCorner(2)+centerOffset(3)+velocity(3)+lifetime(1)+phase(1)
static const int    kFireStride = kFireFloatsPerVert * 4;  // байты
static const double kFireLifetime = 3.5;
static const double kFireMinInterval = 2.0;
static const double kFireMaxInterval = 4.0;
static const int    kFireMaxConcurrent = 3;"""

if old_globals not in src:
    print("ERROR: globals anchor not found", file=sys.stderr); sys.exit(1)
src = src.replace(old_globals, new_globals)

# === 3. Replace fire uniform locations block ===
old_uniforms = """// Uniform-локации для программы огня.
static GLint  g_unifFireCamPos   = -1;
static GLint  g_unifFireCamFwd   = -1;
static GLint  g_unifFireCamRight = -1;
static GLint  g_unifFireCamUp    = -1;
static GLint  g_unifFireAspect   = -1;
static GLint  g_unifFirePos      = -1;
static GLint  g_unifFireSize     = -1;
static GLint  g_unifFireFrameOff = -1;
static GLint  g_unifFireFrameSz  = -1;
static GLint  g_unifFireTex      = -1;
static GLint  g_unifFireAlpha    = -1;
static GLint  g_unifFireTint     = -1;"""

new_uniforms = """// Uniform-локации для программы огня (процедурная, без текстуры).
static GLint  g_unifFireCamPos   = -1;
static GLint  g_unifFireCamFwd   = -1;
static GLint  g_unifFireCamRight = -1;
static GLint  g_unifFireCamUp    = -1;
static GLint  g_unifFireAspect   = -1;
static GLint  g_unifFireTime     = -1;
static GLint  g_unifFirePos      = -1;
static GLint  g_unifFireUp       = -1;
static GLint  g_unifFireSize     = -1;
static GLint  g_unifFireFadeAlpha = -1;"""

if old_uniforms not in src:
    print("ERROR: uniform-locations anchor not found", file=sys.stderr); sys.exit(1)
src = src.replace(old_uniforms, new_uniforms)

# === 4. Replace InitGLResources fire block (no texture; create VBO+VAO with attributes) ===
old_init = """    // === Создаём программу огня ===
    g_fireProgram = CreateProgram(kFireVertexShaderSrc, kFireFragmentShaderSrc);
    if (!g_fireProgram) {
        Log("[Error] Failed to create fire shader program");
        return false;
    }
    g_unifFireCamPos   = glGetUniformLocation(g_fireProgram, "uCamPos");
    g_unifFireCamFwd   = glGetUniformLocation(g_fireProgram, "uCamFwd");
    g_unifFireCamRight = glGetUniformLocation(g_fireProgram, "uCamRight");
    g_unifFireCamUp    = glGetUniformLocation(g_fireProgram, "uCamUp");
    g_unifFireAspect   = glGetUniformLocation(g_fireProgram, "uAspect");
    g_unifFirePos      = glGetUniformLocation(g_fireProgram, "uFirePos");
    g_unifFireSize     = glGetUniformLocation(g_fireProgram, "uFireSize");
    g_unifFireFrameOff = glGetUniformLocation(g_fireProgram, "uFrameOffset");
    g_unifFireFrameSz  = glGetUniformLocation(g_fireProgram, "uFrameSize");
    g_unifFireTex      = glGetUniformLocation(g_fireProgram, "uFireTex");
    g_unifFireAlpha    = glGetUniformLocation(g_fireProgram, "uAlpha");
    g_unifFireTint     = glGetUniformLocation(g_fireProgram, "uTint");

    // Пустой VAO для огня — вершинный шейдер генерирует координаты
    // квада из gl_VertexID (как и в основной сцене).
    glGenVertexArrays(1, &g_fireVAO);

    // Создаём текстуру из декодированных RGB-байтов fire_texture.h
    // (PNG не нуждается в runtime-декодере — все байты уже в коде).
    glGenTextures(1, &g_fireTex);
    glBindTexture(GL_TEXTURE_2D, g_fireTex);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB,
                 kFireTexWidth, kFireTexHeight, 0,
                 GL_RGB, GL_UNSIGNED_BYTE, kFireTexRGB);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    Log("[Fire] Texture loaded %dx%d", kFireTexWidth, kFireTexHeight);

    return true;
}"""

new_init = """    // === Создаём программу огня (процедурная, без текстуры) ===
    g_fireProgram = CreateProgram(kFireVertexShaderSrc, kFireFragmentShaderSrc);
    if (!g_fireProgram) {
        Log("[Error] Failed to create fire shader program");
        return false;
    }
    g_unifFireCamPos   = glGetUniformLocation(g_fireProgram, "uCamPos");
    g_unifFireCamFwd   = glGetUniformLocation(g_fireProgram, "uCamFwd");
    g_unifFireCamRight = glGetUniformLocation(g_fireProgram, "uCamRight");
    g_unifFireCamUp    = glGetUniformLocation(g_fireProgram, "uCamUp");
    g_unifFireAspect   = glGetUniformLocation(g_fireProgram, "uAspect");
    g_unifFireTime     = glGetUniformLocation(g_fireProgram, "uTime");
    g_unifFirePos      = glGetUniformLocation(g_fireProgram, "uFirePos");
    g_unifFireUp       = glGetUniformLocation(g_fireProgram, "uFireUp");
    g_unifFireSize     = glGetUniformLocation(g_fireProgram, "uFireSize");
    g_unifFireFadeAlpha = glGetUniformLocation(g_fireProgram, "uFadeAlpha");

    // === VBO с шаблоном партиклов (один на все источники огня) ===
    // 30 партиклов × 6 вершин = 180 вершин. На партикл: triCorner(2) +
    // centerOffset(3) + velocity(3) + lifetime(1) + phase(1) = 10 float'ов.
    // Широкий разброс по позициям/скоростям — частицы видны как отдельные
    // угольки, а не как монолитный блоб.
    {
        float data[kFireTotalVerts * kFireFloatsPerVert];
        const float corners[6][2] = {
            {-1, -1}, {1, -1}, {-1, 1}, {-1, 1}, {1, -1}, {1, 1}
        };
        // Простой LCG для детерминированной случайности.
        unsigned int rng = 987654321u;
        auto frnd = [&]() -> float {
            rng = rng * 1664525u + 1013904223u;
            return (float)((rng >> 8) & 0xFFFFFF) / (float)0x1000000;
        };
        for (int p = 0; p < kFireParticles; p++) {
            // Диск радиуса 0.18 (равномерное распределение по площади).
            float ang = frnd() * 6.2831853f;
            float r = sqrtf(frnd()) * 0.18f;
            float cx = cosf(ang) * r;
            float cy = (frnd() - 0.5f) * 0.06f;
            float cz = sinf(ang) * r;
            float spAng = frnd() * 6.2831853f;
            float spMag = 0.15f + frnd() * 0.30f;
            float vx = cosf(spAng) * spMag;
            float vy = (frnd() - 0.5f) * 0.25f;
            float vz = sinf(spAng) * spMag;
            float lt = 0.5f + frnd() * 1.6f;   // 0.5..2.1 с
            float phase = frnd() * lt;
            for (int v = 0; v < kFireVertsPerParticle; v++) {
                int i = (p * kFireVertsPerParticle + v) * kFireFloatsPerVert;
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
        glGenBuffers(1, &g_fireVBO);
        glBindBuffer(GL_ARRAY_BUFFER, g_fireVBO);
        glBufferData(GL_ARRAY_BUFFER, sizeof(data), data, GL_STATIC_DRAW);
        glBindBuffer(GL_ARRAY_BUFFER, 0);
        Log("[Fire] VBO built: %d verts %d particles",
            kFireTotalVerts, kFireParticles);
    }

    // VAO с 5 атрибутами, stride 10 float.
    glGenVertexArrays(1, &g_fireVAO);
    glBindVertexArray(g_fireVAO);
    glBindBuffer(GL_ARRAY_BUFFER, g_fireVBO);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, kFireStride, (void*)0);
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, kFireStride, (void*)(2 * 4));
    glEnableVertexAttribArray(2);
    glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, kFireStride, (void*)(5 * 4));
    glEnableVertexAttribArray(3);
    glVertexAttribPointer(3, 1, GL_FLOAT, GL_FALSE, kFireStride, (void*)(8 * 4));
    glEnableVertexAttribArray(4);
    glVertexAttribPointer(4, 1, GL_FLOAT, GL_FALSE, kFireStride, (void*)(9 * 4));
    glBindVertexArray(0);

    return true;
}"""

if old_init not in src:
    print("ERROR: InitGLResources fire block not found", file=sys.stderr); sys.exit(1)
src = src.replace(old_init, new_init)

# === 5. Replace RenderFrame fire block (no texture, use uTime/uFireUp/uFadeAlpha) ===
old_render = """    // === Проход огня (поверх основной сцены, аддитивный блендинг) ===
    if (g_fireEnabled && g_fireProgram && g_fireTex && g_fireCount > 0) {
        glUseProgram(g_fireProgram);
        glBindVertexArray(g_fireVAO);
        glEnable(GL_BLEND);
        glBlendFunc(GL_SRC_ALPHA, GL_ONE);

        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, g_fireTex);
        if (g_unifFireTex >= 0) glUniform1i(g_unifFireTex, 0);

        // Камера (повторяет логику raymarch-сцены).
        float cam_t = (float)g_timeAccum * 0.3f;
        float dist = 3.5f / (g_zoom > 0.001f ? g_zoom : 0.001f);
        Vec3f ro = { sinf(cam_t) * dist,
                     sinf(cam_t * 0.7f) * (dist * 0.35f),
                     cosf(cam_t) * dist };
        Vec3f fwd = { -ro.x, -ro.y, -ro.z };   // ta - ro = (0,0,0) - ro
        float fl = sqrtf(fwd.x*fwd.x + fwd.y*fwd.y + fwd.z*fwd.z);
        fwd.x /= fl; fwd.y /= fl; fwd.z /= fl;
        // right = normalize(cross((0,1,0), fwd)) = normalize((fwd.z, 0, -fwd.x))
        Vec3f right = { fwd.z, 0.0f, -fwd.x };
        float rl = sqrtf(right.x*right.x + right.z*right.z);
        right.x /= rl; right.z /= rl;
        // up = cross(fwd, right)
        Vec3f up = {
            fwd.y * right.z - fwd.z * right.y,
            fwd.z * right.x - fwd.x * right.z,
            fwd.x * right.y - fwd.y * right.x
        };
        float aspect = (float)g_width / (float)g_height;

        if (g_unifFireCamPos   >= 0) glUniform3f(g_unifFireCamPos,
                                                 ro.x, ro.y, ro.z);
        if (g_unifFireCamFwd   >= 0) glUniform3f(g_unifFireCamFwd,
                                                 fwd.x, fwd.y, fwd.z);
        if (g_unifFireCamRight >= 0) glUniform3f(g_unifFireCamRight,
                                                 right.x, right.y, right.z);
        if (g_unifFireCamUp    >= 0) glUniform3f(g_unifFireCamUp,
                                                 up.x, up.y, up.z);
        if (g_unifFireAspect   >= 0) glUniform1f(g_unifFireAspect, aspect);
        if (g_unifFireFrameSz  >= 0) glUniform2f(g_unifFireFrameSz,
                                                 1.0f/kFireCols, 1.0f/kFireRows);
        if (g_unifFireTint     >= 0) glUniform3f(g_unifFireTint,
                                                 1.0f, 1.0f, 1.0f);

        for (int fi = 0; fi < g_fireCount; fi++) {
            double elapsed = g_timeAccum - g_fires[fi].startTime;
            if (elapsed < 0 || elapsed > kFireLifetime) continue;

            int frameIdx = (int)(elapsed * kFireFPS) % kFireFrames;
            int col = frameIdx % kFireCols;
            int row = frameIdx / kFireCols;
            float uOff = (float)col / (float)kFireCols;
            // OpenGL: y вверх; текстура как обычно (row 0 — верх PNG
            // в данных RGB). V offset для row r: (rows-1-r)/rows,
            // чтобы row 0 был в верхней части текстуры.
            float vOff = (float)(kFireRows - 1 - row) / (float)kFireRows;
            if (g_unifFireFrameOff >= 0)
                glUniform2f(g_unifFireFrameOff, uOff, vOff);

            int pIdx = g_fires[fi].particleIdx;
            Vec3f wp = ParticleWorldPos(pIdx, g_timeAccum, g_rotYaw, g_rotPitch);
            if (g_unifFirePos >= 0)
                glUniform3f(g_unifFirePos, wp.x, wp.y, wp.z);

            // Размер = радиус частицы × 2.5 (квад перекрывает сферу).
            float radius = 0.08f + 0.04f * sinf((float)g_timeAccum * 2.0f
                                                + pIdx * 1.5f);
            if (g_unifFireSize >= 0)
                glUniform1f(g_unifFireSize, radius * 2.5f);

            // Fade in (0.4 с) → hold → fade out (0.5 с).
            float alpha;
            if (elapsed < 0.4) alpha = (float)elapsed / 0.4f;
            else if (elapsed > kFireLifetime - 0.5)
                alpha = (float)(kFireLifetime - elapsed) / 0.5f;
            else alpha = 1.0f;
            if (g_unifFireAlpha >= 0) glUniform1f(g_unifFireAlpha, alpha);

            glDrawArrays(GL_TRIANGLES, 0, 6);
        }

        glDisable(GL_BLEND);
        glUseProgram(g_program);
        glBindVertexArray(0);
    }"""

new_render = """    // === Проход огня (поверх основной сцены, аддитивный блендинг) ===
    // Процедурный мультипартикльный огонь: на каждый активный источник —
    // 30 частиц со своими lifetime/velocity/phase. Без текстуры.
    if (g_fireEnabled && g_fireProgram && g_fireCount > 0) {
        glUseProgram(g_fireProgram);
        glBindVertexArray(g_fireVAO);
        glEnable(GL_BLEND);
        glBlendFunc(GL_SRC_ALPHA, GL_ONE);

        // Камера (повторяет логику raymarch-сцены).
        float cam_t = (float)g_timeAccum * 0.3f;
        float dist = 3.5f / (g_zoom > 0.001f ? g_zoom : 0.001f);
        Vec3f ro = { sinf(cam_t) * dist,
                     sinf(cam_t * 0.7f) * (dist * 0.35f),
                     cosf(cam_t) * dist };
        Vec3f fwd = { -ro.x, -ro.y, -ro.z };
        float fl = sqrtf(fwd.x*fwd.x + fwd.y*fwd.y + fwd.z*fwd.z);
        fwd.x /= fl; fwd.y /= fl; fwd.z /= fl;
        Vec3f right = { fwd.z, 0.0f, -fwd.x };
        float rl = sqrtf(right.x*right.x + right.z*right.z);
        right.x /= rl; right.z /= rl;
        Vec3f up = {
            fwd.y * right.z - fwd.z * right.y,
            fwd.z * right.x - fwd.x * right.z,
            fwd.x * right.y - fwd.y * right.x
        };
        float aspect = (float)g_width / (float)g_height;

        if (g_unifFireCamPos   >= 0) glUniform3f(g_unifFireCamPos,
                                                 ro.x, ro.y, ro.z);
        if (g_unifFireCamFwd   >= 0) glUniform3f(g_unifFireCamFwd,
                                                 fwd.x, fwd.y, fwd.z);
        if (g_unifFireCamRight >= 0) glUniform3f(g_unifFireCamRight,
                                                 right.x, right.y, right.z);
        if (g_unifFireCamUp    >= 0) glUniform3f(g_unifFireCamUp,
                                                 up.x, up.y, up.z);
        if (g_unifFireAspect   >= 0) glUniform1f(g_unifFireAspect, aspect);

        for (int fi = 0; fi < g_fireCount; fi++) {
            double elapsed = g_timeAccum - g_fires[fi].startTime;
            if (elapsed < 0 || elapsed > kFireLifetime) continue;

            int pIdx = g_fires[fi].particleIdx;
            Vec3f wp = ParticleWorldPos(pIdx, g_timeAccum, g_rotYaw, g_rotPitch);
            if (g_unifFirePos >= 0)
                glUniform3f(g_unifFirePos, wp.x, wp.y, wp.z);

            // uFireUp = normalize(uFirePos) — партиклы летят радиально наружу.
            float upLen = sqrtf(wp.x*wp.x + wp.y*wp.y + wp.z*wp.z);
            if (upLen < 1e-9f) upLen = 1e-9f;
            if (g_unifFireUp >= 0)
                glUniform3f(g_unifFireUp, wp.x/upLen, wp.y/upLen, wp.z/upLen);

            // Размер = радиус частицы × 2.0.
            float radius = 0.08f + 0.04f * sinf((float)g_timeAccum * 2.0f
                                                + pIdx * 1.5f);
            if (g_unifFireSize >= 0)
                glUniform1f(g_unifFireSize, radius * 2.0f);

            // Локальное время огня (с момента зажигания) — партиклы циклят.
            if (g_unifFireTime >= 0)
                glUniform1f(g_unifFireTime, (float)elapsed);

            // Fade in (0.4 с) → hold → fade out (0.5 с).
            float fadeAlpha;
            if (elapsed < 0.4) fadeAlpha = (float)elapsed / 0.4f;
            else if (elapsed > kFireLifetime - 0.5)
                fadeAlpha = (float)(kFireLifetime - elapsed) / 0.5f;
            else fadeAlpha = 1.0f;
            if (g_unifFireFadeAlpha >= 0)
                glUniform1f(g_unifFireFadeAlpha, fadeAlpha);

            // Все 30 партиклов одним draw call'ом.
            glDrawArrays(GL_TRIANGLES, 0, kFireTotalVerts);
        }

        glDisable(GL_BLEND);
        glUseProgram(g_program);
        glBindVertexArray(0);
    }"""

if old_render not in src:
    print("ERROR: RenderFrame fire block not found", file=sys.stderr); sys.exit(1)
src = src.replace(old_render, new_render)

CPP_PATH.write_text(src, encoding="utf-8")
print(f"Patched: {CPP_PATH} ({len(src)} bytes)")
