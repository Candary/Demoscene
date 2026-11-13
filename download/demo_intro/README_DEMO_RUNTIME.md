# Demo Runtime v50 — Scene Manager Integration

## Что это

Минимальный рантайм для Scene Manager. Загружает `demo.smt` → рендерит 3 сцены + 2 перехода + post-processing через OpenGL 3.3.

## Содержимое

```
demo_intro/
├── demo_runtime.cpp      # main: Win32 + GL context + render loop
├── gl_executor.hpp       # GL binding: FBO pool, shader cache, pass executor
├── sm_runtime.hpp        # SMT parser + RPN evaluator (reference, no GL)
├── opengl_loader.h       # GL function loader (из v49)
├── demo.smt              # 3-scene show: anxiety_mist → sphere_scene → particle_swarm
├── build_demo_runtime.bat # MSVC build script
├── shaders/              # 11 .frag файлов
│   ├── anxiety_mist.frag
│   ├── sphere_scene.frag
│   ├── particle_swarm.frag
│   ├── crossfade.frag
│   ├── flash.frag
│   ├── vignette.frag
│   ├── bloom.frag
│   ├── grain.frag
│   ├── nebula_raymarch.frag
│   ├── morph_grid.frag
│   └── cozy_room_sdf.frag
└── README_DEMO_RUNTIME.md
```

## Сборка (MSVC)

1. Открой "x64 Native Tools Command Prompt for VS 2022"
2. `cd` в папку `demo_intro/`
3. Запусти:
   ```
   build_demo_runtime.bat
   ```
4. Получишь `demo_runtime.exe`

## Запуск

```
demo_runtime.exe demo.smt
```

- **ESC** — выход
- **SPACE** — пауза

## Что увидишь (35 секунд)

```
0-8s:   anxiety_mist — тёмный туман с красными вспышками
8-12s:  crossfade — плавный переход
12-23s: sphere_scene — сфера с 4 орбитальными сферами
23-27s: flash — переход вспышкой
27-35s: particle_swarm — рой из 16 частиц
+ vignette — затемнение краёв (на протяжении всего демо)
```

## Если не работает

1. Проверь `trace.log` (если есть) — должен быть рядом с .exe
2. Проверь что GPU поддерживает OpenGL 3.3+
3. Проверь что все .frag файлы в папке `shaders/`
4. Пришли screenshot ошибки или trace.log

## Известные ограничения

- Нет музыки (synthetic audio в v51)
- Нет титров (SDF text atlas в v51)
- Resolution: 1280×720 (изменить в demo.smt: `meta` строка)
- Нет интерактивного управления (только ESC/SPACE)
