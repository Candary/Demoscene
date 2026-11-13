# Demo Runtime v61 — Volumetric Color Adapter + Per-Scene Palettes + Brighter Shaders

v61 = v60 + Путь 5: устранение hardcoded цветов для volumetric-сцен через
data-driven Density-aware Luminance Adapter + per-scene mood palettes
+ shader brightness boost (user feedback: v60 был слишком тёмным).

## Что нового в v61

| Параметр | v60 | v61 |
|----------|-----|-----|
| Hardcoded RGB dicts | V58_COLORS, V58_FALLBACK | **полностью удалены** |
| Volumetric Color Adapter | — | **volumetric_adapter.py** (OKLCH-based) |
| Per-scene palettes | один palette на все сцены | **scene_palettes param** (mood per scene) |
| nebula DENSITY_SCALE | 0.6 | **1.0** (×1.67 brighter) |
| nebula sampleAlpha | 0.3 | **0.5** (×1.67 brighter) |
| nebula uIntensity | 0.8 | **1.5** (×1.875 brighter) |
| anxiety primaryMod mix | 0.4 | **0.8** (×2.0 brighter primary) |
| anxiety uIntensity | 1.2 | **1.8** (×1.5 brighter) |
| TARGET_EFFECTIVE_L (s1.primary) | 0.036 (v58 baseline) | **0.18** (×5 visible) |
| TARGET_EFFECTIVE_L (s1.accent) | 0.198 | **0.40** (×2) |
| TARGET_EFFECTIVE_L (s4.primary) | 0.051 | **0.15** (×3) |
| TARGET_EFFECTIVE_L (s4.accent) | 0.438 | **0.50** (×1.1) |
| VLM EFFECTIVE_L_FLOOR | 0.03 | **0.10** (perceptual threshold) |
| Tests | (existing suite) | **+25 volumetric_adapter tests (51 total)** |

## Почему v61 ярче v60

v60 калибровал TARGET_EFFECTIVE_L по v58 baseline colors, которые пользователь
принял как видимые. Но v58 baseline был eле-еле видим (eff_L 0.036 для nebula
primary = почти чёрный на тёмном фоне). Когда пользователь запустил v61 с теми
же target'ами, он сказал «ты сделал всё очень тёмным».

Скриншоты v60 подтвердили:
- shot_nebula: avg=1.1/255 (0.4%), max=15/255 — почти полностью чёрный
- shot_anxiety: avg=11.9/255 (4.7%), max=24/255 — очень тёмный
- shot_sphere: avg=15.9/255 — маленький яркий шар на чёрном фоне

**Решение v61:** поднять яркость на двух уровнях одновременно:

1. **Шейдеры** (DENSITY_SCALE, sampleAlpha, primaryMod mix, uIntensity):
   ×5.22 для nebula, ×3.0 для anxiety primary, ×1.5 для anxiety accent.

2. **Адаптер targets** (perceptually motivated, не v58 baseline):
   primary 0.15-0.18 (clearly visible mist), accent 0.40-0.50 (bright accents).

С новыми шейдерами current v61 palette colors проходят targets **без адаптер
boost** — адаптер работает как safety net для очень тёмных палитр.

## Ключевое изменение — Путь 5

**Проблема v60:** Color Matrix возвращает mood-appropriate цвета, но volumetric-шейдеры
(nebula, anxiety) умножают цвет на density × alpha × intensity → bright Color Matrix
цвета становятся невидимыми. Решалось hardcoded `V58_COLORS` dict в scene_bake.py.

**Решение v61:** `volumetric_adapter.py` берёт любой Color Matrix цвет, конвертирует
RGB→OKLCH, вычисляет `effective_L = L × scene_multiplier`, и если ниже **target_eff**
(perceptually motivated), бустит L до `target_eff / mult` с сохранением hue H и
chroma C. Mood остаётся, меняется только яркость.

## Per-scene palettes

scene_bake.py принимает параметр `scene_palettes`:
```python
{
    "s1": {"roles": {"primary": {"hex": "#0d1f4d"}, "accent": {"hex": "#3399cc"}}},
    "s4": {"roles": {"primary": {"hex": "#400d1a"}, "accent": {"hex": "#cc2418"}}},
    ...
}
```

Это позволяет разным сценам иметь разные mood-палитры (nebula=синий, anxiety=красный)
без hardcoded RGB.

## Состав v61

```
demo_intro_v61/
├── README.md            (этот файл)
├── KNOWN_ISSUES.md      (унаследован от v60)
├── Howto_use_demo_show_json.md
├── build_demo_runtime.bat
├── demo.smt             (★ регенерирован, uIntensity 0.8→1.5 для s1, 1.2→1.8 для s4)
├── demo.show.json       (★ обновлён)
├── demo_runtime.cpp     (без изменений — runtime прежний)
├── gl_executor.hpp      (без изменений)
├── opengl_loader.h      (без изменений)
├── sm_runtime.hpp       (без изменений)
└── shaders/             (15 .frag файлов)
    ├── nebula_raymarch.frag  ★ DENSITY_SCALE 0.6→1.0, sampleAlpha 0.3→0.5
    ├── anxiety_mist.frag     ★ primaryMod mix 0.4→0.8
    └── (остальные 13 без изменений)
```

## Управление

| Клавиша | Действие |
|---------|----------|
| **ESC** | Выход |
| **F1**  | Toggle FPS в заголовке |
| **F3**  | PNG→MP4 запись |
| **F4**  | Горячая перезагрузка .smt |

## Сборка и запуск

```bat
build_demo_runtime.bat
demo_runtime.exe
```

## Проверки v61 (выполнены)

1. **Conformance binary** на demo.smt — все 4 volumetric color/role комбинации
   прошли: `effective_L ≥ TARGET_EFFECTIVE_L`
   - s1.uPrimaryColor: eff=0.20 (target 0.18) ✓
   - s1.uAccentColor:  eff=0.65 (target 0.40) ✓
   - s4.uPrimaryColor: eff=0.15 (target 0.15) ✓
   - s4.uAccentColor:  eff=0.55 (target 0.50) ✓
2. **VLM feedback loop** на v61 — converged за 2 итерации
3. **Adapter self-test** — 6 tests passed
4. **Formal test suite** — 51 tests passed (включая 25 volumetric_adapter)
5. **v61 vs v60 .smt diff** — все 8 цветовых uniform'ов изменились + uIntensity
   для s1 и s4 повышен

## Адаптер математика

```
Input:  rgb_in (Color Matrix palette color)
        scene_id (e.g. "s1"), uniform_name (e.g. "uPrimaryColor")

Step 1: L, C, H = rgb_to_oklch(rgb_in)           # OKLCH conversion (Ottosson)
Step 2: mult = SCENE_MULTIPLIERS[scene_id][role] # from shader source analysis
Step 3: target_eff = TARGET_EFFECTIVE_L[scene_id][role]  # perceptual (v61)
Step 4: eff_in = L * mult
Step 5: if eff_in >= target_eff:
            return rgb_in   # already visible
        else:
            L_target = min(target_eff / mult, 0.92)
            C_target = C * (L_target / 0.30) if L_target < 0.30 else C
            return oklch_to_rgb(L_target, C_target, H)   # hue preserved
```

## Что дальше

Если v61 работает (визуальная проверка пользователем):
- Зафиксировать как milestone (#milestone v61)
- Возможные расширения v62:
  - Color Matrix integration для автоматической генерации scene_palettes
    по feel-меткам (anxiety→red palette, nebula→blue palette)
  - Расширить adapter на cozy_room_sdf (если найдутся invisibility cases)
  - Reinforcement learning для auto-tuning TARGET_EFFECTIVE_L
