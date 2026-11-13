// ===================================================================
// opengl_loader.h
// -------------------------------------------------------------------
// Загрузка современных функций OpenGL (3.0+) через wglGetProcAddress.
//
// v42: ТОЧНЫЕ ПРОТОТИПЫ с APIENTRY (stdcall на x86, пусто на x64).
//
// ПОЧЕМУ ВАРИАДИК type (*)(...) БЫЛ СЛОМАН (разбор краша v41):
//   * MSVC x86: вариадик = cdecl, а GL-функции драйвера = stdstack →
//     калли/калли дрейф стека → 0xC0000005 внутри nvoglv32.dll
//     (адрес 0x6Cxxxxxx — диапазон 32-битных DLL; лог v41 показал
//     именно это: краш на первом glCreateShader/glShaderSource).
//   * MinGW x64: int/ptr аргументы случайно совпадали (те же
//     регистры RCX/RDX/R8/R9), НО float-аргументы передаются в
//     ЦЕЛОЧИСЛЕННЫХ регистрах вместо XMM → мусор в glUniform*f →
//     мусорные uTime/uResolution → ЧЁРНЫЙ ЭКРАН (вся история бага).
//   * Точные прототипы решают ВСЕ случаи: stdcall корректен на x86,
//     на x64 одна конвенция, float идут в XMM как положено.
//     Именно так делают GLEW / glad / khrplatform.h.
//
// MSVC совместимость (v39 сохранена):
//   * НИКАКИХ typedef'ов GL-типов! GLenum, GLint, GLuint, GLsizei,
//     GLfloat, GLbitfield — ВСЕ объявлены в <GL/gl.h> (и в mingw-w64,
//     и в Windows SDK 10). Дублирование даёт C2371 в MSVC.
//   * GLchar / GLsizeiptr / GLboolean отсутствуют в gl.h 1.1 —
//     используем ABI-эквиваленты: char, ptrdiff_t (<stddef.h>),
//     unsigned char.
//
// main.cpp ДОЛЖЕН подключить <GL/gl.h> ПЕРЕД этим заголовком.
// ===================================================================

#pragma once

#include <stddef.h>   // ptrdiff_t — ABI-эквивалент GLsizeiptr

// Требуем, чтобы gl.h был уже подключён (иначе типы не определены).
#if !defined(_GL_H_) && !defined(__gl_h_) && !defined(__GL_H__) && !defined(APIENTRY)
#include <GL/gl.h>
#endif

// APIENTRY: __stdcall на x86, пусто на x64 (определяет windows.h/gl.h).
#ifndef APIENTRY
#define APIENTRY
#endif

// Макрос: точный прототип + указатель. params — список параметров,
// например (GLenum) или (GLint, GLfloat, GLfloat).
#define DECL_GL_FN(ret, name, params) \
    typedef ret (APIENTRY *PFN_##name) params; \
    static PFN_##name name = nullptr

// --- Современные функции OpenGL, которые мы используем ---
// (сигнатуры по спецификации OpenGL 3.3 core)

DECL_GL_FN(GLuint,  glCreateShader,  (GLenum type));
DECL_GL_FN(void,    glShaderSource,  (GLuint shader, GLsizei count,
                                      const char* const* string,
                                      const GLint* length));
DECL_GL_FN(void,    glCompileShader, (GLuint shader));
DECL_GL_FN(void,    glGetShaderiv,   (GLuint shader, GLenum pname,
                                      GLint* params));
DECL_GL_FN(void,    glGetShaderInfoLog, (GLuint shader, GLsizei bufSize,
                                         GLsizei* length, char* infoLog));
DECL_GL_FN(void,    glDeleteShader,  (GLuint shader));
DECL_GL_FN(GLuint,  glCreateProgram, (void));
DECL_GL_FN(void,    glAttachShader,  (GLuint program, GLuint shader));
DECL_GL_FN(void,    glLinkProgram,   (GLuint program));
DECL_GL_FN(void,    glGetProgramiv,  (GLuint program, GLenum pname,
                                      GLint* params));
DECL_GL_FN(void,    glGetProgramInfoLog, (GLuint program, GLsizei bufSize,
                                          GLsizei* length, char* infoLog));
DECL_GL_FN(void,    glDeleteProgram, (GLuint program));
DECL_GL_FN(void,    glUseProgram,    (GLuint program));
DECL_GL_FN(GLint,   glGetUniformLocation, (GLuint program, const char* name));
DECL_GL_FN(void,    glUniform1f,     (GLint location, GLfloat v0));
DECL_GL_FN(void,    glUniform2f,     (GLint location, GLfloat v0, GLfloat v1));
DECL_GL_FN(void,    glUniform3f,     (GLint location, GLfloat v0,
                                      GLfloat v1, GLfloat v2));
DECL_GL_FN(void,    glUniform1i,     (GLint location, GLint v0));
DECL_GL_FN(void,    glUniform1fv,    (GLint location, GLsizei count,
                                      const GLfloat* value));
DECL_GL_FN(void,    glGenVertexArrays, (GLsizei n, GLuint* arrays));
DECL_GL_FN(void,    glBindVertexArray, (GLuint array));
DECL_GL_FN(void,    glGenBuffers,      (GLsizei n, GLuint* buffers));
DECL_GL_FN(void,    glBindBuffer,      (GLenum target, GLuint buffer));
DECL_GL_FN(void,    glBufferData,      (GLenum target, ptrdiff_t size,
                                        const void* data, GLenum usage));
DECL_GL_FN(void,    glEnableVertexAttribArray, (GLuint index));
DECL_GL_FN(void,    glVertexAttribPointer, (GLuint index, GLint size,
                                           GLenum type, unsigned char normalized,
                                           GLsizei stride, const void* pointer));
// --- FBO functions (OpenGL 3.0+, needed for Scene Manager) ---
DECL_GL_FN(void,    glGenFramebuffers,    (GLsizei n, GLuint* framebuffers));
DECL_GL_FN(void,    glBindFramebuffer,    (GLenum target, GLuint framebuffer));
DECL_GL_FN(void,    glFramebufferTexture2D, (GLenum target, GLenum attachment,
                                              GLenum textarget, GLuint texture,
                                              GLint level));
DECL_GL_FN(void,    glDeleteFramebuffers, (GLsizei n, const GLuint* framebuffers));
// --- Additional uniform (vec4, needed by some effects) ---
DECL_GL_FN(void,    glUniform4f,     (GLint location, GLfloat v0,
                                      GLfloat v1, GLfloat v2, GLfloat v3));
// --- glActiveTexture (OpenGL 1.3, not in Windows gl.h 1.1) ---
DECL_GL_FN(void,    glActiveTexture, (GLenum texture));
// --- P1.3: OpenGL 1.4 blend functions (needed for opacity application) ---
// glBlendColor sets the GL_CONSTANT_COLOR / GL_CONSTANT_ALPHA values used
// by glBlendFuncSeparate when blending factors reference GL_CONSTANT_*.
// glBlendFuncSeparate allows separate RGB and alpha blend factors, which
// we use to multiply source alpha by clip opacity.
DECL_GL_FN(void,    glBlendColor,      (GLfloat red, GLfloat green,
                                        GLfloat blue, GLfloat alpha));
DECL_GL_FN(void,    glBlendFuncSeparate, (GLenum sfactorRGB, GLenum dfactorRGB,
                                          GLenum sfactorAlpha, GLenum dfactorAlpha));

// v41 diag: имя последней функции, которую не удалось загрузить.
static const char* g_lastMissingGLFn = "(none)";

// Получение функции по имени. Имя оборачивается в строку макросом #.
static void* LoadGLProc(const char* name) {
    void* p = (void*)wglGetProcAddress(name);
    // wglGetProcAddress может вернуть "фейковый" указатель (1-2-3) для
    // расширений, которые не поддерживаются. Проверяем.
    if (p == nullptr || p == (void*)1 || p == (void*)2 || p == (void*)3 ||
        p == (void*)(-1)) {
        return nullptr;
    }
    return p;
}

// Загрузить все нужные функции OpenGL. Возвращает true при успехе.
static bool LoadOpenGLFunctions() {
    #define LOAD_GL_FN(name) \
        name = (PFN_##name)LoadGLProc(#name); \
        if (!name) { g_lastMissingGLFn = #name; return false; }

    LOAD_GL_FN(glCreateShader);
    LOAD_GL_FN(glShaderSource);
    LOAD_GL_FN(glCompileShader);
    LOAD_GL_FN(glGetShaderiv);
    LOAD_GL_FN(glGetShaderInfoLog);
    LOAD_GL_FN(glDeleteShader);
    LOAD_GL_FN(glCreateProgram);
    LOAD_GL_FN(glAttachShader);
    LOAD_GL_FN(glLinkProgram);
    LOAD_GL_FN(glGetProgramiv);
    LOAD_GL_FN(glGetProgramInfoLog);
    LOAD_GL_FN(glDeleteProgram);
    LOAD_GL_FN(glUseProgram);
    LOAD_GL_FN(glGetUniformLocation);
    LOAD_GL_FN(glUniform1f);
    LOAD_GL_FN(glUniform2f);
    LOAD_GL_FN(glUniform3f);
    LOAD_GL_FN(glUniform1i);
    LOAD_GL_FN(glUniform1fv);
    LOAD_GL_FN(glGenVertexArrays);
    LOAD_GL_FN(glBindVertexArray);
    LOAD_GL_FN(glGenBuffers);
    LOAD_GL_FN(glBindBuffer);
    LOAD_GL_FN(glBufferData);
    LOAD_GL_FN(glEnableVertexAttribArray);
    LOAD_GL_FN(glVertexAttribPointer);
    // FBO functions (Scene Manager)
    LOAD_GL_FN(glGenFramebuffers);
    LOAD_GL_FN(glBindFramebuffer);
    LOAD_GL_FN(glFramebufferTexture2D);
    LOAD_GL_FN(glDeleteFramebuffers);
    LOAD_GL_FN(glUniform4f);
    LOAD_GL_FN(glActiveTexture);
    // P1.3: OpenGL 1.4 blend functions (needed for opacity application).
    // These are NOT in Windows gl.h 1.1 — must be loaded via wglGetProcAddress.
    // Required for setBlendMode() to apply clip opacity animations.
    LOAD_GL_FN(glBlendColor);
    LOAD_GL_FN(glBlendFuncSeparate);

    #undef LOAD_GL_FN
    return true;
}

// Константы OpenGL (современные, отсутствующие в базовом gl.h).
// Через #ifndef — безопасно для обоих SDK (могут быть определены).
#ifndef GL_FRAGMENT_SHADER
#define GL_FRAGMENT_SHADER        0x8B30
#endif
#ifndef GL_VERTEX_SHADER
#define GL_VERTEX_SHADER          0x8B31
#endif
#ifndef GL_COMPILE_STATUS
#define GL_COMPILE_STATUS         0x8B81
#endif
#ifndef GL_LINK_STATUS
#define GL_LINK_STATUS            0x8B82
#endif
#ifndef GL_INFO_LOG_LENGTH
#define GL_INFO_LOG_LENGTH        0x8B84
#endif
#ifndef GL_ARRAY_BUFFER
#define GL_ARRAY_BUFFER           0x8892
#endif
#ifndef GL_STATIC_DRAW
#define GL_STATIC_DRAW            0x88E4
#endif
#ifndef GL_SHADING_LANGUAGE_VERSION   // нет в базовом gl.h (OpenGL 1.1)
#define GL_SHADING_LANGUAGE_VERSION   0x8B8C
#endif
// --- FBO constants (OpenGL 3.0+, needed for Scene Manager) ---
#ifndef GL_FRAMEBUFFER
#define GL_FRAMEBUFFER              0x8D40
#endif
#ifndef GL_COLOR_ATTACHMENT0
#define GL_COLOR_ATTACHMENT0        0x8CE0
#endif
#ifndef GL_TEXTURE0
#define GL_TEXTURE0                 0x84C0
#endif
#ifndef GL_RGBA16F
#define GL_RGBA16F                  0x881A
#endif
#ifndef GL_CLAMP_TO_EDGE
#define GL_CLAMP_TO_EDGE            0x812F
#endif
#ifndef GL_TRIANGLE_STRIP
#define GL_TRIANGLE_STRIP           0x0005
#endif
#ifndef GL_ONE_MINUS_SRC_COLOR
#define GL_ONE_MINUS_SRC_COLOR      0x0301
#endif
#ifndef GL_DST_COLOR
#define GL_DST_COLOR                0x0306
#endif
// --- P1.3: OpenGL 1.4 blend color constants (EXT_blend_color / core 1.4) ---
// Used by glBlendColor + glBlendFuncSeparate to apply clip opacity.
#ifndef GL_CONSTANT_COLOR
#define GL_CONSTANT_COLOR           0x8001
#endif
#ifndef GL_ONE_MINUS_CONSTANT_COLOR
#define GL_ONE_MINUS_CONSTANT_COLOR 0x8002
#endif
#ifndef GL_CONSTANT_ALPHA
#define GL_CONSTANT_ALPHA           0x8003
#endif
#ifndef GL_ONE_MINUS_CONSTANT_ALPHA
#define GL_ONE_MINUS_CONSTANT_ALPHA 0x8004
#endif
