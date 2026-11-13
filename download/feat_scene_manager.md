# Scene Manager — функционал для demoscene intro generation

**Документ:** feat_scene_manager.md
**Дата:** 2026-11-01
**Статус:** Documentation only (не installed — per user decision «Scene Manager не будет устанавливать»)
**Назначение:** Подробное описание функционала Scene Manager для будущей реализации, если понадобится multi-scene демо-интро.

---

## 1. Что такое Scene Manager

**Scene Manager** — C++ модуль для управления **несколькими шейдерными сценами** в демо-интро. Позволяет:
- Разбить 3+ минутное интро на 4-8 отдельных сцен
- Переключать сцены по времени
- Делать плавные переходы между сценами (crossfade, cut, wipe)
- Задавать per-scene параметры (цвета, интенсивность, скорость движения)
- Синхронизировать сцены с музыкой (опционально)

**Текущее состояние проекта (v49):** 1 шейдер (`kFragmentShaderSrc`), рендерит одно и то же каждый кадр. Для 3-мин интро нужно 4-8 разных визуальных сегментов.

---

## 2. Зачем нужен

### 2.1. Проблема без Scene Manager

```
Текущий подход (v49):
  main.cpp → RenderFrame() → renders ONE shader (nebula)
  
  • 1 сцена = 1 шейдер
  • Для 3-мин интро с 5 сценами = 5 разных шейдеров
  • Переключение вручную: if (time < 30) render_scene1(); else if ...
  • Transitions: нет, резко обрываются
  • Per-scene params: hardcoded в каждом шейдере
```

### 2.2. Решение с Scene Manager

```
С Scene Manager:
  main.cpp → SceneManager.update(time) → SceneManager.render(time, w, h)
                ↑
                ├── Scene 1 (0:00-0:30): intro shader (anxiety mood)
                ├── Scene 2 (0:30-1:00): build-up (tension)
                ├── Scene 3 (1:00-1:45): main raymarch (warmth)
                ├── Scene 4 (1:45-2:30): 2D effects (delight)
                └── Scene 5 (2:30-3:00): outro (fade)
                
                + transitions между сценами (crossfade 2 сек)
                + per-scene uniforms (colors from Color Matrix)
                + audio sync опционально
```

---

## 3. Архитектура

### 3.1. Структура Scene

```cpp
struct Scene {
    // Идентификация
    const char* name;              // "intro", "main", "outro"
    
    // Шейдер
    const char* vertexShaderSrc;   // обычно общий quad vertex shader
    const char* fragmentShaderSrc; // per-scene fragment shader
    
    // Тайминг
    float startTime;               // секунды от начала демо
    float duration;                // длительность в секундах
    
    // Цвета (из Color Matrix)
    float primaryColor[3];         // RGB 0..1 — main color
    float accentColor[3];          // RGB 0..1 — accent
    float rimColor[3];             // RGB 0..1 — rim light (опц.)
    
    // Параметры
    float intensity;               // 0..1 — overall brightness
    float motionSpeed;             // 0..2 — animation speed multiplier
    float fogDensity;              // 0..1 — atmospheric fog
    
    // Metadata (из Color Matrix)
    int empathyLabel;              // 0=anxiety, 1=tension, 2=neutral, 3=warmth, 4=delight
    int temperatureLevel;          // 0=cold .. 4=hot
};
```

### 3.2. Класс SceneManager

```cpp
class SceneManager {
private:
    std::vector<Scene> scenes;
    std::vector<GLuint> programs;     // compiled shader programs
    int currentSceneIndex;
    float currentTime;
    float transitionDuration;         // default 1.0 sec
    
    enum TransitionType { CUT, CROSSFADE, WIPE, FLASH };
    TransitionType transitionType;
    
    // FBO для transitions (render scene A → texture, render scene B → texture, blend)
    GLuint transitionFBO;
    GLuint transitionTextureA, transitionTextureB;
    
public:
    // === Инициализация ===
    SceneManager();
    ~SceneManager();
    
    // === Scene management ===
    void addScene(Scene s);
    void removeScene(const char* name);
    int  getSceneCount();
    Scene* getSceneByName(const char* name);
    Scene* getSceneByIndex(int index);
    
    // === Compilation ===
    bool compileAll();                // compile all shaders
    bool compileScene(const char* name);
    const char* getCompileStatus(const char* name);  // "OK" or error message
    
    // === Time management ===
    void update(float currentTime);   // determine current scene
    int  getCurrentSceneIndex();
    Scene* getCurrentScene();
    Scene* getNextScene();            // for transitions (nullptr if last)
    float getTotalDuration();         // sum of all scene durations
    void seekTo(float time);          // jump to specific time
    
    // === Rendering ===
    void render(float currentTime, int width, int height);
    void setGlobalUniforms(float time, int w, int h);  // uTime, uResolution
    void setSceneUniforms(Scene* s);  // colors, intensity, motionSpeed
    
    // === Transitions ===
    bool isInTransition();            // true if within transition window
    float getTransitionAlpha();       // 0..1 for crossfade
    void setTransitionDuration(float seconds);
    void setTransitionType(TransitionType type);
    
    // === Per-scene uniforms ===
    void setSceneColor(const char* sceneName, const char* role, float rgb[3]);
    void setSceneFloat(const char* sceneName, const char* param, float value);
    
    // === Audio sync (опционально) ===
    void syncToAudio(float audioTime);  // use audio time instead of system
    void onBeat(int beatIndex);          // trigger scene change on beat
    
    // === Recording (опционально) ===
    void startRecording(const char* outputPath);
    void captureFrame();
    void stopRecording();
};
```

---

## 4. Функции — подробное описание

### 4.1. Scene management

| Функция | Сигнатура | Что делает |
|---------|-----------|-----------|
| `addScene` | `void addScene(Scene s)` | Добавить сцену в список. Сортировка по `startTime` автоматическая. |
| `removeScene` | `void removeScene(const char* name)` | Удалить сцену по имени. Если текущая — переключается на следующую. |
| `getSceneCount` | `int getSceneCount()` | Количество зарегистрированных сцен. |
| `getSceneByName` | `Scene* getSceneByName(const char* name)` | Найти сцену по имени. nullptr если не найдена. |
| `getSceneByIndex` | `Scene* getSceneByIndex(int i)` | Доступ по индексу 0..N-1. |

### 4.2. Compilation

| Функция | Сигнатура | Что делает |
|---------|-----------|-----------|
| `compileAll` | `bool compileAll()` | Компилирует все шейдеры в GPU programs. Возвращает false если хоть один упал. |
| `compileScene` | `bool compileScene(const char* name)` | Перекомпилировать одну сцену (для hot-reload). |
| `getCompileStatus` | `const char* getCompileStatus(const char* name)` | "OK" или сообщение об ошибке GLSL. |

### 4.3. Time management

| Функция | Сигнатура | Что делает |
|---------|-----------|-----------|
| `update` | `void update(float t)` | Определяет текущую сцену по времени. Вызывать каждый кадр. |
| `getCurrentSceneIndex` | `int getCurrentSceneIndex()` | 0..N-1 — индекс текущей сцены. |
| `getCurrentScene` | `Scene* getCurrentScene()` | Указатель на текущую сцену. |
| `getNextScene` | `Scene* getNextScene()` | Следующая сцена (для transition). nullptr если последняя. |
| `getTotalDuration` | `float getTotalDuration()` | Сумма duration всех сцен. |
| `seekTo` | `void seekTo(float time)` | Прыжок к конкретному времени (для debug/recording). |

### 4.4. Rendering

| Функция | Сигнатура | Что делает |
|---------|-----------|-----------|
| `render` | `void render(float t, int w, int h)` | Главный метод. Рендерит текущую сцену (+ transition если активен). |
| `setGlobalUniforms` | `void setGlobalUniforms(float t, int w, int h)` | Устанавливает `uTime`, `uResolution` во все шейдеры. |
| `setSceneUniforms` | `void setSceneUniforms(Scene* s)` | Устанавливает per-scene: `uPrimaryColor`, `uAccentColor`, `uIntensity`, `uMotionSpeed`. |

### 4.5. Transitions

| Функция | Сигнатура | Что делает |
|---------|-----------|-----------|
| `isInTransition` | `bool isInTransition()` | true если сейчас переход между сценами. |
| `getTransitionAlpha` | `float getTransitionAlpha()` | 0..1 — прогресс crossfade. 0 = только сцена A, 1 = только сцена B. |
| `setTransitionDuration` | `void setTransitionDuration(float sec)` | Длительность перехода (default 1.0 сек). |
| `setTransitionType` | `void setTransitionType(TransitionType t)` | CUT (мгновенно), CROSSFADE (плавно), WIPE (щёткой), FLASH (вспышка). |

**Transition logic:**
```
Transition начинается за `transitionDuration` секунд до конца текущей сцены.
Например: Scene 1 ends at 30.0, transitionDuration=2.0
  → transition starts at 28.0, ends at 30.0
  → в момент 28.0-30.0 рендерятся обе сцены, blend по alpha
```

### 4.6. Per-scene uniforms

| Функция | Сигнатура | Что делает |
|---------|-----------|-----------|
| `setSceneColor` | `void setSceneColor(name, role, rgb[3])` | Установить color для роли: "primary", "accent", "rim". |
| `setSceneFloat` | `void setSceneFloat(name, param, value)` | Установить float параметр: "intensity", "motionSpeed", "fogDensity". |

**Пример:**
```cpp
float anxietyRed[3] = {0.75f, 0.03f, 0.0f};  // из Color Matrix
sceneMgr.setSceneColor("intro", "primary", anxietyRed);
sceneMgr.setSceneFloat("intro", "intensity", 0.8f);
```

### 4.7. Audio sync (опционально)

| Функция | Сигнатура | Что делает |
|---------|-----------|-----------|
| `syncToAudio` | `void syncToAudio(float audioTime)` | Использовать audio time вместо system time. Для music sync. |
| `onBeat` | `void onBeat(int beatIndex)` | Триггер смены сцены на beat (для music-driven transitions). |

### 4.8. Recording (опционально)

| Функция | Сигнатура | Что делает |
|---------|-----------|-----------|
| `startRecording` | `void startRecording(const char* path)` | Начать запись кадров в папку. |
| `captureFrame` | `void captureFrame()` | Сохранить текущий кадр как PNG. |
| `stopRecording` | `void stopRecording()` | Закончить, вызвать ffmpeg для encode. |

---

## 5. Use cases

### 5.1. Простое 2-сценное интро (6 сек)

```
Scene 1 (0-3 сек): logo fade-in
  shader: simple logo renderer
  colors: white on black
  intensity: 0 → 1 (fade-in)

Scene 2 (3-6 сек): main visual
  shader: nebula (current v49)
  colors: DRAMATIC_DARK palette
  intensity: 1.0

Transition: CROSSFADE 1 сек (2-3 сек)
```

### 5.2. Multi-scene 3-мин интро (5 сцен)

```
Scene 1 (0:00-0:30): "Anxiety" intro
  shader: kIntroShaderSrc (dark mist, red flashes)
  mood: anxiety (Color Matrix empathy -77)
  colors: #c00800 (anxiety red), #1a0033 (deep purple)
  audio: low rumble, dissonant

Scene 2 (0:30-1:00): "Tension" build-up
  shader: kBuildUpShaderSrc (shapes forming, motion)
  mood: tension (empathy -30)
  colors: #cc4d80 (magenta), #804d20 (orange)
  audio: building rhythm

Scene 3 (1:00-1:45): "Warmth" main
  shader: kMainShaderSrc (raymarch scene, current nebula v49)
  mood: warmth (empathy +23)
  colors: #1a66cc (cyan), #cc4d80 (magenta)
  audio: melody, harmony

Scene 4 (1:45-2:30): "Delight" climax
  shader: kClimaxShaderSrc (particles, bright bursts)
  mood: delight (empathy +90)
  colors: #ffb0c0 (pink), #ffe080 (yellow), #80ffcc (mint)
  audio: full track, peak

Scene 5 (2:30-3:00): "Outro" fade
  shader: kOutroShaderSrc (credits, fade to black)
  mood: neutral
  colors: #202030 (dark), #505080 (soft)
  audio: fade out

Transitions: CROSSFADE 2 сек между каждой парой
Total: 180 сек = 3 минуты
```

### 5.3. Music-synced demo

```
Scenes change on music section boundaries:
  intro (0:00-0:30)     → Scene 1
  verse (0:30-1:00)     → Scene 2
  chorus (1:00-1:30)    → Scene 3 (climax visual)
  verse2 (1:30-2:00)    → Scene 4
  outro (2:00-2:30)     → Scene 5

Beat-triggered transitions:
  onBeat(64)  → switch from Scene 1 to Scene 2
  onBeat(128) → switch from Scene 2 to Scene 3
  etc.
```

---

## 6. Code example (интеграция в main.cpp)

### 6.1. Добавление сцен

```cpp
#include "scene_manager.h"

SceneManager sceneMgr;

void InitScenes() {
    // Scene 1: intro (anxiety)
    sceneMgr.addScene({
        "intro",
        kQuadVertexShader,      // common vertex shader
        kIntroShaderSrc,        // scene-specific fragment
        0.0f,                   // start time
        30.0f,                  // duration
        {0.75f, 0.03f, 0.0f},   // primaryColor: anxiety red
        {0.10f, 0.40f, 0.80f},  // accentColor: cyan
        {0.04f, 0.05f, 0.12f},  // rimColor: deep
        0.8f,                   // intensity
        1.0f,                   // motionSpeed
        0.3f,                   // fogDensity
        0,                      // empathyLabel: anxiety
        4                       // temperatureLevel: hot
    });
    
    // Scene 2: main (warmth)
    sceneMgr.addScene({
        "main",
        kQuadVertexShader,
        kMainShaderSrc,         // current v49 nebula shader
        30.0f, 75.0f,           // start, duration
        {0.10f, 0.40f, 0.80f},  // cyan primary
        {0.80f, 0.30f, 0.50f},  // magenta accent
        {0.04f, 0.05f, 0.12f},
        1.0f, 1.5f, 0.2f,
        3,                      // warmth
        0                       // cold
    });
    
    // Scene 3: outro (fade)
    sceneMgr.addScene({
        "outro",
        kQuadVertexShader,
        kOutroShaderSrc,
        105.0f, 75.0f,          // start, duration (105-180 sec)
        {0.04f, 0.05f, 0.12f},
        {0.50f, 0.50f, 0.80f},
        {0.02f, 0.02f, 0.03f},
        0.3f, 0.5f, 0.5f,
        2, 2                    // neutral
    });
    
    // Compile all shaders
    if (!sceneMgr.compileAll()) {
        Log("[ERROR] Scene compilation failed");
        // handle error
    }
    
    // Configure transitions
    sceneMgr.setTransitionDuration(2.0f);  // 2 sec crossfade
    sceneMgr.setTransitionType(SceneManager::CROSSFADE);
    
    Log("[OK] SceneManager initialized: %d scenes, total %.1f sec",
        sceneMgr.getSceneCount(), sceneMgr.getTotalDuration());
}
```

### 6.2. Render loop

```cpp
void RenderFrame(double dt) {
    float t = (float)getTime();  // или audio.getTime() для music sync
    
    sceneMgr.update(t);
    sceneMgr.render(t, g_width, g_height);
    
    // Log scene changes
    static int lastScene = -1;
    int curScene = sceneMgr.getCurrentSceneIndex();
    if (curScene != lastScene) {
        Scene* s = sceneMgr.getCurrentScene();
        Log("[Scene] %d: %s (t=%.1f)", curScene, s->name, t);
        lastScene = curScene;
    }
}
```

---

## 7. Интеграция с Color Matrix

Scene Manager + Color Matrix = **mood-driven scene design**

### 7.1. Color Matrix → Scene colors

```python
# Python helper: generate scene colors from Color Matrix
from color_matrix_python import FullRGBMatrixReader
from color_matrix_python.tools import ColorToolbox, to_glsl

reader = FullRGBMatrixReader('color-matrix-full-rgb-v11.npz')
tb = ColorToolbox(reader)

# For each scene, query colors by mood
scenes_config = [
    {"name": "intro",  "feel": "anxiety",  "start": 0,   "duration": 30},
    {"name": "main",   "feel": "warmth",   "start": 30,  "duration": 75},
    {"name": "outro",  "feel": "neutral",  "start": 105, "duration": 75},
]

for sc in scenes_config:
    r = tb.dispatch("find_colors", {"feel": sc["feel"], "count": 2})
    primary = r["candidates"][0]
    accent = r["candidates"][1]
    print(f'Scene "{sc["name"]}":')
    print(f'  primary: {to_glsl(primary["rgb"])}  // empathy {primary["empathy"]}')
    print(f'  accent:  {to_glsl(accent["rgb"])}   // empathy {accent["empathy"]}')
```

### 7.2. Color Matrix → Transitions

```python
# For each transition, find animation path
transition = tb.dispatch("find_animation_path", {
    "from_state": {"feel": "anxiety"},  # scene 1 mood
    "to_state": {"feel": "warmth"},     # scene 2 mood
    "steps": 5
})
# Use these 5 colors for transition shader uniforms
```

### 7.3. Scene catalog в color_catalog.md

Каждая сцена записывается в каталог:
```markdown
## Task 70 — Scene Manager: "intro" scene
- Color: #c00800 (anxiety red)
  - synesthesia: hot/medium/pulse
  - empathy: anxiety (-77)
  - role: primary, scene "intro"
  - GLSL: vec3(0.753, 0.031, 0.000)
```

---

## 8. Шейдеры для Scene Manager

Каждая сцена имеет свой fragment shader. Общий pattern:

```glsl
// kIntroShaderSrc — Scene 1 (anxiety)
#version 330 core
in vec2 vUV;
out vec4 FragColor;

uniform float uTime;
uniform vec2 uResolution;
uniform vec3 uPrimaryColor;   // set by SceneManager
uniform vec3 uAccentColor;    // set by SceneManager
uniform float uIntensity;     // set by SceneManager
uniform float uMotionSpeed;

void main() {
    vec2 uv = vUV * 2.0 - 1.0;
    uv.x *= uResolution.x / uResolution.y;
    
    // Anxiety effect: dark mist + red flashes
    float flash = sin(uTime * uMotionSpeed * 3.0) * 0.5 + 0.5;
    flash = pow(flash, 4.0);  // sharp flashes
    
    vec3 col = uPrimaryColor * flash * uIntensity;
    col += uAccentColor * 0.1;  // dim accent
    
    // Vignette
    float vig = 1.0 - length(uv) * 0.5;
    col *= vig;
    
    FragColor = vec4(col, 1.0);
}
```

```glsl
// kOutroShaderSrc — Scene 5 (fade to black)
#version 330 core
in vec2 vUV;
out vec4 FragColor;

uniform float uTime;
uniform vec2 uResolution;
uniform vec3 uPrimaryColor;
uniform float uIntensity;
uniform float uMotionSpeed;

void main() {
    vec2 uv = vUV;
    
    // Fade out over scene duration
    float fadeAlpha = 1.0 - smoothstep(0.0, 1.0, uTime - 150.0);
    
    // Simple credits text would go here (text rendering)
    vec3 col = uPrimaryColor * uIntensity * fadeAlpha;
    
    FragColor = vec4(col, fadeAlpha);
}
```

---

## 9. Transition shaders

### 9.1. Crossfade transition

```glsl
// transition_crossfade.glsl
#version 330 core
in vec2 vUV;
out vec4 FragColor;

uniform sampler2D uSceneA;   // rendered scene A
uniform sampler2D uSceneB;   // rendered scene B
uniform float uAlpha;         // 0 = A, 1 = B

void main() {
    vec4 a = texture(uSceneA, vUV);
    vec4 b = texture(uSceneB, vUV);
    FragColor = mix(a, b, smoothstep(0.0, 1.0, uAlpha));
}
```

### 9.2. Wipe transition

```glsl
// transition_wipe.glsl
void main() {
    vec4 a = texture(uSceneA, vUV);
    vec4 b = texture(uSceneB, vUV);
    float wipe = step(vUV.x, uAlpha);  // left-to-right wipe
    FragColor = mix(a, b, wipe);
}
```

### 9.3. Flash transition

```glsl
// transition_flash.glsl
void main() {
    vec4 a = texture(uSceneA, vUV);
    vec4 b = texture(uSceneB, vUV);
    
    // Flash white at uAlpha=0.5
    float flash = exp(-pow((uAlpha - 0.5) * 6.0, 2.0));
    vec3 col = mix(a.rgb, b.rgb, smoothstep(0.0, 1.0, uAlpha));
    col = mix(col, vec3(1.0), flash);
    
    FragColor = vec4(col, 1.0);
}
```

---

## 10. Implementation effort

### 10.1. Файлы

```
download/demo_intro/
  scene_manager.h        ← NEW (~80 lines, struct + class declaration)
  scene_manager.cpp      ← NEW (~250 lines, implementation)
  shaders.h              ← MODIFIED (add kIntroShaderSrc, kOutroShaderSrc, 
                                   kTransitionShaderSrc)
  main.cpp               ← MODIFIED (add InitScenes(), use sceneMgr.render())
  build_msvc.bat         ← unchanged (auto-detects new .cpp files)
```

### 10.2. Время реализации

| Компонент | Я пишу | Вы компилируете | Итого |
|-----------|--------|------------------|-------|
| scene_manager.h + .cpp | 60 мин | 10 мин (compile) | 70 мин |
| Shader sources (3-5 scenes) | 30 мин | 5 мин | 35 мин |
| Transition shaders | 15 мин | 5 мин | 20 мин |
| main.cpp integration | 15 мин | 10 мин (test) | 25 мин |
| Debug (по trace.log) | 15 мин | 10 мин | 25 мин |
| **Итого** | **135 мин** | **40 мин** | **175 мин (~3 часа)** |

### 10.3. Dependencies

- OpenGL 3.3+ (уже есть)
- OpenGL loader (уже есть `opengl_loader.h`)
- FBO support (для transitions — стандартная OpenGL 3.3)
- **NO external libraries** — всё на стандартном OpenGL

---

## 11. Roadmap для Scene Manager (если решите реализовать)

### Phase 1: Basic Scene Manager (2 scenes)
- Реализовать scene_manager.h/.cpp
- 2 тестовые сцены (intro + main)
- CUT transitions (без crossfade)
- **Время:** 70 мин
- **Результат:** v50 — 2-scene demo

### Phase 2: Transitions
- Добавить FBO для crossfade
- Transition shader
- CROSSFADE, WIPE, FLASH types
- **Время:** 35 мин
- **Результат:** v51 — smooth transitions

### Phase 3: Color Matrix integration
- Каждая сцена получает colors из Color Matrix
- Per-scene mood (empathy label)
- **Время:** 25 мин
- **Результат:** v52 — mood-driven scenes

### Phase 4: Multi-scene (5 scenes)
- Добавить 3+ scenes
- Full 3-min demo
- **Время:** 45 мин
- **Результат:** v53 — 3-minute demoscene intro

### Phase 5: Audio sync (опционально)
- Интеграция с audio engine
- Beat-triggered transitions
- **Время:** 65 мин
- **Результат:** v54 — music-synced demo

---

## 12. Status

**Текущий статус:** Documentation only.

- ❌ НЕ реализовано (per user decision «Scene Manager не будет устанавливать»)
- ✅ Полностью спроектировано (architectture + API + code examples)
- ✅ Готово к реализации если понадобится

**Когда понадобится:**
- Если захотите 3+ мин демо-интro
- Если захотите multiple visual segments
- Если захотите music-synced visuals

**Как запустить реализацию:**
```
!feat scene-manager basic   → Phase 1 (70 мин)
!feat scene-manager full    → Phases 1-4 (175 мин)
!feat scene-manager +audio  → Phases 1-5 (240 мин)
```

---

## 13. Связанные документы

- `download/aesthetics.md` — aesthetic principles (mood, harmony, density)
- `download/color_catalog.md` — color log per Task
- `color_matrix/policy/shader_color_policy.md` — shader-specific color policy
- `color_matrix/output/color_matrix_python/tools.py` — Color Matrix tools (for scene colors)
- `scripts/anim_parser.py` — `%anim` parser (for scene transitions)
- `roadmap.md` — project tasks (Task 68 = Color Matrix integration)
