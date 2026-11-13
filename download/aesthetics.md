# Aesthetic principles

**Документ:** aesthetics.md
**Дата:** 2026-11-01
**Статус:** v0.5 (simplified — removed 3-image comparative analysis §9, added Color Matrix integration §9-§10)

---

## 1. Контекст

Principles, не taste. Между `vec3(0.10, 0.40, 0.80)` и `vec3(0.15, 0.42, 0.85)` выбор делается по принципам. Без явных principles default = «разумно, но не вдохновенно».

Этот документ — **checklist для application**, не рецепт креативности.

---

## 2. Эстетический профиль

```
70 / 25 / 5  ratio
│    │   └─ focal point (single light source, narrative anchor)
│    └───── vivid color accents (contrast against dominant)
└────────── dominant dark space (mood, breathing room)
```

**Anti-pattern:** uniform saturation (всё ярко) — теряет depth, выглядит flat/amateur.

---

## 3. Color theory

### 3.1. 60-30-10 rule

| Role | Доля пикселей | Luminance | Saturation |
|------|---------------|-----------|------------|
| Dominant | 60% | 0.05-0.20 | 0.3-0.5 |
| Secondary | 30% | 0.20-0.50 | 0.5-0.7 |
| Accent | 10% | 0.50-0.90 | 0.7-1.0 |

### 3.2. Color harmony (выбрать ОДНУ, не смешивать)

| Harmony | Colors | Когда |
|---------|--------|-------|
| **Complementary** | 2 colors напротив (cyan↔magenta, blue↔orange, purple↔yellow) | dramatic contrast, tension |
| Analogous | 3 соседних цвета (blue→cyan→teal) | calm, serene, mood-driven |
| Triadic | 3 равноудалённых (red/yellow/blue) | vibrant, playful |
| Split-complementary | 1 base + 2 neighbors of opposite | balanced drama |

### 3.3. Saturation/luminance balance

- **Core (dark) regions**: saturation 0.6-0.8, luminance 0.15-0.25
- **Mid regions**: saturation 0.4-0.5, luminance 0.30-0.50
- **Rim/accent regions**: saturation 0.3-0.4, luminance 0.60-0.80

**Anti-pattern:** saturated core + saturated rim = muddy. Saturated core + desaturated rim = depth.

### 3.4. Sample palette (DRAMATIC_DARK)

```
deep_purple_core:  rgb(0.08, 0.05, 0.20)  HSL(255, 0.60, 0.13)
cyan_mid:          rgb(0.10, 0.40, 0.80)  HSL(215, 0.78, 0.45)
magenta_rim:       rgb(0.80, 0.30, 0.50)  HSL(340, 0.55, 0.55)
star_white_pure:   rgb(1.00, 1.00, 0.95)  HSL(50, 1.00, 0.97)
void_black:        rgb(0.02, 0.02, 0.03)
```

Mood: cold/dramatic/deep. Use cases: core glow, atmospheric depth, rim light.

---

## 4. Composition

### 4.1. Focal point singularity

- **1 focal point per frame.** Если >1 — competing attention, eye fatigue.
- Focal = brightest single element OR highest saturation OR center-most.
- Other elements supporting, НЕ competing.

### 4.2. Rule of thirds

- Camera target / focal element на пересечении thirds (не в центре кадра).
- Для static camera: shift focal to (0.33, 0.50) или (0.66, 0.50).
- Для moving camera: target trajectory проходит через thirds.

### 4.3. Background-foreground density contrast

- Background density < foreground density. **НЕ** заполняйте кадр равномерно.
- Background noise subtle (amplitude 0.3-0.5), foreground accents яркие (amplitude 0.6-1.0).

### 4.4. Vignette as attention director

- Gentle vignette: 0.7-0.85 at edges
- Strong vignette = amateur, eye senses manipulation
- No vignette = flat, lacks depth

---

## 5. Motion (Disney 12 simplified для real-time)

### 5.1. Easing

- **smoothstep(t)** для organic motion (НЕ linear)
- Linear только для mechanical rotation (gears, clock hands)
- `mix(a, b, smoothstep(0.0, 1.0, t))` — standard pattern

### 5.2. Anticipation (10% перед main motion)

- Перед «впрыгиванием» camera — slight pull-back (10% amplitude, 100ms)
- В GLSL: `pos += sin(t * 5.0) * 0.02` перед основным motion

### 5.3. Follow-through (15% после main motion)

- После резкой остановки — slight overshoot + dampened oscillation
- `pos = target + sin((t - t_stop) * 8.0) * exp(-(t - t_stop) * 3.0) * 0.05`

### 5.4. Camera motion: 1 primary axis

- 1 axis primary (largest amplitude)
- Other axes secondary (≤30% of primary amplitude)
- Anti-pattern: chaotic 3-axis motion = nausea, not aesthetic

### 5.5. Phase offsets для variety

- Multiple light sources: each phase offset by ~1.7 radians (golden angle 2.3998 / 2 ≈ 1.7)
- Avoid synchronized pulsing — looks mechanical

---

## 6. Density

### 6.1. FBM octaves

- **4-5 max.** После 5 — mush, lost detail.
- amplitude half per octave (standard fbm)
- frequency double per octave

### 6.2. Light nodes count

- **3-5 max.** Больше — competing, less impact.
- Если добавить ещё — удалить или объединить существующие.

### 6.3. Star field density

- 1 star per ~50×50 pixel area max
- Brighter stars rarer (logarithmic distribution)
- Anti-pattern: dense star field = noise, not depth

### 6.4. Detail vs scale

- Big shapes first, small details last
- 3-tier hierarchy: macro (composition) / meso (light nodes) / micro (noise detail)
- All three tiers needed; missing one = flat

---

## 7. Contrast & luminance balance

### 7.1. Dynamic range

- Min luminance in frame: 0.02-0.05 (deep shadow)
- Max luminance in frame: 0.85-1.00 (HDR accent)
- Ratio: 20:1 to 50:1 — cinematic
- < 10:1 = flat / TV-broadcast look
- > 100:1 = HDR display required, иначе crushed blacks

### 7.2. Tone mapping (ACES recommended)

- `finalColor = ACESFilm(color)` — preserves highlights, lifts shadows
- ACES: `color = (color * (2.51 * color + 0.03)) / (color * (2.43 * color + 0.59) + 0.14)`

### 7.3. Color contrast (S-channel in HSL)

- Average saturation in frame: 0.4-0.6
- Peak saturation (accents): 0.8-1.0
- Anti-pattern: average saturation > 0.7 = eye strain

---

## 8. Self-critique checklist

```
aesthetic_notes:
  color:
    - palette: <name>
    - dominant/secondary/accent ratio: <60/30/10 | other>
    - harmony: <complementary | analogous | triadic>
  composition:
    - focal_point: <which element>
    - rule_of_thirds: <yes/no, where>
    - bg/fg_density_contrast: <yes/no>
  motion:
    - easing: <smoothstep | linear | mixed>
    - anticipation: <yes/no>
    - follow_through: <yes/no>
    - primary_axis: <x | y | z>
  density:
    - fbm_octaves: <N>
    - light_nodes: <N>
    - star_density: <low | med | high>
  contrast:
    - dynamic_range: <min/max luminance>
    - tone_mapping: <ACES | raw | other>
  reference_target:
    - which reference image this aims for: <path or description>
    - delta from reference: <what's different>
  self_critique:
    - 1-2 sentences: what works, what doesn't, what to try next
```

**Если любой пункт empty** — task не закрыт, вернуться к generation.

---

## 9. Color Matrix integration

For per-color emotion data, use Color Matrix v11:
- 16.7M RGB colors with empathy (-100..+100), entropy (0..100), 6 synesthesia dimensions
- Query: `find_colors feel=anxiety` → returns matching colors
- Random mode: `find_colors feel=anxiety random=True` (for "rndm" requests)
- Multi-color: `find_multi_colors [{feel: anxiety}, {feel: delight}]`
- Animation: `find_animation_path(from_state, to_state, steps)`

**Location:** `/home/z/my-project/color_matrix/`
**Policy:** `/home/z/my-project/color_matrix/policy/shader_color_policy.md` (for shader context)
**Honest framing:** Color Matrix values are prior model (computed from H/S/L formulas), not measured on humans.

## 10. Color catalog

Sequential log of colors used per Task: `/home/z/my-project/download/color_catalog.md`
