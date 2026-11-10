# Demo Runtime v51 — C++/OpenGL 3.3

Минимальный рантайм демо-интро. Без HUD, без CrashHandler, без внешних зависимостей.

## Состав

```
demo_intro_v51/
├── demo_runtime.cpp      — точка входа (WinMain + окно + GL контекст + render loop)
├── demo.smt              — данные показа (60 c, 7 клипов, 5 сегментов)
├── gl_executor.hpp       — GL binding: FBO pool, ShaderCache, executeOp, renderFrame
├── sm_runtime.hpp        — SMT-парсер, RPN-вычислитель, audio_vars, segment_at
├── opengl_loader.h       — загрузка функций OpenGL 3.3 core
├── build_demo_runtime.bat — сборка через MSVC (cl)
└── shaders/              — 11 .frag файлов (fullscreen quad fragment shaders)
    ├── nebula_raymarch.frag   — сцена 1 (raymarching)
    ├── sphere_scene.frag      — сцена 2 (орбитальная сфера)
    ├── particle_swarm.frag    — сцена 3 (рой частиц)
    ├── crossfade.frag         — переход 1→2
    ├── flash.frag             — переход 2→3
    ├── vignette.frag          — post-effect (вся демонстрация)
    ├── anxiety_mist.frag      — (не используется в текущей .smt)
    ├── bloom.frag             — (не используется)
    ├── grain.frag             — (не используется)
    ├── morph_grid.frag        — (не используется)
    └── cozy_room_sdf.frag     — (не используется)
```

## Сборка (Windows + MSVC)

Откройте **Developer Command Prompt for VS** (или `vcvarsall.bat x64`),
перейдите в папку `demo_intro_v51` и запустите:

```bat
build_demo_runtime.bat
```

Команда под капотом:
```
cl /std:c++17 /EHsc /O2 /W3 demo_runtime.cpp /I. /link opengl32.lib user32.lib gdi32.lib
```

Результат: `demo_runtime.exe` в той же папке.

## Запуск

```bat
demo_runtime.exe
```

Программа ищет `demo.smt` и папку `shaders/` в текущей рабочей директории.
Лог пишется в `trace.log` (append). При запуске старый `trace.log` удаляется.

## Управление

- **ESC** — выход
- Закрытие окна крестком — выход

## Структура показа

| Время | Что происходит |
|-------|----------------|
| 0–13 c    | nebula_raymarch |
| 13–17 c   | crossfade → sphere_scene |
| 17–28 c   | sphere_scene |
| 28–32 c   | flash → particle_swarm |
| 32–60 c   | particle_swarm |
| 0–60 c    | vignette (поверх) |

## Что логируется

```
[Start] Demo Runtime — loading demo.smt
[OK] SMT loaded: duration=60.0s, 7 clips, 5 segments
  clip 's1' effect='nebula_raymarch' opacity_tokens=1 progress_tokens=4 uniforms=5
  ...
[Window] HWND=... created at (312,160) size 1296x759 (client 1280x720)
[Window] Visible=true, foreground set
[GL] NVIDIA GeForce GTX 750 / 3.3.0 NVIDIA 560.94
[OK] 6 shader programs compiled
[Loop] Entering render loop, duration=60.0s
[Loop] First frame rendered, T=0.003s
[Loop] T=5.04s frames=124
...
[Done] Show finished at T=60.00s, frames=3252
[Loop] Exited, total frames=3252
[Exit] Demo Runtime ended
```

Если строка `[Loop] First frame rendered` не появилась — первый `renderFrame` упал,
смотрите `[Error] renderFrame exception at T=...: ...` с причиной.
