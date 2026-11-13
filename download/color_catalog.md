# Color Catalog — log по Tasks

**Назначение:** Последовательная запись цветов (#rrggbb) → synesthesias → empathies, используемых в каждой Task. Строит "визуальную карту сцены" — какие цвета применялись, с какими эмоциями, в каких задачах.

**Источник данных:** Color Matrix v11 (prior model). Все значения — computed по H/S/L формулам, не измерены на людях.

**Формат записи:**

~~~
## Task N — <description>
- Color: #rrggbb (name)
  - synesthesia: temperature/weight/texture/sound/motion/spatial_depth
  - empathy: label (score -100..+100)
  - entropy: label (score 0..100)
  - role: background|accent|focal|rim|transition
  - GLSL: vec3(r, g, b)
~~~

---

## Task 49 — v49 nebula upper-cyan-fix
- Color: #1a66cc (cyan_mid)
  - synesthesia: cold/medium/unverified/mid/flowing/unverified
  - empathy: warmth (+23)
  - entropy: medium (49)
  - role: accent (upper half)
  - GLSL: vec3(0.102, 0.400, 0.800)

- Color: #cc4d80 (magenta_rim)
  - synesthesia: hot/medium/unverified/mid/pulse/unverified
  - empathy: tension (-30)
  - entropy: high (72)
  - role: rim light
  - GLSL: vec3(0.800, 0.302, 0.502)

---

## Task 68 — Color Matrix integration (template entry)
- Color: #c00800 (anxiety red)
  - synesthesia: hot/medium/unverified/mid/pulse/unverified
  - empathy: anxiety (-77)
  - entropy: medium (58)
  - role: random pick for "rndm" test
  - GLSL: vec3(0.753, 0.031, 0.000)

- Color: #ffb0c0 (delight pink)
  - synesthesia: hot/light/unverified/mid/flowing/unverified
  - empathy: delight (+90)
  - entropy: low (28)
  - role: animation endpoint
  - GLSL: vec3(1.000, 0.690, 0.753)

---

## Как использовать этот каталог

1. **Перед `!feat *shader*`:** проверьте, какие цвета уже использовались в похожих задачах
2. **После генерации shader:** запишите новые цвета с их Color Matrix профилем
3. **Для multi-scene work:** каждая сцена может ссылаться на цвета из каталога
4. **Для animation (`%anim`):** начальная и конечная точки записываются с emotion labels

## Integration с Color Matrix

```python
# Пример: получить профиль цвета для записи в каталог
from color_matrix_python import FullRGBMatrixReader
reader = FullRGBMatrixReader('color-matrix-full-rgb-v11.npz')
cell = reader.get_cell((26, 102, 204))
print(f"empathy: {cell.empathy.label} ({cell.empathy.score})")
print(f"entropy: {cell.entropy.label} ({cell.entropy.score})")
```
