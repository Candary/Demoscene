# Known Issues — v60

> **Статус на 2026-11-11 (v61): решено частично.** Настоящая причина «тёмных»
> volumetric-сцен оказалась не в Color Matrix, а в двух багах: сломанный хэш шума
> (при seed ≥ 22222 `fract()` возвращал 0 — у anxiety туман был нулевым, у grain
> зерно вычитало 0.2 из каждого кадра) и композитинг `mix(bg, vol.rgb, vol.a)`
> при alpha ≈ 0.08. Подробности, замеры и правки — в `CHANGELOG_v61.md`.
> Ниже — исходный текст v60, оставлен как история.

## Color Matrix не работает для volumetric-сцен

**Дата**: 2026-11-11
**Статус**: Отложено (некритично)

### Проблема

Color Matrix возвращает mood-appropriate цвета (например, anxiety → bright red
(0.988, 0.235, 0.220)). Но шейдеры с **volumetric accumulation** (nebula_raymarch,
anxiety_mist) умножают цвет на density (0.1–0.3) и накапливают по шагам:

```
final_color = uPrimaryColor × density × uIntensity × steps × transmittance
```

Bright base color × low density = всё ещё dark. Scaling ×0.1 делает ЕЩЁ ТЕМНЕЕ.

### Что попробовали

| Подход | Результат |
|--------|-----------|
| Color Matrix as-is (0.988, 0.235, 0.220) | Тёмный red, VLM 2/10 |
| Saturation boost ×1.4 (1.0, 0.146, 0.124) | Темнее (меньше G/B), VLM 2/10 |
| Scale ×0.1 (0.1, 0.015, 0.012) | Почти чёрный, VLM "全黑" |
| Revert to v58 hardcoded (0.05, 0.10, 0.30) | Всё ещё тёмный на screenshot |

### Вывод

Color Matrix不适合 volumetric accumulation шейдеров. Нужен **hardcode** цветов
для сцен где цвет умножается на density. Color Matrix работает только для
**direct color output** сцен (sphere, particles, morph_grid, cozy_room).

### Затронутые сцены

| Сцена | Shader type | Color Matrix? |
|-------|-------------|---------------|
| s1 nebula_raymarch | Volumetric accumulation | ❌ Hardcode |
| s4 anxiety_mist | 2D FBM + mix | ❌ Hardcode |
| s2 sphere_scene | Direct (Palette function) | ✅ Works |
| s3 particle_swarm | Direct | ✅ Works |
| s5 morph_grid | Raymarched (periodic) | ✅ Works |
| s6 cozy_room_sdf | SDF raymarch | ✅ Works |
| s7 morphing_figures | SDF + Palette | ✅ Works (own palette) |

### Возможные решения (future)

1. **Shader-aware Color Matrix**: передать shader type в Color Matrix query,
   возвращать разные цвета для volumetric vs direct
2. **Accumulation-aware color scaling**: вычислить `target_brightness / (density × steps)`
   и подобрать color channel values
3. **Post-bake color adjustment**: после bake, анализировать shader type и
   применять разные scaling factors
4. **Tone mapping**: добавить ACES tone mapping в nebula shader для лучшей
   видимости тёмных областей
