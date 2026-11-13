# Scene Manager — 5 архитектурных вариантов

**Документ:** feat_scene_manager_variants.md
**Дата:** 2026-11-06
**Сигил:** `&suggest` — предлагаю варианты для выбора
**Статус:** Proposal (для обсуждения, не для немедленной реализации)
**Связанные документы:**
- `feat_scene_manager.md` — детальный дизайн Variant A (682 строки, готов к реализации)
- `Pipeline_intro.md` — compo pipeline analysis (14 компонентов)
- `aesthetics.md` — mood / harmony / density principles
- `meta.auto` — `[demo:duration]=60`, `[demo:fade_out]=3`

---

## 0. Контекст и цель

**Текущее состояние (v49):** один шейдер `kFragmentShaderSrc` рендерит nebula, 60 секунд, без переходов, без multi-scene.

**Цель Scene Manager:** разбить демо-интро на 4-8 визуальных сегментов, синхронизировать с музыкой (опционально), обеспечить плавные переходы, поддержать per-scene параметры (цвета из Color Matrix, mood из Cozy Engine).

**Ключевой вопрос:** какой архитектуре следовать? Разные compo-категории диктуют разные требования:

| Compo | Лимит размера | Лимит времени | Audio | Требования к Scene Manager |
|-------|---------------|---------------|-------|---------------------------|
| **4K** | 4096 байт | 3 мин | синтез | Минимум кода, всё в одном шейдере |
| **64K** | 65536 байт | 3-5 мин | синтез | Умеренная сложность, можно несколько шейдеров |
| **Demo** | нет лимита | 5-10 мин | streaming | Полная свобода, rich visuals, post-processing |

Ниже — 5 вариантов архитектуры, отсортированных от простого к сложному.

---

## Variant A — Timeline Linear (текущий дизайн)

**Суть:** Сцены на фиксированной таймлайне, переключение по времени, переходы между сценами.

```cpp
struct Scene {
    const char* name;
    const char* fragmentShaderSrc;
    float startTime;            // 0.0, 30.0, 105.0 ...
    float duration;             // 30.0, 75.0, 75.0
    float primaryColor[3];      // из Color Matrix
    float accentColor[3];
    float intensity, motionSpeed, fogDensity;
    int   empathyLabel;         // из Color Matrix
};

SceneManager mgr;
mgr.addScene({"intro", kIntroSrc,  0.0f,  30.0f, ...});
mgr.addScene({"main",  kMainSrc,  30.0f,  75.0f, ...});
mgr.addScene({"outro", kOutroSrc, 105.0f, 75.0f, ...});
mgr.setTransition(CROSSFADE, 2.0f);  // 2 сек между сценами
mgr.compileAll();

// каждый кадр:
mgr.update(time);
mgr.render(time, w, h);
```

**Архитектура:**
- C++ класс `SceneManager` хранит массив `Scene`
- Каждый кадр: `update(t)` находит текущую сцену, `render(t,w,h)` рендерит
- Transitions через FBO: scene A → texture, scene B → texture, blend shader
- Per-scene uniforms: `uPrimaryColor`, `uAccentColor`, `uIntensity`, `uMotionSpeed`

**Pros:**
- ✅ Простой, предсказуемый, легко debug
- ✅ Уже полностью спроектирован (см. `feat_scene_manager.md`, 682 строки)
- ✅ Хорошее соответствие с Color Matrix (`find_colors` per scene)
- ✅ Поддерживает CUT / CROSSFADE / WIPE / FLASH transitions
- ✅ Линейная логика = легко тестировать по trace.log

**Cons:**
- ❌ Не реагирует на музыку (только фиксированное время)
- ❌ Каждая сцена = отдельный шейдер → растёт binary size
- ❌ Для 4K compo: 5 сцен × ~2KB шейдер = 10KB, не влезает в 4K лимит
- ❌ Нет интерактивности / ветвления

**Когда подходит:**
- 64K compo с 3-5 сценами
- Demo compo с фиксированной таймлайной
- Прототипирование, когда ещё не известно сколько сцен

**Effort:** ~3 часа (175 мин) — `feat_scene_manager.md` описан полностью
**Binary cost:** +12-15 KB (shader sources + SceneManager code)
**Результат:** v50-v53 — multi-scene, transitions, Color Matrix integration

---

## Variant B — Uber Shader (single-shader approach)

**Суть:** ВСЕ сцены в одном фрагмент-шейдере. `uSceneId` uniform выбирает ветку. Никакого C++ state для сцен.

```glsl
// kMegaShaderSrc — ВСЕ сцены в одном шейдере
uniform int   uSceneId;        // 0=intro, 1=main, 2=outro
uniform float uSceneTime;      // локальное время сцены (0..duration)
uniform float uTransitionAlpha;// 0..1 для blend между сценами

vec3 scene_intro(vec2 uv, float t) {
    // anxiety effect: dark mist + red flashes
    float flash = pow(sin(t * 3.0) * 0.5 + 0.5, 4.0);
    return uPrimaryColor * flash + uAccentColor * 0.1;
}

vec3 scene_main(vec2 uv, float t) {
    // raymarch nebula (current v49)
    return raymarch(uv, t);
}

vec3 scene_outro(vec2 uv, float t) {
    // fade to black
    return uPrimaryColor * (1.0 - smoothstep(0.0, 3.0, t));
}

void main() {
    vec2 uv = vUV * 2.0 - 1.0;
    vec3 col;
    if (uSceneId == 0)      col = scene_intro(uv, uSceneTime);
    else if (uSceneId == 1) col = scene_main(uv, uSceneTime);
    else                    col = scene_outro(uv, uSceneTime);
    
    // Cross-scene transition: blend with previous scene
    if (uTransitionAlpha > 0.0) {
        vec3 prevCol = scene_prev(uv, uSceneTime);  // указатель на prev
        col = mix(col, prevCol, 1.0 - uTransitionAlpha);
    }
    
    FragColor = vec4(col, 1.0);
}
```

```cpp
// main.cpp — минимум C++ кода
struct SceneDef { int id; float start; float duration; };
SceneDef scenes[] = {
    {0, 0.0f, 30.0f},    // intro
    {1, 30.0f, 75.0f},   // main
    {2, 105.0f, 75.0f},  // outro
};

void RenderFrame(double t) {
    // Найти текущую сцену
    int curId = -1; float sceneTime = 0;
    for (auto& s : scenes) {
        if (t >= s.start && t < s.start + s.duration) {
            curId = s.id;
            sceneTime = t - s.start;
            break;
        }
    }
    glUniform1i(uSceneId, curId);
    glUniform1f(uSceneTime, sceneTime);
    glUniform1f(uTransitionAlpha, computeTransitionAlpha(t));
    glDrawArrays(...);
}
```

**Архитектура:**
- Один fragment shader, функции `scene_*()` для каждой сцены
- C++ — простая lookup-таблица `{sceneId, startTime, duration}`
- Transition: при `uTransitionAlpha > 0` шейдер вычисляет ОБЕ сцены и mix
- Per-scene uniforms ОБЩИЕ: `uPrimaryColor` и т.д. (переопределяются per scene)

**Pros:**
- ✅ Минимум C++ кода (~50 строк вместо 330)
- ✅ Один shader = проще hot-reload
- ✅ GPU сам обрабатывает branching, нет FBO для transitions
- ✅ ИДЕАЛЬНО для 4K compo: весь multi-scene в одном шейдере
- ✅ Transitions в самом шейдере — бесплатно (mix)

**Cons:**
- ❌ Branching в шейдере может быть медленным на старых GPU (GTX 750 OK)
- ❌ Shader source растёт линейно с числом сцен
- ❌ Сложно debug: нужно переключать `uSceneId` чтобы видеть каждую
- ❌ Нет separate compilation — любой syntax error ломает все сцены
- ❌ Все сцены разделяют uniform set (нельзя дать каждой свой `uFooParam`)

**Когда подходит:**
- **4K compo — единственный реальный вариант** (5 сцен, 4KB лимит)
- 64K compo где важна компактность
- Простой 2-3 сценовые демо без сложных transitions

**Effort:** ~1.5 часа (90 мин)
**Binary cost:** +1-2 KB (один шейдер, минимум C++)
**Результат:** v50 — uber-shader multi-scene

---

## Variant C — Music-Synced (beat-driven)

**Суть:** Audio engine — мастер. Сцены меняются по событиям музыки (beat, section change). Время — переменная, зависит от audio.

```cpp
class AudioEngine {
public:
    float getCurrentTime();       // audio time, не system time
    int   getCurrentBeat();       // 0, 1, 2, ...
    int   getCurrentSection();    // 0=intro, 1=verse, 2=chorus ...
    float getSectionProgress();   // 0..1 внутри секции
    bool  isOnBeat();             // true если сейчас beat moment
    float getBPM();               // 120, 140 ...
};

class MusicSceneManager {
    std::vector<std::pair<int, Scene>> sectionScenes;
    // sectionId → Scene
    
public:
    void mapSectionToScene(int sectionId, Scene s);
    void onBeat(int beatIndex);   // можно триггерить mini-transitions
    void update(float audioTime);
    void render(float audioTime, int w, int h);
};

// Конфиг:
mgr.mapSectionToScene(0, introScene);   // 0:00-0:30 intro music → intro visual
mgr.mapSectionToScene(1, buildUpScene); // 0:30-1:00 verse → build-up
mgr.mapSectionToScene(2, climaxScene);  // 1:00-1:45 chorus → main visual
mgr.mapSectionToScene(3, breakdownScene); // 1:45-2:30 bridge → 2D effects
mgr.mapSectionToScene(4, outroScene);   // 2:30-3:00 outro → fade
```

**Архитектура:**
- AudioEngine (4Klang / C99 synth / streaming) выдаёт `audioTime`, `beat`, `section`
- SceneManager слушает audio events, не системное время
- Transitions синхронизированы с music section boundaries (точные до ms)
- Beat-triggered mini-effects: каждый beat → flash / camera shake / color pulse
- Time variable: если audio заикается, демо тоже (acceptable для music-driven)

**Pros:**
- ✅ Полная музыкальная синхронизация (визуал идеально совпадает с аудио)
- ✅ Beat-triggered effects дают ощущение «живого» демо
- ✅ Section-based mapping естественен для music structure
- ✅ Audio time = master, нет дрейфа между аудио и визуалом

**Cons:**
- ❌ Требует audio engine (4Klang или свой синт) — отдельная подсистема
- ❌ Если audio engine не готов, Scene Manager нельзя тестировать
- ❌ Более сложный API (events, callbacks)
- ❌ Beat detection unreliable для variable BPM треков
- ❌ Variable timing = сложнее debug по trace.log

**Когда подходит:**
- Demo compo с готовым soundtrack
- 64K compo где музыка уже есть (4Klang)
- Проекты где audio-driven visual — основная фишка

**Effort:** ~5 часов (300 мин) — требует audio engine integration
**Binary cost:** +18 KB (audio engine + scene manager + beat detection)
**Результат:** v54-v55 — music-synced demo (если audio engine готов)

---

## Variant D — Cozy Engine Generative (mood → scenes)

**Суть:** Сцены АВТО-ГЕНЕРИРУЮТСЯ из Cozy Engine atoms. Дизайнер задаёт «mood flow» (последовательность настроений), движок подбирает атомы и собирает сцены.

```python
# Python: generate scene schedule from mood flow
from cozy_engine.scenes import SceneGenerator
from cozy_engine.atoms import ATOM_LIBRARY  # 64 atoms

gen = SceneGenerator()

mood_flow = [
    {"feel": "anxiety",  "duration": 30, "intensity": 0.6},  # 0:00-0:30
    {"feel": "tension",  "duration": 30, "intensity": 0.8},  # 0:30-1:00
    {"feel": "warmth",   "duration": 45, "intensity": 1.0},  # 1:00-1:45
    {"feel": "delight",  "duration": 45, "intensity": 1.2},  # 1:45-2:30
    {"feel": "neutral",  "duration": 30, "intensity": 0.4},  # 2:30-3:00
]

scenes = gen.generate(mood_flow, total_duration=180)
# output: 5 Scene structs, each with:
#   - chosen atom (e.g. "nebula_raymarch", "particle_swarm", "morph_grid")
#   - colors from Color Matrix matching mood
#   - per-scene uniforms auto-tuned
#   - transition type selected by mood delta
```

```cpp
// C++: сгенерированная таблица embed в binary
const Scene kScenes[] = {
    {"intro",  ATOM_NEBULA_DARK,    0.0f,  30.0f, {0.75, 0.03, 0.0}, ...},
    {"build",  ATOM_MORPH_GRID,    30.0f,  30.0f, {0.80, 0.30, 0.50}, ...},
    {"main",   ATOM_NEBULA_RAYMARCH,60.0f, 45.0f, {0.10, 0.40, 0.80}, ...},
    {"climax", ATOM_PARTICLE_SWARM,105.0f, 45.0f, {1.00, 0.70, 0.80}, ...},
    {"outro",  ATOM_FADE_CREDITS, 150.0f, 30.0f, {0.20, 0.20, 0.30}, ...},
};

// Atom shader library (64 атомов, компилируются по id)
const char* kAtomShaders[64] = {
    ATOM_NEBULA_DARK_src,      // 0
    ATOM_MORPH_GRID_src,       // 1
    ATOM_NEBULA_RAYMARCH_src,  // 2
    // ... 64 shaders
};

void renderScene(const Scene& s, float t, int w, int h) {
    GLuint prog = kAtomPrograms[s.atomId];
    glUseProgram(prog);
    setUniforms(s, t);
    glDrawArrays(...);
}
```

**Архитектура:**
- 64 atom shader library (готовится отдельным pipeline: «atom → GLSL»)
- Python `SceneGenerator` читает mood flow, для каждого segment:
  1. Запрашивает Cozy Engine для подходящего atom (по feel)
  2. Запрашивает Color Matrix для цветов (по empathy)
  3. Подбирает transition type по mood delta (anxiety→warmth = FLASH)
  4. Генерирует C++ struct → embed в binary
- C++ runtime: простой lookup `kScenes[i]` → `kAtomPrograms[atomId]`

**Pros:**
- ✅ Легендарная вариативность: 64 atoms × mood combinations = бесконечность
- ✅ Mood-driven design — естественная интеграция с Color Matrix + Cozy Engine
- ✅ Designer пишет ТОЛЬКО mood flow, не код шейдеров
- ✅ Reusable atom library — следующие демо используют те же 64 atoms
- ✅ Лёгкая A/B итерация: поменял mood flow → пересобрал scenes

**Cons:**
- ❌ Требует atom library (64 готовых шейдера) — большой upfront effort
- ❌ Atom shader compiler — отдельная подсистема (~неделя работы)
- ❌ Binary большой (если включать все 64 atoms = ~50KB shaders)
- ❌ Designer не контролирует точно каждую сцену (delegated to algorithm)
- ❌ Сложно debug: что именно выбрал generator?

**Когда подходит:**
- Demo compo без лимита размера
- Долгосрочная платформа (несколько демо на одной atom library)
- Экспериментальные / generative работы
- Когда mood-driven дизайн — основная концепция

**Effort:** ~8 часов (480 мин) + создание atom library (отдельный pipeline)
**Binary cost:** +25-50 KB (зависит от числа включённых atoms)
**Результат:** v55-v58 — full generative pipeline

---

## Variant E — Layered Hybrid (multi-pass compositing)

**Суть:** Сцены = СЛОИ. Каждый кадр рендерится 3-5 слоёв (bg, mid, fg, overlay, post), каждый со своим timeline и shader. Финальный compositing pass.

```cpp
struct Layer {
    const char* name;            // "background", "main", "particles", "overlay", "postfx"
    const char* shaderSrc;
    float startOffset;           // когда слой появляется (относительно demo start)
    float duration;              // сколько живёт
    float blendAlpha;            // 0..1, animated
    BlendMode blendMode;         // ADD, MULTIPLY, OVERLAY, SCREEN, NORMAL
    int   zOrder;                // 0=bg, 4=postfx
};

Layer layers[] = {
    {"bg_stars",    kStarsSrc,    0.0f, 180.0f, 0.5f, NORMAL,  0},
    {"main_nebula", kNebulaSrc,   0.0f, 105.0f, 1.0f, NORMAL,  1},
    {"particles",   kParticleSrc, 30.0f, 75.0f, 0.8f, ADD,    2},
    {"overlay_flsh",kFlashSrc,    0.0f, 180.0f, 0.0f, ADD,    3},
    {"post_bloom",  kBloomSrc,    0.0f, 180.0f, 1.0f, NORMAL, 4},
};

void RenderFrame(float t, int w, int h) {
    // Render each active layer to its FBO
    for (auto& L : layers) {
        if (t >= L.startOffset && t < L.startOffset + L.duration) {
            renderLayerTo(L, t, w, h, layerFBO[L.zOrder]);
        }
    }
    // Composite: bg + main + particles + overlay + post
    compositePass(layerFBOs, blendModes, blendAlphas, outputFBO);
    // Final blit
    blitToScreen(outputFBO);
}
```

**Архитектура:**
- N слоёв вместо M сцен (N обычно 3-5, M было бы 4-8)
- Каждый слой: свой shader + FBO + timeline + blend mode
- Compositing shader: читает N textures, blend по формуле
- Post-processing встроен как layer (bloom, grain, aberration — zOrder=4)
- Cross-scene transitions = layer alpha animation (не отдельный transition pass)

**Pros:**
- ✅ Богатые visuals: несколько слоёв одновременно = глубина
- ✅ Post-processing естественно встроен (layer, не отдельный pipeline)
- ✅ Параллельная анимация: nebula + particles + flash синхронно
- ✅ Переходы через alpha = плавные, без FBO duplication
- ✅ Layer = переиспользуемый (тот же stars shader в 5 разных демо)

**Cons:**
- ❌ Самый сложный в реализации (~500 строк C++)
- ❌ Multiple FBO = много GPU памяти (5 layers × 1920×1080 RGBA = ~40MB)
- ❌ Compositing pass = дополнительный draw call + bandwidth
- ❌ Layer ordering / blend modes нужно настраивать вручную
- ❌ Debug сложно: какой слой вносит артефакт?

**Когда подходит:**
- Demo compo без лимита размера
- Когда rich visuals важнее размера
- Post-processing как first-class citizen
- Multi-pass rendering с effects chains

**Effort:** ~6 часов (360 мин)
**Binary cost:** +20 KB (5-6 layer shaders + compositing + SceneManager)
**Результат:** v55-v57 — layered multi-pass demo

---

## Сравнительная таблица

| Variant | LoC | Effort | Binary+ | Transitions | Music sync | Color Matrix | Cozy Engine | Best for |
|---------|-----|--------|---------|-------------|-----------|--------------|--------------|----------|
| **A** Timeline | 330 | 3h | +12KB | CUT/CF/WIPE/FLASH | опц. (manual) | ✅ per-scene | ❌ | 64K, Demo, прототип |
| **B** Uber | 80 | 1.5h | +2KB | mix в шейдере | ❌ | partial | ❌ | **4K compo** |
| **C** Music | 450 | 5h | +18KB | beat-triggered | ✅ master | ✅ per-section | ❌ | Demo + soundtrack |
| **D** Cozy Gen | 600+ | 8h+ | +25KB | auto by mood delta | опц. | ✅ auto | ✅ core | Demo, generative |
| **E** Layered | 500 | 6h | +20KB | alpha blend | опц. | ✅ per-layer | ❌ | Demo, rich visuals |

---

## Рекомендация

### Если целью является 4K compo → **Variant B (Uber Shader)**
- Единственный реалистичный вариант под 4096 байт лимит
- Transitions внутри шейдера = бесплатно
- Минимум C++ = максимум места для шейдера

### Если целью является 64K compo → **Variant A (Timeline)**
- Поддержка нескольких шейдеров в лимите 64KB
- Color Matrix integration работает из коробки
- Phase 1-3 = 2-scene + transitions + Color Matrix = ~3 часа

### Если целью является Demo compo → **Variant D (Cozy Generative) или E (Layered)**
- D: mood-driven, бесконечная вариативность, showcase Cozy Engine
- E: rich visuals, post-processing integrated, professional look
- Возможен гибрид D+E: layers генерируются из atoms

### Для быстрого старта → **Variant A**
- Уже спроектирован (feat_scene_manager.md)
- 3 часа → рабочий multi-scene demo
- Migration path: A → C (audio) → D (generative) → E (layered) по фазам

---

## Migration Path (если развивать поэтапно)

```
v49 (текущий)         — single shader nebula
  ↓
v50: Variant A Phase 1 — 2 scenes + CUT (70 мин)
  ↓
v51: Variant A Phase 2 — transitions CROSSFADE/WIPE/FLASH (35 мин)
  ↓
v52: Variant A Phase 3 — Color Matrix per-scene colors (25 мин)
  ↓
v53: Variant A Phase 4 — 5 scenes, 3-min demo (45 мин)
  ↓
[развилка]
  ├── v54: Variant C — music sync (если audio engine готов)
  ├── v55: Variant D — atom library + generator (если Cozy Gen)
  └── v55: Variant E — layered multi-pass (если rich visuals)
```

Каждая фаза = отдельный milestone, можно остановиться на любой.

---

## Что нужно от пользователя

1. **Выбрать variant** (A, B, C, D, E) или комбо
2. **Указать compo category** (4K / 64K / Demo) — это определяет variant
3. **Если C: статус audio engine** (готов? какой synth?)
4. **Если D: готов ли atom library?** (или делать параллельно?)
5. **Длительность демо** `[demo:duration]` — 60 сек / 180 сек / 300 сек?

После выбора — можно либо:
- `!feat scene-manager <variant>` — реализовать выбранный variant
- `&plan detailed <variant>` — детальный план реализации

---

## Status

**Текущий статус:** Proposal (5 variants описаны, ждём выбора)

**Готово к реализации:**
- Variant A: полностью спроектирован в `feat_scene_manager.md`
- Variant B: набросок в этом документе (1.5 часа на полную реализацию)
- Variant C, D, E: high-level design, требуют детализации после выбора

**Не реализовано:** ни один из variants (per user decision «Scene Manager не будет устанавливать» до явного запроса)
