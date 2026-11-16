## Metadata

- **Model:** `qwen3.7-plus`
- **Time:** 2026-11-16 12:51:33 +07:00
- **URL:** https://chat.qwen.ai/c/fb892aca-113e-41b0-8dc3-8cadad89af9e

## Conversation

### 🧑‍💻 User

Проанализируй, напиши свой вариант пайплайн демо и три скриншота к нему. 
Укажи пошагово, как это можно сделать на пайплайне 
Uroboros - Scene manager - motus - Cozy Engine - Color Matrix
напиши примерный код такого проекта, используя python + С++, в виде markdown.
Напиши свои рекомендации, как обойти ограничения пайплайна и гибче его применять (например, cozy engine создавался не для того, чтобы манипулировать только "зашитыми" sdf shapes)
 

### 🤖 Assistant

#### 🤔 Thought Process

**Analyze visual inputs and construct a demonstration pipeline**

I evaluate the provided cyberpunk, wireframe, and abstract imagery to extract key aesthetic elements.I then synthesize these insights into a cohesive workflow that bridges technical structure with artistic fluidity.Finally, I outline a precise sequence of actions to guide the creation of this demonstration.

**Synthesizing a technical solution for a complex rendering pipeline**

I am analyzing the provided cyberpunk imagery to define the visual structure of the raymarched cityscape. I am formulating a hybrid Python and C++ implementation strategy to address the specific constraints of the engine's signed distance field limitations. I am preparing recommendations to bypass these restrictions, focusing on flexible shape integration within the Cozy Engine environment. Finally, I am structuring the output to present code examples and architectural advice in a clear, professional format.

**I am structuring a visual narrative for a generative art demo.**

I define distinct aesthetic phases ranging from abstract gradients to geometric wireframes.I outline a technical architecture involving orchestration, scene management, and procedural generation.I plan the implementation strategy using Python to bring this synthetic dreamscape to life.

**Формирую структуру итогового ответа**

Анализирую предоставленные визуальные материалы для выявления ключевых концепций и архитектуры системыРазрабатываю пошаговый пайплайн интеграции инструментов проектирования и среды выполненияПодготавливаю пример кода на обоих языках и формулирую рекомендации по расширению функциональности

#### 💡 Response

**Neon Genesis — Pipeline Demo Concept**

**1. Анализ трёх референсов и концепция**

| # | Изображение | Визуальный язык | Роль в демо |
|---|---|---|---|
| 1 | Cyberpunk city, blue rain, vertical towers | Raymarched SDF city, volumetric fog, neon accents | **Scene 3 — Main** (кульминация, 1:30–2:30) |
| 2 | Wireframe triangles, neon green/orange, glitch | Procedural geometry, chromatic aberration, scanlines | **Scene 2 — Build-up** (нарастание, 0:30–1:30) |
| 3 | Fluid gradient, purple→blue→pink→orange | Domain warping, FBM, smooth color flow | **Scene 1 — Intro** + **Scene 4 — Outro** (0:00–0:30, 2:30–3:00) |

**Концепция:** *«Synthetic Dreams»* — 3-минутное 64K intro, путешествие сознания от абстрактного потока через геометрическую структуру к мегаполису и обратно.

**Timeline:**
```
0:00 – 0:30  Scene 1: Fluid Dream    (image 3, ambient, slow)
0:30 – 1:30  Scene 2: Neon Wireframe (image 2, build-up, mid-tempo)
1:30 – 2:30  Scene 3: Cyber City     (image 1, climax, fast)
2:30 – 3:00  Scene 4: Dissolve       (image 3 return, fade out)
```

---

**2. Пошаговый пайплайн: Uroboros → Scene Manager → Motus → Cozy Engine → Color Matrix**

**Шаг 0 — Uroboros (оркестратор)**
Uroboros — главный цикл, который держит всё вместе: таймер, аудио-синхронизацию, dispatch событий.

```
[Python: design_timeline.py]  →  генерирует timeline.json
         ↓
[C++: uroboros_main.cpp]      →  читает timeline, запускает loop
         ↓
   ┌──────────────────────────────────────┐
   │  while (!quit) {                     │
   │    t = get_time();                   │
   │    beat = audio.get_beat(t);         │
   │    scene = scene_mgr.current(t);     │
   │    cam   = motus.sample(t);          │
   │    colors= color_matrix.get(scene);  │
   │    render(scene, cam, colors, beat); │
   │  }                                   │
   └──────────────────────────────────────┘
```

**Шаг 1 — Scene Manager (оркестрация сцен)**
Определяет, какая сцена активна, управляет crossfade между ними.

```python
# Python: scene_definition.py
scenes = [
    Scene(id="fluid",    start=0.0,   end=30.0,  shader="fluid.glsl",    transition="fade"),
    Scene(id="wire",     start=30.0,  end=90.0,  shader="wireframe.glsl",transition="glitch"),
    Scene(id="city",     start=90.0,  end=150.0, shader="city.glsl",     transition="zoom"),
    Scene(id="dissolve", start=150.0, end=180.0, shader="fluid.glsl",    transition="fade"),
]
```

**Шаг 2 — Motus (камера и движение)**
Keyframe-система для камеры и параметров сцен.

```python
# Python: motus_timeline.py
camera_path = [
    Keyframe(t=0,    pos=(0,0,5),   target=(0,0,0), fov=60),
    Keyframe(t=30,   pos=(0,0,3),   target=(0,0,0), fov=75),
    Keyframe(t=90,   pos=(0,2,8),   target=(0,0,-10), fov=50),
    Keyframe(t=150,  pos=(0,0.5,2), target=(0,5,-20), fov=40),
    Keyframe(t=180,  pos=(0,0,5),   target=(0,0,0), fov=60),
]
```

**Шаг 3 — Cozy Engine (контент)**
Атомы → объекты → шейдеры. Здесь ключевая гибкость: атомы не только SDF, но и domain-warped поля, particle systems, procedural grids.

```python
# Python: cozy_atoms.py
atoms = {
    "fluid_waves":   Atom(type="fbm", octaves=6, warp=True),
    "neon_tri":      Atom(type="sdf", shape="triangle", glow=1.5),
    "city_tower":    Atom(type="sdf", shape="box", round=0.1, repeat=True),
    "rain":          Atom(type="particles", count=2000, gravity=True),
}
```

**Шаг 4 — Color Matrix (палитры)**
Эмпатийные палитры на сцену.

```python
# Python: color_matrix.py
palettes = {
    "fluid":    Palette(base="#1a0033", accent1="#ff6600", accent2="#00ccff", mood="dreamy"),
    "wire":     Palette(base="#001100", accent1="#ccff00", accent2="#ff8800", mood="aggressive"),
    "city":     Palette(base="#000811", accent1="#0066ff", accent2="#00ffff", mood="dark"),
    "dissolve": Palette(base="#1a0033", accent1="#ff0066", accent2="#6600ff", mood="melancholy"),
}
```

---

**3. Примерный код проекта**

**3.1 Python — Design & Build pipeline**

```python
# build_pipeline.py — генерирует C++ код из деклараций
import json
from pathlib import Path

# ─── Scene definitions ───────────────────────────────────────────
SCENES = [
    {"id": "fluid",    "start": 0.0,   "end": 30.0,  "shader": "fluid.glsl",    "transition": "fade"},
    {"id": "wire",     "start": 30.0,  "end": 90.0,  "shader": "wireframe.glsl","transition": "glitch"},
    {"id": "city",     "start": 90.0,  "end": 150.0, "shader": "city.glsl",     "transition": "zoom"},
    {"id": "dissolve", "start": 150.0, "end": 180.0, "shader": "fluid.glsl",    "transition": "fade"},
]

# ─── Camera keyframes (Motus) ────────────────────────────────────
CAMERA_KEYS = [
    {"t": 0,    "pos": [0,0,5],   "target": [0,0,0],   "fov": 60},
    {"t": 30,   "pos": [0,0,3],   "target": [0,0,0],   "fov": 75},
    {"t": 90,   "pos": [0,2,8],   "target": [0,0,-10], "fov": 50},
    {"t": 150,  "pos": [0,0.5,2], "target": [0,5,-20], "fov": 40},
    {"t": 180,  "pos": [0,0,5],   "target": [0,0,0],   "fov": 60},
]

# ─── Color Matrix ────────────────────────────────────────────────
PALETTES = {
    "fluid":    {"base": [0.10,0.00,0.20], "a1": [1.0,0.40,0.00], "a2": [0.00,0.80,1.0]},
    "wire":     {"base": [0.00,0.07,0.00], "a1": [0.80,1.0,0.00], "a2": [1.0,0.53,0.00]},
    "city":     {"base": [0.00,0.03,0.07], "a1": [0.00,0.40,1.0], "a2": [0.00,1.0,1.0]},
    "dissolve": {"base": [0.10,0.00,0.20], "a1": [1.0,0.00,0.40], "a2": [0.40,0.00,1.0]},
}

# ─── Generate timeline.json (runtime consumption) ────────────────
timeline = {"scenes": SCENES, "camera": CAMERA_KEYS, "palettes": PALETTES}
Path("build/timeline.json").write_text(json.dumps(timeline, indent=2))

# ─── Generate C++ scene table ────────────────────────────────────
cpp = """
// AUTO-GENERATED by build_pipeline.py — DO NOT EDIT
#include "scene_manager.h"

static const SceneDef g_scenes[] = {
"""
for s in SCENES:
    cpp += f'    {{"{s["id"]}", {s["start"]}f, {s["end"]}f, "{s["shader"]}", Transition::{s["transition"].upper()}}},\n'
cpp += "};\n"
cpp += f"const int g_scene_count = {len(SCENES)};\n"
Path("build/scenes_table.cpp").write_text(cpp)

print(f"[build] Generated {len(SCENES)} scenes, {len(CAMERA_KEYS)} camera keys")
```

**3.2 C++ — Runtime (Uroboros + Scene Manager + Motus + Color Matrix)**

```cpp
// uroboros_main.cpp — главный цикл
#include <GL/gl3w.h>
#include <GLFW/glfw3.h>
#include <cmath>
#include <cstdio>
#include "scene_manager.h"
#include "motus.h"
#include "color_matrix.h"
#include "audio_sync.h"

static const float DEMO_DURATION = 180.0f;

int main() {
    glfwInit();
    GLFWwindow* win = glfwCreateWindow(1920, 1080, "Synthetic Dreams", nullptr, nullptr);
    glfwMakeContextCurrent(win);
    gl3wInit();

    SceneManager  sm(g_scenes, g_scene_count);
    Motus         motus(g_camera_keys, g_camera_key_count);
    ColorMatrix   colors(g_palettes);
    AudioSync     audio("track.wav");

    double t0 = glfwGetTime();

    while (!glfwWindowShouldClose(win) && (glfwGetTime() - t0) < DEMO_DURATION + 3.0) {
        double t = glfwGetTime() - t0;

        // Uroboros: dispatch
        SceneState state = sm.evaluate((float)t);
        Camera     cam   = motus.sample((float)t);
        Palette    pal   = colors.get(state.scene_id);
        float      beat  = audio.beat_intensity((float)t);

        // Render active scene
        state.shader->bind();
        state.shader->set_uniform("u_time",     (float)t);
        state.shader->set_uniform("u_beat",     beat);
        state.shader->set_uniform("u_cam_pos",  cam.pos);
        state.shader->set_uniform("u_cam_target", cam.target);
        state.shader->set_uniform("u_fov",      cam.fov);
        state.shader->set_uniform("u_base",     pal.base);
        state.shader->set_uniform("u_accent1",  pal.a1);
        state.shader->set_uniform("u_accent2",  pal.a2);

        // Fullscreen triangle
        glDrawArrays(GL_TRIANGLES, 0, 3);

        // Crossfade transition
        if (state.transition_active) {
            sm.render_transition(state, pal);
        }

        // Ending fade
        if (t > DEMO_DURATION) {
            float fade = std::min(1.0f, (float)(t - DEMO_DURATION) / 3.0f);
            // apply fade via post-process
        }

        glfwSwapBuffers(win);
        glfwPollEvents();
    }

    glfwTerminate();
    return 0;
}
```

```cpp
// scene_manager.h
#pragma once
#include "shader.h"

enum class Transition { FADE, GLITCH, ZOOM, NONE };

struct SceneDef {
    const char* id;
    float start, end;
    const char* shader_path;
    Transition transition;
};

struct SceneState {
    const char* scene_id;
    Shader*     shader;
    bool        transition_active;
    float       transition_t; // 0..1
    Transition  transition_type;
};

class SceneManager {
    const SceneDef* scenes;
    int count;
    int current_idx = 0;
public:
    SceneManager(const SceneDef* s, int n) : scenes(s), count(n) {}

    SceneState evaluate(float t) {
        // find active scene
        for (int i = 0; i < count; ++i) {
            if (t >= scenes[i].start && t < scenes[i].end) {
                current_idx = i;
                break;
            }
        }
        const SceneDef& s = scenes[current_idx];
        SceneState st;
        st.scene_id = s.id;
        st.shader   = ShaderCache::get(s.shader_path);
        st.transition_active = false;
        st.transition_t = 0.0f;
        st.transition_type = s.transition;

        // 1.5s transition at scene boundaries
        float trans_dur = 1.5f;
        if (t < s.start + trans_dur && current_idx > 0) {
            st.transition_active = true;
            st.transition_t = (t - s.start) / trans_dur;
        } else if (t > s.end - trans_dur && current_idx < count - 1) {
            st.transition_active = true;
            st.transition_t = (s.end - t) / trans_dur;
        }
        return st;
    }

    void render_transition(const SceneState& st, const Palette& pal) {
        // FBO crossfade or shader-based glitch
        // depends on st.transition_type
    }
};
```

```cpp
// motus.h — camera interpolation
#pragma once
#include <glm/glm.hpp>
#include <glm/gtc/quaternion.hpp>

struct CameraKey {
    float t;
    glm::vec3 pos, target;
    float fov;
};

struct Camera {
    glm::vec3 pos, target;
    float fov;
};

class Motus {
    const CameraKey* keys;
    int n;
public:
    Motus(const CameraKey* k, int count) : keys(k), n(count) {}

    Camera sample(float t) const {
        // find bracket
        int i = 0;
        while (i < n - 1 && keys[i+1].t < t) ++i;
        if (i >= n - 1) return {keys[n-1].pos, keys[n-1].target, keys[n-1].fov};

        const CameraKey& a = keys[i];
        const CameraKey& b = keys[i+1];
        float f = (t - a.t) / (b.t - a.t);
        f = f*f*(3 - 2*f); // smoothstep

        Camera c;
        c.pos    = glm::mix(a.pos,    b.pos,    f);
        c.target = glm::mix(a.target, b.target, f);
        c.fov    = glm::mix(a.fov,    b.fov,    f);
        return c;
    }
};
```

```cpp
// color_matrix.h
#pragma once
#include <glm/glm.hpp>
#include <unordered_map>
#include <string>

struct Palette {
    glm::vec3 base, a1, a2;
};

class ColorMatrix {
    std::unordered_map<std::string, Palette> db;
public:
    void add(const char* id, glm::vec3 b, glm::vec3 x, glm::vec3 y) {
        db[id] = {b, x, y};
    }
    Palette get(const char* id) const {
        auto it = db.find(id);
        return it != db.end() ? it->second : Palette{{0,0,0},{1,1,1},{1,1,1}};
    }
};
```

**3.3 GLSL — Шейдеры для трёх сцен**

```glsl
// shaders/fluid.glsl — Scene 1 & 4 (image 3)
#version 330 core
out vec4 fragColor;
uniform float u_time;
uniform vec3  u_base, u_accent1, u_accent2;
uniform vec2  u_resolution;

// FBM + domain warping
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
float noise(vec2 p){
    vec2 i=floor(p), f=fract(p);
    f=f*f*(3.0-2.0*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),
               mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);
}
float fbm(vec2 p){
    float v=0.0, a=0.5;
    for(int i=0;i<6;i++){ v+=a*noise(p); p*=2.0; a*=0.5; }
    return v;
}

void main(){
    vec2 uv = (gl_FragCoord.xy - 0.5*u_resolution) / u_resolution.y;
    vec2 q = vec2(fbm(uv + u_time*0.1), fbm(uv + vec2(1.7,9.2) + u_time*0.15));
    vec2 r = vec2(fbm(uv + 4.0*q + vec2(1.7,9.2) + u_time*0.2),
                  fbm(uv + 4.0*q + vec2(8.3,2.8) + u_time*0.25));
    float f = fbm(uv + 4.0*r);

    vec3 col = mix(u_base, u_accent1, clamp(f*f*4.0, 0.0, 1.0));
    col = mix(col, u_accent2, clamp(length(q), 0.0, 1.0));
    col = mix(col, vec3(1.0,0.8,0.4), clamp(length(r.x), 0.0, 1.0));

    fragColor = vec4(col, 1.0);
}
```

```glsl
// shaders/wireframe.glsl — Scene 2 (image 2)
#version 330 core
out vec4 fragColor;
uniform float u_time, u_beat;
uniform vec3  u_base, u_accent1, u_accent2;
uniform vec2  u_resolution;

float sdTri(vec2 p, float r){
    vec2 q = abs(p) - vec2(r, r*0.577);
    return length(max(q,0.0)) + min(max(q.x,q.y),0.0);
}

void main(){
    vec2 uv = (gl_FragCoord.xy - 0.5*u_resolution) / u_resolution.y;
    uv *= 3.0;

    // rotating triangle grid
    float a = u_time*0.3;
    mat2 rot = mat2(cos(a),-sin(a),sin(a),cos(a));
    vec2 p = rot * uv;

    vec2 id = floor(p + 0.5);
    vec2 fp = fract(p + 0.5) - 0.5;

    float d = sdTri(fp*2.0, 0.9);
    float edge = smoothstep(0.02, 0.0, abs(d));

    vec3 col = u_base;
    col += u_accent1 * edge * (0.8 + 0.4*u_beat);
    col += u_accent2 * edge * 0.3;

    // scanlines
    col *= 0.85 + 0.15*sin(gl_FragCoord.y*1.5);
    // chromatic aberration
    float ca = 0.003 * (1.0 + u_beat);
    col.r = mix(col.r, col.r*1.2, edge*ca*100.0);

    fragColor = vec4(col, 1.0);
}
```

```glsl
// shaders/city.glsl — Scene 3 (image 1)
#version 330 core
out vec4 fragColor;
uniform float u_time, u_beat;
uniform vec3  u_base, u_accent1, u_accent2;
uniform vec2  u_resolution;
uniform vec3  u_cam_pos, u_cam_target;
uniform float u_fov;

float sdBox(vec3 p, vec3 b){ vec3 q=abs(p)-b; return length(max(q,0.0))+min(max(q.x,max(q.y,q.z)),0.0); }
float sdRoundBox(vec3 p, vec3 b, float r){ return sdBox(p,b)-r; }

float map(vec3 p){
    // ground
    float d = p.y + 2.0;

    // repeated towers
    vec3 q = p;
    q.xz = mod(q.xz + 8.0, 16.0) - 8.0;
    float h = 20.0 + 15.0*sin(q.x*0.7 + q.z*0.5);
    float tower = sdRoundBox(q - vec3(0, h*0.5, 0), vec3(1.5, h*0.5, 1.5), 0.3);
    d = min(d, tower);

    // rain particles (cheap)
    float rain = 0.0;
    for(int i=0;i<3;i++){
        vec3 rp = p + vec3(0, fract(u_time*2.0 + float(i)*0.33)*30.0 - 15.0, 0);
        rp.xz = mod(rp.xz, 4.0) - 2.0;
        rain += smoothstep(0.05, 0.0, length(rp.xz));
    }
    d = min(d, rain*0.1 - 0.05);
    return d;
}

vec3 normal(vec3 p){
    vec2 e = vec2(0.01,0);
    return normalize(vec3(map(p+e.xyy)-map(p-e.xyy),
                          map(p+e.yxy)-map(p-e.yxy),
                          map(p+e.yyx)-map(p-e.yyx)));
}

void main(){
    vec2 uv = (gl_FragCoord.xy - 0.5*u_resolution) / u_resolution.y;
    vec3 ro = u_cam_pos;
    vec3 ta = u_cam_target;
    vec3 ww = normalize(ta-ro);
    vec3 uu = normalize(cross(ww, vec3(0,1,0)));
    vec3 vv = cross(uu, ww);
    vec3 rd = normalize(uv.x*uu + uv.y*vv + 1.5*ww);

    float t = 0.0;
    vec3 p;
    for(int i=0;i<80;i++){
        p = ro + rd*t;
        float d = map(p);
        if(d<0.001) break;
        t += d;
        if(t>100.0) break;
    }

    vec3 col = u_base;
    if(t<100.0){
        vec3 n = normal(p);
        float dif = max(dot(n, normalize(vec3(1,1,0.5))), 0.0);
        col = u_base * 0.3 + u_accent1 * dif * 0.5;

        // neon windows
        float windows = step(0.7, fract(p.y*2.0)) * step(0.7, fract(p.x*3.0));
        col += u_accent2 * windows * 0.8;

        // fog
        col = mix(col, u_base, 1.0-exp(-t*0.02));
    }

    // bloom-ish bright pass
    col += u_accent1 * u_beat * 0.1;

    fragColor = vec4(col, 1.0);
}
```

---

**4. Рекомендации: как обойти ограничения пайплайна**

**4.1 Cozy Engine — выход за рамки «зашитых» SDF**

**Проблема:** Cozy Engine v1.2 спроектирован вокруг фиксированного набора атомов (sofa, fireplace, warm_light → sdRoundBox, flame particles, bloom). Это ограничивает креативность.

**Решения:**

| Стратегия | Описание | Пример |
|---|---|---|
| **SDF Composition DSL** | Добавить операторы union/intersection/subtraction/smooth-min как first-class atoms | `Atom("city_block") = smooth_union(tower, tower, k=0.3)` |
| **Domain Warping Atoms** | Атомы, которые не рисуют форму, а искажают UV/поле | `Atom("fluid_warp") = warp(fbm, strength=2.0)` |
| **Particle Atoms** | Не SDF, а точечные эмиттеры с физикой | `Atom("rain") = emit(count=2000, gravity=9.8, life=2.0)` |
| **Procedural Grid Atoms** | Repeat + jitter для city/wireframe | `Atom("tower_grid") = repeat(sdBox, cell=16.0, jitter=0.3)` |
| **Runtime Parameterization** | Атомы принимают uniform-параметры из Motus/beat | `Atom("pulse_tri").scale = 1.0 + 0.3*beat` |
| **Shader Macro Expansion** | Python-генератор разворачивает атомы в GLSL-код до компиляции | `{{atom.fluid_warp | render}}` → полный GLSL |

**Практический приём — «Atom as Function»:**

```python
# вместо жёсткого маппинга atom → SDF
class Atom:
    def __init__(self, kind, **params):
        self.kind = kind            # "sdf" | "warp" | "particle" | "field"
        self.params = params        # свободно расширяемо
        self.compose = None         # optional: функция композиции

    def to_glsl(self, var_name="p"):
        if self.kind == "sdf":
            return f"sd{self.params['shape'].capitalize()}({var_name}, ...)"
        elif self.kind == "warp":
            return f"domain_warp({var_name}, strength={self.params['strength']})"
        elif self.kind == "particle":
            return f"particle_field({var_name}, count={self.params['count']})"
```

**4.2 Scene Manager — динамические сцены**

- **Nested scenes:** сцена внутри сцены (picture-in-picture через FBO)
- **Conditional scenes:** ветвление по beat intensity (`if beat > 0.8 → switch to climax`)
- **Procedural transitions:** не только fade/glitch/zoom, но и shader-driven morph между двумя шейдерами через shared uniforms

**4.3 Motus — не только камера**

Расширить Motus до управления **любыми** параметрами:
- camera pos/fov
- shader uniforms (warp strength, particle count)
- color palette interpolation
- audio reverb/delay

```python
class Motus:
    def __init__(self):
        self.tracks = {}  # name -> list of keyframes

    def add_track(self, name, keys):
        self.tracks[name] = keys

    def sample_all(self, t):
        return {name: self.interpolate(keys, t) for name, keys in self.tracks.items()}
```

**4.4 Color Matrix — динамические палитры**

- **Inter-palette blending:** плавный переход между палитрами сцен (не резкий switch)
- **Beat-reactive accent:** `accent1 = base_palette.a1 * (1 + 0.5*beat)`
- **Emotion curves:** вместо фиксированных цветов — кривые настроения (tension, warmth, energy) → map → RGB

**4.5 Uroboros — гибкий оркестратор**

- **Event bus:** сцены подписываются на события (`on_beat`, `on_transition`, `on_climax`)
- **Hot-reload шейдеров:** в dev-режиме — перезагрузка `.glsl` без рестарта
- **Deterministic mode:** фиксированный seed для рендера превью/скриншотов

**4.6 Обход лимита 64K**

- **Shader compression:** Crinkler + ручная минификация GLSL (убрать пробелы, короткие имена uniform)
- **Procedural textures:** никаких PNG — всё через FBM/noise
- **Shared code:** один `common.glsl` с FBM/SDF-примитивами, инклюдится во все сцены
- **Music:** C99 synth ~4K, остаётся ~60K на visuals

---

**5. Итоговая структура проекта**

```
synthetic_dreams/
├── design/
│   ├── build_pipeline.py       # Python: генерация timeline + C++ таблиц
│   ├── scene_definition.py
│   ├── motus_timeline.py
│   └── color_matrix.py
├── src/
│   ├── uroboros_main.cpp       # C++: главный цикл
│   ├── scene_manager.h/.cpp
│   ├── motus.h
│   ├── color_matrix.h
│   ├── audio_sync.h
│   └── shader_cache.h
├── shaders/
│   ├── common.glsl             # shared FBM, SDF primitives
│   ├── fluid.glsl
│   ├── wireframe.glsl
│   └── city.glsl
├── build/
│   ├── timeline.json           # generated
│   └── scenes_table.cpp        # generated
└── README.md
```

**Build:**
```bash
python design/build_pipeline.py          # генерация
cl /MT /O2 /Isrc src/*.cpp build/scenes_table.cpp /link opengl32.lib glfw3.lib
upx --brute synthetic_dreams.exe         # сжатие до ~60K
```

**Результат:** ~20 часов работы, 64K .exe, 3 минуты, 4 сцены, три визуальных мира из референсов — от fluid dream через neon wireframe к cyber city и обратно.
