// ===================================================================
// main.cpp  —  Demo Intro (чистый Win32 + OpenGL 3.3, без библиотек)
// -------------------------------------------------------------------
//
// Это "вступительная" демо-программа в стиле демосцены. Запусти exe —
// получишь полноэкранное окно с медитативно вращающейся морфящей
// фигурой (9 фигур: сфера -> ... -> додекаэдр) на градиентном звёздном небе.
// ESC — выход, SPACE — пауза (сцену можно крутить мышью), F1 — FPS,
// F2 — медленный режим, drag ЛКМ — вращение сцены.
//
// Архитектура:
//   * Создаём окно через Win32 API (RegisterClass + CreateWindowEx).
//   * Получаем OpenGL-контекст через PIXELFORMATDESCRIPTOR + wgl.
//   * Загружаем современные GL-функции через wglGetProcAddress.
//   * Компилируем вершинный и фрагментный шейдеры (см. shaders.h).
//   * Главный цикл: каждый кадр передаём uTime и uResolution в шейдер
//     и рисуем fullscreen quad.
//
// ===================================================================

#define _CRT_SECURE_NO_WARNINGS  // v43: нет варнингов C4996 (strcpy/fopen)
#define WIN32_LEAN_AND_MEAN      // не тащим весь windows.h
#include <windows.h>
#include <windowsx.h>

// Заголовок OpenGL из Windows SDK / mingw. Включает базовые функции
// (glClear, glFlush, glBegin, ... и константы GL_xxx).
#include <GL/gl.h>
#include <GL/glu.h>            // для gluPerspective, если понадобится (здесь не нужна)

#include <stdio.h>             // для вывода логов в OutputDebugString
#include <stdint.h>
#include <math.h>             // для expf() в обработчике колеса мыши
#include <string.h>            // strrchr — путь лог-файла (v41 diag)

// Подключаем загрузчик современных GL-функций и шейдеры.
#include "opengl_loader.h"
#include "shaders.h"

// -------------------------------------------------------------------
// Глобальные переменные
// -------------------------------------------------------------------
static HWND   g_hwnd       = nullptr;  // дескриптор окна
static HDC    g_hdc        = nullptr;   // контекст устройства (device context)
static HGLRC  g_hglrc      = nullptr;  // OpenGL контекст
static bool   g_running    = true;     // флаг работы главного цикла
static int    g_width      = 1280;     // ширина окна
static int    g_height     = 720;      // высота окна
static bool   g_showFPS    = false;    // показывать FPS в углу
static bool   g_slowMo      = false;   // медленный режим (F2)
static float  g_zoom       = 1.0f;    // коэффициент зума: >1 ближе, <1 дальше
static bool   g_droplets    = false;    // эффект капель (D) — ОТКЛ по умолчанию
                                         // (DropletEffect использует рекурсию через
                                         // RenderSceneCoarse, GLSL не разрешает)
static bool   g_paused      = false;    // пауза анимации (SPACE)

// Вращение мышью (drag ЛКМ): текущие (сглаженные) и целевые углы.
// Целевые накапливаются в WM_MOUSEMOVE — если мышь шлёт события чаще,
// чем кадры, НИЧЕГО не теряется: всё накопится до следующего кадра.
// Текущие углы плавно догоняют целевые в RenderFrame (экспоненциальное
// сглаживание, независимое от FPS).
static float  g_rotYaw         = 0.0f;    // yaw  — вокруг оси Y (drag по X)
static float  g_rotPitch       = 0.0f;    // pitch — вокруг оси X (drag по Y)
static float  g_rotYawTarget   = 0.0f;
static float  g_rotPitchTarget = 0.0f;
static bool   g_dragging       = false;   // ЛКМ зажата — вращаем сцену
static POINT  g_lastMouse      = {0, 0};  // последняя позиция курсора при drag

// === ОГОНЬ НА ЧАСТИЦАХ ВОДЫ ===
// Спрайт-лист: PNG 512×512, 4×6 = 24 кадра, 12 fps (цикл 2с).
// Появление: каждые 2–4с случайно выбранная частица «загорается» на 3.5с
// (1.75 цикла), максимум 3 одновременно. Когда горит — вода скрыта
// (uFireMask=0), на её месте рисуется билборд-квад с анимированным
// огнём из текстуры (аддитивный блендинг).
static bool   g_fireEnabled   = true;
static GLuint g_fireProgram   = 0;
static GLuint g_fireVAO       = 0;
// VAO для основной сцены. В GL 3.3 CORE PROFILE default VAO (id=0)
// не работает — glDrawArrays без VAO = GL_INVALID_OPERATION (0x502).
static GLuint g_defaultVAO    = 0;
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
static const int    kFireMaxConcurrent = 3;

// Идентификаторы шейдерной программы и uniform'ов.
static GLuint g_program    = 0;
static GLint  g_unifTime   = -1;
static GLint  g_unifRes    = -1;
static GLint  g_unifZoom   = -1;   // uniform для зума камеры
static GLint  g_unifDrops  = -1;   // uniform для вкл/выкл эффекта капель
static GLint  g_unifMouseRot = -1; // uniform для вращения мышью (yaw, pitch)
static GLint  g_unifFireMask = -1; // uniform uFireMask[0..7] (1=вода видна, 0=горит)

// Uniform-локации для программы огня (процедурная, без текстуры).
static GLint  g_unifFireCamPos   = -1;
static GLint  g_unifFireCamFwd   = -1;
static GLint  g_unifFireCamRight = -1;
static GLint  g_unifFireCamUp    = -1;
static GLint  g_unifFireAspect   = -1;
static GLint  g_unifFireTime     = -1;
static GLint  g_unifFirePos      = -1;
static GLint  g_unifFireUp       = -1;
static GLint  g_unifFireSize     = -1;
static GLint  g_unifFireFadeAlpha = -1;

// Для FPS-расчёта.
static LARGE_INTEGER g_freq;      // частота QueryPerformanceCounter
static double        g_prevTime = 0.0;
static int           g_frameCount = 0;
static double        g_fpsAccumTime = 0.0;
static double        g_fps = 0.0;

// Текущее время в секундах (с учётом паузы и замедления).
static double g_timeAccum = 0.0;

// -------------------------------------------------------------------
// Утилита: получить текущее время в секундах (высокая точность).
// -------------------------------------------------------------------
static double GetTimeSeconds() {
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    return (double)now.QuadPart / (double)g_freq.QuadPart;
}

// -------------------------------------------------------------------
// Логирование в отладочный вывод (OutputDebugString + printf в консоль).
// -------------------------------------------------------------------
static void Log(const char* fmt, ...) {
    char buf[2048];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    OutputDebugStringA(buf);
    OutputDebugStringA("\n");

    // v45: ЕДИНЫЙ trace.log — build-вывод (от build_msvc.bat) + runtime
    // (этот лог) в одном файле. Режим APPEND: к build-секции дописывается
    // runtime. Небуферизованный — содержимое переживает любой краш.
    // Если файла нет после запуска — процесс вообще не стартовал
    // (антивирус/SmartScreen), а не упал внутри нашего кода.
    static FILE* s_log = nullptr;
    static bool  s_tried = false;
    if (!s_tried) {
        s_tried = true;
        char path[MAX_PATH];
        DWORD n = GetModuleFileNameA(nullptr, path, MAX_PATH);
        if (n > 0 && n < MAX_PATH) {
            char* slash = strrchr(path, '\\');
            if (slash) strcpy(slash + 1, "trace.log");
            else       strcpy(path, "trace.log");
        } else {
            strcpy(path, "trace.log");
        }
        s_log = fopen(path, "a");   // append — дописываем к build-выводу
        if (s_log) {
            setvbuf(s_log, nullptr, _IONBF, 0);
            // RUN START banner с таймстампом — отделяет runtime-секцию
            // от build-вывода выше.
            SYSTEMTIME st;
            GetLocalTime(&st);
            fprintf(s_log, "\n=== RUN START %04u-%02u-%02u %02u:%02u:%02u.%03u ===\n",
                    st.wYear, st.wMonth, st.wDay,
                    st.wHour, st.wMinute, st.wSecond, st.wMilliseconds);
        }
    }
    if (s_log) {
        fprintf(s_log, "%s\n", buf);
    }
}

// -------------------------------------------------------------------
// v41 diag: ловим фатальные исключения (access violation и т.п.).
// Превращает «после запуска ничего не происходит» в понятную причину
// в trace.log (appended к build-выводу).
// -------------------------------------------------------------------
#if defined(_MSC_VER)
static const char* kBuildCompiler = "MSVC";
#elif defined(__GNUC__)
static const char* kBuildCompiler = "GCC (MinGW)";
#else
static const char* kBuildCompiler = "unknown";
#endif

static LONG WINAPI CrashHandler(EXCEPTION_POINTERS* ep) {
    if (ep && ep->ExceptionRecord) {
        Log("[FATAL] Exception 0x%08lX at address %p",
            (unsigned long)ep->ExceptionRecord->ExceptionCode,
            ep->ExceptionRecord->ExceptionAddress);
    } else {
        Log("[FATAL] Unknown exception");
    }
    MessageBoxA(nullptr,
                "Demo Intro crashed.\n"
                "Details are in trace.log next to the exe.",
                "Demo Intro — fatal error", MB_ICONERROR);
    return EXCEPTION_EXECUTE_HANDLER;
}

// -------------------------------------------------------------------
// Forward declaration нашего обработчика сообщений (определён ниже).
// Используем именно статическую функцию, а не лямбду — это гарантия
// корректного calling convention (CALLBACK = __stdcall).
static LRESULT CALLBACK WndProc(HWND, UINT, WPARAM, LPARAM);

// -------------------------------------------------------------------
// Создание Win32 окна. Возвращает HWND или nullptr при ошибке.
// -------------------------------------------------------------------
static HWND CreateIntroWindow(int w, int h) {
    // 1. Регистрируем класс окна.
    WNDCLASSEX wc = {};
    wc.cbSize        = sizeof(WNDCLASSEX);
    wc.style         = CS_OWNDC | CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc   = WndProc;        // наш обработчик сообщений
    wc.hInstance      = GetModuleHandle(nullptr);
    wc.hCursor        = LoadCursor(nullptr, IDC_ARROW);
    wc.lpszClassName  = "DemoIntroClass";
    if (!RegisterClassEx(&wc)) {
        Log("[Error] RegisterClassEx failed: %lu", GetLastError());
        return nullptr;
    }

    // 2. Стиль окна: можно сделать borderless, для аутентичности.
    DWORD style = WS_POPUP;   // borderless fullscreen, показ через ShowWindow
    // Альтернатива: WS_OVERLAPPEDWINDOW для окна с рамкой.

    // 3. Подгоняем размер клиентской области под желаемый размер.
    RECT rc = { 0, 0, w, h };
    AdjustWindowRectEx(&rc, style, FALSE, 0);

    // 4. Центрируем окно на экране.
    int screenW = GetSystemMetrics(SM_CXSCREEN);
    int screenH = GetSystemMetrics(SM_CYSCREEN);
    int winW = rc.right - rc.left;
    int winH = rc.bottom - rc.top;
    int x = (screenW - winW) / 2;
    int y = (screenH - winH) / 2;

    // 5. Создаём окно.
    HWND hwnd = CreateWindowEx(
        0,
        "DemoIntroClass",
        "Demo Intro",
        style,
        x, y, winW, winH,
        nullptr, nullptr, GetModuleHandle(nullptr), nullptr
    );
    if (!hwnd) {
        Log("[Error] CreateWindowEx failed: %lu", GetLastError());
        return nullptr;
    }

    return hwnd;
}

// -------------------------------------------------------------------
// Создание OpenGL контекста. Должно вызываться ПОСЛЕ создания окна.
// -------------------------------------------------------------------
static bool CreateOpenGLContext(HWND hwnd) {
    g_hdc = GetDC(hwnd);
    if (!g_hdc) {
        Log("[Error] GetDC failed");
        return false;
    }

    // 1. Описание формата пикселей. Здесь задаём 32-битный цвет,
    // 24-битный Z-буфер, 8-битный stencil, double-buffer.
    PIXELFORMATDESCRIPTOR pfd = {};
    pfd.nSize      = sizeof(PIXELFORMATDESCRIPTOR);
    pfd.nVersion   = 1;
    pfd.dwFlags    = PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER;
    pfd.iPixelType = PFD_TYPE_RGBA;
    pfd.cColorBits = 32;
    pfd.cDepthBits = 24;
    pfd.cStencilBits = 8;
    pfd.iLayerType = PFD_MAIN_PLANE;

    int pixelFormat = ChoosePixelFormat(g_hdc, &pfd);
    if (pixelFormat == 0) {
        Log("[Error] ChoosePixelFormat failed");
        return false;
    }
    if (!SetPixelFormat(g_hdc, pixelFormat, &pfd)) {
        Log("[Error] SetPixelFormat failed: %lu", GetLastError());
        return false;
    }
    {
        PIXELFORMATDESCRIPTOR chosen = {};
        DescribePixelFormat(g_hdc, pixelFormat, sizeof(chosen), &chosen);
        Log("[GL] Pixel format %d: color=%u depth=%u stencil=%u",
            pixelFormat, chosen.cColorBits, chosen.cDepthBits,
            chosen.cStencilBits);
    }

    // 2. Создаём "временный" (legacy) OpenGL-контекст. Он нужен, чтобы
    // получить доступ к wglGetProcAddress для современных функций.
    HGLRC tmpCtx = wglCreateContext(g_hdc);
    if (!tmpCtx) {
        Log("[Error] wglCreateContext (temp) failed");
        return false;
    }
    if (!wglMakeCurrent(g_hdc, tmpCtx)) {
        Log("[Error] wglMakeCurrent (temp) failed");
        wglDeleteContext(tmpCtx);
        return false;
    }

    // 3. Пробуем создать современный контекст (3.3+) через
    // wglCreateContextAttribsARB. Эта функция сама является расширением,
    // поэтому получаем её через wglGetProcAddress.
    typedef HGLRC (WINAPI * PFNWGLCREATECONTEXTATTRIBSARB)(HDC, HGLRC, const int*);
    PFNWGLCREATECONTEXTATTRIBSARB wglCreateContextAttribsARB =
        (PFNWGLCREATECONTEXTATTRIBSARB)(void*)wglGetProcAddress("wglCreateContextAttribsARB");

    if (wglCreateContextAttribsARB) {
        // Запрашиваем OpenGL 3.3 core profile.
        int attribs[] = {
            0x2091 /* WGL_CONTEXT_MAJOR_VERSION_ARB */, 3,
            0x2092 /* WGL_CONTEXT_MINOR_VERSION_ARB */, 3,
            0x9126 /* WGL_CONTEXT_PROFILE_MASK_ARB  */, 0x0001 /* WGL_CONTEXT_CORE_PROFILE_BIT_ARB */,
            0x2094 /* WGL_CONTEXT_FLAGS_ARB          */, 0,
            0
        };
        HGLRC modernCtx = wglCreateContextAttribsARB(g_hdc, nullptr, attribs);
        if (modernCtx) {
            // Успех — переключаемся на новый контекст, старый удаляем.
            wglMakeCurrent(nullptr, nullptr);
            wglDeleteContext(tmpCtx);
            wglMakeCurrent(g_hdc, modernCtx);
            g_hglrc = modernCtx;
            Log("[OK] Created OpenGL 3.3 core context");
        } else {
            // Современный контекст не создался — оставим временный.
            g_hglrc = tmpCtx;
            Log("[Warn] Modern context failed, using legacy context");
        }
    } else {
        // Расширение недоступно — оставим временный контекст.
        g_hglrc = tmpCtx;
        Log("[Warn] wglCreateContextAttribsARB not available, using legacy context");
    }

    // 4. Диагностика драйвера: если RENDERER = "GDI Generic" —
    // аппаратного OpenGL нет (RDP-сессия/сломанный драйвер).
    {
        const char* glVer   = (const char*)glGetString(GL_VERSION);
        const char* glRend  = (const char*)glGetString(GL_RENDERER);
        const char* glVend  = (const char*)glGetString(GL_VENDOR);
        const char* glSlVer = (const char*)glGetString(GL_SHADING_LANGUAGE_VERSION);
        Log("[GL] VERSION:    %s", glVer   ? glVer   : "(null)");
        Log("[GL] RENDERER:   %s", glRend  ? glRend  : "(null)");
        Log("[GL] VENDOR:     %s", glVend  ? glVend  : "(null)");
        Log("[GL] GLSL:       %s", glSlVer ? glSlVer : "(null)");
    }

    // 5. Загружаем современные функции OpenGL (шейдеры, программы).
    if (!LoadOpenGLFunctions()) {
        Log("[Error] OpenGL function not available: %s", g_lastMissingGLFn);
        return false;
    }

    // 5. Включаем vsync (если поддерживается) для плавности.
    typedef BOOL (WINAPI * PFNWGLSWAPINTERVALEXT)(int);
    PFNWGLSWAPINTERVALEXT wglSwapIntervalEXT =
        (PFNWGLSWAPINTERVALEXT)(void*)wglGetProcAddress("wglSwapIntervalEXT");
    if (wglSwapIntervalEXT) {
        wglSwapIntervalEXT(1);  // 1 = синхронизировать с монитором
    }

    return true;
}

// -------------------------------------------------------------------
// Компиляция одного шейдера. Возвращает shader object (0 при ошибке).
// -------------------------------------------------------------------
static GLuint CompileShader(GLenum type, const char* src) {
    GLuint shader = glCreateShader(type);
    glShaderSource(shader, 1, &src, nullptr);
    glCompileShader(shader);

    // Проверяем, что компиляция прошла успешно.
    GLint status = 0;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &status);
    if (!status) {
        // Если ошибка — выводим лог.
        GLint logLen = 0;
        glGetShaderiv(shader, GL_INFO_LOG_LENGTH, &logLen);
        if (logLen > 0) {
            char* log = new char[logLen];
            glGetShaderInfoLog(shader, logLen, nullptr, log);
            Log("[Shader] Compile error: %s", log);
            delete[] log;
        }
        glDeleteShader(shader);
        return 0;
    }
    return shader;
}

// -------------------------------------------------------------------
// Создание шейдерной программы: вершинный + фрагментный, линковка.
// -------------------------------------------------------------------
static GLuint CreateProgram(const char* vsSrc, const char* fsSrc) {
    GLuint vs = CompileShader(GL_VERTEX_SHADER, vsSrc);
    if (!vs) return 0;
    GLuint fs = CompileShader(GL_FRAGMENT_SHADER, fsSrc);
    if (!fs) {
        glDeleteShader(vs);
        return 0;
    }

    GLuint prog = glCreateProgram();
    glAttachShader(prog, vs);
    glAttachShader(prog, fs);
    glLinkProgram(prog);

    // Проверяем линковку.
    GLint status = 0;
    glGetProgramiv(prog, GL_LINK_STATUS, &status);
    if (!status) {
        GLint logLen = 0;
        glGetProgramiv(prog, GL_INFO_LOG_LENGTH, &logLen);
        if (logLen > 0) {
            char* log = new char[logLen];
            glGetProgramInfoLog(prog, logLen, nullptr, log);
            Log("[Program] Link error: %s", log);
            delete[] log;
        }
        glDeleteProgram(prog);
        prog = 0;
    }

    // Шейдеры больше не нужны после линковки.
    glDeleteShader(vs);
    glDeleteShader(fs);
    return prog;
}

// === Хелперы для огня: векторная математика + логика частиц ===
// Повороты 2D-плоскостью (повторяют логику шейдера). Чтобы получить
// МИРОВУЮ позицию частицы (как её видит камера), применяем ОБРАТНУЮ
// композицию R^-1 к particlePos_raw (отражённые вращения в обратном
// порядке): R5^-1 → R4^-1 → R3^-1 → R2^-1 → R1^-1.
struct Vec3f { float x, y, z; };

static Vec3f rotXZ(Vec3f p, float ang) {
    float c = cosf(ang), s = sinf(ang);
    return { c*p.x + s*p.z, p.y, -s*p.x + c*p.z };
}
static Vec3f rotYZ(Vec3f p, float ang) {
    float c = cosf(ang), s = sinf(ang);
    return { p.x, c*p.y + s*p.z, -s*p.y + c*p.z };
}
static Vec3f rotXY(Vec3f p, float ang) {
    float c = cosf(ang), s = sinf(ang);
    return { c*p.x + s*p.y, -s*p.x + c*p.y, p.z };
}
static Vec3f yawRot(Vec3f p, float ang) {
    float c = cosf(ang), s = sinf(ang);
    return { c*p.x - s*p.z, p.y, s*p.x + c*p.z };
}
static Vec3f pitchRot(Vec3f p, float ang) {
    float c = cosf(ang), s = sinf(ang);
    return { p.x, c*p.y - s*p.z, s*p.y + c*p.z };
}

// Мир-позиция частицы i в момент t с учётом вращений мыши (yaw, pitch).
static Vec3f ParticleWorldPos(int i, double t, float yaw, float pitch) {
    float ft = (float)t;
    float angle = ft * (0.4f + i * 0.06f) + i * 0.78f;
    float radius = 1.6f + 0.4f * sinf(i * 1.7f + ft * 0.2f);
    float yOff  = 0.8f * sinf(i * 0.9f + ft * 0.3f + i);
    Vec3f p = { cosf(angle) * radius, yOff, sinf(angle) * radius };
    p = rotXY(p, -ft * 0.2f);    // R5^-1
    p = rotYZ(p, -ft * 0.3f);    // R4^-1
    p = rotXZ(p, -ft * 0.5f);    // R3^-1
    p = pitchRot(p, -pitch);     // R2^-1
    p = yawRot(p, -yaw);         // R1^-1
    return p;
}

// Простой LCG для детерминированной случайности.
static unsigned int g_fireRngState = 987654321u;
static float FireRand() {
    g_fireRngState = g_fireRngState * 1664525u + 1013904223u;
    return (float)((g_fireRngState >> 8) & 0xFFFFFF) / (float)0x1000000;
}

// Спавн новых огней и удаление истёкших. Вызывается каждый кадр.
static void SpawnFireIfNeeded(double t) {
    if (!g_fireEnabled) return;
    // Удаляем истёкшие (за LIFETIME).
    for (int i = g_fireCount - 1; i >= 0; i--) {
        if (t - g_fires[i].startTime > kFireLifetime) {
            g_fires[i] = g_fires[--g_fireCount];
        }
    }
    if (g_fireCount >= kFireMaxConcurrent) return;
    if (t < g_nextSpawnAt) return;
    // Выбираем частицу, которая ещё не горит.
    bool burning[8] = {false};
    for (int i = 0; i < g_fireCount; i++) {
        if (g_fires[i].particleIdx >= 0 && g_fires[i].particleIdx < 8) {
            burning[g_fires[i].particleIdx] = true;
        }
    }
    int candidates[8];
    int n = 0;
    for (int i = 0; i < 8; i++) if (!burning[i]) candidates[n++] = i;
    if (n == 0) return;
    int idx = candidates[(int)(FireRand() * n) % n];
    g_fires[g_fireCount].particleIdx = idx;
    g_fires[g_fireCount].startTime = t;
    g_fireCount++;
    g_nextSpawnAt = t + kFireMinInterval
                    + FireRand() * (kFireMaxInterval - kFireMinInterval);
}

// Значение маски для частицы (1=вода видна, 0=горит, воду скрыть).
static float FireMaskValue(int i, double t) {
    if (!g_fireEnabled) return 1.0f;
    for (int k = 0; k < g_fireCount; k++) {
        if (g_fires[k].particleIdx == i
            && (t - g_fires[k].startTime) < kFireLifetime) {
            return 0.0f;
        }
    }
    return 1.0f;
}

// -------------------------------------------------------------------
// Инициализация всех OpenGL-ресурсов. Вызывается ОДИН раз после
// создания контекста.
// -------------------------------------------------------------------
static bool InitGLResources() {
    g_program = CreateProgram(kVertexShaderSrc, kFragmentShaderSrc);
    if (!g_program) {
        Log("[Error] Failed to create shader program");
        return false;
    }
    Log("[OK] Main shader program created (id=%u)", (unsigned)g_program);

    // Получаем позиции uniform-переменных (для последующих кадров).
    g_unifTime = glGetUniformLocation(g_program, "uTime");
    g_unifRes  = glGetUniformLocation(g_program, "uResolution");
    g_unifZoom = glGetUniformLocation(g_program, "uZoom");
    g_unifDrops = glGetUniformLocation(g_program, "uDroplets");
    g_unifMouseRot = glGetUniformLocation(g_program, "uMouseRot");
    g_unifFireMask = glGetUniformLocation(g_program, "uFireMask[0]");

    // Минимальное состояние GL: нет глубины (всё в одном фрагменте),
    // нет смешивания. Просто закрашиваем quad.
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_CULL_FACE);

    // ДЕФОЛТНЫЙ VAO для основной сцены (core profile требует VAO).
    glGenVertexArrays(1, &g_defaultVAO);
    glBindVertexArray(g_defaultVAO);
    Log("[OK] Default VAO created (id=%u)", (unsigned)g_defaultVAO);

    // === Создаём программу огня (процедурная, без текстуры) ===
    g_fireProgram = CreateProgram(kFireVertexShaderSrc, kFireFragmentShaderSrc);
    if (!g_fireProgram) {
        Log("[Error] Failed to create fire shader program");
        return false;
    }
    Log("[OK] Fire shader program created (id=%u)", (unsigned)g_fireProgram);
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

    Log("[OK] GL resources initialized (VAO=%u fireVAO=%u fireVBO=%u)",
        (unsigned)g_defaultVAO, (unsigned)g_fireVAO, (unsigned)g_fireVBO);
    return true;
}

// -------------------------------------------------------------------
// Отрисовка одного кадра.
// -------------------------------------------------------------------
static void RenderFrame(double dt) {
    static bool s_firstFrame = true;
    if (s_firstFrame) {
        Log("[OK] First frame rendered %dx%d", g_width, g_height);
        Log("[OK] nebula bg rendered");
        Log("[OK] nebula v2 probe");
        s_firstFrame = false;
    }
    // Накапливаем время (если не на паузе). На slow-mo делим на 4.
    // Важно: на паузе мы НЕ пропускаем рендер — кадры рисуются каждый
    // цикл, просто timeAccum замирает. Поэтому сцена остаётся живой:
    // её можно крутить мышью без единого пропущенного кадра.
    if (!g_paused) {
        double timeStep = dt;
        if (g_slowMo) timeStep *= 0.25;
        g_timeAccum += timeStep;
    }

    // Плавное догоняние углов вращения мыши. Экспонента с k=50: отклик
    // ~20 мс (лаг незаметен), рывки опроса мыши сглаживаются. Полное
    // смещение сохраняется — экспонента сходится к цели, ничего не
    // теряется даже если кадры редкие (dt ограничен, но target точен).
    float rotSmooth = 1.0f - expf((float)(-dt * 50.0));
    g_rotYaw   += (g_rotYawTarget   - g_rotYaw)   * rotSmooth;
    g_rotPitch += (g_rotPitchTarget - g_rotPitch) * rotSmooth;

    // Размеры viewport'а — на всё окно.
    glViewport(0, 0, g_width, g_height);

    // Очищаем экран (хотя шейдер всё равно закрасит всё).
    glClearColor(0.0f, 0.0f, 0.0f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);

    // Выбираем нашу шейдерную программу.
    glUseProgram(g_program);

    // В core profile рисовать без VAO — GL_INVALID_OPERATION.
    if (g_defaultVAO) glBindVertexArray(g_defaultVAO);

    // Передаём значения uniform-переменных.
    if (g_unifTime >= 0) {
        glUniform1f(g_unifTime, (GLfloat)g_timeAccum);
    }
    if (g_unifRes >= 0) {
        glUniform2f(g_unifRes, (GLfloat)g_width, (GLfloat)g_height);
    }
    if (g_unifZoom >= 0) {
        glUniform1f(g_unifZoom, (GLfloat)g_zoom);
    }
    if (g_unifDrops >= 0) {
        glUniform1i(g_unifDrops, g_droplets ? 1 : 0);
    }
    if (g_unifMouseRot >= 0) {
        glUniform2f(g_unifMouseRot, g_rotYaw, g_rotPitch);
    }

    // ОГОНЬ: спавн + маска частиц (передаётся в основной шейдер,
    // чтобы скрыть воду на месте горящих частиц).
    SpawnFireIfNeeded(g_timeAccum);
    if (g_unifFireMask >= 0) {
        float mask[8];
        for (int i = 0; i < 8; i++) mask[i] = FireMaskValue(i, g_timeAccum);
        glUniform1fv(g_unifFireMask, 8, mask);
    }

    // Рисуем fullscreen quad из 4 вершин (triangle strip).
    // Вершинный шейдер генерирует их сам из gl_VertexID, так что
    // буферов вершин (VBO) не требуется.
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

    // === Проход огня (поверх основной сцены, аддитивный блендинг) ===
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
    }

    // Показ FPS, если включён (F1).
    if (g_showFPS) {
        // Подсчёт FPS: суммируем время в g_fpsAccumTime, считаем кадры,
        // каждые 0.5 сек обновляем g_fps.
        g_frameCount++;
        g_fpsAccumTime += dt;
        if (g_fpsAccumTime >= 0.5) {
            g_fps = (double)g_frameCount / g_fpsAccumTime;
            g_frameCount = 0;
            g_fpsAccumTime = 0.0;
        }
        char title[96];
        snprintf(title, sizeof(title), "Demo Intro  |  %.1f FPS%s%s",
                 g_fps, g_slowMo ? "  (slow-mo)" : "", g_paused ? "  (paused)" : "");
        SetWindowTextA(g_hwnd, title);
    } else {
        SetWindowTextA(g_hwnd, "Demo Intro  -  ESC quit, SPACE pause, LMB drag rotate");
    }

    // Показываем задний буфер.
    SwapBuffers(g_hdc);
}

// -------------------------------------------------------------------
// Обработчик сообщений окна.
// Здесь обрабатываем закрытие, ESC, SPACE (пауза), F1, F2, resize,
// зум (колесо +/-) и вращение сцены мышью (drag ЛКМ).
// -------------------------------------------------------------------

// Утилита для безопасного изменения зума с ограничением [0.3, 2.5].
// Верхний предел 2.5x вместо 3.0x — иначе камера входит внутрь фигуры
// (т.к. dist = 3.5 / zoom = 1.17, а радиус фигуры ~1.0).
static void AdjustZoom(float multiplier) {
    g_zoom *= multiplier;
    if (g_zoom < 0.3f) g_zoom = 0.3f;
    if (g_zoom > 2.5f) g_zoom = 2.5f;
}
static void ResetZoom() { g_zoom = 1.0f; }

static LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
        case WM_KEYDOWN: {
            switch (wp) {
                case VK_ESCAPE:
                    // Пользователь нажал ESC — выходим.
                    Log("[Exit] ESC pressed");
                    g_running = false;
                    PostQuitMessage(0);
                    return 0;
                case VK_F1:
                    g_showFPS = !g_showFPS;
                    return 0;
                case VK_F2:
                    g_slowMo = !g_slowMo;
                    return 0;
                case VK_SPACE:
                    // Пауза анимации. Рендер НЕ останавливается — кадры
                    // продолжают рисоваться, просто timeAccum замирает.
                    // Сцену при этом можно вращать мышью (drag ЛКМ).
                    g_paused = !g_paused;
                    return 0;
                case VK_OEM_PLUS:    // '+' на основной клавиатуре
                case VK_ADD:         // '+' на numpad
                    AdjustZoom(1.15f);
                    return 0;
                case VK_OEM_MINUS:  // '-' на основной клавиатуре
                case VK_SUBTRACT:   // '-' на numpad
                    AdjustZoom(1.0f / 1.15f);
                    return 0;
                case '0':
                case VK_NUMPAD0:
                    ResetZoom();
                    return 0;
                case 'D':
                case 'd':
                    g_droplets = !g_droplets;
                    return 0;
                case 'F':
                case 'f':
                    g_fireEnabled = !g_fireEnabled;
                    if (!g_fireEnabled) {
                        g_fireCount = 0;  // тушим все текущие огни
                    } else {
                        g_nextSpawnAt = g_timeAccum + 1.5;  // короткая пауза
                    }
                    return 0;
            }
            return 0;
        }

        case WM_MOUSEWHEEL: {
            // GET_WHEEL_DELTA_WPARAM возвращает величину прокрутки (обычно ±120).
            // Прокрутка вверх — приближаем, вниз — отдаляем.
            short delta = GET_WHEEL_DELTA_WPARAM(wp);
            // exp() даёт плавный, "чувствительный" зум.
            float factor = expf((float)delta * 0.0015f);
            AdjustZoom(factor);
            return 0;
        }

        case WM_LBUTTONDOWN: {
            // Начало drag-вращения: запоминаем точку старта и захватываем
            // мышь (SetCapture), чтобы получать WM_MOUSEMOVE даже когда
            // курсор уходит за пределы окна — вращение не «срывается».
            g_dragging    = true;
            g_lastMouse.x = GET_X_LPARAM(lp);
            g_lastMouse.y = GET_Y_LPARAM(lp);
            SetCapture(hwnd);
            return 0;
        }

        case WM_MOUSEMOVE: {
            if (!g_dragging) return 0;
            // Дельта курсора с прошлого события → приращение целевых углов.
            // 0.008 рад/пиксель ≈ 0.46° — комфортная чувствительность.
            // Минус по dy: тянем вниз — передняя грань уходит вниз («глобус»).
            int mx = GET_X_LPARAM(lp);
            int my = GET_Y_LPARAM(lp);
            g_rotYawTarget   += (float)(mx - g_lastMouse.x) * 0.008f;
            g_rotPitchTarget -= (float)(my - g_lastMouse.y) * 0.008f;
            // Ограничиваем наклон — фигура не переворачивается через полюс.
            if (g_rotPitchTarget >  1.45f) g_rotPitchTarget =  1.45f;
            if (g_rotPitchTarget < -1.45f) g_rotPitchTarget = -1.45f;
            g_lastMouse.x = mx;
            g_lastMouse.y = my;
            return 0;
        }

        case WM_LBUTTONUP: {
            if (g_dragging) {
                g_dragging = false;
                ReleaseCapture();
            }
            return 0;
        }

        case WM_CAPTURECHANGED:
            // Захват мыши забрали (например, всплывающее окно) — drag прерван.
            g_dragging = false;
            return 0;

        case WM_SIZE: {
            // Окно изменило размер — обновляем ширину/высоту.
            g_width  = LOWORD(lp);
            g_height = HIWORD(lp);
            if (g_width < 1)  g_width = 1;
            if (g_height < 1) g_height = 1;
            return 0;
        }

        case WM_CLOSE:
            Log("[Exit] WM_CLOSE");
            g_running = false;
            PostQuitMessage(0);
            return 0;

        case WM_DESTROY:
            PostQuitMessage(0);
            return 0;
    }
    return DefWindowProc(hwnd, msg, wp, lp);
}

// -------------------------------------------------------------------
// Точка входа программы.
// -------------------------------------------------------------------
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE, LPSTR, int) {
    (void)hInstance;

    // v45: первый Log дописывает RUN START banner в trace.log
    // (build-секция уже там от build_msvc.bat).
    SetUnhandledExceptionFilter(CrashHandler);
    Log("[Start] Demo Intro v48 noise3fix | compiler=%s | arch=%d-bit | build=%s %s",
        kBuildCompiler, (int)(sizeof(void*) * 8), __DATE__, __TIME__);

    // DPI awareness (Win 11 125%/150% масштабирование).
    {
        typedef BOOL (WINAPI *PFN_SetProcessDpiAwarenessContext)(HANDLE);
        HMODULE user32 = GetModuleHandleA("user32.dll");
        PFN_SetProcessDpiAwarenessContext p = user32
            ? (PFN_SetProcessDpiAwarenessContext)(void*)GetProcAddress(
                  user32, "SetProcessDpiAwarenessContext")
            : nullptr;
        if (p) p((HANDLE)-4);   // PER_MONITOR_AWARE_V2
        else   SetProcessDPIAware();
    }

    QueryPerformanceFrequency(&g_freq);

    // Fullscreen borderless: размер = primary monitor.
    g_width  = GetSystemMetrics(SM_CXSCREEN);
    g_height = GetSystemMetrics(SM_CYSCREEN);
    if (g_width  < 2) g_width  = 1280;
    if (g_height < 2) g_height = 720;
    Log("[OK] Primary screen: %dx%d", g_width, g_height);

    // 1. Создаём окно.
    g_hwnd = CreateIntroWindow(g_width, g_height);
    if (!g_hwnd) {
        MessageBoxA(nullptr, "Failed to create window", "Error", MB_ICONERROR);
        return 1;
    }
    Log("[OK] Window created: %dx%d borderless, hwnd=%p",
        g_width, g_height, (void*)g_hwnd);

    // 2. Создаём OpenGL-контекст.
    if (!CreateOpenGLContext(g_hwnd)) {
        MessageBoxA(nullptr, "Failed to create OpenGL context.\n"
                            "Make sure your GPU drivers support OpenGL 3.3+.",
                    "Error", MB_ICONERROR);
        return 2;
    }
    Log("[OK] OpenGL context ready (hglrc=%p)", (void*)g_hglrc);

    // 3. Загружаем шейдеры и ресурсы.
    if (!InitGLResources()) {
        MessageBoxA(nullptr, "Failed to compile shaders.\n"
                            "Check debug output for details.",
                    "Error", MB_ICONERROR);
        return 3;
    }

    // 4. Показываем окно.
    ShowWindow(g_hwnd, SW_SHOW);
    UpdateWindow(g_hwnd);
    SetForegroundWindow(g_hwnd);
    SetFocus(g_hwnd);
    Log("[OK] Window shown — entering main loop");

    // Обработчик сообщений уже задан в RegisterClassEx, никаких лишних
    // действий не нужно.

    // 5. Главный цикл.
    g_prevTime = GetTimeSeconds();
    MSG msg = {};
    while (g_running) {
        // Обрабатываем все накопленные сообщения Windows.
        while (PeekMessage(&msg, nullptr, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) {
                g_running = false;
                break;
            }
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }
        if (!g_running) break;

        // Считаем время кадра.
        double now = GetTimeSeconds();
        double dt = now - g_prevTime;
        g_prevTime = now;

        // Ограничиваем dt: если была пауза (например, при дебагге),
        // не делаем шаг больше 1/30 сек, чтобы физика не сломалась.
        if (dt > 1.0 / 30.0) dt = 1.0 / 30.0;

        RenderFrame(dt);
    }

    // 6. Очистка.
    if (g_hglrc) {
        wglMakeCurrent(nullptr, nullptr);
        wglDeleteContext(g_hglrc);
    }
    if (g_hdc && g_hwnd) {
        ReleaseDC(g_hwnd, g_hdc);
    }
    if (g_hwnd) {
        DestroyWindow(g_hwnd);
    }

    Log("[Exit] Main loop ended (code %d)", (int)msg.wParam);

    return (int)msg.wParam;
}
