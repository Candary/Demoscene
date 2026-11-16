

### 🧑‍💻 User

Напиши документацию по motus в формате markdown

### 🤖 Assistant

#### 🤔 Thought Process

The user wants documentation for `motus` in markdown format. I should write comprehensive documentation similar in style to the Uroboros_doc.md that was provided. Let me structure it well.

Key things to document:
1. What motus is
2. Installation
3. Architecture
4. Quick start
5. Concepts
6. API Reference
7. DSL/Free language
8. Extending
9. Integration with Uroboros
10. Limitations
11. FAQ

Let me write this comprehensively but not excessively verbose. The previous response already had `docs/README.md`, `docs/DESIGN.md`, `docs/DSL.md`, `docs/EXTENDING.md`. The user wants a full documentation file, likely consolidated or like the `Uroboros_doc.md` style.

I'll write a comprehensive `motus_doc.md` file that covers everything. It should be detailed, accurate to the code, and useful.

Let me be thorough and accurate with what's in the code:
- Runtime.submit / frame
- Scene with preorder, dirty flags
- Track with kinds, easings
- Binding with Mode phases, loops
- Channels registry with position, position.x/y/z, rotation, scale, scale.uniform, param.*
- Procedures: orbit, spin, pulse, drift
- Effects: burst, fountain, spiral (emitters), shockwave, vignette, grain (post), pulse (surface)
- Query: DSL verbs (new, set, anim, proc, fx, drop), free language
- Modes: dsl, free, auto
- Transport for beats/bars
- bake with mmap
- glsl shaders
- Adapter to Uroboros

Let me write comprehensive documentation. I'll follow the Uroboros_doc.md structure for consistency.

Important accuracy checks:
- `position.x` accepts float
- `rotation` accepts quat
- `scale` allows MUL
- `scale.uniform` allows MUL
- `param.*` allows MUL, defaults to FLOAT identity
- Mode phases: REPLACE=0, ADD=1, MUL=2
- Loops: hold, repeat, pingpong, once
- Animation keys in local time of binding
- `at` is absolute start
- `over` sets duration
- `from/to` sugar for two keys
- Free language uses verb segmentation
- `@name` for explicit entity
- Transport: bpm, offset, beats_per_bar
- Time units: `2`, `2s`, `500ms`, `beat:8`, `bar:2`
- Vector values: `(1,2,3)` with spaces ok
- Free state accumulates `clock` and `last` between submits

For the adapter - note that the adapter is a separate addition, should mention how to use it.

Let me write it now. I'll write in Russian since the user's messages are in Russian and the previous docs were in Russian.

#### 💡 Response

**motus — документация**

**Версия:** 0.1.0
**Python:** ≥ 3.8
**Зависимости:** только stdlib для ядра; `numpy` — опционально (только для частиц)

---

**Содержание**

1. [Что такое motus](#1-что-такое-motus)
2. [Гарантии (инварианты)](#2-гарантии-инварианты)
3. [Установка](#3-установка)
4. [Архитектура](#4-архитектура)
5. [Быстрый старт](#5-быстрый-старт)
6. [Концепции](#6-концепции)
   - 6.1 [Время и Transport](#61-время-и-transport)
   - 6.2 [Scene и иерархия](#62-scene-и-иерархия)
   - 6.3 [Track: keyframe-анимация](#63-track-keyframe-анимация)
   - 6.4 [Процедуры (procedural)](#64-процедуры-procedural)
   - 6.5 [Binding: биндинг источника к каналу](#65-binding-биндинг-источника-к-каналу)
   - 6.6 [Фазы блендинга](#66-фазы-блендинга)
   - 6.7 [События и переигровка](#67-события-и-переигровка)
   - 6.8 [Эффекты и частицы](#68-эффекты-и-частицы)
7. [Язык запросов (DSL)](#7-язык-запросов-dsl)
8. [Свободный язык](#8-свободный-язык)
9. [API Reference](#9-api-reference)
10. [Расширяемость](#10-расширяемость)
11. [Интеграция с Uroboros](#11-интеграция-с-uroboros)
12. [Кэш поз (bake)](#12-кэш-поз-bake)
13. [GLSL](#13-glsl)
14. [Ограничения](#14-ограничения)
15. [FAQ](#15-faq)

---

**1. Что такое motus**

`motus` — **детерминированный motion-core**, которым управляют **текстовым запросом**. Это не редактор и не формат файла: в центре — два метода.

```python
report = rt.submit(text)   # разобрать текст → применить мутации
plan   = rt.frame(t)       # вычислить кадр на момент t
```

`frame(t)` — **чистая функция времени**. Она не зависит от того, сколько раз её вызывали, в каком порядке и с какими `t` раньше. Это открывает:

- скраб в обе стороны без накопленных артефактов;
- точное совпадение offline-рендера и realtime-проигрывания;
- воспроизводимость в тестах и CI.

motus не рисует. Он возвращает `FramePlan` — данные для рендера (матрицы, параметры, частицы, post-эффекты). Адаптер к GL/Vulkan/софт-рендеру — отдельный слой.

---

**2. Гарантии (инварианты)**

Все инварианты покрыты исполняемыми тестами в `tests/test_motus.py`.

| # | Инвариант | Формулировка |
|---|---|---|
| **I1** | Determinism | `frame(t)` дважды даёт идентичный `FramePlan` |
| **I2** | Purity | Процедурный шум и частицы зависят только от `(t, seed, params)`, не от истории вызовов |
| **I3** | Framerate independence | Значения при 60 и 240 fps совпадают в общих точках |
| **I4** | Boundaries | `NaN`, `±inf`, `t` вне диапазона трека, пустой трек — всё clamp'ится, не падает |
| **I5** | Identity defaults | По умолчанию `scale=(1,1,1)`, `rot=(0,0,0,1)`, `pos=(0,0,0)`, а не ноль |
| **I6** | Blend algebra | `weight=0` → базовая поза; фазы `REPLACE→ADD→MUL` фиксированы |
| **I7** | Hierarchy | preorder O(N) совпадает с наивным перемножением родителей |
| **I8** | Replay | Перемотка назад переигрывает события; кадр не зависит от пути к нему |
| **I9** | Offline = realtime | Offline-сетка и realtime дают идентичные `FramePlan` |
| **I10** | Quaternion | slerp по кратчайшей дуге, результат нормализован |

---

**3. Установка**

```bash
# Клонировать / распаковать motus
cd motus

# Опционально — виртуальное окружение
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate

# Ядро: только stdlib
pip install -e .

# Частицы требуют numpy
pip install numpy
```

Проверка:

```bash
python -m motus selfcheck    # запускает tests/test_motus.py без pytest
python -m motus demo         # DSL + свободный язык, план кадров в консоль
```

Пример вывода `demo`:

```
=== DSL === ok: применено 8 команд (режим dsl)
  t= 0.0: objects=[ball, halo] stats={'entities': 2, 'drawn': 2, ...}
        pos=(0.0, 0.0, 0.0) params={'color': (1.0, 0.6, 0.2)}
  t= 0.5: objects=[ball, halo] ...
```

---

**4. Архитектура**

```
текст ──► query (роутер режима) ──► DSL ─┐
                                        ├─► Cmd[] (единый IR)
                            свободный ──┘
                                          │ submit: всё-или-ничего
                                          ▼
                            Runtime: события(at) + Binding(start) + Emitter(start)
                                          │ frame(t) — чистая функция t
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
              Animator.evaluate      Scene.update          EffectSystem.field
              (фазы blend)           (preorder O(N))       (закрытая форма, numpy)
                    └─────────────────────┼─────────────────────┘
                                          ▼
                                      FramePlan  ──► любой рендер (GL/Vulkan/софт)
```

| Файл | Ответственность |
|---|---|
| `core.py` | Ошибки + `Registry` (единственный механизм расширения) |
| `mathx.py` | vec3/quat/mat4, slerp, детерминированный хэш |
| `clock.py` | `Transport` (биты/такты), `fixed_frames`, `LiveClock` |
| `track.py` | Типизированные ключи, easing-реестр, безопасное семплирование |
| `scene.py` | Базовая поза vs вычисленная, preorder, dirty-флаги |
| `anim.py` | Каналы, процедуры, `Binding`, фазы блендинга |
| `effects.py` | Описание эффектов, эмиттеры, закрытая форма частиц |
| `query.py` | Лексер, DSL, свободный язык, роутер режимов |
| `runtime.py` | События + `frame(t)` → `FramePlan`, откат при ошибке |
| `bake.py` | Опциональный плоский кэш поз (mmap) |
| `glsl.py` | Опциональные шейдеры GLSL 330 core |

---

**5. Быстрый старт**

**5.1 Минимальный пример**

```python
from motus import Runtime

rt = Runtime()

print(rt.submit("""
new ball pos=(0,0,0) param.color=(1.0,0.6,0.2)
anim ball.position from=(0,0,0) to=(3,0,0) over=2 ease=smooth
proc ball.rotation spin rate=180
fx burst on=ball at=2 for=1.5 count=600 seed=7
"""))
# ok: применено 4 команд (режим auto)

plan = rt.frame(1.0)
for item in plan.items:
    print(item.name, item.world[12:15])   # позиция из column-major матрицы
```

**5.2 Свободный язык**

```python
rt = Runtime()
rt.submit("""
mode free
Создай шар, покрась в оранжевый.
Пусть летит вправо две секунды, потом взорвётся искрами и исчезнет.
""")

for t in (0.0, 1.0, 2.0, 2.6):
    print(t, [i.name for i in rt.frame(t).items])
```

**5.3 Смешанный режим**

```python
rt.submit("""
mode free
создай шар
mode dsl
anim ball.position from=(0,0,0) to=(1,0,0) over=1 ease=smooth
mode free
потом взорви искрами
""")
```

**5.4 Обработка ошибок**

```python
report = rt.submit("new a\nanim a.nosuch from=(0,0,0) to=(1,0,0)\n")
if not report.ok:
    for issue in report.issues:
        print(issue)   # QueryError с подсказками
# Состояние не изменилось: атомарность запроса гарантирована
```

**5.5 Offline-рендер кадров**

```python
from motus import Runtime, fixed_frames

rt = Runtime()
rt.submit("new a\nanim a.position from=(0,0,0) to=(4,0,0) over=1 ease=smooth\n")

for t in fixed_frames(fps=60, duration=2.0):
    plan = rt.frame(t)
    upload(plan)   # ваш рендер
```

**5.6 С музыкальной сеткой**

```python
from motus import Runtime, Transport

rt = Runtime(Transport(bpm=120.0, beats_per_bar=4))
rt.submit("""
new a
anim a.position from=(0,0,0) to=(1,0,0) at=beat:4 over=bar:1 ease=smooth
fx burst on=a at=bar:2 count=200
""")
# beat:4 = 2 сек, bar:1 = 2 сек, bar:2 = 4 сек
```

---

**6. Концепции**

**6.1 Время и Transport**

`Transport` — музыкальная сетка:

```python
from motus import Transport

tr = Transport(bpm=120.0, offset=0.0, beats_per_bar=4)
tr.seconds(4)   # 2.0 — четыре бита = 2 секунды
tr.beat(2.0)    # 4.0 — два секунды = четыре бита
tr.bar(2.0)     # 1.0 — два секунды = один такт
```

Время в DSL можно задавать в секундах или музыкальных единицах:

| Формат | Пример | Значение |
|---|---|---|
| Секунды | `2` | 2.0 сек |
| Секунды явно | `2s` | 2.0 сек |
| Миллисекунды | `500ms` | 0.5 сек |
| Биты | `beat:8` | 8 бит = 4 сек при 120 bpm |
| Такты | `bar:2` | 2 такта = 4 сек при 120 bpm и 4/4 |

`fixed_frames` — offline-сетка, совпадающая с realtime:

```python
from motus import fixed_frames

for t in fixed_frames(fps=60, duration=2.0, start=0.0):
    ...   # t = 0, 1/60, 2/60, ...
```

`LiveClock` — настенные часы, если нужен realtime:

```python
from motus import LiveClock

clock = LiveClock()
t = clock.now()
clock.seek(0.0)   # сбросить в ноль
```

**6.2 Scene и иерархия**

`Scene` — граф объектов. Каждый объект:

- `name` — уникальное имя;
- `parent` — ссылка на родителя (или None);
- `base` — базовая поза `(pos, rot, scale)`;
- `pose` — вычисленная поза на момент `frame(t)`;
- `params` — словарь пользовательских параметров (`param.color`, `param.glow`, ...);
- `alive` — флаг живого объекта (drop → False).

**Обход — O(N) preorder**. Порядок кэшируется, матрицы пересчитываются только у «грязных» поддеревьев (dirty flags).

```python
from motus import Scene

sc = Scene()
root = sc.add("root", pos=(1, 0, 0))
a    = sc.add("a", parent=root, pos=(0, 2, 0))
b    = sc.add("b", parent=a, pos=(0, 0, 3))
sc.update()

print(sc.world(b)[12:15])   # (1.0, 2.0, 3.0) — мировая позиция b
```

Матрицы **column-major**, готовы к `glUniformMatrix4fv(..., GL_FALSE, ...)`. Элемент `m[col*4 + row]`. Позиция — это `m[12:15]`.

**Цикл запрещён:**

```python
sc.set_parent(root, b)   # MotusError: цикл в иерархии
```

**6.3 Track: keyframe-анимация**

`Track` — типизированные ключи с безопасным семплированием:

```python
from motus import Kind, Track

tr = Track(Kind.VEC3, ease="smooth")
tr.key(0.0, (0, 0, 0))
tr.key(1.0, (1, 2, 3))
tr.key(2.0, (0, 1, 0))

tr.sample(0.5)     # интерполяция между keys
tr.sample(-100)    # первое значение (clamp)
tr.sample(1e9)     # последнее значение (clamp)
tr.sample(float('nan'))  # первое значение
```

**Типы:**

| Kind | Значение | Identity |
|---|---|---|
| `Kind.FLOAT` | `float` | `0.0` |
| `Kind.VEC3` | `(x, y, z)` | `(0, 0, 0)` |
| `Kind.QUAT` | `(x, y, z, w)` | `(0, 0, 0, 1)` |

**Easing-функции** (`EASINGS`):

- `linear` — линейная
- `smooth` — smoothstep `u²(3−2u)`
- `in` — `u²`
- `out` — `1−(1−u)²`
- `inout` — симметричная
- `step` — ступенька (первое значение до половины, потом второе)

Расширить можно через `EASINGS.add("my", lambda u: ...)`.

**6.4 Процедуры (procedural)**

Процедуры — **чистые функции** `(t, params, seed) → value`. Никакого состояния.

**Встроенные:**

| Имя | Kind | Параметры (default) | Что делает |
|---|---|---|---|
| `orbit` | VEC3 | `center=(0,0,0)`, `radius=1`, `speed=0.25`, `phase=0`, `bob=0` | Круговое движение в плоскости XZ |
| `spin` | QUAT | `axis=(0,1,0)`, `rate=90` (градусы/сек), `phase=0` | Равномерное вращение |
| `pulse` | FLOAT | `base=1`, `amp=0.15`, `freq=1`, `phase=0` | Синусоидальное пульсирование |
| `drift` | VEC3 | `base=(0,0,0)`, `amp=0.2`, `freq=0.35` | Гладкий шум (сумма синусов) |

```python
from motus import ProcCall

p = ProcCall("orbit", {"radius": 2.0}, seed=3)
p.sample(1.25)   # детерминировано: всегда одно и то же
p.sample(1.25)   # совпадает с первым вызовом
```

`seed` влияет только на `drift` (через `hash01`). Для `orbit`, `spin`, `pulse` seed не важен.

**6.5 Binding: биндинг источника к каналу**

`Binding` связывает **источник** (Track или ProcCall) с **каналом** конкретного объекта:

```python
from motus import Animator, Binding, Kind, Mode, Track

sc = Scene()
sc.add("ball")
an = Animator()

an.add(Binding(
    target="ball",
    channel="position",
    source=Track(Kind.VEC3).key(0.0, (0,0,0)).key(2.0, (3,0,0)),
    mode=Mode.REPLACE,
    weight=1.0,
    priority=0,
    start=0.0,
    duration=2.0,
    loop="hold",
))

an.evaluate(1.0, sc)   # применить биндинги на момент t=1.0
sc.update()            # пересчитать матрицы
```

**Поля Binding:**

| Поле | Тип | Смысл |
|---|---|---|
| `target` | str | Имя объекта |
| `channel` | str | Канал (`position`, `rotation`, `scale`, `param.glow`, ...) |
| `source` | Track \| ProcCall | Источник значений |
| `mode` | Mode | `REPLACE`, `ADD`, `MUL` |
| `weight` | float | 0..1 |
| `priority` | int | Порядок внутри фазы |
| `start` | float | Абсолютное время старта |
| `duration` | float | Длительность (0 = бесконечная) |
| `loop` | str | `hold` / `repeat` / `pingpong` / `once` |

**Локальное время биндинга:**

```python
b.local_time(t)  # t - start, с учётом loop
```

Ключи в `Track` задаются **в локальном времени биндинга**, а не в абсолютном.

**Каналы:**

| Канал | Kind | Add-identity | Mul |
|---|---|---|---|
| `position` | VEC3 | `(0,0,0)` | нет |
| `position.x` / `.y` / `.z` | FLOAT | `0.0` | нет |
| `rotation` | QUAT | identity | нет |
| `scale` | VEC3 | `(1,1,1)` | да |
| `scale.uniform` | FLOAT | `0.0` | да |
| `param.<имя>` | из значения | identity типа | да |

`param.<имя>` — **динамический канал**. Регистрировать не нужно, тип выводится из значения:

```python
# этот объект имеет params["color"] = (1, 0.6, 0.2) и params["glow"] = 0.5
rt.submit("""
new ball param.color=(1.0,0.6,0.2) param.glow=0.5
proc ball.scale.uniform pulse freq=2 mode=mul
proc ball.param.glow pulse base=0.5 amp=0.3
""")
```

**6.6 Фазы блендинга**

Порядок применения биндингов **фиксирован**:

```
REPLACE (phase=0) → ADD (phase=1) → MUL (phase=2)
```

Внутри фазы — сортировка по `priority` (возрастание), затем по `seq` (порядок добавления).

**Семантика режимов:**

| Mode | FLOAT | VEC3 | QUAT |
|---|---|---|---|
| **REPLACE** | `lerp(cur, value, w)` | `lerp(cur, value, w)` | `slerp(cur, value, w)` |
| **ADD** | `cur + (value − identity) * w` | `cur + (value − identity) * w` | `cur * slerp(ID, value, w)` |
| **MUL** | `cur * (1 + (value − 1) * w)` | поэлементно | (запрещён) |

Пример:

```python
an.add(Binding("ball", "position", move_track,   Mode.REPLACE, 1.0))
an.add(Binding("ball", "position", bob_track,    Mode.ADD,     0.5))
an.add(Binding("ball", "scale",    pulse_proc,   Mode.MUL,     1.0))
```

**6.7 События и переигровка**

**События** — команды с абсолютным временем `at`:

- `new` — создать объект
- `set` — изменить базовую позу или param
- `drop` — пометить неживым

События хранятся в отсортированном списке. `frame(t)`:

1. применяет все события с `at <= t`, которых ещё не применил;
2. если `t` меньше предыдущего кадра — **сбрасывает сцену** и переигрывает события с нуля;
3. вычисляет анимации и частицы.

Это гарантирует **I8 (Replay)**: кадр не зависит от пути к нему.

```python
rt.frame(3.0)   # перемотали вперёд
rt.frame(0.5)   # перемотали назад → сцена сброшена, события переиграны
rt.frame(3.0)   # снова вперёд — идентично первому вызову
```

**6.8 Эффекты и частицы**

**Типы эффектов:**

| Kind | Имена | Что делает |
|---|---|---|
| `emitter` | `burst`, `fountain`, `spiral` | Частицы |
| `post` | `shockwave`, `vignette`, `grain` | Пост-обработка |
| `surface` | `pulse` | Процедурный биндинг на `param.glow` |

**Emitter:** частицы считаются в **закрытой форме** от `(t, seed)` — без интегрирования:

```
pos(age)  = origin + direction * speed * age + 0.5 * gravity * age²
alpha(age) = (1 − age/life)^fade
size(age)  = size * (1 − shrink * age/life)
color(age) = color_a * (1 − k) + color_b * k
```

`direction`, `speed`, `life`, `delay` — все определяются через `hash01(seed, i, ...)`. Никакого состояния, никакой истории. **Скраб не ломает картинку.**

Эмиттер может быть привязан к объекту:

```python
rt.submit("new ball\nfx burst on=ball at=2 for=1.5 count=600\n")
```

**Post-эффекты** активны на `[start, start+duration)`:

```python
rt.submit("fx shockwave at=2 for=0.8 radius=0.4 strength=0.1\n")
```

**Частицы требуют numpy:**

```python
rt = Runtime(particles=False)   # без numpy: batches есть, данных нет
rt = Runtime(particles=True)    # по умолчанию
```

**GPU-ready формат:**

`Field.interleaved()` — 8 float32 на частицу: `pos3 + rgba4 + size1`. Stride 32 байта. Прямо в VBO.

---

**7. Язык запросов (DSL)**

**7.1 Режимы**

| Директива | Что делает |
|---|---|
| `mode dsl` | Дальше — структурированный DSL |
| `mode free` | Дальше — свободный текст (RU/EN) |
| `mode auto` | Определять по строке: первое слово — команда DSL? → dsl : free |

Директива действует до конца запроса **и запоминается в сессии** `Runtime.mode`. Внутри запроса можно переключаться:

```
mode free
создай шар
mode dsl
anim ball.position from=(0,0,0) to=(1,0,0) over=1
mode free
потом взорви искрами
```

По умолчанию — `auto`.

**7.2 Значения**

| Тип | Пример |
|---|---|
| Число | `2`, `-0.5`, `3.14` |
| Вектор | `(1,2,3)`, `(1, 2, 3)` (пробелы допустимы) |
| Кватернион | `(0,0,0,1)` (нормализуется) |
| Строка | `"text"` |
| Флаг | `true`, `false` |
| Время | `2`, `2s`, `500ms`, `beat:8`, `bar:2` |

Комментарии: `#` и `//` (до конца строки).

**7.3 Команды**

**`new`**

```
new <имя> [parent=<имя>] [at=<время>] [pos=(..)] [rot=(..)] [scale=(..)] [param.<k>=<v>]
```

Создаёт объект. `at` — момент появления; до него объект не существует.

```python
new ball pos=(0,0,0) param.color=(1.0,0.6,0.2)
new halo parent=ball pos=(0,0.6,0)
new late at=bar:2 pos=(0,0,0)
```

**`set`**

```
set <имя>.<канал> v=<значение> [at=<время>]
```

Меняет **базовую** позу или пользовательский параметр. Постоянное изменение.

```python
set ball.param.color v=(1.0,0.2,0.1) at=1
set ball.position v=(2,0,0) at=2
```

**`anim`**

```
anim <имя>.<канал> [k=<t>:<v> ...] [from=<v> to=<v> over=<d>]
     [at=<время>] [ease=<имя>] [mode=replace|add|mul] [weight=0..1]
     [loop=hold|repeat|pingpong|once] [prio=<int>]
```

Ключи — во **локальном** времени биндинга (`0` — момент `at`, `over` — конец). `from=/to=` — сахар для двух ключей `0` и `over`.

```python
anim ball.position from=(0,0,0) to=(3,0,0) over=2 ease=smooth
anim ball.rotation k=0:(0,0,0,1) k=1:(0,0.707,0,0.707) at=1 over=1
anim ball.scale from=(1,1,1) to=(2,2,2) over=0.5 mode=replace loop=pingpong
```

**`proc`**

```
proc <имя>.<канал> <процедура> [k=v ...] [at=..] [over=..] [mode=..] [weight=..] [seed=..]
```

Привязывает процедуру к каналу.

```python
proc ball.rotation spin rate=180 axis=(0,1,0)
proc halo.scale.uniform pulse base=1.0 amp=0.2 freq=2 mode=mul
proc ball.position orbit radius=2 speed=0.25 seed=7
```

**`fx`**

```
fx <эффект> [on=<имя>] [at=..] [for=<d>] [count=N] [seed=N] [origin=(..)] [k=v ...]
```

Эффект. Тип определяется по имени:

- emitter → эмиттер частиц;
- post → пост-проход;
- surface → процедурный биндинг.

```python
fx burst on=ball at=2 for=1.5 count=600 seed=7 speed=7
fx fountain on=ball at=0 for=3 count=400
fx spiral on=ball at=0 count=200 radius=1.2 turns=3
fx shockwave at=2 for=0.8 radius=0.4 strength=0.1
fx vignette at=0 amount=0.4
fx pulse on=ball at=0 for=2
```

**`drop`**

```
drop <имя> [at=<время>]
```

Помечает объект неживым. Анимации и привязанные эффекты замолкают. `id` не переиспользуется.

```python
drop ball at=3
```

---

**8. Свободный язык**

Свободный язык — **правила, не NLU**. Клауза режется по найденным **глаголам**, а не по союзам. Поэтому «взорвётся и исчезнет» = две команды.

**8.1 Глаголы**

| Глагол | Действие |
|---|---|
| создай, добавь, new, create, spawn, add | `new` |
| двигай, лети, move, animate, fly | `anim` позиции |
| вращай, крути, spin, rotate | `proc spin` |
| пульсируй, дыши, pulse | `proc pulse` |
| взорви, искры, фейерверк, burst, explode | `fx burst` |
| фонтан, струя, fountain | `fx fountain` |
| спираль, вихрь, spiral, vortex | `fx spiral` |
| ударная, волна, shockwave | `fx shockwave` |
| покрась, цвет, color, paint | `set param.color` |
| удали, убери, исчезни, remove, hide | `drop` |
| подожди, жди, wait | сдвиг курсора |

**8.2 Существительные → имена**

| Слово | Имя |
|---|---|
| шар, сфера, sphere, ball | `ball` |
| куб, cube, box | `box` |
| тор, torus | `torus` |
| точка, dot | `dot` |

**8.3 Цвета**

| Слово | RGB |
|---|---|
| оранжевый, orange | (1.0, 0.6, 0.2) |
| красный, red | (1.0, 0.15, 0.1) |
| синий, blue | (0.2, 0.4, 1.0) |
| голубой, cyan | (0.3, 0.8, 1.0) |
| зелёный, green | (0.3, 1.0, 0.4) |
| белый, white | (1.0, 1.0, 1.0) |

**8.4 Направления и числительные**

| Слово | Значение |
|---|---|
| вправо, right | `(2, 0, 0)` |
| влево, left | `(-2, 0, 0)` |
| вверх, up | `(0, 2, 0)` |
| вниз, down | `(0, -2, 0)` |
| полсекунды, секунду, две, два, три, ... | 0.5, 1.0, 2.0, 2.0, 3.0, ... |

**8.5 Примеры**

```python
rt.submit("""
mode free
создай шар, покрась в оранжевый
пусть летит вправо две секунды
потом взорвётся искрами
""")
```

Что произойдёт:

1. `new ball param.color=(1.0,0.6,0.2)` at=0
2. `anim ball.position from=(0,0,0) to=(2,0,0) over=2 ease=smooth` at=0
3. `fx burst on=ball at=2 for=1.5 count=400` at=2

**8.6 Явное имя объекта**

Префикс `@имя` задаёт объект напрямую:

```
создай @hero
двигай @hero вправо три секунды
```

**8.7 Состояние между запросами**

`Runtime` хранит `_free_state` между `submit`-вызовами: `clock` (курсор свободного языка) и `last` (последний созданный объект). Это позволяет:

```python
rt.submit("mode free\nсоздай шар")
rt.submit("mode free\nпокрась в красный")   # → красит тот же шар
```

**8.8 Атомарность**

Если хотя бы одно действие не распознано — **весь запрос отклонён**:

```python
rt.submit("mode free\nсоздай шар. покрась зелёным. взорви.")
# Report(ok=False, issues=[QueryError(...)])
# Состояние не изменилось
```

---

**9. API Reference**

**9.1 `Runtime`**

```python
from motus import Runtime, Transport

rt = Runtime(
    transport=Transport(bpm=120.0),
    mode="auto",              # dsl | free | auto
    max_particles=200_000,
    particles=True,           # False → без numpy
)
```

| Метод / атрибут | Возвращает | Описание |
|---|---|---|
| `submit(text)` | `Report` | Разобрать и применить. Всё-или-ничего. |
| `frame(t)` | `FramePlan` | Кадр на момент `t`. Чистая функция. |
| `.scene` | `Scene` | Текущая сцена |
| `.animator` | `Animator` | Текущие биндинги |
| `.effects` | `EffectSystem` | Текущие эмиттеры и посты |
| `.mode` | str | Текущий режим (запоминается между submit) |
| `.transport` | `Transport` | Музыкальная сетка |

**9.2 `Report`**

```python
report = rt.submit(text)
report.ok         # bool
report.applied    # int (кол-во команд)
report.issues     # list[QueryError]
report.mode       # str
str(report)       # human-readable
```

**9.3 `FramePlan`**

```python
plan = rt.frame(t)
plan.time     # float
plan.items    # list[DrawItem]
plan.batches  # list[Batch]
plan.posts    # list[Post]
plan.stats    # dict
```

**`DrawItem`:**

```python
item.entity   # int (id)
item.name     # str
item.world    # Mat4 (16 float, column-major)
item.params   # dict (param.* значения)
```

**`Batch`** (эмиттер):

```python
b.emitter   # int
b.effect    # str
b.count     # int
b.origin    # tuple (мировая позиция)
b.data      # Field | None (None если particles=False)
```

**`Post`** (пост-эффект):

```python
p.effect   # str
p.params   # dict (оценённые параметры)
```

**9.4 `Field` (частицы)**

```python
field = batch.data
field.pos     # numpy (N,3) float32
field.color   # numpy (N,4) float32 (rgb + alpha)
field.size    # numpy (N,) float32
field.alive   # int (кол-во живых)

field.interleaved()   # bytes: 8 float32 на частицу, stride 32
```

**9.5 `Scene`**

| Метод | Описание |
|---|---|
| `add(name, parent=None, *, pos, rot, scale, params)` | Создать объект → eid |
| `set_parent(child, parent)` | Изменить родителя (проверяет цикл) |
| `mark(eid)` | Пометить грязным |
| `reset_pose(eid)` | Вернуть в базовую позу |
| `drop(eid)` | Пометить неживым |
| `world(eid)` | Мировая матрица (column-major) |
| `update()` | Пересчитать грязные матрицы (O(N)) |
| `entity(eid)` | `Entity` |
| `find(name)` | eid или None |
| `id_of(name)` | eid или QueryError |
| `names()` | Список имён |
| `len(scene)` | Кол-во объектов |

**9.6 `Track`**

| Метод | Описание |
|---|---|
| `Track(kind, *, ease="linear", default=None)` | Создать |
| `.key(t, value)` | Добавить ключ (t строго возрастает) |
| `.keys(pairs)` | Добавить несколько |
| `.sample(t)` | Значение на момент t (безопасно на любых t) |
| `.span` | (first, last) |
| `len(track)` | Кол-во ключей |

**9.7 `Animator` и `Binding`**

**Binding** — см. [6.5](#65-binding-биндинг-источника-к-каналу).

**Animator:**

| Метод | Описание |
|---|---|
| `.add(binding, stack=False)` | Добавить. `stack=False` заменяет биндинги с тем же `(target, channel, mode)`. |
| `.clear_target(name)` | Удалить все биндинги объекта |
| `.evaluate(t, scene)` | Применить все биндинги → int (кол-во применённых) |
| `len(animator)` | Кол-во биндингов |

**9.8 `EffectSystem`**

| Метод | Описание |
|---|---|
| `.spawn(effect, *, origin, start, duration, count, seed, attach, **params)` | Создать эмиттер |
| `.post(effect, *, start, duration, **params)` | Создать пост-эффект |
| `.active_emitters(t)` | Живые эмиттеры |
| `.active_posts(t)` | Живые посты |

**9.9 `Registry`**

Единый механизм расширения. Подробнее — [10](#10-расширяемость).

```python
from motus import Registry

reg = Registry("my-kind")
reg.add("foo", obj)
reg.get("foo")              # obj или QueryError с подсказками
reg.find("foo")             # obj или None
reg.names()                 # ['foo', ...]
"foo" in reg                # True
len(reg)                    # 1
```

---

**10. Расширяемость**

Все подсистемы используют `Registry`. **Ноль правок ядра** для нового easing, канала, процедуры, эффекта или слова.

**10.1 Свой easing**

```python
from motus import EASINGS
import math

EASINGS.add("elastic", lambda u: 1.0 - (1.0 - u) ** 3 * abs(math.cos(9 * u)))

rt.submit("anim a.position from=(0,0,0) to=(1,0,0) over=1 ease=elastic")
```

**10.2 Свой канал**

```python
from motus.anim import CHANNELS, ChannelSpec
from motus import Kind

CHANNELS.add("tilt", ChannelSpec(
    "tilt", Kind.FLOAT,
    get=lambda tr: tr.pos[1],
    put=lambda tr, v: setattr(tr, "pos", (tr.pos[0], v, tr.pos[2])),
    add_identity=0.0,
    allow_mul=True,
))

rt.submit("new a\nanim a.tilt from=0 to=1 over=1\n")
```

Требования: `get` и `put` работают с `Transform`, `add_identity` — нейтраль для `ADD`.

**10.3 Своя процедура**

```python
from motus import PROCS, ProcSpec, Kind
import math

PROCS.add("breathe", ProcSpec(
    "breathe",
    fn=lambda t, p, seed: p["base"] + p["amp"] * math.sin(2 * math.pi * p["freq"] * t),
    kinds=(Kind.FLOAT,),
    defaults={"base": 1.0, "amp": 0.1, "freq": 0.5},
))

rt.submit("proc a.scale.uniform breathe freq=0.8 mode=mul")
```

**Требование:** `fn` — чистая функция `(t, params, seed)`. Никакого состояния, никакого `random`.

**10.4 Свой эффект**

```python
from motus import EFFECTS, EffectSpec, ParamSpec

EFFECTS.add("confetti", EffectSpec(
    "confetti", "emitter",
    (
        ParamSpec("speed", "float", 4.0, 0.0),
        ParamSpec("life", "float", 2.0, 0.1),
        ParamSpec("gravity", "float", 2.0),
        ParamSpec("size", "float", 0.08, 0.001),
        ParamSpec("shrink", "float", 0.0, 0.0, 1.0),
        ParamSpec("fade", "float", 1.0, 0.1),
        ParamSpec("spread", "float", 0.3, 0.0, 1.0),
        ParamSpec("color_a", "vec3", (1, 1, 0.3)),
        ParamSpec("color_b", "vec3", (0.3, 1, 1)),
    ),
    glsl="particle",
))

rt.submit("fx confetti on=a at=1 count=800")
```

Эмиттер использует геометрию `burst` (сферический разлёт). Своя геометрия — добавьте ветку в `effects.field()` или зарегистрируйте отдельный вычислитель.

**10.5 Лексика свободного языка**

```python
from motus.query import VERBS, NOUNS, COLORS, NUMWORDS, DIRS

VERBS.add("осыпь", "burst")
NOUNS.add("кубик", "box")
COLORS.add("лавандовый", (0.7, 0.6, 1.0))
NUMWORDS.add("десяток", 10.0)
DIRS.add("по диагонали", (1.5, 1.5, 0.0))
```

**10.6 Новая команда DSL**

Единственное место, где нужно тронуть ядро:

1. имя в `query.DSL_VERBS`;
2. ветка в `query.parse_dsl_line` (возвращает `Cmd`);
3. обработка в `Runtime._ingest_timeless` (stateless) или `_apply_event` (с `at`).

**10.7 Рендер**

`FramePlan` — данные. Адаптер:

```python
plan = rt.frame(t)
for it in plan.items:
    shader.set_mat4("uModel", it.world)   # column-major, transpose=GL_FALSE
    draw(mesh_of(it.name))

for b in plan.batches:
    if b.data:
        vbo.write(b.data.interleaved())   # 8 float32 на частицу
    gl.draw_arrays(gl.POINTS, 0, b.count)

for p in plan.posts:
    apply_post(p.effect, p.params)
```

**10.8 Контракт расширений**

1. Никакого мутабельного состояния в вычислителях — только `(t, params, seed)`.
2. Никакого `random` — только `mathx.hash01`.
3. Значения нормализуются через `track.coerce`, время конечно.
4. Новое поведение покрывается тестом на детерминизм (I1) и границы (I4).

---

**11. Интеграция с Uroboros**

motus можно использовать как патч в `Uroboros` через adapter.

**11.1 Adapter**

Добавьте в `uroboros/adapters.py`:

```python
_MOTUS_CACHE: dict[str, object] = {}

def motus_available() -> bool:
    if "motus_avail" not in _MOTUS_CACHE:
        try:
            import motus  # noqa: F401
            _MOTUS_CACHE["motus_avail"] = True
        except ImportError:
            _MOTUS_CACHE["motus_avail"] = False
    return bool(_MOTUS_CACHE["motus_avail"])

def motus_scene(query, times, *, particles=False, bpm=120.0, mode="auto"):
    if not motus_available():
        return {"ok": False, "source": "fallback",
                "error": "motus is not installed"}
    from motus import Runtime, Transport
    rt = Runtime(Transport(bpm=float(bpm)), mode=str(mode), particles=bool(particles))
    report = rt.submit(str(query))
    if not report.ok:
        return {"ok": False, "source": "motus", "error": str(report),
                "issues": [str(i) for i in report.issues]}
    frames = []
    for t in times:
        plan = rt.frame(float(t))
        frames.append({
            "time": plan.time,
            "items": [{"entity": it.entity, "name": it.name,
                       "world": list(it.world), "params": _json_safe(it.params)}
                      for it in plan.items],
            "batches": [{"emitter": b.emitter, "effect": b.effect,
                         "count": b.count, "origin": list(b.origin)}
                        for b in plan.batches],
            "posts": [{"effect": p.effect, "params": _json_safe(p.params)}
                      for p in plan.posts],
            "stats": _json_safe(plan.stats),
        })
    return {"ok": True, "source": "motus", "mode": report.mode, "frames": frames}
```

**11.2 Патч `patches/motus_scene.py`**

```python
"""motus.scene — выполнить motus-запрос и вернуть снимки кадров."""
from uroboros.adapters import motus_scene

OP = "motus.scene"

def apply(context, params):
    query = params.get("query")
    if not query:
        return {"ok": False, "source": "fallback", "error": "query is required"}
    try:
        return motus_scene(
            query,
            [float(t) for t in params.get("times", [0.0])],
            particles=bool(params.get("particles", False)),
            bpm=float(params.get("bpm", 120.0)),
            mode=str(params.get("mode", "auto")),
        )
    except Exception as exc:
        return {"ok": False, "source": "fallback",
                "error": f"{type(exc).__name__}: {exc}"}
```

**11.3 План**

```json
{
  "format": "uroboros.patch/2",
  "name": "motus_room",
  "nodes": [
    {"id": "geometry", "target": "scene", "operation": "geometry.generate",
     "params": {"width": 5.0, "depth": 4.0}},
    {"id": "palette", "target": "color", "operation": "color.palette",
     "params": {"mood": "quiet_warm"}},
    {"id": "compose", "target": "scene", "operation": "scene.compose",
     "needs": ["geometry", "palette"], "params": {}},
    {"id": "motion", "target": "scene", "operation": "motus.scene",
     "needs": ["compose"],
     "params": {
       "mode": "auto",
       "bpm": 120.0,
       "times": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5],
       "query": "mode dsl\nnew ball pos=(0,0,0)\nanim ball.position from=(0,0,0) to=(3,0,0) over=2 ease=smooth\nproc ball.rotation spin rate=180\nfx burst on=ball at=2 for=1.5 count=600\n"
     }}
  ]
}
```

**11.4 Запуск**

```bash
export PYTHONPATH="$PWD/../motus:$PYTHONPATH"
pip install -e .
python -m uroboros patches         # должен появиться motus.scene
python -m uroboros run --plan examples/plan_motus.json --auto-approve
python -m uroboros inspect --run <id>
```

**11.5 Контракт adapter**

| Случай | `ok` | `source` | Данные |
|---|---|---|---|
| motus установлен, запрос успешен | `true` | `motus` | `frames: [...]` |
| motus установлен, ошибка запроса | `false` | `motus` | `error`, `issues` |
| motus не установлен | `false` | `fallback` | `error` |

Adapter **никогда не падает**. Uroboros-пайплайн сохраняет кеш, approval, журнал.

---

**12. Кэш поз (bake)**

Опциональный плоский кэш поз для очень быстрого воспроизведения. **Не источник истины** — производный артефакт.

```python
from motus import Runtime
from motus.bake import bake, Playback

rt = Runtime(particles=False)
rt.submit("new a\nanim a.position from=(0,0,0) to=(4,0,0) over=1 ease=smooth\n")

manifest = bake(rt, fps=60, duration=2, out="cache")
# -> cache/poses.f32 + cache/manifest.json

with Playback("cache") as pb:
    print(pb.pose(frame=30, index=0))   # (pos3, quat4, scale3)
```

**Формат:**

- `poses.f32` — frame-major, entity-minor, 10 float32 на запись: `pos3 + quat4 + scale3`. Stride 40 байт.
- `manifest.json` — метаданные: version, fps, frames, entities.

**Ограничение:** требует стабильного набора объектов на всём интервале. Все `new` должны быть на `at <= start`.

**Преимущества:**

- `mmap` — один открытый файл, адресная арифметика, никаких numpy зависимостей;
- детерминированный формат;
- версионирование (VERSION).

**Почему не `.npz`:** zip-контейнер нельзя `mmap`, доступ требует распаковки.

---

**13. GLSL**

Опциональные шейдеры GLSL 330 core в `motus/glsl.py`:

- `PARTICLE_VS` — вершинный для GL_POINTS (`gl_PointSize`, `gl_PointCoord`);
- `PARTICLE_FS` — фрагментный (круглые спрайты, premultiplied alpha, additive-friendly);
- `POST_FS` — композитный пост: vignette + grain + shockwave.

Ядро их **не использует**. Это адаптер для тех, кто рендерит.

**Внимание:** шейдеры **не прогонялись** через `glslangValidator` в этой версии. Перед встраиванием:

```bash
glslangValidator -S vert particle.vert
glslangValidator -S frag particle.frag
```

Для `GL_POINTS` нужен `glEnable(GL_PROGRAM_POINT_SIZE)`.

---

**14. Ограничения**

**Честный список:**

| Ограничение | Следствие | Обход |
|---|---|---|
| `Track.sample` использует внутренний курсор | Не thread-safe | Свой трек на поток, или внешняя блокировка |
| Свободный язык — правила, не NLU | Ограниченная морфология | `mode dsl`, явное `@имя` |
| Частицы требуют numpy | Без numpy — нет данных | `Runtime(particles=False)` |
| `submit` = полный rebuild (O(событий)) | Не для 10⁵ объектов | Инкрементальный путь (не реализован) |
| `bake` требует стабильного набора | Все `new` на `at <= start` | Динамические объекты — без bake |
| `drop` не освобождает id | Имена не переиспользуются | Уникальные имена |
| Шейдеры не валидированы | Нужен glslangValidator | Прогнать перед встраиванием |
| Один `Transport` на Runtime | Нельзя разные темпы на объект | Отдельные Runtime |

---

**15. FAQ**

**Чем motus отличается от редактора/таймлайна?**

motus — это **библиотека без UI**. Он принимает текст и возвращает кадры. Редактор, таймлайн, UI — надстройки, которых в пакете нет.

**Почему `frame(t)` — чистая функция, а не состояние?**

Так решаются три проблемы: скраб назад, повтор offline-рендера и воспроизводимость в тестах. Накопители (счётчики, `random`) ломают всё это; motus их не использует.

**Можно ли использовать motus с numpy-free?**

Да. `Runtime(particles=False)`. Ядро (Scene, Track, Animator, Binding, DSL) полностью stdlib. Только `effects.field()` и `Field.interleaved()` требуют numpy.

**Что происходит, если запрос содержит ошибку?**

`submit` возвращает `Report(ok=False, issues=[...])`. **Ни одна команда не применяется** — атомарность через snapshot + restore. Сцена остаётся нетронутой.

**Как перемотать назад?**

Просто вызовите `frame(t)` с меньшим `t`. Runtime сбросит сцену и переиграет события с нуля. Гарантия **I8**.

**Как сделать бесконечное вращение?**

`proc ball.rotation spin rate=180` без `over`. Биндинг с `duration=0` работает всегда.

**Как сделать паузу?**

`drop` не пауза — объект исчезает. Для паузы — используйте `weight=0` или не добавляйте биндинг на этом интервале (через `at` и `over`).

**Как скомбинировать два трека на одном канале?**

Режимы `REPLACE` + `ADD`:

```python
anim ball.position from=(0,0,0) to=(3,0,0) over=2
anim ball.position from=(0,0,0) to=(0,0.5,0) over=1 loop=pingpong mode=add
```

**Как связать эффект с движущимся объектом?**

`fx burst on=ball`. Эмиттер будет привязан к мировой позиции `ball` в момент кадра. Если `ball` умрёт — эффект продолжит работать по последней позиции.

**Совпадает ли offline и realtime?**

Да, гарантия **I9**. `fixed_frames(fps, duration)` и `frame(t)` в любом порядке дают идентичные `FramePlan`.

**Как расширить свободный язык?**

`VERBS.add`, `NOUNS.add`, `COLORS.add`, `NUMWORDS.add`, `DIRS.add`. Ноль правок ядра.

**Как связать motus с Uroboros?**

Через adapter `motus_scene` и патч `motus.scene`. См. [11](#11-интеграция-с-uroboros).

**Почему матрицы column-major?**

Прямая совместимость с `glUniformMatrix4fv(..., GL_FALSE, ...)`. Позиция — `m[12:15]`. Порядок трансформаций: `M = T * R * S`.

**Можно ли использовать motus без Python?**

Пока нет. DSL — внутренний формат, не самостоятельный язык. Но текст DSL можно передавать из любого источника (файл, HTTP, CLI).

---

**Лицензия**

MIT. См. заголовок пакета.

---

**Структура пакета**

```
motus/
├── motus/
│   ├── __init__.py
│   ├── __main__.py
│   ├── core.py
│   ├── mathx.py
│   ├── clock.py
│   ├── track.py
│   ├── scene.py
│   ├── anim.py
│   ├── effects.py
│   ├── query.py
│   ├── runtime.py
│   ├── bake.py
│   └── glsl.py
├── tests/
│   └── test_motus.py
├── docs/
│   ├── README.md
│   └── MOTUS_ADAPTER.md
├── pack.py
└── README.md
```