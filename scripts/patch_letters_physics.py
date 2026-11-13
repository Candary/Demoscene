# Правка физики букв: сферическая мантия полёта вместо плоского бокса.
# Применяется к preview.html (JS) и main.cpp (C++) — паритет.
import pathlib

def patch(path, pairs):
    p = pathlib.Path(path)
    s = p.read_text(encoding='utf-8')
    for old, new in pairs:
        assert old in s, f'{path}: NOT FOUND: {old[:60]}...'
        s = s.replace(old, new)
    p.write_text(s, encoding='utf-8')
    print(path, 'patched')

js_pairs = [
    # 1. Границы и сфера выталкивания
    ("const LETTER_BOUND = [1.65, 1.25, 1.05]; // полуразмеры бокса-границ (всегда в кадре)",
     "const LETTER_BOUND = [1.65, 1.65, 1.65]; // куб-границы (всегда в кадре: кадр ±3.5)"),
    ("const LETTER_KEEP  = [1.18, 0.92, 0.78]; // эллипсоид выталкивания от центральной фигуры",
     "const LETTER_KEEP  = [1.25, 1.25, 1.25]; // сфера выталкивания от центральной фигуры\nconst LETTER_R_WALL = 0.32; // отступ букв от стен куба (диагональ глифа ~0.29)"),
    # 2. Сила выталкивания
    ("const push = 2.2 * (1.0 - e2);",
     "const push = 3.0 * (1.0 - e2);"),
    # 3. Отражение от сферы-мантии (сразу после блока выталкивания)
    ("""            vx += gx / glen * push * dt;
            vy += gy / glen * push * dt;
            vz += gz / glen * push * dt;
        }

        // 3. Движение.""",
     """            vx += gx / glen * push * dt;
            vy += gy / glen * push * dt;
            vz += gz / glen * push * dt;
        }

        // 2b. Отражение от сферы-«мантии»: если буква у границы выталкивания
        // летит К ЦЕНТРУ — разворачиваем нормальную составляющую скорости.
        const rr = Math.hypot(px, py, pz);
        if (rr > LETTER_KEEP[0] * 0.92 && rr > 1e-6) {
            const nrx = px / rr, nry = py / rr, nrz = pz / rr;
            const vn = vx*nrx + vy*nry + vz*nrz;
            if (vn < 0) {
                vx -= nrx * vn * 1.5;
                vy -= nry * vn * 1.5;
                vz -= nrz * vn * 1.5;
            }
        }

        // 3. Движение."""),
    # 4. Отступ стен: R_COL -> R_WALL
    ("            const lim = LETTER_BOUND[a] - R;",
     "            const lim = LETTER_BOUND[a] - LETTER_R_WALL;"),
]

cpp_pairs = [
    ("static const float kLetterBound[3] = { 1.65f, 1.25f, 1.05f };    // бокс-границы (в кадре)",
     "static const float kLetterBound[3] = { 1.65f, 1.65f, 1.65f };    // куб-границы (в кадре)"),
    ("static const float kLetterKeep[3]  = { 1.18f, 0.92f, 0.78f };    // эллипсоид выталкивания",
     "static const float kLetterKeep[3]  = { 1.25f, 1.25f, 1.25f };    // сфера выталкивания\nstatic const float kLetterRWall   = 0.32f;                      // отступ от стен куба"),
    ("            const float push = 2.2f * (1.0f - e2);",
     "            const float push = 3.0f * (1.0f - e2);"),
    ("""            vx += gx / glen * push * dt;
            vy += gy / glen * push * dt;
            vz += gz / glen * push * dt;
        }

        // 3. Движение.""",
     """            vx += gx / glen * push * dt;
            vy += gy / glen * push * dt;
            vz += gz / glen * push * dt;
        }

        // 2b. Отражение от сферы-«мантии»: если буква у границы выталкивания
        // летит К ЦЕНТРУ — разворачиваем нормальную составляющую скорости.
        const float rr = sqrtf(px*px + py*py + pz*pz);
        if (rr > kLetterKeep[0] * 0.92f && rr > 1e-6f) {
            const float nrx = px / rr, nry = py / rr, nrz = pz / rr;
            const float vn = vx*nrx + vy*nry + vz*nrz;
            if (vn < 0.0f) {
                vx -= nrx * vn * 1.5f;
                vy -= nry * vn * 1.5f;
                vz -= nrz * vn * 1.5f;
            }
        }

        // 3. Движение."""),
    ("            const float lim = kLetterBound[a] - R;",
     "            const float lim = kLetterBound[a] - kLetterRWall;"),
]

patch('/home/z/my-project/download/demo_intro/preview.html', js_pairs)
patch('/home/z/my-project/download/demo_intro/main.cpp', cpp_pairs)
print('OK')
