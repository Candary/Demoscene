// demo_runtime.cpp — рантайм демо-интро (v53 base + v54 stats + v58 morphing_figures).
// v51-fix: WS_POPUP→WS_OVERLAPPEDWINDOW, single-instance mutex,
//          SetForegroundWindow + WS_EX_APPWINDOW, diagnostics in render loop.
// v53: F1 toggles FPS in window title.
// v54: always-on min/max/avg FPS stats + final report in trace.log.
// v55: 6 scenes 180s (в .smt) + cozy_room_sdf.frag fix.
// v58: +morphing_figures.frag scene (crossfade 1s + 30s) → total 211s.
//
// cl /std:c++17 /EHsc /O2 demo_runtime.cpp /I. /link opengl32.lib user32.lib gdi32.lib

#define _CRT_SECURE_NO_WARNINGS
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <GL/gl.h>
#include <stdio.h>
#include <string>

#include "opengl_loader.h"
#include "sm_runtime.hpp"
#include "gl_executor.hpp"

static HWND g_hwnd = nullptr;
static HDC g_hdc = nullptr;
static HGLRC g_hglrc = nullptr;
static bool g_running = true;
static int g_width = 1280, g_height = 720;

// v53: FPS counter (toggleable via F1, shown in window title).
static bool   g_showFPS    = false;   // F1 переключает показ FPS в заголовке окна
static int    g_fpsFrames  = 0;       // счётчик кадров с последнего обновления
static double g_fpsAccum   = 0.0;     // накопленное время с последнего обновления
static double g_fpsValue   = 0.0;     // последнее вычисленное значение FPS
static char   g_titleBuf[200];        // буфер для SetWindowTextA

// v54: статистика FPS за весь показ (накапливается всегда, независимо от F1).
static double g_fpsMin     = 0.0;     // минимальный sampled FPS
static double g_fpsMax     = 0.0;     // максимальный sampled FPS
static double g_fpsSum     = 0.0;     // сумма всех sampled FPS (для avg)
static int    g_fpsSamples = 0;       // количество sampled обновлений

static double getTime() {
    static LARGE_INTEGER freq = {0};
    static bool init = false;
    if (!init) { QueryPerformanceFrequency(&freq); init = true; }
    LARGE_INTEGER now; QueryPerformanceCounter(&now);
    return (double)now.QuadPart / (double)freq.QuadPart;
}

static void Log(const char* fmt, ...) {
    char buf[1024]; va_list args; va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args); va_end(args);
    OutputDebugStringA(buf); OutputDebugStringA("\n");
    printf("%s\n", buf);
    static FILE* s_log = nullptr;
    if (!s_log) { s_log = fopen("trace.log", "a"); if (s_log) setvbuf(s_log, nullptr, _IONBF, 0); }
    if (s_log) fprintf(s_log, "%s\n", buf);
}

static LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
        case WM_KEYDOWN:
            if (wp == VK_ESCAPE) { g_running = false; PostQuitMessage(0); return 0; }
            if (wp == VK_F1)    { g_showFPS = !g_showFPS; return 0; }   // v53: toggle FPS
            break;
        case WM_CLOSE: g_running = false; PostQuitMessage(0); return 0;
        case WM_SIZE: g_width = LOWORD(lp); g_height = HIWORD(lp); return 0;
    }
    return DefWindowProc(hwnd, msg, wp, lp);
}

static HWND createWindow(int w, int h) {
    // Регистрируем класс (игнорируем "уже зарегистрирован" — это нормально
    // если предыдущий экземпляр не снял класс).
    WNDCLASSEX wc = {};
    wc.cbSize = sizeof(WNDCLASSEX);
    wc.style = CS_OWNDC | CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc = WndProc;
    wc.hInstance = GetModuleHandle(nullptr);
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.hbrBackground = nullptr;
    wc.lpszClassName = "DemoRT";
    ATOM cls = RegisterClassEx(&wc);
    if (!cls && GetLastError() != 0x582) { // 0x582 = ERROR_CLASS_ALREADY_EXISTS
        Log("[Error] RegisterClassEx failed, err=0x%lx", GetLastError());
    }

    // WS_OVERLAPPEDWINDOW вместо WS_POPUP — даёт рамку, заголовок,
    // кнопку в taskbar. Надёжно видно на Windows 11.
    DWORD style = WS_OVERLAPPEDWINDOW | WS_VISIBLE | WS_CLIPSIBLINGS | WS_CLIPCHILDREN;
    DWORD exStyle = WS_EX_APPWINDOW | WS_EX_WINDOWEDGE;
    RECT rc = {0, 0, w, h};
    AdjustWindowRectEx(&rc, style, FALSE, exStyle);
    int cw = rc.right - rc.left;
    int ch = rc.bottom - rc.top;
    int sw = GetSystemMetrics(SM_CXSCREEN), sh = GetSystemMetrics(SM_CYSCREEN);
    int x = (sw - cw) / 2, y = (sh - ch) / 2;
    if (x < 0) x = 0;
    if (y < 0) y = 0;
    HWND hwnd = CreateWindowEx(exStyle, "DemoRT", "Demo Runtime v59v2v2", style,
        x, y, cw, ch,
        nullptr, nullptr, GetModuleHandle(nullptr), nullptr);
    if (hwnd) {
        Log("[Window] HWND=%p created at (%d,%d) size %dx%d (client %dx%d)",
            hwnd, x, y, cw, ch, w, h);
    }
    return hwnd;
}

static bool createGLContext(HWND hwnd) {
    g_hdc = GetDC(hwnd);
    PIXELFORMATDESCRIPTOR pfd = {};
    pfd.nSize = sizeof(pfd); pfd.nVersion = 1;
    pfd.dwFlags = PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER;
    pfd.iPixelType = PFD_TYPE_RGBA; pfd.cColorBits = 32; pfd.cDepthBits = 24;
    int pf = ChoosePixelFormat(g_hdc, &pfd);
    SetPixelFormat(g_hdc, pf, &pfd);
    HGLRC tmp = wglCreateContext(g_hdc);
    wglMakeCurrent(g_hdc, tmp);
    typedef HGLRC (WINAPI *PFN_wglCreateContextAttribsARB)(HDC, HGLRC, const int*);
    auto fn = (PFN_wglCreateContextAttribsARB)(void*)wglGetProcAddress("wglCreateContextAttribsARB");
    if (fn) {
        int attribs[] = {0x2091, 3, 0x2092, 3, 0x9126, 0x0001, 0x2094, 0, 0};
        HGLRC modern = fn(g_hdc, nullptr, attribs);
        if (modern) { wglMakeCurrent(nullptr, nullptr); wglDeleteContext(tmp); wglMakeCurrent(g_hdc, modern); g_hglrc = modern; }
        else g_hglrc = tmp;
    } else g_hglrc = tmp;
    if (!LoadOpenGLFunctions()) { Log("[Error] GL functions not loaded"); return false; }
    typedef BOOL (WINAPI *PFN_wglSwapIntervalEXT)(int);
    auto swi = (PFN_wglSwapIntervalEXT)(void*)wglGetProcAddress("wglSwapIntervalEXT");
    if (swi) swi(1);
    return true;
}

int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    std::string smtPath = "demo.smt";
    std::string shaderDir = "shaders";

    Log("[Start] Demo Runtime — loading %s", smtPath.c_str());
    sm::Show show;
    try {
        show = sm::load(smtPath);
    } catch (const std::exception& e) {
        Log("[Error] Failed to load %s: %s", smtPath.c_str(), e.what());
        MessageBoxA(nullptr, ("Failed to load " + smtPath + ":\n" + e.what()).c_str(), "Demo", MB_ICONERROR);
        return 1;
    }
    Log("[OK] SMT loaded: duration=%.1fs, %d clips, %d segments",
        show.duration, (int)show.clips.size(), (int)show.segs.size());

    // Диагностика парсера: проверяем что opacity/progress непустые у каждого клипа.
    for (const auto& c : show.clips) {
        Log("  clip '%s' effect='%s' opacity_tokens=%d progress_tokens=%d uniforms=%d",
            c.id.c_str(), c.effect.c_str(),
            (int)c.opacity.size(), (int)c.progress.size(),
            (int)c.uniforms.size());
    }

    // Single-instance mutex — предотвращает двойной запуск (был виден в трейсе).
    HANDLE hMutex = CreateMutexA(nullptr, TRUE, "Global\\DemoRT_v51_SingleInstance");
    if (hMutex && GetLastError() == ERROR_ALREADY_EXISTS) {
        Log("[Warn] Another instance is already running — exiting this one.");
        if (hMutex) CloseHandle(hMutex);
        return 0;
    }

    g_width = show.w; g_height = show.h;
    g_hwnd = createWindow(g_width, g_height);
    if (!g_hwnd) { Log("[Error] Window creation failed, err=0x%lx", GetLastError()); return 1; }
    if (!createGLContext(g_hwnd)) { Log("[Error] GL context failed"); return 2; }

    // Делаем окно видимым и активным.
    ShowWindow(g_hwnd, SW_SHOWNORMAL);
    UpdateWindow(g_hwnd);
    SetForegroundWindow(g_hwnd);
    SetFocus(g_hwnd);
    Log("[Window] Visible=true, foreground set");
    Log("[GL] %s / %s", glGetString(GL_RENDERER), glGetString(GL_VERSION));

    glx::ShaderCache shaders;
    shaders.init(shaderDir);
    glx::FBOPool fbos;
    fbos.init(g_width, g_height);

    int compiled = 0;
    for (const auto& c : show.clips) {
        if (c.effect != "finish" && c.effect != "-" && shaders.getProgram(c.effect)) compiled++;
    }
    Log("[OK] %d shader programs compiled", compiled);

    double startTime = getTime();
    int frameCount = 0;
    double lastDiag = 0.0;
    double prevT = 0.0;   // для dt (расчёт FPS)
    MSG msg = {};
    Log("[Loop] Entering render loop, duration=%.1fs", show.duration);
    Log("[Help] F1 = toggle FPS in window title (min/max/avg tracked always)");
    while (g_running) {
        while (PeekMessage(&msg, nullptr, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) { g_running = false; break; }
            TranslateMessage(&msg); DispatchMessage(&msg);
        }
        if (!g_running) break;

        double T = getTime() - startTime;
        if (T >= show.duration) { Log("[Done] Show finished at T=%.2fs, frames=%d", T, frameCount); break; }

        try {
            glx::renderFrame(show, T, shaders, fbos);
        } catch (const std::exception& e) {
            Log("[Error] renderFrame exception at T=%.3f: %s", T, e.what());
            g_running = false;
            break;
        }
        SwapBuffers(g_hdc);
        frameCount++;

        // v53+v54: FPS calculation — накапливаем ВСЕГДА (для статистики),
        // окно обновляем только если F1 включён.
        double dt = T - prevT;
        prevT = T;
        g_fpsFrames++;
        g_fpsAccum += dt;
        if (g_fpsAccum >= 0.5) {
            g_fpsValue = (double)g_fpsFrames / g_fpsAccum;
            g_fpsFrames = 0;
            g_fpsAccum = 0.0;

            // v54: обновляем статистику (всегда).
            if (g_fpsSamples == 0) {
                g_fpsMin = g_fpsValue;
                g_fpsMax = g_fpsValue;
            } else {
                if (g_fpsValue < g_fpsMin) g_fpsMin = g_fpsValue;
                if (g_fpsValue > g_fpsMax) g_fpsMax = g_fpsValue;
            }
            g_fpsSum += g_fpsValue;
            g_fpsSamples++;

            // v53: заголовок только когда F1 on.
            if (g_showFPS) {
                double avgSoFar = g_fpsSum / g_fpsSamples;
                snprintf(g_titleBuf, sizeof(g_titleBuf),
                    "Demo Runtime v59v2v2  |  %.1f FPS (min=%.1f max=%.1f avg=%.1f)  |  T=%.2fs  |  frames=%d  |  F1 toggle",
                    g_fpsValue, g_fpsMin, g_fpsMax, avgSoFar, T, frameCount);
                SetWindowTextA(g_hwnd, g_titleBuf);
            }
        }

        // v53: заголовок управляется transitions F1.
        {
            static bool s_prevShowFPS = true;
            if (g_showFPS != s_prevShowFPS) {
                s_prevShowFPS = g_showFPS;
                if (!g_showFPS) {
                    SetWindowTextA(g_hwnd, "Demo Runtime v59v2v2  -  ESC quit, F1 toggle FPS");
                }
            }
        }

        // Логируем 1-й кадр и затем каждые 5 секунд — подтверждает, что цикл жив.
        if (frameCount == 1) {
            Log("[Loop] First frame rendered, T=%.3fs", T);
            lastDiag = T;
        } else if (T - lastDiag >= 5.0) {
            Log("[Loop] T=%.2fs frames=%d", T, frameCount);
            lastDiag = T;
        }
    }
    Log("[Loop] Exited, total frames=%d", frameCount);

    // v54: финальная статистика FPS в trace.log.
    {
        double finalT = getTime() - startTime;
        if (g_fpsSamples > 0) {
            double avgFPS = g_fpsSum / g_fpsSamples;
            double theoreticalAvg = (finalT > 0.0) ? (double)frameCount / finalT : 0.0;
            Log("[Stats] FPS over %.2fs (%d samples @ 0.5s window):", finalT, g_fpsSamples);
            Log("  sampled:     min=%.2f  max=%.2f  avg=%.2f  FPS", g_fpsMin, g_fpsMax, avgFPS);
            Log("  theoretical: %d frames / %.2fs = %.2f FPS", frameCount, finalT, theoreticalAvg);
            Log("  range:       %.1f FPS (max-min = %.1f)", g_fpsMax - g_fpsMin, g_fpsMax - g_fpsMin);
        } else {
            Log("[Stats] No FPS samples collected (show ended too quickly).");
        }
    }

    if (g_hglrc) { wglMakeCurrent(nullptr, nullptr); wglDeleteContext(g_hglrc); }
    if (g_hdc && g_hwnd) ReleaseDC(g_hwnd, g_hdc);
    if (g_hwnd) DestroyWindow(g_hwnd);
    if (hMutex) ReleaseMutex(hMutex);
    if (hMutex) CloseHandle(hMutex);
    Log("[Exit] Demo Runtime ended");
    return 0;
}
