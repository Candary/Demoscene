# Uroboros Visual Debugger

**Patch:** `uroboros/patches/visual_debugger.py`
**HTML:** `uroboros/visual_debug.html`

Встроенный в Uroboros визуальный дебаггер. Позволяет делать скриншоты
сцен автоматически (через headless Chrome + WebGL2), без необходимости
запускать демо вручную и загружать BMP-скриншоты.

## Архитектура

```
visual_debugger.py (Uroboros patch)
├── _ensure_http_server() — in-process Python http.server (serves /home/z/my-project)
├── _open_url(url) — agent-browser open <url>
├── _eval_js("window.frameReady") — poll for ready signal
├── _screenshot(path) — agent-browser screenshot
└── analyze_screenshot(path) — PIL CV analysis (brightness, hue, visible %)

visual_debug.html (WebGL2)
├── Reads URL params: scene, t, uPrimaryColor, uAccentColor, ...
├── fetch('/demo_intro_v61/shaders/<effect>.frag')
├── Convert GL 3.3 → GL ES 3.0 (strip #version 330 core, add precision)
├── Compile + link WebGL2 program
├── Render ONE frame at time T
└── Set window.frameReady = true + postMessage('READY')
```

## Запуск (standalone)

### Захват одной сцены

```bash
python3 uroboros/patches/visual_debugger.py \
    --scene s1 \
    --t 7 \
    --uPrimaryColor 0.05,0.10,0.30 \
    --uAccentColor 0.20,0.60,0.90 \
    --uIntensity 1.5 \
    --uSeed 11111 \
    --output-dir /tmp/vdebug
```

### Захват всех 7 сцен

```bash
python3 uroboros/patches/visual_debugger.py \
    --output-dir /tmp/vdebug
```

### Захват из .smt файла (с пользовательскими uniform'ами)

```bash
python3 uroboros/patches/visual_debugger.py \
    --smt /home/z/my-project/download/demo_intro_v61/demo.smt \
    --output-dir /tmp/vdebug
```

## Запуск (как Uroboros patch)

```python
from uroboros.patches.visual_debugger import apply

result = apply({}, {
    "scenes": [
        {"id": "s1", "t": 7.0,
         "uniforms": {"uPrimaryColor": [0.05, 0.10, 0.30],
                      "uAccentColor": [0.20, 0.60, 0.90],
                      "uIntensity": 1.5}},
        # ... more scenes
    ],
    "output_dir": "/tmp/vdebug",
    "width": 1280,
    "height": 720,
})

# result = {
#   "source": "param",
#   "output_dir": "/tmp/vdebug",
#   "screenshots": [{scene, effect, t, path, ready, analysis}, ...],
#   "summary": {total, succeeded, failed, verdicts, dark_scenes, bright_scenes}
# }
```

## Параметры URL для visual_debug.html

| Param | Default | Description |
|-------|---------|-------------|
| `scene` | nebula_raymarch | Effect name (matches .frag filename) |
| `t` | 5.0 | Time T (seconds) to render at |
| `shaderPath` | /demo_intro_v61/shaders/<scene>.frag | Path to .frag file |
| `width` | 1280 | Canvas width |
| `height` | 720 | Canvas height |
| `uPrimaryColor` | — | r,g,b floats 0..1 |
| `uAccentColor` | — | r,g,b floats 0..1 |
| `uColor` | — | r,g,b floats 0..1 |
| `uLightColor` | — | r,g,b floats 0..1 |
| `uIntensity` | — | float |
| `uMotionSpeed` | — | float |
| `uWarmth` | — | float |
| `uPulse` | — | float |
| `uSeed` | 2026 | int |

## CV analysis output

Каждый скриншот анализируется PIL:

```python
{
    "avg_brightness": 54.11,         # 0..255, средняя яркость всех пикселей
    "max_brightness": 153.0,         # 0..255, brightest pixel
    "visible_pct": 99.15,            # % pixels with brightness > 30
    "center_avg": 61.02,             # avg brightness in center 30% region
    "hue_dominant": "blue",          # dominant hue among visible pixels
    "hue_distribution": {            # fraction of each hue
        "red": 0.0, "yellow": 0.0, "green": 0.0,
        "cyan": 0.001, "blue": 0.999, "purple": 0.0, "gray": 0.0
    },
    "verdict": "ok",                 # pitch_black / too_dark / dark / ok / bright / too_bright
    "resolution": [1280, 577]
}
```

## Verdict thresholds

| Verdict | avg brightness |
|---------|----------------|
| pitch_black | < 5 |
| too_dark | 5-15 |
| dark | 15-30 |
| ok | 30-100 |
| bright | 100-200 |
| too_bright | > 200 |

## Time T formula

User requirement: "screenshot when scene loads + 2 seconds".

For each scene in the demo timeline:
- T_capture = clip.start_time + 2.0

Default capture times (matching v61 demo.smt):
- s1 nebula: 0 + 2 = 2s (LOW quality, 24 steps) — but I use 7s for HIGH quality
- s2 sphere: 25 + 2 = 27s
- s3 particles: 50 + 2 = 52s
- s4 anxiety: 75 + 2 = 77s
- s5 morph_grid: 100 + 2 = 102s
- s6 cozy_room: 127 + 2 = 129s
- s7 morphing_figures: 181 + 2 = 183s

## Интеграция с vlm_feedback_loop.py

Visual debugger можно использовать вместо conformance binary для
визуальной верификации (вместо проверки только uniform values):

```python
# In vlm_feedback_loop.py (future integration):
from uroboros.patches.visual_debugger import apply as visual_debug_apply

# After bake:
debug_result = visual_debug_apply({}, {
    "smt_path": smt_path,
    "output_dir": "/tmp/vlm_shots",
})

# Use debug_result["summary"]["dark_scenes"] for verdict
# instead of uniform-only analysis
```

## Зависимости

- `agent-browser` (CLI tool, /usr/local/bin/agent-browser)
- `PIL` (Python Pillow, для CV анализа)
- Headless Chrome (управляется agent-browser)
- WebGL2 (Chrome с `--use-angle=swiftshader-webgl`)

## Ограничения

1. Shader porting: GL 3.3 → GL ES 3.0 — автоматически стрипается `#version 330 core`,
   добавляются precision qualifiers. Сложные layout qualifiers могут требовать
   ручной правки.
2. Headless Chrome + SwiftShader: производительность ниже чем GPU, но
   достаточно для single-frame capture.
3. preserveDrawingBuffer: true обязательно для screenshot (иначе canvas пустой).
4. localhost: Chrome может блокировать `localhost` — используйте `127.0.0.1`.
