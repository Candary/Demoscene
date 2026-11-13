// ===================================================================
// shaders.h
// -------------------------------------------------------------------
// Вершинный и фрагментный шейдеры нашего интро.
//
// Здесь живёт вся "магия" демо:
//   - Морфинг между SDF-фигурами (сфера, куб, тор, октаэдр)
//   - Анимированный градиентный фон с IQ-palette
//   - Звёздное поле как частицы вокруг фигуры
//   - Мягкие тени и ambient occlusion
//   - Плавное вращение камеры
//   - Интерактивное вращение мышью (drag ЛКМ, работает на паузе)
//
// Шейдеры заданы как inline-строки — никаких внешних файлов,
// компиляция в один .exe.
// ===================================================================

#pragma once

// ----- Вершинный шейдер ---------------------------------------------
// Делаем "fullscreen quad" без VBO — просто генерируем 4 вершины
// треугольного стрипа из gl_VertexID. Это классическая демосценовская
// фишка: не нужно создавать буферы вершин.
static const char* kVertexShaderSrc = R"GLSL(
#version 330 core

void main() {
    // gl_VertexID будет 0, 1, 2, 3 — четыре вершины.
    // Раскладываем их как два треугольника, покрывающие весь экран.
    vec2 positions[4] = vec2[4](
        vec2(-1.0, -1.0),
        vec2( 1.0, -1.0),
        vec2(-1.0,  1.0),
        vec2( 1.0,  1.0)
    );
    gl_Position = vec4(positions[gl_VertexID], 0.0, 1.0);
}
)GLSL";

// ----- Фрагментный шейдер --------------------------------------------
// Это сердце демо. Здесь raymarching по SDF-фигурам, освещение,
// частицы-звёзды и градиентный фон.
static const char* kFragmentShaderSrc =
R"GLSL(
#version 330 core

// uniform-переменные: значения, которые мы передаём из C++ каждый кадр.
uniform float uTime;        // время в секундах от старта
uniform vec2  uResolution; // размер окна в пикселях (w, h)
uniform float uZoom;        // коэффициент зума: >1 — ближе, <1 — дальше
uniform vec2  uMouseRot;    // вращение мышью (drag ЛКМ): .x = yaw, .y = pitch
uniform float uFireMask[8]; // маска частиц воды: 1=видна, 0=горит огнём (воду скрыть)

// --- Полезные константы и функции -------------------------------------

const float PI  = 3.14159265359;
const float TAU = 6.28318530718;

// --- НОВАЯ ПАЛИТРА: неоновая магента-циан-лайм ---
// Палитра в стиле кибер-синтвейв: насыщенные пурпурные, циан и лайм.
// Формула та же (Иниго Квилес), но с разными частотами по каналам —
// даёт больше переливов и более "неоновый" характер.
vec3 Palette(float t) {
    vec3 a = vec3(0.5, 0.5, 0.5);    // базовая яркость
    vec3 b = vec3(0.5, 0.5, 0.5);    // амплитуда
    vec3 c = vec3(2.0, 1.0, 1.5);    // разная частота по каналам
    vec3 d = vec3(0.0, 0.25, 0.5);   // сдвиг: магента-циан-лайм
    return a + b * cos(TAU * (c * t + d));
}

// Поворот в 2D (для поворота координат в плоскости).
mat2 Rot2D(float angle) {
    float s = sin(angle);
    float c = cos(angle);
    return mat2(c, -s, s, c);
}

// --- SDF-примитивы (Signed Distance Fields) --------------------------
// SDF возвращает расстояние от точки p до поверхности фигуры:
//   * отрицательное — точка внутри фигуры
//   * ноль — точка на поверхности
//   * положительное — точка снаружи

// Сфера радиуса r в центре координат.
float sdSphere(vec3 p, float r) {
    return length(p) - r;
}

// Куб со сторонами b (параллелепипед если b != одинаковые).
float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}

// Тор с радиусами R (главный) и r (труба).
float sdTorus(vec3 p, float R, float r) {
    vec2 q = vec2(length(p.xz) - R, p.y);
    return length(q) - r;
}

// Октаэдр с радиусом r.
float sdOctahedron(vec3 p, float r) {
    p = abs(p);
    return (p.x + p.y + p.z - r) * 0.57735027; // sqrt(3)/3
}

// НОВАЯ ФИГУРА: треугольная призма («треугольник»).
// Равносторонний треугольник вершиной вверх (+Y), выдавленный по Z:
// h.x — радиус описанной окружности (масштаб), h.y — половина толщины.
// Вершина треугольника лежит в точке (0, h.x, 0) — при h.x = 1 она
// совпадает с верхней вершиной октаэдра и с вершиной конуса, поэтому
// переходы октаэдр → призма → конус держат «острую» верхнюю точку
// на месте, и морфинг выглядит плавнее, чем прямой октаэдр → конус.
float sdTriPrism(vec3 p, vec2 h) {
    vec3 q = abs(p);
    float d1 = q.z - h.y;
    float d2 = max(q.x * 0.866025 + p.y * 0.5, -p.y) - h.x * 0.5;
    return length(max(vec2(d1, d2), 0.0)) + min(max(d1, d2), 0.0);
}

// НОВАЯ ФИГУРА: круговой конус.
// Высота h по оси y, радиус основания r в плоскости y=0.
// ФИКС: прежняя формула (k1/k2/s/ca/cb) возвращала мусорный знак —
// «минус» снаружи конуса и «плюс» внутри. Пока конус был 5-й фигурой,
// это маскировалось соседями в mix() и «удачными» углами вращения;
// после сдвига фаз (вставка треугольника после октаэдра) конус стал
// чистым при t=20..24, и лучи, проходившие через дефектный сектор,
// «застревали внутри»: кадр заливало пустым цветом фона или гигантской
// массой. Новое тело — осесимметричное пересечение двух полуплоскостей
// (боковая грань + основание): знак верен во всём пространстве,
// расстояние точно на гранях и слегка занижено у апекса (безопасно).
float sdCone(vec3 p, float h, float r) {
    vec2 q = vec2(length(p.xz), p.y);
    float d_side = (q.x * h + q.y * r - h * r) / sqrt(h * h + r * r);
    float d_base = -q.y;
    return max(d_base, d_side);
}

// НОВАЯ ФИГУРА: капсула между двумя точками a и b радиусом r.
float sdCapsule(vec3 p, vec3 a, vec3 b, float r) {
    vec3 pa = p - a;
    vec3 ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h) - r;
}

// Плавное слияние (polynomial smooth min) — нужно для объединения частей
// составных SDF (например, чайника). Защита от k=0: при делении на 0
// в формуле возникает NaN, поэтому clamp k к минимальному значению.
float smin(float a, float b, float k) {
    float kk = max(k, 0.005);
    float h = clamp(0.5 + 0.5 * (b - a) / kk, 0.0, 1.0);
    return mix(b, a, h) - kk * h * (1.0 - h);
}

// НОВАЯ ФИГУРА: упрощённый Utah Teapot (чайник).
// Композиция из 5 частей:
//   * Тело — сплюснутая по Y сфера («пузико»)
//   * Крышка — маленькая сфера сверху
//   * Пимпочка — малюсенькая сфера на крышке
//   * Носик — капсула, идущая от тела наружу и вверх
//   * Ручка — вертикальный тор (через swizzle .xzy на sdTorus)
float sdTeapot(vec3 p) {
    // --- Тело: сплюснутая сфера (пузико) ---
    vec3 bodyP = p;
    bodyP.y /= 1.3;
    float body = sdSphere(bodyP, 0.5);

    // --- Крышка сверху ---
    float lid = sdSphere(p - vec3(0.0, 0.65, 0.0), 0.10);

    // --- Пимпочка на крышке ---
    float knob = sdSphere(p - vec3(0.0, 0.78, 0.0), 0.04);

    // --- Носик: капсула-клювик ---
    float spout = sdCapsule(p, vec3(0.40, 0.05, 0.0), vec3(0.85, 0.45, 0.0), 0.07);

    // --- Ручка: вертикальный тор ---
    vec3 handleP = (p - vec3(-0.45, 0.15, 0.0)).xzy;
    float handle = sdTorus(handleP, 0.20, 0.04);

    // Объединяем через smin — мягкое слияние швов.
    float d = body;
    d = smin(d, spout, 0.04);
    d = smin(d, handle, 0.04);
    d = smin(d, lid, 0.05);
    d = smin(d, knob, 0.02);

    return d;
}

// НОВАЯ ФИГУРА: додекаэдр (12-гранник — платоново тело).
// Грани ориентированы вдоль направлений (0, ±1, ±φ), (±1, ±φ, 0), (±φ, 0, ±1),
// где φ — золотое сечение. Для симметричного тела достаточно 6 осей
)GLSL"
R"GLSL(// (по паре противоположных граней), используем abs(dot) — 6 dot вместо 12.
float sdDodecahedron(vec3 p, float r) {
    const float PHI  = 1.61803398875;    // золотое сечение
    const float NORM = 0.525731112119134; // 1/sqrt(1 + φ²) — нормализация

    // 6 уникальных осей додекаэдра (каждая покрывает 2 противоположные грани).
    float d1 = abs(dot(p, vec3(0.0, 1.0,  PHI) * NORM));
    float d2 = abs(dot(p, vec3(0.0, 1.0, -PHI) * NORM));
    float d3 = abs(dot(p, vec3(1.0,  PHI, 0.0) * NORM));
    float d4 = abs(dot(p, vec3(1.0, -PHI, 0.0) * NORM));
    float d5 = abs(dot(p, vec3(PHI, 0.0, 1.0)  * NORM));
    float d6 = abs(dot(p, vec3(PHI, 0.0, -1.0) * NORM));

    // SDF выпуклого многогранника = max по всем полуплоскостям.
    float d = max(max(d1, d2), max(d3, d4));
    d = max(d, max(d5, d6));
    return d - r;
}

// --- Морфинг фигур ---------------------------------------------------
// Используем mix() для интерполяции SDF — это даёт прямой переход
// между формами, и при frac_=0/1 мы видим чистую фигуру.
// (smin с k=0 не подходит: вырождается в min(a,b), а когда одна
//  фигура содержит другую — всегда выбирается внешняя.)

// --- Идентификаторы материалов --------------------------------------
// Что вернул RayMarch: 0 — мимо, 1 — основная фигура, 2.x — частица с ID x.
const float MAT_NONE     = 0.0;
const float MAT_MAIN     = 1.0;
const float MAT_PARTICLE = 2.0;  // + pid * 0.1 кодирует ID частицы

// Хеш-функция для "случайного характера" каждой частицы.
// Возвращает псевдослучайное число в [0, 1) по численному ключу.
float hash(float n) {
    uint i = floatBitsToUint(n) ^ 0x12345678u;
    i = (i ^ (i >> 16u)) * 0x85ebca6bu;
    i = (i ^ (i >> 13u)) * 0xc2b2ae35u;
    i = i ^ (i >> 16u);
    return float(i) * (1.0 / 4294967296.0);
}

// --- Глобальные переменные для оптимизации ---------------------------
// Матрицы вращения вычисляются ОДИН РАЗ в RenderScene (перед raymarch),
// а не в каждом вызове MapScene (который вызывается ~60 раз на пиксель).
mat2 gRotXZ = mat2(1.0);
mat2 gRotYZ = mat2(1.0);
mat2 gRotXY = mat2(1.0);

// Вращение мышью (drag ЛКМ). Применяется ПЕРВЫМ (снаружи всех остальных
// поворотов), поэтому оси вращения всегда выровнены по экрану: тянем
// вправо — фигура крутится как глобус вправо, независимо от её
// собственного кувыркания от time-анимации.
mat2 gRotMouseYaw   = mat2(1.0);
mat2 gRotMousePitch = mat2(1.0);

// ОПТИМИЗАЦИЯ 6: precompute позиции и радиусы частиц.
// Раньше для каждой из 8 частиц вычислялись sin/cos на КАЖДЫЙ вызов
// MapScene (60 шагов raymarch × 8 частиц × 3 sin/cos = ~1440 sin/cos
// на пиксель!). Теперь вычисляются один раз в RenderScene.
vec3 gParticlePos[8];
float gParticleRad[8];

vec2 MapScene(vec3 p) {
    float t = uTime;

    // Вращение мышью (drag ЛКМ) — внешнее преобразование поверх
    // time-анимации. Работает и на паузе: сдвигает всю сцену (фигуру
    // и частицы) как единое целое, фон и звёзды остаются на месте.
    p.xz = gRotMouseYaw * p.xz;
    p.yz = gRotMousePitch * p.yz;

    // Поворот камеры (точки) в нескольких плоскостях — фигура вертится.
    // Используем предвычисленные глобальные матрицы (см. RenderScene).
    p.xz = gRotXZ * p.xz;
    p.yz = gRotYZ * p.yz;
    p.xy = gRotXY * p.xy;

    // Параметр морфинга: 9 фигур = 9 фаз по кругу.
    float phase = mod(t * 0.25, 9.0);

    // ОПТИМИЗАЦИЯ: вычисляем только 2 нужные фигуры (по текущей фазе),
    // а не все 9. Экономит 7 SDF-вызовов на каждый MapScene (× 48 шагов
    // raymarch + 4 CalcNormal = ~370 сэкономленных SDF-вызовов на пиксель).
    float idx   = floor(phase);
    float frac_ = smoothstep(0.0, 1.0, phase - idx);

    float d_main;
    if      (idx < 0.5) d_main = mix(sdSphere       (p, 1.0),
                                      sdBox          (p, vec3(0.85)), frac_);
    else if (idx < 1.5) d_main = mix(sdBox          (p, vec3(0.85)),
                                      sdTorus        (p, 0.8, 0.3), frac_);
    else if (idx < 2.5) d_main = mix(sdTorus        (p, 0.8, 0.3),
                                      sdOctahedron   (p, 1.0), frac_);
    else if (idx < 3.5) d_main = mix(sdOctahedron   (p, 1.0),
                                      sdTriPrism     (p, vec2(1.0, 0.5)), frac_);
    else if (idx < 4.5) d_main = mix(sdTriPrism     (p, vec2(1.0, 0.5)),
                                      sdCone         (p, 1.0, 0.9), frac_);
    else if (idx < 5.5) d_main = mix(sdCone         (p, 1.0, 0.9),
                                      sdCapsule      (p, vec3(-0.8, -0.6, 0.0), vec3(0.8, 0.6, 0.0), 0.35), frac_);
    else if (idx < 6.5) d_main = mix(sdCapsule      (p, vec3(-0.8, -0.6, 0.0), vec3(0.8, 0.6, 0.0), 0.35),
                                      sdTeapot       (p), frac_);
    else if (idx < 7.5) d_main = mix(sdTeapot       (p),
                                      sdDodecahedron (p, 1.0), frac_);
    else                d_main = mix(sdDodecahedron (p, 1.0),
                                      sdSphere       (p, 1.0), frac_);   // петля

    // --- ОБЪЁМНЫЕ ЧАСТИЦЫ ---
    // ОПТИМИЗАЦИЯ 6: позиции/радиусы частиц берутся из предвычисленных
    // глобальных массивов (см. RenderScene) — вместо 16 sin/cos на каждый
    // вызов MapScene.
    float d_part = 1e9;
    float pid_nearest = 0.0;
    for (int i = 0; i < 8; i++) {
        if (uFireMask[i] < 0.5) continue;  // частица горит — воду скрываем
        // ФИКС: возврат к полному sdSphere без bounding-skip (пропуск
        // далёких частиц давал овершут raymarch — частицы исчезали).
        float ds = sdSphere(p - gParticlePos[i], gParticleRad[i]);
        if (ds < d_part) {
            d_part = ds;
            pid_nearest = float(i);
        }
    }

    // SDF-объединение (smin) для плавного визуального слияния.
    float d_combined = smin(d_main, d_part, 0.15);

    // Материал: что ближе к точке — основная фигура или ближайшая частица.
    float matID = (d_main < d_part)
        ? MAT_MAIN
        : MAT_PARTICLE + pid_nearest * 0.1;

    return vec2(d_combined, matID);
}

// CalcNormal через tetrahedron trick — вместо 6 вызовов MapScene
// (3 оси × 2 стороны) используем 4 вызова по вершинам тетраэдра.
// ОПТИМИЗАЦИЯ 7: экономия 33% на расчёте нормали.
vec3 CalcNormal(vec3 p) {
)GLSL"
R"GLSL(    const vec2 k = vec2(1.0, -1.0);
    const float e = 0.001;
    return normalize(
        k.xyy * MapScene(p + k.xyy * e).x +
        k.yyx * MapScene(p + k.yyx * e).x +
        k.yxy * MapScene(p + k.yxy * e).x +
        k.xxx * MapScene(p + k.xxx * e).x
    );
}

// --- Raymarching -----------------------------------------------------
// Идём по лучу из точки ro в направлении rd, шагами, пока SDF не станет
// почти нулём (нашли поверхность) или не выйдем за пределы дистанции.
// Возвращает vec2: .x = расстояние, .y = material ID.
vec2 RayMarch(vec3 ro, vec3 rd) {
    float t = 0.0;          // текущее расстояние
    const int steps = 48;   // ОПТИМИЗАЦИЯ: 60 → 48 шагов (с lazy SDF eval достаточно)
    const float maxDist = 50.0; // макс. дистанция

    for (int i = 0; i < steps; i++) {
        vec3 p = ro + rd * t;
        vec2 hit = MapScene(p);
        // Если почти на поверхности — попали.
        if (hit.x < 0.001) return vec2(t, hit.y);
        // Если ушли слишком далеко — выходим без попадания.
        if (t > maxDist) return vec2(-1.0, MAT_NONE);
        // Иначе шагаем вперёд на значение SDF (это свойство SDF).
        t += hit.x;
    }
    return vec2(-1.0, MAT_NONE);
}

// ОПТИМИЗАЦИЯ 8: RayMarchCoarse — облегчённая версия (30 шагов) для
// преломлённого прохода капель. Преломлённое изображение видно только
// внутри капель (маленькая область экрана), точность там не критична.
vec2 RayMarchCoarse(vec3 ro, vec3 rd) {
    float t = 0.0;
    const int steps = 20;   // ОПТИМИЗАЦИЯ: 30 → 20 шагов (преломление в каплях)
)GLSL"
R"GLSL(    const float maxDist = 50.0;

    for (int i = 0; i < steps; i++) {
        vec3 p = ro + rd * t;
        vec2 hit = MapScene(p);
        if (hit.x < 0.002) return vec2(t, hit.y);  // чуть более "грубый" порог
        if (t > maxDist) return vec2(-1.0, MAT_NONE);
        t += hit.x * 1.2;  // чуть больше шаг для быстрого прохождения
    }
    return vec2(-1.0, MAT_NONE);
}

// --- Небула-фон (domain-warped FBM + 5 световых узлов) ---
// v46: заменяет gradient+stars. Task 19 небула (откачена Task 34) — аккуратная версия.
// Палитра: deep indigo base + vibrant purple / electric cyan / neon orange / hot pink.
float hash3(vec3 p) {
    p = fract(p * 0.3183099 + 0.1);
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float noise3(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float na = hash3(i);
    float nb = hash3(i + vec3(1.0, 0.0, 0.0));
    float nc = hash3(i + vec3(0.0, 1.0, 0.0));
    float nd = hash3(i + vec3(1.0, 1.0, 0.0));
    float ne = hash3(i + vec3(0.0, 0.0, 1.0));
    float nf = hash3(i + vec3(1.0, 0.0, 1.0));
    float ng = hash3(i + vec3(0.0, 1.0, 1.0));
    float nh = hash3(i + vec3(1.0, 1.0, 1.0));
    return mix(mix(mix(na, nb, f.x), mix(nc, nd, f.x), f.y),
               mix(mix(ne, nf, f.x), mix(ng, nh, f.x), f.y), f.z);
}
float fbm3(vec3 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 3; i++) {
        v += a * noise3(p);
        p = p * 2.0 + vec3(1.3, 1.7, 2.1);
        a *= 0.5;
    }
    return v;
}
vec3 NebulaBackground(vec3 rd, vec2 uv) {
    vec3 base = vec3(0.04, 0.05, 0.12);
    vec3 p = rd * 2.5 + vec3(0.0, 0.0, uTime * 0.03);
    float warp = fbm3(p + 5.2);
    float n = fbm3(p + 2.0 * warp);
    vec3 col = base;
    col = mix(col, vec3(0.12, 0.05, 0.20), smoothstep(0.3, 0.7, n));
    col = mix(col, vec3(0.05, 0.15, 0.25), smoothstep(0.4, 0.8, n * n));
    col *= 0.7 + 0.6 * n;
    // 5 световых узлов (screen-space, HDR-свечения, пульсируют)
    vec2 q0 = uv - vec2(0.5, 0.5); col += vec3(0.15, 0.6, 0.9) * (0.08 / (dot(q0,q0) + 0.02)) * (0.6 + 0.4 * sin(uTime*0.8)) * 0.5;
    vec2 q1 = uv - vec2(0.2, 0.6); col += vec3(0.9, 0.5, 0.1) * (0.08 / (dot(q1,q1) + 0.02)) * (0.6 + 0.4 * sin(uTime*0.8 + 1.7)) * 0.5;
    vec2 q2 = uv - vec2(0.8, 0.7); col += vec3(0.95, 0.2, 0.55) * (0.08 / (dot(q2,q2) + 0.02)) * (0.6 + 0.4 * sin(uTime*0.8 + 3.4)) * 0.5;
    vec2 q3 = uv - vec2(0.3, 0.2); col += vec3(0.6, 0.2, 0.9) * (0.08 / (dot(q3,q3) + 0.02)) * (0.6 + 0.4 * sin(uTime*0.8 + 5.1)) * 0.5;
    vec2 q4 = uv - vec2(0.7, 0.3); col += vec3(0.95, 0.85, 0.3) * (0.08 / (dot(q4,q4) + 0.02)) * (0.6 + 0.4 * sin(uTime*0.8 + 6.8)) * 0.5;
    // 2 диагональные ленты (flowing ribbons)
    float r1 = 0.5 + 0.5 * sin((uv.x + uv.y) * 6.0 + uTime * 0.5 + n * 4.0);
    col += vec3(0.1, 0.3, 0.5) * smoothstep(0.6, 0.9, r1) * 0.4;
    float r2 = 0.5 + 0.5 * sin((uv.x - uv.y) * 8.0 - uTime * 0.7);
    col += vec3(0.4, 0.1, 0.4) * smoothstep(0.65, 0.95, r2) * 0.3;
    // виньетка
    vec2 vd = uv - 0.5;
    col *= 1.0 - 0.4 * dot(vd, vd) * 2.0;
    return col;
}

// --- Звёздное поле (частицы) ----------------------------------------
// Простой 3D-шум для генерации "звёзд" на сфере вокруг камеры.
// Возвращает яркость звезды в направлении dir.
float StarField(vec3 dir) {
    // Дискретизируем сетку на единичной сфере: переводим направление
    // в сферические координаты, умножаем на частоту, округляем.
    vec3 p = dir * 8.0;
    vec3 id = floor(p);
    vec3 f = fract(p) - 0.5;

    // Псевдослучайная яркость для каждой ячейки.
    float rnd = hash(dot(id, vec3(12.9898, 78.233, 37.719)));

    // Звезда — это небольшое яркое пятно в центре ячейки.
    float d = length(f);
    float star = smoothstep(0.5, 0.0, d) * rnd;

    // Мерцание: медленная модуляция яркости по времени.
    star *= 0.6 + 0.4 * sin(uTime * 3.0 + rnd * 100.0);

    return star * 0.7;
}

// --- Точка входа в шейдер -------------------------------------------
out vec4 FragColor;

uniform int uApplyToneMap;  // 1 = включить ACES, 0 = без тонмаппинга
uniform int uDroplets;       // 1 = включить эффект стекающих капель

// --- Эффект стекающих по экрану капель ---------------------------------
// Возвращает vec4:
//   .xy = смещение UV для преломления
//   .z  = "мокрость" 0..1 (влияет на силу преломления)
//   .w  = 1 если пиксель в активной капле (нужен spec-блик),
//         0 если в trail или в мокром пути
vec4 DropletEffect(vec2 screenUV) {
    vec2 refractOffset = vec2(0.0);
    float wetness = 0.0;
    float isActiveDrop = 0.0;

    // 12 капель, детерминированно распределённых по экрану.
    // ОПТИМИЗАЦИЯ 4: 5 hash → 2 hash на каплю через переиспользование.
    for (int i = 0; i < 8; i++) {   // ОПТИМИЗАЦИЯ: 12 → 8 капель
        float fi = float(i);
        // Один master-hash, остальные параметры — арифметические функции от него.
        float h1 = hash(fi * 7.1 + 0.5);
        float h2 = hash(fi * 3.7 + 1.9);

        float seedX  = h1;
        float speed  = 0.05 + 0.12 * h2;
        float radius = 0.005 + 0.005 * fract(h1 * 3.0);   // радиус в ~2 раза меньше
        float trailL = 0.02 + 0.06 * fract(h2 * 2.0);     // длина следа пропорционально
        float xJitter = (h1 - 0.5) * 0.0025;
        float wetPathLen = 0.25 + 0.25 * fract(h2 * 5.0);

        // Капля движется сверху вниз, зацикливаясь через y = 1.2 → -0.1.
        // Скорость нелинейная — капля ускоряется к низу (как от гравитации).
        float cyc = mod(uTime * speed + fi * 0.13, 1.2) - 0.1;
        float y = cyc * (0.7 + 0.6 * cyc);

        vec2 dropPos = vec2(seedX + xJitter, y);
        vec2 toDrop = screenUV - dropPos;

        // 1. КРУГЛАЯ КАПЛЯ (активная) — основная вода.
        float distSq = dot(toDrop, toDrop);
        if (distSq < radius * radius) {
            float dist = sqrt(distSq);
            float strength = 1.0 - dist / radius;
            vec2 dir = toDrop / max(dist, 0.0001);
            refractOffset = dir * strength * 0.04 + vec2(0.0, -strength * 0.015);
            wetness = 1.0;
            isActiveDrop = 1.0;
            break;
        }

        // 2. TRAIL — короткий след прямо под каплей.
        if (abs(toDrop.x) < radius * 0.55 && toDrop.y > 0.0 && toDrop.y < trailL) {
            float trailStrength = (1.0 - toDrop.y / trailL) * 0.35;
            vec2 trailOffset = vec2(0.0, -toDrop.y / trailL * 0.025);
            if (trailStrength > wetness) {
                wetness = trailStrength;
                refractOffset = trailOffset;
                isActiveDrop = 0.0;
            }
        }

        // 3. МОКРЫЙ ПУТЬ — длинный след ОТ СТАРТА КАПЛИ до её текущей позиции.
        // Вода, оставшаяся на стекле после прохождения капли. Со временем
        // испаряется (экспоненциальное затухание по расстоянию от капли).
        // toDrop.y < 0 — пиксель ВЫШЕ капли (capля прошла через него ранее).
        if (toDrop.y < 0.0) {
            float verticalDist = -toDrop.y;
            if (verticalDist < wetPathLen) {
                // Шумная ширина — края не ровные, а с волнами.
                // ОПТИМИЗАЦИЯ: используем h2 вместо отдельного hash вызова.
                float waveAmp  = 0.4 + 0.3 * fract(h2 * 7.0);
                float wetWidth = radius * (0.9 + waveAmp * sin(verticalDist * 40.0 + fi * 2.0));

                if (abs(toDrop.x) < wetWidth) {
                    float distNorm = verticalDist / wetPathLen;
                    float wetStrength = exp(-distNorm * 2.5) * 0.30;
                    float edgeFalloff = 1.0 - abs(toDrop.x) / wetWidth;
                    wetStrength *= edgeFalloff;

                    // Слабое преломление — вверх + лёгкий шумный X.
                    vec2 wetOffset = vec2(
                        (hash(fi * 23.1 + floor(verticalDist * 20.0)) - 0.5) * 0.008,
                        -verticalDist * 0.008
                    );

                    if (wetStrength > wetness) {
                        wetness = wetStrength;
                        refractOffset = wetOffset;
                        isActiveDrop = 0.0;
                    }
                }
            }
        }
    }

    return vec4(refractOffset, wetness, isActiveDrop);
}

// --- Основная функция рендера сцены (внутренняя) ----------------------
// Принимает UV и флаг качества: isCoarse=true использует RayMarchCoarse
// (30 шагов) вместо полного RayMarch (60 шагов) — для преломлённого прохода.
vec3 RenderSceneInner(vec2 uv, bool isCoarse) {
    // --- ОПТИМИЗАЦИЯ 1: предвычисление матриц вращения ---
    gRotXZ = Rot2D(uTime * 0.5);
    gRotYZ = Rot2D(uTime * 0.3);
    gRotXY = Rot2D(uTime * 0.2);

    // Матрицы вращения мышью. Строим ТРАНСПОНИРОВАННУЮ матрицу: MapScene
    // вращает точку запроса (а не объект), поэтому визуальный поворот
    // фигуры — это обратная матрица. Транспонирование = обратная для
    // ортогональной матрицы вращения. Результат — эффект «вращаю глобус
    // рукой»: тянешь вправо — передняя грань уходит вправо.
    float cy = cos(uMouseRot.x);
)GLSL"
R"GLSL(    float sy = sin(uMouseRot.x);
    float cp = cos(uMouseRot.y);
    float sp = sin(uMouseRot.y);
    gRotMouseYaw   = mat2(cy, sy, -sy, cy);
    gRotMousePitch = mat2(cp, sp, -sp, cp);

    // --- ОПТИМИЗАЦИЯ 6: precompute позиции/радиусы частиц ---
    for (int i = 0; i < 8; i++) {
        float fi = float(i);
        float angle = uTime * (0.4 + fi * 0.06) + fi * 0.78;
        float radius = 1.6 + 0.4 * sin(fi * 1.7 + uTime * 0.2);
        float yOff  = 0.8 * sin(fi * 0.9 + uTime * 0.3 + fi);
        gParticlePos[i] = vec3(cos(angle) * radius, yOff, sin(angle) * radius);
        gParticleRad[i] = 0.08 + 0.04 * sin(uTime * 2.0 + fi * 1.5);
    }

    // --- Камера ---
    // uZoom > 1 — камера ближе, uZoom < 1 — дальше.
    float cam_t = uTime * 0.3;
    float baseDist = 3.5;
    float dist = baseDist / max(uZoom, 0.001);
    vec3 ro = vec3(
        sin(cam_t) * dist,
        sin(cam_t * 0.7) * (dist * 0.35),
        cos(cam_t) * dist
    );
    vec3 ta = vec3(0.0);
    vec3 forward = normalize(ta - ro);
    vec3 right   = normalize(cross(vec3(0.0, 1.0, 0.0), forward));
    vec3 up      = cross(forward, right);

    // Направление луча для этого пикселя.
    vec3 rd = normalize(forward + uv.x * right + uv.y * up);

    // --- ОПТИМИЗАЦИЯ 2: bounding sphere check ---
    // Все фигуры + частицы лежат внутри сферы радиуса ~2.2 в центре.
    // Если луч не пересекает эту сферу — фигуры не видны, сразу
    // возвращаем фон, не тратя 60 шагов raymarching.
    float bsRadius = 2.2;
    float bsB = dot(ro, rd);
    float bsC = dot(ro, ro) - bsRadius * bsRadius;
    float bsDisc = bsB * bsB - bsC;
    if (bsDisc < 0.0) {
        // Луч мимо bounding sphere — рисуем только небулу.
        vec2 uv0 = gl_FragCoord.xy / uResolution;
        return NebulaBackground(rd, uv0);
    }

    // --- Фон: небула (domain-warped FBM + 5 световых узлов) ---
    vec2 bgUv = gl_FragCoord.xy / uResolution;
    vec3 bg = NebulaBackground(rd, bgUv);

    // --- Raymarching ---
    // ОПТИМИЗАЦИЯ 8: для преломлённого прохода используем coarse-версию.
    vec2 hit;
    if (isCoarse) {
        hit = RayMarchCoarse(ro, rd);
    } else {
        hit = RayMarch(ro, rd);
    }
    vec3 col = bg;

    if (hit.x > 0.0) {
        vec3 p = ro + rd * hit.x;
        vec3 n = CalcNormal(p);

        // Направление света — кружит вокруг сцены.
        vec3 lightDir = normalize(vec3(
            sin(uTime * 0.7), 0.8, cos(uTime * 0.7)
        ));
        float diff = max(dot(n, lightDir), 0.0);
        float amb = 0.15 + 0.15 * max(dot(n, vec3(0.0, 1.0, 0.0)), 0.0);
        vec3 viewDir = -rd;
        vec3 halfDir = normalize(lightDir + viewDir);
        float spec = pow(max(dot(n, halfDir), 0.0), 32.0);

        if (hit.y >= MAT_PARTICLE) {
            // ====== ЧАСТИЦА ======
            float pid = (hit.y - MAT_PARTICLE) * 10.0;
            float rndType  = hash(pid * 7.3 + 1.0);
            float rndColor = hash(pid * 3.7 + 5.0);
            float pulse = 0.5 + 0.5 * sin(uTime * (1.5 + rndType * 2.0) + pid * 0.7);
            vec3 particleCol = Palette(pid * 0.13 + rndColor + uTime * 0.1);

            if (rndType > 0.5) {
                // --- СВЕТЯЩАЯСЯ ---
                float glow = 1.5 + 1.0 * pulse;
                col = particleCol * glow;
                col += vec3(1.0) * pow(pulse, 3.0) * 0.4;
            } else {
                // --- ПОЛУПРОЗРАЧНАЯ ---
                float alpha = 0.25 + 0.35 * pulse;
                float rim = pow(1.0 - abs(dot(n, viewDir)), 2.5);
                vec3 surface = particleCol * (amb * 0.7 + diff * 0.5);
                surface += particleCol * rim * 1.2;
                surface += vec3(1.0) * spec * 0.3;
                col = mix(bg, surface, alpha);
            }
        } else {
            // ====== ОСНОВНАЯ ФИГУРА ======
            vec3 objCol = Palette(p.x * 0.5 + p.y * 0.3 + p.z * 0.2 + uTime * 0.1);
            vec3 surface = objCol * (amb + diff * 0.8) + vec3(1.0) * spec * 0.5;
            float fog = 1.0 - exp(-hit.x * 0.08);
            col = mix(surface, bg, fog * 0.5);
            col += surface * 0.15;
        }
    }

    // Виньетирование (в линейном пространстве).
    vec2 q = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.x;
    float vignette = 1.0 - 0.5 * dot(q, q);
    col *= vignette;

    return col;
}

// Публичные обёртки.
vec3 RenderScene(vec2 uv) { return RenderSceneInner(uv, false); }
vec3 RenderSceneCoarse(vec2 uv) { return RenderSceneInner(uv, true); }

void main() {
    // UV-координаты пикселя: [-1, 1] по X, с поправкой на aspect ratio.
    vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;

    // 1. Основной рендер сцены — возвращает ЛИНЕЙНЫЙ цвет.
    vec3 col = RenderScene(uv);

    // 2. Эффект стекающих капель — только если включён (клавиша D).
    // Важно: эффект применяется ДО тонмаппинга — преломлённый цвет
    // пересчитывается через повторный RenderScene, и должен быть
    // в том же линейном пространстве.
    if (uDroplets == 1) {
        vec2 screenUV = gl_FragCoord.xy / uResolution.xy;

        vec4 drop = DropletEffect(screenUV);
        if (drop.z > 0.001) {
            // Преломление: пересчитываем цвет сцены со смещённым UV.
            float aspect = uResolution.x / uResolution.y;
            vec2 refractedUv = uv + drop.xy * vec2(aspect, 1.0);

            // ОПТИМИЗАЦИЯ 8: coarse-проход (30 шагов raymarch вместо 60).
            vec3 refractedCol = RenderSceneCoarse(refractedUv);

            float wetness = drop.z;

            if (drop.w > 0.5) {
                // === АКТИВНАЯ КАПЛЯ — сильный refract + spec-блик ===
                vec2 toCenter = drop.xy;
                vec2 lightDir2D = normalize(vec2(0.7, -0.7));
                float spec2D = pow(max(dot(normalize(toCenter + vec2(0.001)),
                                            -lightDir2D), 0.0), 16.0);

                col = mix(col, refractedCol, wetness);
                col += vec3(1.0) * spec2D * wetness * 0.8;
                col *= 1.0 - 0.15 * wetness * (1.0 - wetness);
            } else {
                // === МОКРЫЙ ПУТЬ / TRAIL — слабый refract, без spec, темнее ===
                col = mix(col, refractedCol, wetness);
                // Вода делает стекло темнее — мениск на водяной плёнке.
                col *= 1.0 - 0.20 * wetness;
                // Лёгкое мерцание — капризные блики света на водяной плёнке.
                float shimmer = 0.05 * wetness *
                    sin(uTime * 2.0 + screenUV.x * 50.0 + screenUV.y * 30.0);
                col += vec3(shimmer);
            }
        }
    }

)GLSL"
R"GLSL(    // 3. Постобработка: ACES-тонмаппинг + гамма-коррекция.
    if (uApplyToneMap == 1) {
        col = (col * (2.51 * col + 0.03)) / (col * (2.43 * col + 0.59) + 0.14);
    }
    col = pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2));

    FragColor = vec4(col, 1.0);
}
)GLSL";

// ===================================================================
// ОГОНЬ НА ЧАСТИЦАХ ВОДЫ — ПРОЦЕДУРНАЯ ВЕРСИЯ (без текстуры)
// -------------------------------------------------------------------
// Каждый источник огня = 30 мелких частиц со своими lifetime/velocity/
// offset/phase. Время циклит через mod(t+phase, lifetime) — частицы
// рециклятся, огонь выглядит непрерывным. Билборд через right/up
// камеры (как в основной сцене). Цвет и форма полностью процедурные
// во фрагментном шейдере: жёлто-белое ядро → жёлтый → оранжевый →
// тёмно-красный по возрасту. Аддитивный блендинг (gl.SRC_ALPHA, gl.ONE).
// Подход из урока Chinedufn (particle billboard), но без текстуры.
// ===================================================================

// ----- Вершинный шейдер огня ---------------------------------------
// 5 атрибутов на вершину: aTriCorner(2) + aCenterOffset(3) + aVelocity(3)
// + aLifetime(1) + aPhase(1) = 10 float'ов. Страйд задан в main.cpp.
static const char* kFireVertexShaderSrc = R"GLSL(
#version 330 core

layout(location = 0) in vec2  aTriCorner;     // угол квада (-1..1)
layout(location = 1) in vec3  aCenterOffset;  // стартовое смещение (мир)
layout(location = 2) in vec3  aVelocity;      // скорость партикла (мир)
layout(location = 3) in float aLifetime;      // длительность жизни (сек)
layout(location = 4) in float aPhase;         // фазовый сдвиг 0..aLifetime

uniform float uTime;        // локальное время с момента старта огня (сек)
uniform vec3  uFirePos;    // позиция источника в мире
uniform vec3  uFireUp;     // «вверх» для партиклов (= normalize(uFirePos))
uniform float uFireSize;   // базовый размер партикла
uniform vec3  uCamPos;
uniform vec3  uCamFwd;
uniform vec3  uCamRight;
uniform vec3  uCamUp;
uniform float uAspect;

out vec2  vLocalUV;
out float vLife;     // 1 = молодая, 0 = умирающая

void main() {
    // Локальное время циклит — частица рециклится.
    float t = mod(uTime + aPhase, aLifetime);
    float normT = t / aLifetime;
    vLife = 1.0 - normT;

    // Скорость: в основном вдоль uFireUp + лёгкий случайный разброс.
    vec3 velocity = uFireUp * (0.35 + aLifetime * 0.15) + aVelocity * 0.15;
    vec3 worldPos = uFirePos + aCenterOffset + t * velocity;

    // Билборд: смещение по right/up камеры * размер * угол квада.
    // Размер падает квадратично с возрастом.
    float size = uFireSize * (vLife * vLife * 0.5 + 0.15);
    worldPos += (uCamRight * aTriCorner.x + uCamUp * aTriCorner.y) * size;

    // Проекция в clip space (повторяет логику raymarch-камеры).
    vec3 view = worldPos - uCamPos;
    float z = dot(view, uCamFwd);
    float invZ = 1.0 / max(z, 0.001);
    vec2 screenUV = vec2(dot(view, uCamRight) * invZ, dot(view, uCamUp) * invZ);
    gl_Position = vec4(vec2(screenUV.x / uAspect, screenUV.y) * 2.0, 0.0, 1.0);

    vLocalUV = aTriCorner;
}
)GLSL";

// ----- Фрагментный шейдер огня ------------------------------------
// Процедурная частица: мягкий круг с цветовым градиентом по возрасту.
// Жёлто-белое ядро (родился) -> жёлтый -> оранжевый -> тёмно-красный
// (умирает). Аддитивный блендинг даёт неоновое свечение.
static const char* kFireFragmentShaderSrc = R"GLSL(
#version 330 core

in vec2  vLocalUV;
in float vLife;

uniform float uFadeAlpha;

out vec4 FragColor;

vec3 fireColor(float age) {
    vec3 hotCore  = vec3(1.00, 0.85, 0.40);
    vec3 yellow   = vec3(1.00, 0.65, 0.15);
    vec3 orange   = vec3(1.00, 0.30, 0.05);
    vec3 deepRed  = vec3(0.55, 0.08, 0.02);
    if (age < 0.15) return mix(hotCore, yellow, age / 0.15);
    if (age < 0.50) return mix(yellow, orange, (age - 0.15) / 0.35);
    return mix(orange, deepRed, (age - 0.50) / 0.50);
}

void main() {
    vec2 uv = vLocalUV;
    float d2 = dot(uv, uv);
    if (d2 > 1.0) discard;

    float alpha = exp(-d2 * 4.0);
    alpha *= vLife * uFadeAlpha;

    float age = 1.0 - vLife;
    vec3 col = fireColor(age);
    col *= 1.0 + (1.0 - age) * 0.15;

    FragColor = vec4(col, alpha);
}
)GLSL";
