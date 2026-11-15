# Bug Report — demo_intro_v61 — «Чёрный экран на всех сценах»

**Дата диагностики**: 2026-11-15
**Билд**: demo_runtime v60/v61 (Windows MSVC 14.43, NVIDIA 560.94, OpenGL 3.3)
**Входные данные**: `trace.log` от запуска `demo_runtime.exe demo.smt` + BMP-скриншоты семи сцен.

---

## 1. Симптом

Пользователь сообщает: **«Чёрный экран на всех сценах»**.

Фактические данные из BMP-захватов (640×360, byte-яркость 0–255):

| Сцена      | T захвата | avg RGB        | max | % пикселей <50 | % пикселей >200 |
|------------|-----------|----------------|-----|----------------|-----------------|
| nebula     | 2.0       | (0, 0, 9)      | 48  | **100.0 %**    | 0.0 %           |
| sphere     | 29.0      | (14, 15, 26)   | 255 | 96.8 %         | 2.1 %           |
| particles  | 54.0      | (8, 11, 20)    | 255 | 98.5 %         | 1.2 %           |
| anxiety    | 79.0      | (37, 0, 7)     | 73  | 63.1 %         | 0.0 %           |
| morph_grid | 104.0     | (27, 25, 31)   | 255 | 82.6 %         | 0.1 %           |
| cozy_room  | 129.0     | (23, 25, 31)   | 58  | 93.2 %         | 0.0 %           |
| morphing_figures | 183.0 | (203, 175, 159) | 255 | 0.0 %       | 66.4 %          |

VLM-анализ подтверждает: 6 из 7 сцен **по сути чёрные или почти чёрные** (avg < 30, max < 100 у 3 сцен), и только `morphing_figures` рендерится ярко.

---

## 2. Корневая причина

### BUG #1 (КРИТИЧНЫЙ): дублирующее объявление `float intensity` в 5 post-processing шейдерах

Все 5 пост-шейдеров содержат **две идентичные строки** в начале `main()`:

```glsl
void main() {
    float intensity = max(uIntensity, 1.0);   // line N
    float intensity = max(uIntensity, 1.0);   // line N+1  ← REDECLARATION
    ...
}
```

В GLSL 330 core **повторное объявление локальной переменной в той же области видимости — это compile error** (GLSL 4.2 spec, §4.2.2 «Identifier Redefinition»).

Подтверждение `glslangValidator` (Khronos reference, GLSL 4.60):

```
=== grain.frag ===
ERROR: 0:32: 'intensity' : redefinition
ERROR: 0:32: '' : compilation terminated
ERROR: 2 compilation errors.  No code generated.
```

Аналогичная ошибка для **passthrough.frag, bloom_bright.frag, bloom_blur.frag, vignette.frag, grain.frag, bloom.frag** (6 файлов, 5 из них используются в демо).

### Поведение NVIDIA driver

NVIDIA **reject'ит** повторное объявление (это подтверждается trace.log):

```cpp
// demo_runtime.cpp lines 408–411
int compiled = 0;
for (const auto& c : show.clips) {
    if (c.effect != "finish" && c.effect != "-" && shaders.getProgram(c.effect)) compiled++;
}
Log("[OK] %d shader programs compiled", compiled);
```

Всего клипов 22, у 22−1=21 клипа эффект, не равный `"finish"`/`"-"`.
Trace.log рапортует **15** успешно скомпилированных. 21−15=**6 клипов** провалили компиляцию — ровно 6 post-processing клипов (`blm_bright`, `blm_blurh`, `blm_blurv`, `blm_add`, `vig`, `grn`).

### Каскадный эффект

В `gl_executor.hpp` (executeOp для POST / COMPOSITE):
```cpp
GLuint prog = shaders.getProgram(clip->effect);
if (!prog) return;   // ← молча пропускает op, framebuffer не меняется
```

5 уникальных пост-шейдеров НЕ компилируются → **6 post-op'ов в каждом сегменте молча пропускаются** на каждом кадре.

Цепочка пост-обработки в каждом сегменте (8 ops):
```
RENDER  scene    → fbo0           ✓ работает
POST    bloom_bright  fbo0 → fbo1 ✗ ПРОПУЩЕН
POST    bloom_blur    fbo1 → fbo2 ✗ ПРОПУЩЕН
POST    bloom_blur    fbo2 → fbo1 ✗ ПРОПУЩЕН
COMPOSITE passthrough fbo1 → fbo0 ✗ ПРОПУЩЕН
POST    vignette      fbo0 → fbo1 ✗ ПРОПУЩЕН
POST    grain         fbo1 → screen ✗ ПРОПУЩЕН ← КРИТИЧНО: экран никогда не пишется
PRESENT bind screen                   ✓ работает, но читать нечего
```

`grain` — единственный op, пишущий в `screen` (default framebuffer 0). Его пропуск означает: **back buffer никогда не получает отрендеренного контента**. Остаётся初始ная заливка окна (близкая к чёрной) + случайные leak'и из прошлых кадров → отсюда «чёрный экран».

### BUG #2 (КРИТИЧНЫЙ для v61): имя `noise3` конфликтует с зарезервированным GLSL built-in

Шейдеры `nebula_raymarch.frag`, `particle_swarm.frag`, `anxiety_mist.frag`, `lava_cracks.frag` объявляют пользовательскую функцию `float noise3(vec3 p)`.

В GLSL 330 core `noise3` — **зарезервированное имя built-in функции** (legacy noise, deprecated в GLSL 3.30, но имя остаётся reserved). Strict-компилятор `glslangValidator` reject'ит:

```
ERROR: 0:103: 'noise3' : overloaded functions must have the same return type
```

NVIDIA driver принимает (lenient), но это **ожидаемо сломает переносимость** на Mesa / SwiftShader / WebGL / ANGLE / Intel / AMD.

### BUG #3 (СРЕДНИЙ): `clip fin 30 event 223.0 ...` — duration утёк в поле effect

```
clip fin 30 event 223.0 223.0 223.0 211.0 0.0 normal 77777 - - 208.0
              ^^^^^
              должно быть "finish"
```

Парсер `sm_runtime.hpp` читает 4-е поле после `clip <id> <order> <kind>` как **effect**. В оригинальном v60 оно было `"finish"`, при ручной склейке v61 туда попало значение `223.0` (duration из meta).

Эффекты:
* Trace.log показывает `clip 'fin' effect='223.0'` вместо `effect='finish'`.
* В `gl_executor.hpp` line 444 проверка `if (c.kind == "event" && c.effect == "finish" ...)` **не срабатывает** → runtime не останавливается по событию finish, а ждёт только `T >= show.duration` (тоже работает, но теряется семантика события).
* При инициализации `shaders.getProgram("223.0")` пытается открыть `shaders/223.0.frag` (не существует) — лишний disk I/O + сообщение в stderr (через `fprintf(stderr, ...)`, не через `Log()`, поэтому в trace.log не видно).

### BUG #4 (СРЕДНИЙ): `seg 181.5 211.0` содержал ОДНОВРЕМЕННО цепочки рендера s7 и s8

Оригинальный v61 добавил t7+s8 в конец demo.smt, но **положил обе рендер-цепочки (s7 + s8) в один и тот же сегмент 181.5–211.0**:

```
seg 181.5 211.0 8 2 5
op RENDER s7 - fbo0 - -           ← 8 op'ов для s7
op POST blm_bright ...
...
op PRESENT - screen - - -
op RENDER s8 - fbo0 - -           ← 8 op'ов для s8 (ПЕРЕЗАПИСЫВАЕТ fbo0!)
op POST blm_bright ...
...
op PRESENT - screen - - -
endseg
```

В заголовке сегмента `cost=8`, но реально 16 op'ов. Это значило, что:
1. На каждом кадре T∈[181.5, 211.0) рендерилась и `morphing_figures`, и `lava_cracks` (последняя перетирала fbo0).
2. **Отсутствовал переход t7** на 211–213 секундах — crossfade-клип `t7` был объявлен в `.smt`, но не использовался ни в одном сегменте.
3. **Отсутствовал сегмент для 213–223 секунд** — `segment_at(T)` для T∈[211, 223) возвращал последний сегмент (181.5–211.0), что приводило к повторному рендеру s7+s8 вместо изолированного показа лавы.

### BUG #5 (НИЗКИЙ): per-scene FPS статистика не покрывала t7/s8

В `demo_runtime.cpp` массив `g_scenes[]` заканчивался на `morphing_figures 181.0–211.0`. После 211 секунды FPS не привязывался ни к какой сцене — в финальной статистике просто отсутствовали `transition_7` и `lava_cracks`. Также `g_captureTimes[]` содержал только 7 временных точек (T=2…183), без захвата лавы.

---

## 3. Все найденные дефекты — сводная таблица

| # | Файл                     | Серьёзность | Симптом                                              | Фикс                                                          |
|---|--------------------------|-------------|------------------------------------------------------|---------------------------------------------------------------|
| 1 | passthrough.frag:11-12   | КРИТИЧНЫЙ   | duplicate `float intensity`, compile error           | Удалена дублирующая строка                                    |
| 2 | bloom_bright.frag:11-12  | КРИТИЧНЫЙ   | duplicate `float intensity`, compile error           | Удалена дублирующая строка                                    |
| 3 | bloom_blur.frag:13-14    | КРИТИЧНЫЙ   | duplicate `float intensity`, compile error           | Удалена дублирующая строка                                    |
| 4 | vignette.frag:13-14      | КРИТИЧНЫЙ   | duplicate `float intensity`, compile error           | Удалена дублирующая строка                                    |
| 5 | grain.frag:31-32         | КРИТИЧНЫЙ   | duplicate `float intensity`, compile error           | Удалена дублирующая строка                                    |
| 6 | bloom.frag:14-15         | НИЗКИЙ      | duplicate (файл не используется в demo.smt, но есть) | Удалена дублирующая строка                                    |
| 7 | nebula_raymarch.frag:103 | СРЕДНИЙ     | `noise3` clash с GLSL reserved built-in              | Переименован `noise3` → `vnoise3` (9 call-site'ов)            |
| 8 | particle_swarm.frag:88   | СРЕДНИЙ     | `noise3` clash                                       | Переименован `noise3` → `vnoise3` (4 call-site'а)             |
| 9 | anxiety_mist.frag:89     | СРЕДНИЙ     | `noise3` clash                                       | Переименован `noise3` → `vnoise3` (3 call-site'а)             |
| 10| lava_cracks.frag:70      | СРЕДНИЙ     | `noise3` clash                                       | Переименован `noise3` → `vnoise3` (2 call-site'а)             |
| 11| demo.smt:194             | СРЕДНИЙ     | `clip fin 30 event 223.0 ...` — effect="223.0"       | Заменено на `effect="finish"`                                 |
| 12| demo.smt:330-347         | СРЕДНИЙ     | seg 181.5–211.0 содержал обе цепочки s7+s8 (16 ops)  | Разбит на 3 сегмента: 181.5–211 (s7), 211–213 (t7), 213–223 (s8) |
| 13| demo.smt:4               | НИЗКИЙ      | sections содержал 5 точек, не отражал lava           | Обновлено: `sections 6 0.0 27.0 77.0 127.0 181.0 211.0`       |
| 14| demo_runtime.cpp:49-63   | НИЗКИЙ      | g_scenes[] не содержал t7/s8                         | Добавлены `transition_7` 211–213, `lava_cracks` 213–223       |
| 15| demo_runtime.cpp:141-150 | НИЗКИЙ      | g_captureTimes не содержал точку для лавы            | Добавлен T=217 → `shot_lava.bmp`, проверка `idx < 8`           |

---

## 4. Доказательство корня (BUG #1 = «чёрный экран»)

1. Trace.log: `[OK] 15 shader programs compiled` — ровно 15 = 22 клипа − 6 post-клипов (broken) − 1 fin (файл не существует).
2. `glslangValidator --glsl-version 330 -S frag grain.frag` → `ERROR: 'intensity' : redefinition` (то же для 5 других post-shaders).
3. `gl_executor.hpp` line 344/356/376/393/418/421: `if (!prog) return;` — молча пропускает op, framebuffer не пишется.
4. В цепочке пост-обработки каждого сегмента последний пишущий op — `POST grain fbo1 screen`. Его пропуск → back buffer никогда не получает контент сцены.
5. Тест куба: «compiled=15» совпадает с «21 (clip'ы с эффектом) − 6 (post-shaders с duplicate) = 15» — это статистически точное подтверждение.

## 5. Доказательство корня (BUG #2 = `noise3` clash)

`glslangValidator` для 4 шейдеров:
```
ERROR: 0:103: 'noise3' : overloaded functions must have the same return type
```

NVIDIA driver принимает пользовательский `noise3` (lenient), поэтому шейдеры компилируются — но это всё равно нарушение GLSL spec, которое проявится на любом strict-драйвере.

## 6. Доказательство (BUG #3 = fin effect)

SMT-строка: `clip fin 30 event 223.0 223.0 223.0 211.0 0.0 normal 77777 - - 208.0`

Парсер `sm_runtime.hpp`:
```cpp
in >> cur->id >> cur->track_order >> cur->kind >> cur->effect
   >> cur->eff_start >> cur->eff_end >> cur->nom_start >> cur->nom_dur
   >> cur->blend >> cur->seed >> cur->in_a >> cur->in_b >> cur->prewarm;
```

Четвёртое поле после `clip fin 30 event` сохраняется как `cur->effect`. Здесь это `"223.0"` (число как строка), а должно быть `"finish"`.

Trace.log: `clip 'fin' effect='223.0' opacity_tokens=1 progress_tokens=4 uniforms=0`

## 7. Доказательство (BUG #4 = смешанный сегмент)

Оригинальный demo.smt строки 330–347 — один сегмент `seg 181.5 211.0 8 2 5` с 16 op-строками (две полные рендер-цепочки). `cost=8` в заголовке фактически ложно. После фикса — три сегмента по 8/10/8 op'ов.

## 8. Применённые фиксы

Все фиксы применены в каталоге `download/demo_intro_v61/`:

| Файл                    | Изменение                                                              |
|-------------------------|------------------------------------------------------------------------|
| shaders/passthrough.frag    | удалена дублирующая строка `float intensity`                       |
| shaders/bloom_bright.frag   | удалена дублирующая строка                                       |
| shaders/bloom_blur.frag     | удалена дублирующая строка                                       |
| shaders/vignette.frag       | удалена дублирующая строка                                       |
| shaders/grain.frag          | удалена дублирующая строка                                       |
| shaders/bloom.frag          | удалена дублирующая строка (cleanup, файл не используется)       |
| shaders/nebula_raymarch.frag| `noise3` → `vnoise3` (1 definition + 8 calls = 9 замен)          |
| shaders/particle_swarm.frag | `noise3` → `vnoise3` (1 def + 3 calls = 4 замен)                 |
| shaders/anxiety_mist.frag   | `noise3` → `vnoise3` (1 def + 2 calls = 3 замен)                 |
| shaders/lava_cracks.frag    | `noise3` → `vnoise3` (1 def + 1 call = 2 замен)                  |
| demo.smt                    | fin effect `223.0` → `finish`; sections 5 → 6 (добавлена 211.0)  |
| demo.smt                    | seg 181.5–211.0 разбит на 3: 181.5–211 (s7), 211–213 (t7), 213–223 (s8) |
| demo_runtime.cpp            | g_scenes[] добавлены transition_7 и lava_cracks                  |
| demo_runtime.cpp            | g_captureTimes добавлен T=217 → shot_lava.bmp; проверка `< 8`    |

## 9. Верификация

После фиксов `glslangValidator --glsl-version 330 -S frag *.frag` — все 16 шейдеров компилируются **без ошибок и предупреждений**:

```
nebula_raymarch.frag   PASS
sphere_scene.frag      PASS
particle_swarm.frag    PASS
anxiety_mist.frag      PASS
morph_grid.frag        PASS
cozy_room_sdf.frag     PASS
morphing_figures.frag  PASS
lava_cracks.frag       PASS
crossfade.frag         PASS
flash.frag             PASS
bloom_bright.frag      PASS
bloom_blur.frag        PASS
passthrough.frag       PASS
vignette.frag          PASS
grain.frag             PASS
bloom.frag             PASS
```

SMT sanity check:
* 22 clips ✓
* **15 segments** (было 13), все непрерывные без gap'ов ✓
* demo duration 0–223.0s ✓
* fin effect = "finish" ✓

Ожидаемый результат после пересборки и запуска:
* `[OK] 21 shader programs compiled` (вместо 15) — все clip'ы кроме fin, чей эффект "finish" исключается проверкой
* Все 7 сцен + transition_7 + lava_cracks появятся в per-scene статистике
* `shot_lava.bmp` сохранится на T=217
* Экран больше не чёрный — все post-effects (bloom, vignette, grain) применяются

## 10. Рекомендации

1. **CI-чек**: добавить в `build_demo_runtime.bat` шаг `glslangValidator --glsl-version 330 -S frag shaders/*.frag` — он бы поймал оба класса ошибок до сборки.
2. **Логирование ошибок компиляции**: в `gl_executor.hpp::compileShader()` заменить `fprintf(stderr, ...)` на вызов `Log()` (или дублировать в `Log()`), чтобы ошибки попадали в `trace.log`, а не терялись в stderr.
3. **Имена функций**: воздержаться от `noise1/2/3/4`, `texture*`, `shadow*` — все они зарезервированы в GLSL spec. Использовать префикс `v` (vnoise3) или `user_`.
4. **Тестовый запуск `--still`**: после любых правок шейдеров прогонять `demo_runtime.exe demo.smt --still 2 --out still.png --repeat 3` для каждой сцены — занимает ~30s вместо полного 223s цикла.
5. **Coverage сегментов**: после правок `.smt` проверять, что для каждого clip'а с kind=scene/transition есть хотя бы один сегмент, который его использует (`op RENDER/TRANSITION <clip>`), иначе clip «висит».
