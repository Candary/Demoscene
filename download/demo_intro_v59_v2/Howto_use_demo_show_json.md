# Как используется demo.show.json

## Pipeline

```
demo.show.json          ← SOURCE: человекочитаемый spec (редактируете вы)
       ↓
  ShowSession.compile() ← валидация + разрешение ссылок
       ↓
  plan(resolved, cat)   ← планирование сегментов и ops
       ↓
  bake(resolved, ...)   ← компиляция в canonical format
       ↓
  to_smt(baked)         ← конвертация в текстовый .smt
       ↓
demo.smt                ← OUTPUT: машинный формат (читает C++ runtime)
```

**C++ runtime читает ТОЛЬКО `.smt`** — `demo.show.json` ему не нужен.

## Роль каждого файла

| Файл | Аналог | Кто читает | Назначение |
|------|--------|-----------|------------|
| `demo.show.json` | **исходный код** (.c) | Python toolchain | Редактирование, валидация, version control |
| `demo.smt` | **бинарник** (.exe) | C++ runtime | Запуск демо |
| `demo.baked.json` | **object file** (.o) | Python (intermediate) | Canonical data для сверки |

## Что внутри show JSON (v59-v2)

```json
{
  "meta": { "duration": 211, "resolution": [1280, 720], ... },
  "audio": { "bpm": 128.0, ... },
  "palettes": { "p": { "primary": "#000000", ... } },
  "clips": [
    { "id": "s1", "effect": "nebula_raymarch", "start": 0, "duration": 25,
      "map": { "uPrimaryColor": [0.988, 0.235, 0.220], ... } },
    ...
  ]
}
```

## Структура show JSON

### Верхний уровень

```json
{
  "format": "scene-manager/1",
  "meta": { ... },
  "audio": { ... },
  "palettes": { ... },
  "looks": {},
  "tracks": [ ... ],
  "clips": [ ... ]
}
```

### meta — глобальные настройки

```json
"meta": {
  "title": "My Demo",
  "duration": 211,
  "resolution": [1280, 720],
  "fps": 60,
  "seed": 2026,
  "prewarm": 3.0
}
```

### audio — музыка

```json
"audio": {
  "bpm": 128.0,
  "offset": 0.0,
  "beats_per_bar": 4,
  "markers": []
}
```

### palettes — цветовые палитры

```json
"palettes": {
  "p_nebula": {
    "primary": "#0c1a4d",
    "accent": "#3399e6",
    "text": "#ffffff",
    "bg": "#000000"
  }
}
```

Цвета в палитре указываются в **sRGB hex**. Python конвертирует их в **linear RGB** для шейдеров. Если нужен точный float, используйте `map`.

### tracks — дорожки

```json
"tracks": [
  {"id": "main", "order": 10},
  {"id": "post", "order": 25},
  {"id": "evt",  "order": 30}
]
```

`order` определяет приоритет рендеринга. Меньше = раньше.

### clips — главный массив

Каждый клип — один визуальный элемент на таймлайне:

```json
{
  "id": "s1",
  "track": "main",
  "kind": "scene",
  "effect": "nebula_raymarch",
  "start": 0,
  "duration": 25,
  "palette": "p_nebula",
  "map": { ... },
  "prewarm": 1.0
}
```

#### kind = "scene"

```json
{"id": "s1", "track": "main", "kind": "scene",
 "effect": "nebula_raymarch", "start": 0, "duration": 25,
 "palette": "p_nebula",
 "map": {
   "uPrimaryColor": [0.05, 0.10, 0.30],
   "uAccentColor":  [0.20, 0.60, 0.90],
   "uIntensity":    0.8,
   "uMotionSpeed":  1.0,
   "uPulse":        0.0
 }}
```

#### kind = "transition"

```json
{"id": "t1", "track": "main", "kind": "transition",
 "effect": "crossfade", "start": 23, "duration": 4,
 "between": ["s1", "s2"],
 "palette": "p", "map": {}}
```

#### kind = "post"

```json
{"id": "blm", "track": "post", "kind": "post",
 "effect": "bloom", "start": 0, "duration": 211,
 "map": {"uThreshold": 0.6, "uIntensity": 1.0, "uRadius": 4.0}}
```

#### kind = "event"

```json
{"id": "fin", "track": "evt", "kind": "event",
 "effect": "finish", "start": 211, "duration": 0}
```

## map — override uniforms

`map` — это dict `{uniform_name: value}`:

| Тип | Формат | Пример |
|-----|--------|--------|
| float | число | `"uIntensity": 0.8` |
| vec3 (color) | список 3 чисел | `"uColor": [0.1, 0.5, 0.8]` |
| Expression | строка | `"uOrbit": "mod(t * 0.3, 6.2832)"` |
| int | число | `"uSeed": 11111` |

Если uniform не в `map`: Python берёт значение из **effect manifest** (`.effect.json` файл).

## Expressions — динамические uniforms

```json
"map": {
  "uBeatKick": "pow(1.0 - audio.beat_phase, 3.0)",
  "uOrbit":    "mod(t * 0.3, 6.2832)",
  "uIntensity": "0.8 + energy * 0.2"
}
```

### Доступные переменные

| Переменная | Что |
|------------|-----|
| `t` | clip time = T - nom_start |
| `p` | progress = t / duration |
| `dur` | clip duration |
| `time` | global time T |
| `energy` | audio.energy |
| `audio.beat` | beat count |
| `audio.beat_phase` | 0..1 within beat |
| `audio.bar_phase` | 0..1 within bar |
| `audio.section` | section index |

### Доступные функции

`sin`, `cos`, `mod(a,b)`, `pow(a,b)`, `clamp(a,b,c)`, `smoothstep(a,b,c)`, `mix(a,b,c)`, `abs`, `floor`, `ceil`, `fract`, `sqrt`, `exp`, `min(a,b)`, `max(a,b)`, `step(a,b)`

## arrays — массивы (для cozy_room)

```json
{
  "id": "s6", "kind": "scene", "effect": "cozy_room_sdf",
  "start": 125, "duration": 55,
  "map": {"uLightColor": [1.0, 0.85, 0.6], "uCamAngle": 0.4},
  "arrays": {
    "uPrimitives": [0, 0, 5.0, 0.1, 5.0, ...]
  }
}
```

**Примечание**: Python baker может не включить `arrays` в output. В этом случае добавьте `arr uPrimitives` постпроцессором.

## Как изменить демо

### Вручную (редактируете show JSON)

```bash
# 1. Редактируете demo.show.json (меняете timing, цвета, эффекты)
# 2. Пересобираете .smt:
python3 -c "
from scene_manager.session import ShowSession
from scene_manager.bake import bake, to_smt
session = ShowSession.load('demo.show.json', cat)
resolved = session.compile()
smt = to_smt(bake(resolved, cat, session.show, plan(resolved, cat)))
open('demo.smt', 'w').write(smt)
"
```

### Программно (через ShowSession API)

```python
session = ShowSession.load('demo.show.json', cat)
session.dispatch("edit_show", {"ops": [
    {"op": "move_clip", "id": "s1", "start": 5},
]})
session.save('demo.show.json')
session.bake('output/')
```

## Timing — как вычисляются eff_start/eff_end

Python автоматически вычисляет:

```
eff_start = nom_start - prewarm
eff_end   = max(nom_start + duration, transition_end)
```

Пример: s2 с start=25, duration=25, prewarm=2:
- nom_start = 25
- eff_start = 25 - 2 = 23
- eff_end = 25 + 25 = 50 (или больше если transition extends)

## В нашем проекте

| Версия | show JSON | .smt | Как создан |
|--------|-----------|------|------------|
| v58 | нет | hand-written | Ручное написание .smt |
| v59 | нет | Python bake() | build_v59_v2.py → bake → .smt |
| v59-v2 | `demo.show.json` | Python bake() | Color Matrix → show JSON → bake → .smt |
| auto_demo | `demo.show.json` | Python bake() | build_demo.py → полный auto pipeline |

## Практическое использование

`demo.show.json` — это **source code вашего демо**. Коммитьте его в git, не .smt.

```bash
# Пример: поменять s1 duration с 25 на 30
sed -i 's/"start": 0, "duration": 25/"start": 0, "duration": 30/' demo.show.json
python3 rebuild_smt.py demo.show.json demo.smt
# .smt обновлён, всё валидировано
```
