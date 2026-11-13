# Demo Runtime v53 — FPS Counter (F1 в заголовке окна)

v53 = v52 stable + возврат FPS counter как в v48–v50.

Базируется на `milestone_v52_stable` (120 c, bloom + vignette + grain).
Изменён только `demo_runtime.cpp` — добавлена обработка F1 и обновление заголовка
окна с FPS/T/frames. .smt и все шейдеры **без изменений**.

## Что нового в v53

| Компонента | Изменение |
|------------|-----------|
| `demo_runtime.cpp` | +5 static globals (`g_showFPS`, `g_fpsFrames`, `g_fpsAccum`, `g_fpsValue`, `g_titleBuf`) |
| | +`VK_F1` handler в WndProc: `g_showFPS = !g_showFPS` |
| | +блок расчёта FPS в render loop (после `SwapBuffers`) |
| | заголовок окна обновляется каждые 0.5 с когда F1 включён |
| | заголовок показывает: `Demo Runtime v53 | 60.0 FPS | T=12.34s | frames=735 | ESC quit, F1 toggle FPS` |
| `demo.smt` | без изменений (v52 iter.3: 120 c, 9 clips, bloom+vignette+grain) |
| `shaders/*.frag` | без изменений (11 файлов) |
| `gl_executor.hpp`, `sm_runtime.hpp`, `opengl_loader.h` | без изменений |

## Управление

| Клавиша | Действие |
|---------|----------|
| **ESC** | Выход |
| **F1**  | Переключить показ FPS в заголовке окна (on/off) |

Когда F1 **off** (по умолчанию): заголовок
`Demo Runtime v53  -  ESC quit, F1 toggle FPS`

Когда F1 **on**: заголовок обновляется 2×/сек, формат
`Demo Runtime v53  |  60.0 FPS  |  T=12.34s  |  frames=735  |  ESC quit, F1 toggle FPS`

## Расчёт FPS

```cpp
// Накопление за 0.5 с окно (как в v48-v50):
g_fpsFrames++;
g_fpsAccum += dt;
if (g_fpsAccum >= 0.5) {
    g_fpsValue = (double)g_fpsFrames / g_fpsAccum;
    g_fpsFrames = 0;
    g_fpsAccum = 0.0;
    SetWindowTextA(g_hwnd, ...);
}
```

Почему 0.5 с окно, а не каждый кадр: цифра в заголовке не должна «дёргаться»
(на GTX 750 с vsync цифра стабильно около 60; без усреднения были бы скачки
55–62). Обновление 2×/сек даёт достаточно реакции и стабильное отображение.

## Сборка и запуск

```bat
build_demo_runtime.bat
demo_runtime.exe
```

После старта нажмите **F1** — в заголовке появятся замеры. ESC — выход.

## Что должно произойти

При F1 on заголовок окна показывает实时 FPS, текущее время T (от 0.00 до 120.00),
и количество отрендеренных кадров. Это позволяет:

- **Замерять FPS на разных сценах** (нажмите F1 в нужный момент и смотрите)
- **Видеть текущее время** без открытия trace.log
- **Отслеживать прогресс** (frame count растёт, FPS должен быть 50–100)
- **Diagnose stalls** — если FPS резко падает, заголовок сразу это покажет

## trace.log

В trace.log добавилась строка после `[Loop] Entering`:
```
[Help] F1 = toggle FPS in window title
```

Остальной trace.log не изменился — логирование каждые 5 с (`[Loop] T=... frames=...`)
продолжает работать независимо от F1.

## Что дальше

Если F1 → FPS работает как ожидалось — v53 можно зафиксировать как milestone.
Возможные расширения v54:
- **B**: On-screen overlay (текст поверх 3D-сцены через `glRasterPos` + `glBitmap`)
- **C**: Min/max/avg FPS за всё время показа + write в trace.log
- **D**: Fullscreen mode (WS_POPUP, F11 toggle)