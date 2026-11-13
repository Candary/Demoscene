// gl_executor.hpp — GL binding layer для Scene Manager runtime.
// Берёт sm::Show + время T → находит segment → выполняет ops (CLEAR/RENDER/
// DRAW/COMPOSITE/TRANSITION/POST/PRESENT) через OpenGL 3.3.
//
// Зависимости: sm_runtime.hpp (header-only), OpenGL 3.3 core (через opengl_loader.h).
// Не зависит от внешних библиотек.
#pragma once

#include "sm_runtime.hpp"
#include <map>
#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <cstring>

// OpenGL types — предполагается что opengl_loader.h уже загружен.
// Если нет — раскомментируй нужные include.
// #include "opengl_loader.h"
// Или для теста без GL: можно stub'нуть.

namespace glx {

// Adaptive quality: set by demo_runtime.cpp based on FPS.
// HIGH: full raymarch steps (40). LOW: reduced steps (24) for stable 30+ FPS.
inline bool g_qualityHigh = true;

// ============================================================================
// FBO Pool — manage framebuffer objects by name ("screen", "fbo0", "fbo1", ...)
// ============================================================================
struct FBO {
    GLuint fbo = 0;
    GLuint tex = 0;
    int w = 0, h = 0;
};

class FBOPool {
    std::map<std::string, FBO> pool_;
    int w_, h_;
public:
    void init(int w, int h) { w_ = w; h_ = h; }

    FBO& get(const std::string& name) {
        auto it = pool_.find(name);
        if (it != pool_.end()) return it->second;

        FBO fbo;
        if (name == "screen") {
            // screen = default framebuffer, no texture.
            fbo.fbo = 0; fbo.tex = 0; fbo.w = w_; fbo.h = h_;
        } else {
            // Create FBO + texture.
            glGenFramebuffers(1, &fbo.fbo);
            glGenTextures(1, &fbo.tex);
            glBindTexture(GL_TEXTURE_2D, fbo.tex);
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA16F, w_, h_, 0, GL_RGBA, GL_FLOAT, nullptr);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
            glBindFramebuffer(GL_FRAMEBUFFER, fbo.fbo);
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, fbo.tex, 0);
            glBindFramebuffer(GL_FRAMEBUFFER, 0);
            fbo.w = w_; fbo.h = h_;
        }
        return pool_[name] = fbo;
    }

    void bind(const std::string& name) {
        FBO& f = get(name);
        glBindFramebuffer(GL_FRAMEBUFFER, f.fbo);
        glViewport(0, 0, f.w, f.h);
    }

    void bindTexture(const std::string& name, int unit) {
        FBO& f = get(name);
        glActiveTexture(GL_TEXTURE0 + unit);
        glBindTexture(GL_TEXTURE_2D, f.tex);
    }

    void clear(const std::string& name) {
        bind(name);
        glClearColor(0, 0, 0, 0);
        glClear(GL_COLOR_BUFFER_BIT);
    }
};

// ============================================================================
// Shader Cache — compile .frag files by effect name, cache GL programs.
// ============================================================================
class ShaderCache {
    std::string shaderDir_;
    std::map<std::string, GLuint> programs_;
    std::map<std::string, long long> fileTimes_;  // v60: hot-reload — last modification time
    GLuint vao_ = 0;
    GLuint vs_ = 0;  // shared vertex shader

    static const char* kVertSrc;

    // v60: Get file modification time (Windows FILETIME as long long).
    long long getFileTime(const std::string& path) {
        WIN32_FIND_DATAA fd;
        HANDLE h = FindFirstFileA(path.c_str(), &fd);
        if (h == INVALID_HANDLE_VALUE) return 0;
        long long t = ((long long)fd.ftLastWriteTime.dwHighDateTime << 32) | fd.ftLastWriteTime.dwLowDateTime;
        FindClose(h);
        return t;
    }

    GLuint compileShader(GLenum type, const char* src) {
        GLuint sh = glCreateShader(type);
        glShaderSource(sh, 1, &src, nullptr);
        glCompileShader(sh);
        GLint ok; glGetShaderiv(sh, GL_COMPILE_STATUS, &ok);
        if (!ok) {
            char log[2048]; glGetShaderInfoLog(sh, sizeof(log), nullptr, log);
            fprintf(stderr, "[GL executor] Shader compile error: %s\n", log);
            glDeleteShader(sh);
            return 0;
        }
        return sh;
    }

public:
    void init(const std::string& dir) {
        shaderDir_ = dir;
        // VAO for core profile (required for glDrawArrays without VBO).
        glGenVertexArrays(1, &vao_);
        // Shared vertex shader (fullscreen quad via gl_VertexID).
        vs_ = compileShader(GL_VERTEX_SHADER, kVertSrc);
    }

    // v60: Reload a single shader from disk (hot-reload).
    bool reloadProgram(const std::string& effectId) {
        std::string path = shaderDir_ + "/" + effectId + ".frag";
        std::ifstream f(path);
        if (!f) return false;
        std::stringstream ss; ss << f.rdbuf();
        std::string fragSrc = ss.str();

        GLuint fs = compileShader(GL_FRAGMENT_SHADER, fragSrc.c_str());
        if (!fs) return false;

        GLuint prog = glCreateProgram();
        glAttachShader(prog, vs_);
        glAttachShader(prog, fs);
        glLinkProgram(prog);
        glDeleteShader(fs);
        GLint ok; glGetProgramiv(prog, GL_LINK_STATUS, &ok);
        if (!ok) {
            char log[2048]; glGetProgramInfoLog(prog, sizeof(log), nullptr, log);
            fprintf(stderr, "[GL executor] Hot-reload link error for %s: %s\n", effectId.c_str(), log);
            glDeleteProgram(prog);
            return false;
        }
        // Replace old program.
        auto it = programs_.find(effectId);
        if (it != programs_.end() && it->second) glDeleteProgram(it->second);
        programs_[effectId] = prog;
        fileTimes_[effectId] = getFileTime(path);
        return true;
    }

    // v60: Check all shaders for file changes, reload if modified.
    int checkReload() {
        int reloaded = 0;
        for (auto& kv : programs_) {
            std::string path = shaderDir_ + "/" + kv.first + ".frag";
            long long t = getFileTime(path);
            long long prev = fileTimes_[kv.first];
            if (prev > 0 && t > prev) {
                if (reloadProgram(kv.first)) {
                    reloaded++;
                }
            }
        }
        return reloaded;
    }

    GLuint getProgram(const std::string& effectId) {
        auto it = programs_.find(effectId);
        if (it != programs_.end()) return it->second;

        // Load .frag from disk.
        std::string path = shaderDir_ + "/" + effectId + ".frag";
        std::ifstream f(path);
        if (!f) {
            fprintf(stderr, "[GL executor] Cannot open shader: %s\n", path.c_str());
            return 0;
        }
        std::stringstream ss; ss << f.rdbuf();
        std::string fragSrc = ss.str();

        GLuint fs = compileShader(GL_FRAGMENT_SHADER, fragSrc.c_str());
        if (!fs) return 0;

        GLuint prog = glCreateProgram();
        glAttachShader(prog, vs_);
        glAttachShader(prog, fs);
        glLinkProgram(prog);
        glDeleteShader(fs);
        GLint ok; glGetProgramiv(prog, GL_LINK_STATUS, &ok);
        if (!ok) {
            char log[2048]; glGetProgramInfoLog(prog, sizeof(log), nullptr, log);
            fprintf(stderr, "[GL executor] Link error for %s: %s\n", effectId.c_str(), log);
            glDeleteProgram(prog);
            return 0;
        }
        return programs_[effectId] = prog;
    }

    void bindVAO() { glBindVertexArray(vao_); }
    void drawQuad() { glDrawArrays(GL_TRIANGLE_STRIP, 0, 4); }
};

const char* ShaderCache::kVertSrc = R"GLSL(
#version 330 core
void main() {
    vec2 p[4] = vec2[4](
        vec2(-1.0, -1.0), vec2(1.0, -1.0),
        vec2(-1.0, 1.0), vec2(1.0, 1.0)
    );
    gl_Position = vec4(p[gl_VertexID], 0.0, 1.0);
}
)GLSL";

// ============================================================================
// Uniform Setter — evaluate RPN programs, set GL uniforms.
// ============================================================================
// safeRun: не падает на пустой программе, возвращает 0.
static inline double safeRun(const sm::Program& p, const double* vars) {
    if (p.empty()) return 0.0;
    try { return sm::run(p, vars); }
    catch (const std::exception& e) {
        fprintf(stderr, "[GL executor] run() error: %s\n", e.what());
        return 0.0;
    }
}

void setUniforms(const sm::Show& show, const sm::Clip& clip, double T, GLuint prog) {
    // Standard uniforms (set by runtime, not in .smt uni records).
    double vars[sm::V_COUNT];
    show.audio_vars(T, vars);
    vars[sm::V_t] = T - clip.nom_start;
    vars[sm::V_dur] = clip.nom_dur;
    vars[sm::V_p] = clip.nom_dur > 0 ? vars[sm::V_t] / clip.nom_dur : 0.0;
    vars[sm::V_time] = T;

    // Standard uniforms.
    GLint loc;
    loc = glGetUniformLocation(prog, "uTime");
    if (loc >= 0) glUniform1f(loc, (float)(T - clip.eff_start));
    loc = glGetUniformLocation(prog, "uClipTime");
    if (loc >= 0) glUniform1f(loc, (float)vars[sm::V_t]);
    loc = glGetUniformLocation(prog, "uProgress");
    if (loc >= 0) glUniform1f(loc, (float)safeRun(clip.progress, vars));
    loc = glGetUniformLocation(prog, "uGlobalTime");
    if (loc >= 0) glUniform1f(loc, (float)T);
    loc = glGetUniformLocation(prog, "uResolution");
    if (loc >= 0) glUniform2f(loc, (float)show.w, (float)show.h);
    loc = glGetUniformLocation(prog, "uSeed");
    if (loc >= 0) glUniform1i(loc, (int)clip.seed);
    loc = glGetUniformLocation(prog, "uBeat");
    if (loc >= 0) glUniform1f(loc, (float)vars[sm::V_beat]);
    loc = glGetUniformLocation(prog, "uBeatPhase");
    if (loc >= 0) glUniform1f(loc, (float)vars[sm::V_beat_phase]);
    loc = glGetUniformLocation(prog, "uBarPhase");
    if (loc >= 0) glUniform1f(loc, (float)vars[sm::V_bar_phase]);
    loc = glGetUniformLocation(prog, "uEnergy");
    if (loc >= 0) glUniform1f(loc, (float)vars[sm::V_energy]);

    // Adaptive quality: uVolumeSteps for nebula raymarch.
    loc = glGetUniformLocation(prog, "uVolumeSteps");
    if (loc >= 0) glUniform1i(loc, g_qualityHigh ? 40 : 24);

    // Clip opacity.
    float opacity = (float)safeRun(clip.opacity, vars);

    // Effect uniforms from .smt uni records.
    for (const auto& u : clip.uniforms) {
        loc = glGetUniformLocation(prog, u.name.c_str());
        if (loc < 0) continue;

        if (u.type == "float") {
            glUniform1f(loc, (float)safeRun(u.comps[0], vars));
        } else if (u.type == "int") {
            glUniform1i(loc, (int)(safeRun(u.comps[0], vars) + 0.5));
        } else if (u.type == "bool") {
            glUniform1i(loc, safeRun(u.comps[0], vars) != 0.0 ? 1 : 0);
        } else if (u.type == "vec2") {
            glUniform2f(loc, (float)safeRun(u.comps[0], vars), (float)safeRun(u.comps[1], vars));
        } else if (u.type == "vec3") {
            glUniform3f(loc, (float)safeRun(u.comps[0], vars),
                               (float)safeRun(u.comps[1], vars),
                               (float)safeRun(u.comps[2], vars));
        } else if (u.type == "vec4") {
            glUniform4f(loc, (float)safeRun(u.comps[0], vars),
                               (float)safeRun(u.comps[1], vars),
                               (float)safeRun(u.comps[2], vars),
                               (float)safeRun(u.comps[3], vars));
        }
    }

    // Arrays (farray).
    for (const auto& ar : clip.arrays) {
        loc = glGetUniformLocation(prog, ar.first.c_str());
        if (loc >= 0) {
            std::vector<float> vals(ar.second.size());
            for (size_t i = 0; i < ar.second.size(); i++) vals[i] = (float)ar.second[i];
            glUniform1fv(loc, (GLsizei)vals.size(), vals.data());
        }
        // Also set <name>Count if present.
        std::string cntName = ar.first + "Count";
        loc = glGetUniformLocation(prog, cntName.c_str());
        if (loc >= 0) glUniform1i(loc, (int)ar.second.size());
    }
}

// ============================================================================
// Blend mode helper.
// ============================================================================
void setBlendMode(const std::string& blend, float opacity) {
    if (blend == "normal") {
        glEnable(GL_BLEND);
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    } else if (blend == "add") {
        glEnable(GL_BLEND);
        glBlendFunc(GL_ONE, GL_ONE);
    } else if (blend == "screen") {
        glEnable(GL_BLEND);
        glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_COLOR);
    } else if (blend == "multiply") {
        glEnable(GL_BLEND);
        glBlendFunc(GL_DST_COLOR, GL_ZERO);
    } else {
        glDisable(GL_BLEND);
    }
}

// ============================================================================
// Pass Executor — execute one Op from the render plan.
// ============================================================================
static int g_opCount = 0;  // debug counter

void executeOp(const sm::Show& show, const sm::Op& op, double T,
               ShaderCache& shaders, FBOPool& fbos) {
    g_opCount++;

    // Find clip referenced by op (if any).
    const sm::Clip* clip = nullptr;
    if (op.clip != "-") {
        for (const auto& c : show.clips) {
            if (c.id == op.clip) { clip = &c; break; }
        }
        if (!clip) {
            fprintf(stderr, "[GL executor] op %d: clip '%s' not found!\n", g_opCount, op.clip.c_str());
            return;
        }
    }

    // Check for GL errors from previous op.
    GLenum prevErr = glGetError();
    if (prevErr != GL_NO_ERROR) {
        fprintf(stderr, "[GL executor] op %d: GL error before '%s %s': 0x%x\n",
                g_opCount, op.op.c_str(), op.clip.c_str(), prevErr);
    }

    if (op.op == "CLEAR") {
        fbos.clear(op.write);
    }
    else if (op.op == "RENDER") {
        // Render clip's effect to write target (replace).
        if (!clip) return;
        GLuint prog = shaders.getProgram(clip->effect);
        if (!prog) return;
        fbos.bind(op.write);
        glUseProgram(prog);
        setUniforms(show, *clip, T, prog);
        glDisable(GL_BLEND);
        shaders.bindVAO();
        shaders.drawQuad();
    }
    else if (op.op == "DRAW") {
        // Draw clip's effect directly to dest with blend mode.
        if (!clip) return;
        GLuint prog = shaders.getProgram(clip->effect);
        if (!prog) return;
        fbos.bind(op.dest);
        glUseProgram(prog);
        double vars[sm::V_COUNT];
        show.audio_vars(T, vars);
        vars[sm::V_t] = T - clip->nom_start;
        vars[sm::V_dur] = clip->nom_dur;
        vars[sm::V_p] = clip->nom_dur > 0 ? vars[sm::V_t] / clip->nom_dur : 0.0;
        vars[sm::V_time] = T;
        setUniforms(show, *clip, T, prog);
        float opacity = (float)safeRun(clip->opacity, vars);
        setBlendMode(op.blend, opacity);
        shaders.bindVAO();
        shaders.drawQuad();
        glDisable(GL_BLEND);
    }
    else if (op.op == "COMPOSITE") {
        // Composite texture from reads[0] onto dest with blend.
        if (!clip) return;
        GLuint prog = shaders.getProgram(clip->effect);
        if (!prog) return;
        fbos.bind(op.dest);
        glUseProgram(prog);
        setUniforms(show, *clip, T, prog);
        // Bind input texture.
        fbos.bindTexture(op.reads, 0);
        GLint loc = glGetUniformLocation(prog, "uInput");
        if (loc >= 0) glUniform1i(loc, 0);
        setBlendMode(op.blend, 1.0f);
        shaders.bindVAO();
        shaders.drawQuad();
        glDisable(GL_BLEND);
    }
    else if (op.op == "TRANSITION") {
        // Transition: reads 2 textures (A, B), writes to write target.
        if (!clip) return;
        GLuint prog = shaders.getProgram(clip->effect);
        if (!prog) return;
        // Parse reads: "fbo0,fbo1"
        std::string readA, readB;
        size_t comma = op.reads.find(',');
        if (comma != std::string::npos) {
            readA = op.reads.substr(0, comma);
            readB = op.reads.substr(comma + 1);
        }
        fbos.bind(op.write);
        glUseProgram(prog);
        setUniforms(show, *clip, T, prog);
        fbos.bindTexture(readA, 0);
        fbos.bindTexture(readB, 1);
        GLint locA = glGetUniformLocation(prog, "uA");
        GLint locB = glGetUniformLocation(prog, "uB");
        if (locA >= 0) glUniform1i(locA, 0);
        if (locB >= 0) glUniform1i(locB, 1);
        glDisable(GL_BLEND);
        shaders.bindVAO();
        shaders.drawQuad();
    }
    else if (op.op == "POST") {
        // Post: reads 1 texture, writes to write target.
        if (!clip) return;
        GLuint prog = shaders.getProgram(clip->effect);
        if (!prog) return;
        fbos.bind(op.write);
        glUseProgram(prog);
        setUniforms(show, *clip, T, prog);
        fbos.bindTexture(op.reads, 0);
        GLint loc = glGetUniformLocation(prog, "uInput");
        if (loc >= 0) glUniform1i(loc, 0);
        glDisable(GL_BLEND);
        shaders.bindVAO();
        shaders.drawQuad();
    }
    else if (op.op == "PRESENT") {
        // Present: blit screen to window (already on screen, just swap).
        // In Win32, SwapBuffers is called by the caller.
        // Here we just ensure screen FBO is bound.
        fbos.bind("screen");
    }
}

// ============================================================================
// Render Frame — main entry point. Renders one frame at time T.
// ============================================================================
void renderFrame(const sm::Show& show, double T, ShaderCache& shaders, FBOPool& fbos) {
    // Check if show is finished.
    if (T >= show.duration) return;
    for (const auto& c : show.clips) {
        if (c.kind == "event" && c.effect == "finish" && T >= c.eff_start) return;
    }

    // Find current segment.
    const sm::Segment* seg = show.segment_at(T);
    if (!seg) return;

    // Execute all ops in segment.
    for (const auto& op : seg->ops) {
        executeOp(show, op, T, shaders, fbos);
    }
}

} // namespace glx
