# ROADMAP — рабочая память проекта Demo Intro

**ПЕРЕЧИТЫВАТЬ ПРИ КАЖДОМ ЗАПРОСЕ!** Сохранять в `/home/z/my-project/roadmap.md`
и `/home/z/my-project/download/demo_intro/roadmap.md` (backup).

## 📌 ТЕКУЩЕЕ СОСТОЯНИЕ: v43 — РАБОЧАЯ ✅ (user confirmed 2026-10-30)

**Проект:** демо-интро на C++/OpenGL 3.3 + WebGL2 preview
**Папка:** `/home/z/my-project/download/demo_intro/`
**Архив rolling:** `/home/z/my-project/download/demo_intro_latest.zip`
**Архив milestone (замороженный):** `/home/z/my-project/download/demo_intro_v43_WORKING.zip`

**Окружение пользователя:** Windows 11 Pro 23H2, NVIDIA GeForce GTX 750,
driver 560.94, OpenGL 3.3 core. Сборка: MSVC (x64 Native Tools), x64 target.

### СТАТУС: ИНТРО РАБОТАЕТ У ПОЛЬЗОВАТЕЛЯ.
v43 собрана MSVC x64, запущена, рендерит. Долгая охота за двумя багами
закончена (см. Task 42 + 43 ниже — корневые причины доказаны).

### Sandbox recovery (Task 44, ВАЖНО для будущих сессий):
Между двумя сообщениями sandbox пересоздался и откатился к старому снимку
(v12–v15). Всё, что я сделал в этой сессии (v39→v43, roadmap.md, бекапы,
demo_intro_latest.zip), пропало из моего окружения. Пользователь
реаплоаднул рабочий zip (MD5 c0cb…) — я восстановил sandbox из него.
**УРОК:** canonical-копия живёт у пользователя; мой sandbox — черновик,
может быть откачен в любой момент. В новый запрос пользователь должен
давать контекст (roadmap/лог/папку), если был разрыв.

### Замороженный milestone (Task 44):
- `download/demo_intro_v43_WORKING.zip` — байт-в-байт копия
  пользовательского рабочего zip (MD5 `c0cbce51ba1b11f90cbfc474c0b2d70a`,
  70870 байт). НИКОГДА не перезаписывать — это эталон «версии, которая
  работает».
- `download/demo_intro/backup_v43_working_milestone/` — папка с 8
  исходниками + MILESTONE.txt.
- `download/demo_intro_latest.zip` — rolling-latest, сейчас == milestone.

### mingw ВЫКИНУТ из workflow (user instruction, Task 44):
Пользователь сказал «больше не компилируй под mingw». MSVC — единственный
путь сборки. build_mingw.bat ОСТАЁТСЯ в проекте (исторический/опциональный),
но я его не запускаю и не проверяю код mingw-компилятором. Минус: у меня
нет локальной верификации (MSVC тут нет) → правки проверяются сборкой на
стороне пользователя, он ретранслирует вывод cl / demo_intro_log.txt.

---

## КОРНЕВЫЕ ПРИЧИНЫ (доказаны, fixation history)

**Баг A — чёрный экран (mingw x64):** вариадик-указатель `type (*)(...)`
из Task 20 → компилятор продвигает float в double (`cvtss2sd`, доказано
дизассемблером scripts/abi_test_proof.cpp) → драйвер читает мусор в
uniform'ах → uTime/uResolution = 0 → чёрный экран.

**Баг B — крах 0xC0000005 в nvoglv32.dll (MSVC x86):** тот же вариадик =
cdecl, а GL-функции = stdcall → дрейф ESP → крах на первом glCreateShader.

**Баг C — C2026 string too big (MSVC x64):** лимит строкового токена x64 cl
= 16,384 байт; главный шейдер был разбит на литералы 17,995 + 16,192 байт.
Математика совпала со строкой ошибки 344 (= 371 − 27).

**Фиксы:** v42 (точные APIENTRY-прототипы, лечит A+B) + v43 (сплит литералов
≤8 КБ + _CRT_SECURE_NO_WARNINGS, лечит C).

---

## 📋 ВСЕ ЗАПРОСЫ (кратко)

19 — небула-фон (откачено в Task 34)
20 — opengl_loader.h mingw фикс (GLsizei=int, вариадик PFN) ← КОРЕНЬ БАГА A/B
21 — void* касты (убрать варнинги)
22 — -static (libstdc++-6.dll)
23 — DPI + fullscreen
24 — /MT для MSVC
25 — objdump анализ
26 — расширенное логирование
27 — VAO фикс (GL_INVALID_OPERATION ушёл, но экран чёрный)
28 — glReadPixels: (0,0,0) во всех пикселях → шейдер пишет чёрный
29 — droplets off (рекурсия)
30 — roadmap.md создание
31 — debug gradient mode (G key) → жёлтый = GL pipeline работает
32 — PCG hash (не помог — mode 3/4/5 всё ещё чёрные)
33 — прямые клавиши 0/2/3/4/5
34 — rollback на v18
35 — v18 + minimal fixes
36 — v18 + PCG hash
37 — cleanup старых файлов
38 — MSVC ready (build_msvc.bat обновлён)
39 — MSVC compat: opengl_loader.h без GL typedef'ов + без __stdcall
    в вариадике (C2371/C2165), include order в main.cpp
40 — ПЕРЕСБОРКА АРХИВА (сессия оборвалась): -static восстановлен,
    roadmap.md в zip, компиляция перепроверена
41 — ДИАГНОСТИКА «ничего не происходит»: лог-файл, краш-фильтр,
    имя GL-функции, GL-строки, стек 8 МБ. РЕЗУЛЬТАТ: контекст NVIDIA
    OK, краш 0xC0000005 в nvoglv32.dll на первом GL-вызове → 32-битная
    сборка + cdecl/stdcall-мисматч
42 — КОРНЕВОЙ ФИКС: вариадик-указатель заменён точными APIENTRY-
    прототипами (26 функций). float→double promotion в вариадике
    доказан дизассемблером = причина чёрного экрана; cdecl/stdcall
    мисматч = причина краха. Лечит оба
43 — C2026 string too big при x64-сборке: лимит строкового токена
    x64 cl = 16,384 байт (математика совпала со строкой 344!).
    Оба литерала главного шейдера разбиты на куски ≤ 8 КБ с
    байт-в-байт проверкой склейки; + _CRT_SECURE_NO_WARNINGS
44 — MILESTONE: v43 подтверждена рабочей пользователем. Sandbox
    откатился к v12–v15 — восстановлен из реаплоада zip (MD5 c0cb…).
    Создан замороженный milestone `demo_intro_v43_WORKING.zip` +
    папка backup_v43_working_milestone/. mingw выкинут из workflow
    (MSVC — единственный путь). Canonical-копия = у пользователя.

---

## 🛠 ИНСТРУМЕНТЫ

**Сборка (единственный путь):** MSVC на стороне пользователя.
`build_msvc.bat` из "x64 Native Tools Command Prompt for VS 2022".
Батник печатает `Target architecture: x64`. Локально MSVC недоступен.

**mingw cross-compiler (НЕ ИСПОЛЬЗОВАТЬ — user instruction Task 44):**
команда оставлена только как историческая справка; запускать нельзя.
```bash
# (исторически, НЕ ЗАПУСКАТЬ)
x86_64-w64-mingw32-gcc-posix -x c++ -O2 -std=c++17 -Wall -Wextra ...
```

**Восстановление sandbox после отката:**
1. Пользователь реаплоадит demo_intro_latest.zip (или рабочую папку).
2. `md5sum` сверяем с эталоном c0cb… (v43) или с тем, что было в последнем
   сообщении.
3. `rm -rf download/demo_intro && unzip upload/demo_intro_latest.zip -d download/`
4. Проверить маркеры (см. чек-лист ниже).

---

## 📝 ПРАВИЛА

1. ПЕРЕЧИТЫВАТЬ roadmap.md в начале каждого запроса.
2. Если primary отсутствует — восстановить из backup (demo_intro/roadmap.md).
   Если обе отсутствуют — sandbox откатился; просить пользователя реаплоад.
3. Проверять state через grep — при расхождении пере-применять фиксы
   (State drift guard, см. реальный случай: потеря -static при v39).
4. Перед отправкой архива — пройти чек-лист (v43):
   - opengl_loader.h: НЕТ typedef GLsizei/GLint/... (типы из GL/gl.h) ✓
   - opengl_loader.h: DECL_GL_FN С APIENTRY, точные прототипы, БЕЗ вариадика ✓
   - main.cpp: `#include <GL/gl.h>` ПЕРЕД "opengl_loader.h" ✓
   - `/MT /std:c++17 /Zc:__cplusplus /utf-8 /F8388608` в build_msvc.bat ✓
   - build_msvc.bat печатает %VSCMD_ARG_TGT_ARCH% ✓
   - g_defaultVAO в main.cpp ✓
   - SetProcessDpiAwareness в main.cpp ✓
   - g_droplets = false ✓
   - Log() пишет в demo_intro_log.txt (файл, не только DebugView) ✓
   - SetUnhandledExceptionFilter + CrashHandler в main.cpp ✓
   - g_lastMissingGLFn в opengl_loader.h + лог имени ✓
   - GL_SHADING_LANGUAGE_VERSION 0x8B8C #ifndef в loader ✓
   - НИ ОДИН raw-литерал в shaders.h не больше 8,000 байт
     (лимит x64 MSVC 16,384) ✓
   - _CRT_SECURE_NO_WARNINGS в начале main.cpp ✓
   - в zip включён roadmap.md ✓
   - mingw НЕ компилировать (user instruction); верификация — на стороне
     пользователя, он присылает вывод cl / demo_intro_log.txt
5. ВСЕГДА сообщать пользователю: путь к архиву + MD5 + размер.
6. Backup в `backup_v{N}_*/` перед каждым архивом.
7. Параллельно обновлять roadmap.md (primary + backup).
8. ПОСЛЕ КАЖДОГО ЗАПРОСА — ЧИСТИТЬ СТАРЫЕ ФАЙЛЫ:
   - temp .bak_*, *.tmp, /tmp/demo_intro*.exe
   - backup folders старше 3 задач
   - Оставлять: source + build scripts + roadmap.md + 2-3 backups + zip
9. State drift guard: если grep возвращает 0 — пере-применять фиксы.
10. НЕ бросать сессию после правок без сборки архива и сообщения
    (путь + MD5 + размер) — иначе пользователь не может скачать.
11. SANDBOX CAN ROLLBACK: /home/z/my-project/ не гарантирует persist.
    Canonical = у пользователя. Каждый delivered zip + MD5 = чекпойнт.
    В новый запрос (особенно после паузы) — давать контекст (roadmap/лог/
    папку). Milestone zip (v43_WORKING) НЕ перезаписывать.
