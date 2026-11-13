// ============================================================================
// flash.frag
// ----------------------------------------------------------------------------
// Эффект: переход "вспышка на стыке" — A -> bright flash -> B.
//
// Контракт (из BUILTIN effects в effects.py):
//   kind: transition (2 входа: uA, uB)
//   uColor vec3   — color of flash, default [1, 1, 1] (white)
//   uPeak  float  — peak intensity 0..2, default 1.0
//
// Стандартные uniforms для transition:
//   uProgress (0..1) — прогресс перехода (уже с применённой кривой smoothstep/ease)
//   uA, uB (sampler2D) — входные текстуры (сцены A и B)
//   uResolution, uTime, uSeed, uBeat, uBeatPhase, uBarPhase, uEnergy
//
// Поведение:
//   progress = 0.0  → показывается только A
//   progress = 0.5  → пик вспышки (uColor * uPeak)
//   progress = 1.0  → показывается только B
//
// Формула:
//   mixA = 1 - smoothstep(0.0, 0.5, progress)   // A fade-out в первой половине
//   mixB = smoothstep(0.5, 1.0, progress)       // B fade-in во второй половине
//   flash = uPeak * pow(sin(progress * PI), 4)  // пик в центре, плавно по краям
//   col = mixA * texA + mixB * texB + flash * uColor
//
// Совместимость: OpenGL 3.3 core, GLSL 330. Total-semantic (нет NaN-операций).
// ============================================================================

#version 330 core

// --- Стандартные uniforms ---------------------------------------------------
uniform float uTime;
uniform float uClipTime;
uniform float uProgress;       // 0..1 — прогресс перехода (ключевой uniform для transition)
uniform float uGlobalTime;
uniform vec2  uResolution;
uniform int   uSeed;
uniform float uBeat;
uniform float uBeatPhase;
uniform float uBarPhase;
uniform float uEnergy;

// --- Effect uniforms (из manifest) ------------------------------------------
uniform vec3  uColor;          // flash color (default white)
uniform float uPeak;           // 0..2 — peak intensity

// --- Входные текстуры (контракт transition: 2 входа) ------------------------
uniform sampler2D uA;          // сцена A
uniform sampler2D uB;          // сцена B

// --- Выход ------------------------------------------------------------------
out vec4 FragColor;

// ============================================================================
// Main — точка входа
// ============================================================================
void main() {
    // UV в [0, 1] для текстурных lookups.
    vec2 uv = gl_FragCoord.xy / uResolution;

    // --- Сэмплы входных сцен ------------------------------------------------
    vec4 a = texture(uA, uv);
    vec4 b = texture(uB, uv);

    // --- Прогресс перехода --------------------------------------------------
    float p = uProgress;

    // --- Mix coefficients: A fade-out, B fade-in ----------------------------
    // A виден в [0, 0.5], плавно исчезает к 0.5.
    float mixA = 1.0 - smoothstep(0.0, 0.5, p);
    // B появляется с 0.5, полностью виден к 1.0.
    float mixB = smoothstep(0.5, 1.0, p);

    // --- Flash intensity — пик в центре (progress = 0.5) -------------------
    // sin(progress * PI) даёт 0 в начале и конце, 1 в середине.
    // pow(..., 4) делает пик острым.
    float flashIntensity = uPeak * pow(max(0.0, sin(p * 3.14159265359)), 4.0);

    // --- Финальный цвет: weighted mix + flash additive --------------------
    vec3 col = a.rgb * mixA + b.rgb * mixB + uColor * flashIntensity;

    // Alpha — максимум из mixA, mixB, flashIntensity (для premultiplied output).
    // Для transition обычно alpha=1 (opaque), но оставляем flexibility.
    float alpha = max(max(mixA, mixB), min(flashIntensity, 1.0));

    FragColor = vec4(col, alpha);
}
