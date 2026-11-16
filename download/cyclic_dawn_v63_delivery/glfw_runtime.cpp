// path: cyclic_dawn_v63/glfw_runtime.cpp
// Cross-platform runtime (Linux test build + Windows build via GLFW).
// Reuses sm_runtime.hpp + gl_executor.hpp unchanged.
//
// Linux build:
//   g++ -std=c++17 -O2 glfw_runtime.cpp -I<glfw_inc> -I<gl_inc> \
//       -L<glfw_lib> -lglfw -lGL -ldl -lpthread -o demo_v63_glfw
//
// Windows build (MinGW or MSVC with GLFW installed):
//   cl /std:c++17 /EHsc /O2 glfw_runtime.cpp /I<glfw_inc> \
//       /link glfw3.lib opengl32.lib user32.lib gdi32.lib shell32.lib

#include <cstdio>
#include <cstdarg>
#include <cmath>
#include <cstring>
#include <string>
#include <vector>

#ifdef _WIN32
  #define WIN32_LEAN_AND_MEAN
  #include <windows.h>
  #include "opengl_loader.h"   // Windows: wglGetProcAddress loader
#else
  #include "opengl_loader_linux.h"  // Linux: GL_GLEXT_PROTOTYPES
#endif

#define GLFW_INCLUDE_NONE
#include <GLFW/glfw3.h>

#include "sm_runtime.hpp"
#include "gl_executor.hpp"

static GLFWwindow* g_win = nullptr;
static int g_width = 1280, g_height = 720;
static bool g_showFPS = false;
static bool g_manualCapture = false;
static bool g_recording = false;
static int  g_recordFrame = 0;

// v63 capture times (matches g_captureTimes in demo_runtime_v63.cpp).
static double g_captureTimes[] = {3.0, 18.0, 22.0, 38.0};
static const char* g_captureNames[] = {
    "shot_dawn.bmp",
    "shot_spire.bmp",
    "shot_transition_bloom.bmp",
    "shot_fall.bmp",
};
static int g_captureIdx = 0;

// FPS stats.
static double g_fpsMin = 0, g_fpsMax = 0, g_fpsSum = 0;
static int    g_fpsSamples = 0, g_fpsFrames = 0;
static double g_fpsAccum = 0, g_fpsValue = 0;

static void logPrintf(const char* fmt, ...) {
    char buf[1024]; va_list args; va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args); va_end(args);
    printf("%s\n", buf);
    static FILE* f = nullptr;
    if (!f) { f = fopen("trace.log", "a"); if (f) setvbuf(f, nullptr, _IONBF, 0); }
    if (f) fprintf(f, "%s\n", buf);
}
#define Log logPrintf

// Per-scene FPS tracking — v63 timeline.
struct SceneStat { const char* name; double start, end; double minFps, maxFps, sumFps; int samples; };
static SceneStat g_scenes[] = {
    {"dawn",            0.0,  12.0,  999, 0, 0, 0},
    {"transition_1",   12.0,  16.5,  999, 0, 0, 0},
    {"spire",          16.5,  28.5,  999, 0, 0, 0},
    {"transition_2",   28.5,  33.0,  999, 0, 0, 0},
    {"fall",           33.0,  45.0,  999, 0, 0, 0},
};
static const int g_numScenes = (int)(sizeof(g_scenes) / sizeof(g_scenes[0]));

static double getTime() {
    return glfwGetTime();
}

// Write BMP (24-bit) at half resolution — same format as v61.2 captureFrame.
static void captureFrame(const char* filename, int w, int h) {
    unsigned char* px = new unsigned char[w * h * 4];
    glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, px);
    int sw = w / 2, sh = h / 2;
    unsigned char* small = new unsigned char[sw * sh * 3];
    for (int y = 0; y < sh; y++) {
        for (int x = 0; x < sw; x++) {
            int r = 0, g = 0, b = 0;
            for (int dy = 0; dy < 2; dy++) {
                for (int dx = 0; dx < 2; dx++) {
                    int idx = ((y * 2 + dy) * w + (x * 2 + dx)) * 4;
                    r += px[idx]; g += px[idx + 1]; b += px[idx + 2];
                }
            }
            int si = (y * sw + x) * 3;
            small[si] = b / 4; small[si + 1] = g / 4; small[si + 2] = r / 4;  // BGR for BMP
        }
    }
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
    int z6 = 0; fwrite(&z6, 4, 1, f);  // compression
    fwrite(&dataSize, 4, 1, f);
    int ppm = 2835; fwrite(&ppm, 4, 1, f); fwrite(&ppm, 4, 1, f);
    fwrite(&z, 4, 1, f); fwrite(&z, 4, 1, f);
    for (int y = sh - 1; y >= 0; y--) {
        fwrite(small + y * sw * 3, 1, sw * 3, f);
        int pad = rowSize - sw * 3;
        for (int i = 0; i < pad; i++) fputc(0, f);
    }
    fclose(f);
    delete[] px; delete[] small;
}

static void keyCallback(GLFWwindow* win, int key, int /*scancode*/, int action, int /*mods*/) {
    if (action != GLFW_PRESS) return;
    if (key == GLFW_KEY_ESCAPE) { glfwSetWindowShouldClose(win, GLFW_TRUE); }
    else if (key == GLFW_KEY_F1) { g_showFPS = !g_showFPS; }
    else if (key == GLFW_KEY_F2) { g_manualCapture = true; }
    else if (key == GLFW_KEY_F3) {
        g_recording = !g_recording;
        if (g_recording) { Log("[Record] Started (frames -> BMP)"); g_recordFrame = 0; }
        else Log("[Record] Stopped (%d frames)", g_recordFrame);
    }
}

int main(int argc, char** argv) {
    std::string smtPath = "demo_v63.smt";
    std::string shaderDir = "shaders";
    double stillTime = -1.0;
    std::string stillOut;
    int stillRepeat = 0;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--still" && i + 1 < argc) stillTime = atof(argv[++i]);
        else if (a == "--out" && i + 1 < argc) stillOut = argv[++i];
        else if (a == "--repeat" && i + 1 < argc) stillRepeat = atoi(argv[++i]);
        else if (!a.empty() && a[0] != '-') smtPath = a;
    }

    Log("[Start] Demo Runtime v63 (GLFW) — loading %s", smtPath.c_str());
    sm::Show show;
    try {
        show = sm::load(smtPath);
    } catch (const std::exception& e) {
        Log("[Error] Failed to load %s: %s", smtPath.c_str(), e.what());
        return 1;
    }
    Log("[OK] SMT loaded: duration=%.1fs, %d clips, %d segments",
        show.duration, (int)show.clips.size(), (int)show.segs.size());

    for (const auto& c : show.clips) {
        Log("  clip '%s' effect='%s' opacity_tokens=%d progress_tokens=%d uniforms=%d",
            c.id.c_str(), c.effect.c_str(),
            (int)c.opacity.size(), (int)c.progress.size(), (int)c.uniforms.size());
    }

    if (!glfwInit()) { Log("[Error] glfwInit failed"); return 2; }
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
    glfwWindowHint(GLFW_OPENGL_FORWARD_COMPAT, GLFW_TRUE);
    glfwWindowHint(GLFW_RESIZABLE, GLFW_FALSE);
    g_width = show.w; g_height = show.h;
    g_win = glfwCreateWindow(g_width, g_height, "Demo Runtime v63 (GLFW)", nullptr, nullptr);
    if (!g_win) { Log("[Error] glfwCreateWindow failed"); glfwTerminate(); return 3; }
    glfwMakeContextCurrent(g_win);
    glfwSwapInterval(1);
    glfwSetKeyCallback(g_win, keyCallback);

    if (!LoadOpenGLFunctions()) {
        Log("[Error] GL functions not loaded");
        glfwDestroyWindow(g_win); glfwTerminate();
        return 4;
    }

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

    // Still mode: render one frame and exit.
    if (stillTime >= 0.0) {
        if (stillOut.empty()) stillOut = "still.png";
        int warm = (stillRepeat > 0) ? stillRepeat : 1;
        for (int i = 0; i < warm; ++i) glx::renderFrame(show, stillTime, shaders, fbos);
        glFinish();
        // Save as BMP (PNG writer omitted for portability — convert externally).
        captureFrame(stillOut.c_str(), g_width, g_height);
        Log("[Still] Saved %s at T=%.2fs (warmup=%d)", stillOut.c_str(), stillTime, warm);
        glfwDestroyWindow(g_win); glfwTerminate();
        return 0;
    }

    double startTime = getTime();
    int frameCount = 0;
    double lastDiag = 0.0, prevT = 0.0;
    Log("[Loop] Entering render loop, duration=%.1fs", show.duration);
    Log("[Help] F1=FPS | F2=capture BMP | F3=record | ESC=quit");

    while (!glfwWindowShouldClose(g_win)) {
        double T = getTime() - startTime;
        if (T >= show.duration) { Log("[Done] T=%.2fs frames=%d", T, frameCount); break; }

        try { glx::renderFrame(show, T, shaders, fbos); }
        catch (const std::exception& e) {
            Log("[Error] renderFrame exception at T=%.3f: %s", T, e.what());
            break;
        }

        if (g_captureIdx < 4 && T >= g_captureTimes[g_captureIdx]) {
            captureFrame(g_captureNames[g_captureIdx], g_width, g_height);
            Log("[Capture] Saved %s (%dx%d -> %dx%d)",
                g_captureNames[g_captureIdx], g_width, g_height, g_width/2, g_height/2);
            g_captureIdx++;
        }
        if (g_manualCapture) {
            char fname[64];
            snprintf(fname, sizeof(fname), "shot_manual_T%03d.bmp", (int)T);
            captureFrame(fname, g_width, g_height);
            Log("[Capture] Manual: %s at T=%.2f", fname, T);
            g_manualCapture = false;
        }
        if (g_recording) {
            char fname[64];
            snprintf(fname, sizeof(fname), "rec_%05d.bmp", g_recordFrame);
            captureFrame(fname, g_width, g_height);
            g_recordFrame++;
        }

        glfwSwapBuffers(g_win);
        glfwPollEvents();

        frameCount++;

        // FPS sampling every 0.5s.
        double dt = T - prevT; prevT = T;
        g_fpsFrames++; g_fpsAccum += dt;
        if (g_fpsAccum >= 0.5) {
            g_fpsValue = (double)g_fpsFrames / g_fpsAccum;
            g_fpsFrames = 0; g_fpsAccum = 0.0;
            if (g_fpsSamples == 0) { g_fpsMin = g_fpsValue; g_fpsMax = g_fpsValue; }
            else { if (g_fpsValue < g_fpsMin) g_fpsMin = g_fpsValue;
                   if (g_fpsValue > g_fpsMax) g_fpsMax = g_fpsValue; }
            g_fpsSum += g_fpsValue; g_fpsSamples++;

            for (int i = 0; i < g_numScenes; ++i) {
                if (T >= g_scenes[i].start && T < g_scenes[i].end) {
                    if (g_fpsValue < g_scenes[i].minFps) g_scenes[i].minFps = g_fpsValue;
                    if (g_fpsValue > g_scenes[i].maxFps) g_scenes[i].maxFps = g_fpsValue;
                    g_scenes[i].sumFps += g_fpsValue; g_scenes[i].samples++;
                    break;
                }
            }

            // Adaptive quality (nebula-style steps — not used in v63 but kept for parity).
            if (g_fpsValue > 0) {
                if (glx::g_qualityHigh && g_fpsValue < 28.0) {
                    glx::g_qualityHigh = false;
                    Log("[Quality] LOW (FPS=%.1f)", g_fpsValue);
                } else if (!glx::g_qualityHigh && g_fpsValue > 45.0) {
                    glx::g_qualityHigh = true;
                    Log("[Quality] HIGH (FPS=%.1f)", g_fpsValue);
                }
            }

            if (g_showFPS) {
                char title[200];
                snprintf(title, sizeof(title),
                    "Demo v63  %.1f FPS (min=%.1f max=%.1f avg=%.1f)  T=%.2fs  frames=%d",
                    g_fpsValue, g_fpsMin, g_fpsMax, g_fpsSum / g_fpsSamples, T, frameCount);
                glfwSetWindowTitle(g_win, title);
            }
        }

        if (frameCount == 1) { Log("[Loop] First frame T=%.3fs", T); lastDiag = T; }
        else if (T - lastDiag >= 5.0) { Log("[Loop] T=%.2fs frames=%d", T, frameCount); lastDiag = T; }
    }
    Log("[Loop] Exited, total frames=%d", frameCount);

    if (g_fpsSamples > 0) {
        double avgFPS = g_fpsSum / g_fpsSamples;
        double finalT = getTime() - startTime;
        Log("[Stats] FPS over %.2fs (%d samples):", finalT, g_fpsSamples);
        Log("  sampled:     min=%.2f  max=%.2f  avg=%.2f", g_fpsMin, g_fpsMax, avgFPS);
        Log("  theoretical: %d frames / %.2fs = %.2f FPS", frameCount, finalT,
            (finalT > 0) ? frameCount / finalT : 0.0);
        Log("  per-scene:");
        for (int i = 0; i < g_numScenes; ++i) {
            if (g_scenes[i].samples > 0) {
                double avg = g_scenes[i].sumFps / g_scenes[i].samples;
                Log("    %-18s T=%5.1f-%5.1fs (%4.1fs)  min=%5.1f max=%5.1f avg=%5.1f FPS (%d samples)",
                    g_scenes[i].name, g_scenes[i].start, g_scenes[i].end,
                    g_scenes[i].end - g_scenes[i].start,
                    g_scenes[i].minFps, g_scenes[i].maxFps, avg, g_scenes[i].samples);
            }
        }
    }

    glfwDestroyWindow(g_win);
    glfwTerminate();
    Log("[Exit] Demo Runtime v63 ended");
    return 0;
}
