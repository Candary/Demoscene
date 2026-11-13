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

// v60: Per-scene FPS tracking.
// Scenes defined by time ranges (from .smt segment boundaries).
struct SceneStat {
    const char* name;
    double start, end;
    double minFps, maxFps, sumFps;
    int samples;
};
static SceneStat g_scenes[] = {
    {"nebula",          0.0,  23.0,  999, 0, 0, 0},
    {"transition_1",   23.0,  27.0,  999, 0, 0, 0},
    {"sphere",         27.0,  48.0,  999, 0, 0, 0},
    {"transition_2",   48.0,  52.0,  999, 0, 0, 0},
    {"particle_swarm", 52.0,  73.0,  999, 0, 0, 0},
    {"transition_3",   73.0,  77.0,  999, 0, 0, 0},
    {"anxiety_mist",   77.0,  98.0,  999, 0, 0, 0},
    {"transition_4",   98.0, 102.0,  999, 0, 0, 0},
    {"morph_grid",    102.0, 123.0,  999, 0, 0, 0},
    {"transition_5",  123.0, 127.0,  999, 0, 0, 0},
    {"cozy_room",     127.0, 180.0,  999, 0, 0, 0},
    {"transition_6",  180.0, 181.0,  999, 0, 0, 0},
    {"morphing_figures",181.0,211.0,  999, 0, 0, 0},
};
static const int g_numScenes = sizeof(g_scenes) / sizeof(g_scenes[0]);

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

// v60: Frame capture for visual regression testing.
// Saves JPEG-quality BMP at scene boundaries + 2s.
static void captureFrame(const char* filename, int w, int h) {
    unsigned char* px = new unsigned char[w * h * 4];
    glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, px);
    // Downscale to 640x360 for smaller files (half resolution).
    int sw = w / 2, sh = h / 2;
    unsigned char* small = new unsigned char[sw * sh * 3];
    for (int y = 0; y < sh; y++) {
        for (int x = 0; x < sw; x++) {
            // Average 2x2 block
            int r = 0, g = 0, b = 0;
            for (int dy = 0; dy < 2; dy++) {
                for (int dx = 0; dx < 2; dx++) {
                    int idx = ((y * 2 + dy) * w + (x * 2 + dx)) * 4;
                    r += px[idx]; g += px[idx + 1]; b += px[idx + 2];
                }
            }
            int si = (y * sw + x) * 3;
            small[si] = b / 4; small[si + 1] = g / 4; small[si + 2] = r / 4;
        }
    }
    // Write BMP at half resolution
    FILE* f = fopen(filename, "wb");
    if (!f) { delete[] px; delete[] small; return; }
    int rowSize = ((sw * 3 + 3) / 4) * 4;
    int dataSize = rowSize * sh;
    int fileSize = 54 + dataSize;
    fputc('B', f); fputc('M', f);
    fwrite(&fileSize, 4, 1, f);
    int z = 0; fwrite(&z, 4, 1, f);
    int off = 54; fwrite(&off, 4, 1, f);
    int h40 = 40; fwrite(&h40, 4, 1, f);
    fwrite(&sw, 4, 1, f); fwrite(&sh, 4, 1, f);
    short s1 = 1; fwrite(&s1, 2, 1, f);
    short s24 = 24; fwrite(&s24, 2, 1, f);
    fwrite(&z, 4, 1, f); fwrite(&dataSize, 4, 1, f);
    int dpi = 2835; fwrite(&dpi, 4, 1, f); fwrite(&dpi, 4, 1, f);
    fwrite(&z, 4, 1, f); fwrite(&z, 4, 1, f);
    for (int y = sh - 1; y >= 0; y--) {
        for (int x = 0; x < sw; x++) {
            int idx = (y * sw + x) * 3;
            fputc(small[idx], f); fputc(small[idx + 1], f); fputc(small[idx + 2], f);
        }
        for (int p = sw * 3; p < rowSize; p++) fputc(0, f);
    }
    fclose(f);
    delete[] px; delete[] small;
}

// Capture schedule: scene boundary + 2s after transition ends.
// Scene transitions end at: T=27 (s1→s2), T=52 (s2→s3), T=77 (s3→s4),
// T=102 (s4→s5), T=127 (s5→s6), T=181 (s6→s7).
// Capture 2s after: T=29, 54, 79, 104, 129, 183.
// Plus T=2 for initial scene.
static double g_captureTimes[] = {2.0, 29.0, 54.0, 79.0, 104.0, 129.0, 183.0};
static const char* g_captureNames[] = {
    "shot_nebula.bmp",
    "shot_sphere.bmp",
    "shot_particles.bmp",
    "shot_anxiety.bmp",
    "shot_morph_grid.bmp",
    "shot_cozy_room.bmp",
    "shot_morphing_figures.bmp",
};
static int g_captureIdx = 0;
static bool g_manualCapture = false;

// v60: Recording (F3 toggle) — saves every frame as PNG for ffmpeg.
static bool g_recording = false;
static int g_recordFrame = 0;

// v61: Still mode — один кадр в PNG для быстрой визуальной проверки.
// demo_runtime.exe demo.smt --still 2.0 --out still.png [--repeat 3]
static double g_stillTime = -1.0;
static std::string g_stillOut;
static int g_stillRepeat = 1;

// v61: PNG требует big-endian для длин чанков и CRC (баг v60: писали host-order).
static void putBE32(FILE* f, unsigned int v) {
    unsigned char b[4] = {(unsigned char)(v >> 24), (unsigned char)(v >> 16),
                          (unsigned char)(v >> 8), (unsigned char)v};
    fwrite(b, 1, 4, f);
}

// Minimal PNG writer (no external library, ~50 lines).
static void writePNG(const char* filename, int w, int h, const unsigned char* rgba) {
    FILE* f = fopen(filename, "wb");
    if (!f) return;
    // PNG signature
    static const unsigned char sig[] = {137,80,78,71,13,10,26,10};
    fwrite(sig, 1, 8, f);
    // IHDR chunk
    unsigned char ihdr[13] = {0};
    ihdr[0] = (w >> 24) & 0xFF; ihdr[1] = (w >> 16) & 0xFF;
    ihdr[2] = (w >> 8) & 0xFF; ihdr[3] = w & 0xFF;
    ihdr[4] = (h >> 24) & 0xFF; ihdr[5] = (h >> 16) & 0xFF;
    ihdr[6] = (h >> 8) & 0xFF; ihdr[7] = h & 0xFF;
    ihdr[8] = 8;  // bit depth
    ihdr[9] = 6;  // color type: RGBA
    // CRC and chunk writing
    auto writeChunk = [&](const char* type, const unsigned char* data, int len) {
        unsigned int clen = len;
        putBE32(f, clen);
        fwrite(type, 1, 4, f);
        if (len > 0) fwrite(data, 1, len, f);
        // CRC32
        static unsigned int table[256];
        static bool init = false;
        if (!init) {
            for (unsigned int i = 0; i < 256; i++) {
                unsigned int c = i;
                for (int k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >> 1)) : (c >> 1);
                table[i] = c;
            }
            init = true;
        }
        unsigned int crc = 0xFFFFFFFF;
        for (int i = 0; i < 4 + len; i++) {
            unsigned char b = (i < 4) ? type[i] : data[i - 4];
            crc = table[(crc ^ b) & 0xFF] ^ (crc >> 8);
        }
        crc ^= 0xFFFFFFFF;
        putBE32(f, crc);
    };
    writeChunk("IHDR", ihdr, 13);
    // IDAT: raw pixel data with filter byte per row
    // Use stored (no compression) — zlib header + raw deflate
    int rowBytes = w * 4;
    int rawLen = (rowBytes + 1) * h;  // +1 for filter byte per row
    unsigned char* raw = new unsigned char[rawLen];
    for (int y = 0; y < h; y++) {
        raw[y * (rowBytes + 1)] = 0;  // filter: none
        memcpy(raw + y * (rowBytes + 1) + 1, rgba + (h - 1 - y) * rowBytes, rowBytes);  // flip Y
    }
    // zlib wrapper: 2-byte header + raw deflate (stored blocks) + 4-byte adler32
    int maxBlock = 65535;
    int numBlocks = (rawLen + maxBlock - 1) / maxBlock;
    int zlibLen = 2 + numBlocks * 5 + rawLen + 4;  // header + blocks + adler32
    unsigned char* zlib = new unsigned char[zlibLen];
    int zpos = 0;
    zlib[zpos++] = 0x78; zlib[zpos++] = 0x01;  // zlib header (deflate, no compression)
    int offset = 0;
    while (offset < rawLen) {
        int blockLen = (rawLen - offset < maxBlock) ? (rawLen - offset) : maxBlock;
        bool last = (offset + blockLen >= rawLen);
        zlib[zpos++] = last ? 0x01 : 0x00;  // BFINAL + BTYPE=00 (stored)
        zlib[zpos++] = blockLen & 0xFF; zlib[zpos++] = (blockLen >> 8) & 0xFF;
        int inv = ~blockLen;
        zlib[zpos++] = inv & 0xFF; zlib[zpos++] = (inv >> 8) & 0xFF;
        memcpy(zlib + zpos, raw + offset, blockLen);
        zpos += blockLen;
        offset += blockLen;
    }
    // Adler32
    unsigned int a = 1, b = 0;
    for (int i = 0; i < rawLen; i++) { a = (a + raw[i]) % 65521; b = (b + a) % 65521; }
    unsigned int adler = (b << 16) | a;
    zlib[zpos++] = (adler >> 24) & 0xFF; zlib[zpos++] = (adler >> 16) & 0xFF;
    zlib[zpos++] = (adler >> 8) & 0xFF; zlib[zpos++] = adler & 0xFF;
    writeChunk("IDAT", zlib, zpos);
    writeChunk("IEND", nullptr, 0);
    fclose(f);
    delete[] raw; delete[] zlib;
}

static void captureFramePNG(const char* filename, int w, int h) {
    unsigned char* px = new unsigned char[w * h * 4];
    glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, px);
    writePNG(filename, w, h, px);
    delete[] px;
}

static LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
        case WM_KEYDOWN:
            if (wp == VK_ESCAPE) { g_running = false; PostQuitMessage(0); return 0; }
            if (wp == VK_F1)    { g_showFPS = !g_showFPS; return 0; }   // v53: toggle FPS
            if (wp == VK_F2)    { g_manualCapture = true; return 0; } // v60: capture BMP
            if (wp == VK_F3)    { g_recording = !g_recording;
                                  if (g_recording) { Log("[Record] Started (frames → PNG)"); g_recordFrame = 0; }
                                  else Log("[Record] Stopped (%d frames)", g_recordFrame);
                                  return 0; } // v60: toggle recording
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
    HWND hwnd = CreateWindowEx(exStyle, "DemoRT", "Demo Runtime v60", style,
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

int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR lpCmdLine, int) {
    std::string smtPath = "demo.smt";
    std::string shaderDir = "shaders";

    // v61: разбор аргументов командной строки (путь к .smt + режим одиночного кадра).
    {
        std::string args = lpCmdLine ? lpCmdLine : "";
        std::vector<std::string> argv;
        size_t i = 0;
        while (i < args.size()) {
            while (i < args.size() && args[i] == ' ') ++i;
            size_t j = i;
            while (j < args.size() && args[j] != ' ') ++j;
            if (j > i) argv.push_back(args.substr(i, j - i));
            i = j;
        }
        for (size_t k = 0; k < argv.size(); ++k) {
            const std::string& a = argv[k];
            if (a == "--still" && k + 1 < argv.size()) g_stillTime = atof(argv[++k].c_str());
            else if (a == "--out" && k + 1 < argv.size()) g_stillOut = argv[++k];
            else if (a == "--repeat" && k + 1 < argv.size()) g_stillRepeat = atoi(argv[++k].c_str());
            else if (!a.empty() && a[0] != '-') smtPath = a;
        }
    }

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

    // v61: Still mode — рендерим один кадр и выходим (быстрые проверки цвета/кадра).
    if (g_stillTime >= 0.0) {
        if (g_stillOut.empty()) g_stillOut = "still.png";
        int warm = (g_stillRepeat > 0) ? g_stillRepeat : 1;
        for (int i = 0; i < warm; ++i) glx::renderFrame(show, g_stillTime, shaders, fbos);
        glFinish();
        captureFramePNG(g_stillOut.c_str(), g_width, g_height);
        Log("[Still] Saved %s at T=%.2fs (%dx%d, warmup=%d)",
            g_stillOut.c_str(), g_stillTime, g_width, g_height, warm);
        if (g_hglrc) { wglMakeCurrent(nullptr, nullptr); wglDeleteContext(g_hglrc); }
        if (g_hdc && g_hwnd) ReleaseDC(g_hwnd, g_hdc);
        if (g_hwnd) DestroyWindow(g_hwnd);
        if (hMutex) { ReleaseMutex(hMutex); CloseHandle(hMutex); }
        Log("[Exit] Demo Runtime ended (still mode)");
        return 0;
    }

    double startTime = getTime();
    int frameCount = 0;
    double lastDiag = 0.0;
    double prevT = 0.0;   // для dt (расчёт FPS)
    MSG msg = {};
    Log("[Loop] Entering render loop, duration=%.1fs", show.duration);
    Log("[Help] F1 = toggle FPS | F2 = capture BMP | F3 = toggle recording | min/max/avg tracked always");
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

        // v60: Auto-capture at scene boundaries + 2s.
        if (g_captureIdx < 7 && T >= g_captureTimes[g_captureIdx]) {
            captureFrame(g_captureNames[g_captureIdx], g_width, g_height);
            Log("[Capture] Saved %s (%dx%d → 640x360)", g_captureNames[g_captureIdx], g_width, g_height);
            g_captureIdx++;
        }
        // v60: Manual capture on F2.
        if (g_manualCapture) {
            char fname[64];
            snprintf(fname, sizeof(fname), "shot_manual_T%03d.bmp", (int)T);
            captureFrame(fname, g_width, g_height);
            Log("[Capture] Manual: %s at T=%.2f", fname, T);
            g_manualCapture = false;
        }
        // v60: Recording — save every frame as PNG.
        if (g_recording) {
            char fname[64];
            snprintf(fname, sizeof(fname), "rec_%05d.png", g_recordFrame);
            captureFramePNG(fname, g_width, g_height);
            g_recordFrame++;
        }

        SwapBuffers(g_hdc);

        // v60: Frame limiter — cap at 60 FPS to prevent tearing and waste.
        // vsync in windowed mode on Win11/NVIDIA doesn't always work strictly.
        {
            static double s_lastFrameTime = 0.0;
            double now = getTime();
            double frameElapsed = now - s_lastFrameTime;
            double targetFrameTime = 1.0 / 60.0;  // 16.67 ms
            if (frameElapsed < targetFrameTime) {
                double sleepMs = (targetFrameTime - frameElapsed) * 1000.0;
                if (sleepMs > 1.0) Sleep((DWORD)(sleepMs - 0.5));  // 0.5ms bias for Sleep overhead
            }
            s_lastFrameTime = getTime();
        }

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

            // v60: Per-scene FPS tracking.
            for (int i = 0; i < g_numScenes; i++) {
                if (T >= g_scenes[i].start && T < g_scenes[i].end) {
                    if (g_fpsValue < g_scenes[i].minFps) g_scenes[i].minFps = g_fpsValue;
                    if (g_fpsValue > g_scenes[i].maxFps) g_scenes[i].maxFps = g_fpsValue;
                    g_scenes[i].sumFps += g_fpsValue;
                    g_scenes[i].samples++;
                    break;
                }
            }

            // Adaptive quality with hysteresis: switch to LOW when FPS < 28,
            // back to HIGH when FPS > 35. Prevents oscillation.
            if (g_fpsValue > 0) {
                static bool s_lastQuality = true;
                if (glx::g_qualityHigh && g_fpsValue < 28.0) {
                    glx::g_qualityHigh = false;
                    Log("[Quality] LOW (steps=24, FPS=%.1f)", g_fpsValue);
                } else if (!glx::g_qualityHigh && g_fpsValue > 45.0) {
                    glx::g_qualityHigh = true;
                    Log("[Quality] HIGH (steps=40, FPS=%.1f)", g_fpsValue);
                }
            }

            // v53: заголовок только когда F1 on.
            if (g_showFPS) {
                double avgSoFar = g_fpsSum / g_fpsSamples;
                snprintf(g_titleBuf, sizeof(g_titleBuf),
                    "Demo Runtime v60  |  %.1f FPS (min=%.1f max=%.1f avg=%.1f)  |  T=%.2fs  |  frames=%d  |  F1 toggle",
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
                    SetWindowTextA(g_hwnd, "Demo Runtime v60  -  ESC quit, F1 toggle FPS");
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
            Log("  quality:     %s (nebula steps=%d)", glx::g_qualityHigh ? "HIGH" : "LOW", glx::g_qualityHigh ? 40 : 24);
            // v60: Per-scene FPS breakdown.
            Log("  per-scene:");
            for (int i = 0; i < g_numScenes; i++) {
                if (g_scenes[i].samples > 0) {
                    double avg = g_scenes[i].sumFps / g_scenes[i].samples;
                    double dur = g_scenes[i].end - g_scenes[i].start;
                    Log("    %-20s T=%5.0f-%5.0fs (%4.0fs)  min=%5.1f  max=%5.1f  avg=%5.1f  FPS  (%d samples)",
                        g_scenes[i].name, g_scenes[i].start, g_scenes[i].end, dur,
                        g_scenes[i].minFps, g_scenes[i].maxFps, avg, g_scenes[i].samples);
                }
            }
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
