# ROADMAP — рабочая память проекта Demo Intro

**ПЕРЕЧИТЫВАТЬ ПРИ КАЖДОМ ЗАПРОСЕ!** Сохранять в `/home/z/my-project/roadmap.md`
и `/home/z/my-project/download/demo_intro/roadmap.md` (backup).

## 📌 ТЕКУЩЕЕ СОСТОЯНИЕ: v48 — CONFIRMED + code booster (booster_final.json) + сигил & (предложения) + sigil+BTB protocol v2.1 ✅

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
- `download/demo_intro_latest.zip` — rolling-latest (v45 код + protocol-файлы meta.auto/btb_stats.json): 77421 байт, MD5 `900e38a607457dd944b7e2347d7b46cc`. v43 milestone (c0cb…) — отдельно, заморожен.

### mingw ВЫКИНУТ из workflow (user instruction, Task 44):
Пользователь сказал «больше не компилируй под mingw». MSVC — единственный
путь сборки. build_mingw.bat ОСТАЁТСЯ в проекте (исторический/опциональный),
но я его не запускаю и не проверяю код mingw-компилятором. Минус: у меня
нет локальной верификации (MSVC тут нет) → правки проверяются сборкой на
стороне пользователя, он ретранслирует вывод cl / trace.log.

### trace.log — единый диагностический файл (Task 45, user instruction):
**ОДИН файл `trace.log`** = build-вывод + runtime-лог. Пользователь
присылает его ВСЕГДА — этого достаточно для диагноза.
- **build_msvc.bat**: при старте `> trace.log` (truncate) + баннер
  `=== BUILD START %DATE% %TIME% ===` + Target architecture; вывод `cl`
  redirect'ится `>> trace.log 2>&1` (все ошибки/варнинги компиляции — туда);
  финал: `=== BUILD OK ===` или `=== BUILD FAILED with error level N ===`.
- **main.cpp Log()**: пишет в `trace.log` режимом **append** (`fopen "a"`) —
  дописывает к build-секции. Первый вызов пишет баннер
  `=== RUN START YYYY-MM-DD HH:MM:SS.mmm ===` (GetLocalTime) — отделяет
  runtime от build. Небуферизованный — переживает любой краш.
- CrashHandler пишет `[FATAL] Exception 0x… at …` в тот же trace.log.
- Итог: в одном файле видно ВСЁ — что сказал компилятор + что сделала
  программа + где/почему упала. Прежнее имя `demo_intro_log.txt` убрано.

### v45 ПОДТВЕРЖДЕНА рабочей (чистый trace.log получен 2026-10-30 16:24):
x64-сборка, cl без ошибок/варнингов, arch=64-bit, NVIDIA GTX 750,
GL 3.3, все milestone'ы OK, `First frame rendered 1920x1080`,
`[Exit] ESC pressed` → `Main loop ended (code 0)`. Эталонный хороший
trace сохранён: `download/demo_intro/trace_v45_GOOD_reference.log`
(1048 байт, 26 строк). При будущих багах — сравнивать с ним.

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
45 — trace.log unified (user instruction): ОДИН файл = build + runtime.
    build_msvc.bat: truncate + баннер + redirect cl >> trace.log 2>&1.
    main.cpp Log(): append-режим + RUN START banner с таймстампом.
    CrashHandler пишет туда же. Прежнее demo_intro_log.txt убрано.
    Пользователь присылает trace.log всегда.
46 — rule 13: нет trace.log → блок «⚠ Где trace.log? Атдай!» + отмена.
47 — rule 14: ведущий '?' → rule 13 off (soft variant).
48 — soft variant rule 14 подтверждён (правки под '?' разрешены, верификация отложена).
49 — ПРОТОКОЛ sigil+BTB принят (user #ok): 4 сигила (? ! @ #) + 8 глаголов
    ! (fix feat remove revert diag snapshot verify clean) + @ автотокены
    (maxTask/latestZip/milestone/mine/auto/lastgood) + meta.auto (файл-конфиг,
    декларативный) + btb_stats.json (BTB как ФАЙЛОВЫЙ read-modify-write
    артефакт, НЕ фоновая магия; hit/miss = prefetch accuracy, отдельная ось
    от work outcome в roadmap; auto-prune <0.3) + verb-mandatory agreement
    (сигил обязателен в формальном запросе; глагол обязателен внутри !)
    + !remove глагол. docx → v1.0. Rules 5/6/8/10/13 переформулированы
    в терминах грамматики.
50 — #proto amendment (user #ok): after: — исполняемый предикат DSL
    (contains/grep==N/NOT/AND/OR), проверяется grep -c по trace.log.
    meta.auto [after:default] → псевдокод. docx → v1.1 (+раздел 8.1 DSL,
    примеры 9.2/9.4 переписаны в псевдокод). Лечит слабость LLM в проверке
    отсутствия: 'нет milestone' → grep(STR)==0 (точный счётчик).
51 — #proto: команда #stats (метрики BTB). btb_stats.json +schema: pruned[],
    last_stats. #stats → отчёт (hits/misses/hit-rate, top-3 файла, per-сигнатура,
    pruned). Nudge: если last_stats >7 дней — напоминаю. docx +раздел 7.5.

---

## 🛠 ИНСТРУМЕНТЫ

**Сборка (единственный путь):** MSVC на стороне пользователя.
`build_msvc.bat` из "x64 Native Tools Command Prompt for VS 2022".
Батник печатает `Target architecture: x64`. Локально MSVC недоступен.

**GLSL validator (Task 59):** scripts/validate_glsl.py → glslangValidator 15.2.0 (tools/glslang/). Run before !*shader* delivery. errors=blocking.

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
4. Перед отправкой архива — пройти чек-лист (v45):
   - opengl_loader.h: НЕТ typedef GLsizei/GLint/... (типы из GL/gl.h) ✓
   - opengl_loader.h: DECL_GL_FN С APIENTRY, точные прототипы, БЕЗ вариадика ✓
   - main.cpp: `#include <GL/gl.h>` ПЕРЕД "opengl_loader.h" ✓
   - `/MT /std:c++17 /Zc:__cplusplus /utf-8 /F8388608` в build_msvc.bat ✓
   - build_msvc.bat печатает %VSCMD_ARG_TGT_ARCH% ✓
   - g_defaultVAO в main.cpp ✓
   - SetProcessDpiAwareness в main.cpp ✓
   - g_droplets = false ✓
   - SetUnhandledExceptionFilter + CrashHandler в main.cpp ✓
   - g_lastMissingGLFn в opengl_loader.h + лог имени ✓
   - GL_SHADING_LANGUAGE_VERSION 0x8B8C #ifndef в loader ✓
   - НИ ОДИН raw-литерал в shaders.h не больше 8,000 байт
     (лимит x64 MSVC 16,384) ✓
   - _CRT_SECURE_NO_WARNINGS в начале main.cpp ✓
   - в zip включён roadmap.md ✓
   - mingw НЕ компилировать (user instruction); верификация — на стороне
     пользователя, он присылает trace.log (build + runtime)
   - build_msvc.bat пишет build-секцию в trace.log (truncate + баннер +
     `cl >> trace.log 2>&1`) ✓
   - main.cpp Log() пишет в trace.log режимом append + RUN START баннер ✓
   - в исходниках НЕТ упоминаний demo_intro_log.txt (устарело) ✓
   - GLSL validated (glslangValidator, scripts/validate_glsl.py) ✓ для !*shader* delivery
5. ВСЕГДА сообщать пользователю: путь к архиву + MD5 + размер
   (в терминах протокола: в ответе — @md5= / @v= / размер).
6. Backup в `backup_v{N}_*/` перед каждым архивом
   (в протоколе: авто для любого !-действия).
7. Параллельно обновлять roadmap.md (primary + backup).
8. ПОСЛЕ КАЖДОГО ЗАПРОСА — ЧИСТИТЬ СТАРЫЕ ФАЙЛЫ (глагол !clean):
   - temp .bak_*, *.tmp, /tmp/demo_intro*.exe
   - backup folders старше 3 задач
   - Оставлять: source + build scripts + roadmap.md + meta.auto +
     btb_stats.json + 2-3 backups + zip
9. State drift guard: если grep возвращает 0 — пере-применять фиксы.
10. НЕ бросать сессию после правок без сборки архива и сообщения
    (путь + MD5 + размер) — иначе пользователь не может скачать.
    В протоколе: ответ = #ack + @md5 + deliverable + btb-репорт.
11. SANDBOX CAN ROLLBACK: /home/z/my-project/ не гарантирует persist.
    Canonical = у пользователя. Каждый delivered zip + MD5 = чекпойнт.
    В новый запрос (особенно после паузы) — давать контекст (roadmap/лог/
    папку). Milestone zip (v43_WORKING) НЕ перезаписывать.
12. trace.log — ЕДИНЫЙ диагностический файл (user instruction Task 45).
    Пользователь присылает его ВСЕГДА. В нём: build-секция (ошибки/варнинги
    cl, errorlevel) + runtime-секция (RUN START баннер, milestone'ы, GL
    строки, [FATAL] при краше). При разборе проблемы — читать trace.log
    целиком, не просить «опиши словами». Если trace.log пустой/отсутствует
    → процесс не стартовал (SmartScreen/AV) или собран не из этой папки.
13. НЕТ trace.log → НЕ ВЫПОЛНЯТЬ запрос (user instruction Task 46).
    В терминах протокола: срабатывает на !-глаголах fix/feat/remove/diag
    без ведущего '?' и без @trace=attached. Если сработало — СРАЗУ вывести
    визуально-агрессивное предупреждение:
      ╔══════════════════════════════════════════════╗
      ║   ⚠️  ГДЕ trace.log? АТДАЙ!  ⚠️              ║
      ╚══════════════════════════════════════════════╝
    и ОТМЕНИТЬ запрос (не делать работу, не угадывать вслепую). trace.log
    = единственный канал диагностики (rule 12). Без него — стоп. Это
    дисциплина обратной связи, пользователь её закрепил.
14. Ведущий '?' в сообщении → правило 13 ПРИОСТАНОВЛЕНО для этого
    сообщения (user instruction Task 47; soft variant ПОДТВЕРЖДЁН Task 48).
    Назначение: не-диагностические сообщения — концептуальные вопросы,
    планирование, обсуждение архитектуры, контекст-recall — где trace.log
    не нужен и требовать его бессмысленно. Проверка: сообщение НАЧИНАЕТСЯ
    с '?' (первый непробельный символ). Если да — отвечаю без требования
    trace.log.
    EDGE CASE (мягкий вариант, окончательно): если '?' сообщение всё же
    просит правку кода — выполняю, но ЯВНО отмечаю, что верификация
    отложена до следующего trace.log (rule 13 реактивируется на follow-up).
    Примечание о сфере rule 13: правило 13 нацелено на запросы правки
    кода / диагноза («особенно к запросу на правку кода / диагноз»).
    Чисто разговорные реплики (подтверждения, «спасибо», согласие с
    правилом) — не являются code/diagnosis-запросами, rule 13 на них не
    срабатывает. Если пользователь захочет строгую буквальную трактовку
    (rule 13 на ЛЮБОЕ не-‘?’ сообщение без trace.log, включая реплики) —
    пусть скажет, тогда затяну.
15. sigil+BTB ПРОТОКОЛ (Task 49, user #ok 2026-10-30). Полное описание —
    в docx sigil_btb_documentation v1.0 + секция PROTOCOL ниже. Кратко:
    - 4 сигила: ? (вопрос, rule 13 off) | ! (действие+глагол) | @ (факт) | # (мета)
    - 8 глаголов !: fix feat remove revert diag snapshot verify clean
    - @ автотокены: maxTask latestZip milestone mine auto; revert: lastgood
    - Файловые артефакты: meta.auto (декларативный конфиг) + btb_stats.json
      (состояние BTB). Survive via zip + canonical, как roadmap.md.
    - BTB = read-modify-write каждый ход (read в начале — prefetch фаза;
      write в конце — перед ответом). НЕ фоновая магия — я stateless между
      промптами, поэтому BTB обязан быть файлом.
    - hit/miss = prefetch accuracy (отдельная ось от work outcome в roadmap).
    - auto-prune: entries confidence<0.3 после N trials → удаляю при write.
    - after: — исполняемый предикат DSL (contains/grep==N/NOT/AND/OR), проверяется `grep -c` по trace.log; work-outcome verification (отдельно от BTB hit/miss). Task 50.
    - Сигил обязателен в формальном запросе; глагол обязателен внутри !.
    - Сигил `&` (Task 62): предложения/обсуждение методов. trace.log не нужен.
      Глаголы: &suggest &review &plan. BTB: delta=[] (базовый набор).
    - Code booster (Task 63): booster_final.json — ngram-статистика GLSL стиля
      (3 674 контекста, 7 правил, 40 arity, 9 test_cases, top3=77%). llm_prompt_block
      вставляю в промпт при !feat/!fix *shader*. НЕ заменяет glslangValidator.
    - btb_stats.json update: в конце каждого хода self-assess hit/miss →
      read-modify-write → репорт в ответе (btb: signature X hit→H/M conf C).
    - BTB v2 (Task 55): delta-only prefetch (base_set НЕ в entries); seed vs measured split;
      Laplace confidence (h+1)/(n+2); shadow_mode (evaluate даже ниже prefetch-порога —
      нет мёртвой зоны 0.3-0.6). BTB = round-trip batching (не parallel-with-parsing).
    - after-DSL v2 (A7): fixed-string (-F), scoped (run.contains/build.contains/line),
      count()=lines, precedence NOT>AND>OR, no bare-string shorthand.
    - status (A10): unverified→passed→confirmed; lastgood = only confirmed.
    - md5:canonical (A6): md5 в #ack chat-блоке = checkpoint; sandbox-md5 сверяется с
      последним напечатанным; chat не откатывается.
    - Signature refinement (Task 52): сигнатуры уточняются через #proto
      (split/merge) при over-fetch или gap. MISS → diagnose gap → fix prefetch.
    - #stats (Task 51): команда → отчёт метрик BTB (hits/misses/hit-rate, top-3
      prefetched файла, per-сигнатура, pruned[] лог). Nudge: если last_stats>7д →
      напоминаю. Pruned записи логируются в btb_stats.json.pruned[].
52 — #proto (user #ok): split #stats в свою BTB-сигнатуру (tighter prefetch
    [btb_stats.json, roadmap.md]); #proto|#ok осталось с [meta.auto, roadmap,
    btb_stats, docx-gen]. BTB SELF-TUNE: этот #ok-ход вскрыл gap (btb_stats.json
    не был в #proto|#ok prefetch) → MISS → btb_stats.json добавлен в prefetch.
    Демонстрирует цикл read-modify-write: miss → diagnose → fix — работает.
53 — #proto: !macro (пользовательские макросы) ОТКЛОНЁН пользователем. Протокол
    остаётся на 8 глаголах. !workflow (multi-turn) — тоже отложен. docx → v1.3
    (+раздел 7.6 BTB self-tuning, +footnote про отклонение !macro). Принцип:
    не расширять про запас — соблюдён.
54 — !feat nebula background (user, trace.log attached, rule 13 passed): shaders.h
    kFragmentShaderSrc — добавлены hash3/noise3/fbm3/NebulaBackground (domain-warped
    FBM + 5 световых узлов + 2 ленты + виньетка); заменены 2 блока background
    (ранний возврат + основной). main.cpp: v45→v46 + milestone [OK] nebula bg rendered.
    after-контракт: contains("[OK] nebula bg rendered") + дефолт. after-PASSED ✅
    (user trace.log v46: все 5 предикатов grep -c ✓: nebula=1, FirstFrame=1, FATAL=0, Exit=2, code0=1).
    v46=WORKING (nebula рендерится, clean exit). arch=x86 (32-bit build — работает, ABI-фикс v42 держит).
    BTB: !feat *shader* MISS (gap: shaders.h не был в prefetch) → prefetch fixed.
55 — РЕФОРМА BTB v2 + priority fixes (review Claude, user #ok):
    A2+A4+A5 — btb_stats.json v2: delta-only prefetch (base_set [meta.auto,btb_stats,roadmap]
    убран из entries; BTB трекает только delta); seed vs measured split; Laplace confidence
    (h+1)/(n+2); shadow_mode (evaluate даже ниже порога — нет мёртвой зоны 0.3-0.6). ?* и #stats
    retired (base-only, no delta). Reframe: BTB = round-trip batching (не parallel-with-parsing).
    A6 — md5:canonical = chat-printed; sandbox-md5 сверяется с последним напечатанным в чате
    (chat не откатывается). 'Нет памяти' → 'нет cross-session памяти; within-chat history видна'.
    A7 — after-DSL fix: fixed-string (-F), scoped (run.contains/build.contains), line-exact
    (run.line), count()=lines, precedence NOT>AND>OR, no bare-string shorthand. Фикс code 0xC0000005
    false-positive + grep('nebula')==0 не ломается на 'nebula.glsl' в выводе компилятора.
    A10 — status: unverified→passed→confirmed; lastgood = only confirmed (не after-passed).
    btb_stats.json v2 schema. docx v1.4 + B-polish → Task 56 (очередь).
56 — !feat probe (BTB v2 live validation, user #ok с trace.log v46): tweak nebula cyan
    0.1→0.15 + [OK] nebula v2 probe milestone. v46→v47. BTB v2 цикл прогнан end-to-end:
    md5:canonical MATCH (A6✓), signature match + delta prefetch (A5✓ delta-only),
    shadow-eval recall=1.0 precision=0.75 HIT, measured{1,0} first real v2 measurement,
    Laplace conf 0.63→0.667 (A2✓). after-verification выявила ДВА execution-бага:
    (L1) grep -F с regex-экранированием \[OK\] → литерал \[ (не [) → 0 match. Фикс: под -F
    НЕ экранировать. (L2) run.line (grep -Fx) хрупок к CRLF (trace.log Windows = \r) → 0.
    Фикс: run.line→run.contains (fixed-string substring, CRLF-robust, точная строка
    '[Exit] Main loop ended (code 0)' безопасна от code 0xC0000005). after-PASSED 4/4 ✓.
    v47=passed (user verbally confirmed «работает, всё в порядке» → effectively confirmed;
    formal confirmed = #milestone или @status=confirmed по A10). meta.auto v2.1 (run.contains).
57 — docx v1.4: cover v1.4; meta.auto example → v2.1 (run.contains + status:levels + md5:canonical +
    btb:source); Table 10 → after-DSL v2.1 (fixed-string -F без экранирования, scoped run.contains
    CRLF-robust, run.line deprecated, precedence NOT>AND>OR) + L1/L2 lessons; cheat sheet per-verb
    trace.log + @v=lastBuild/@task=maxTask; section 13 'v2 reforms summary' (Таблица 11). 20 стр, 12 табл.
    Очередь v1.5: diagram 2/4, #milestone/!snapshot split, # subcommand table+#ok, avoid→allow,
    !clean dry-run, @ precedence, [env:mine] auto-extract, version-cleanup.
58 — #milestone v47 (user): v47 → confirmed (A10). demo_intro_v47_WORKING.zip заморожен (MD5 b0b6413…). lastgood → v47 (latest confirmed; v43 c0cb… — исторический reference, оба заморожены). meta.auto += [md5:v47].
59 — GLSL validator pipeline (code booster, user #ok): glslangValidator 15.2.0 (apt-get download + dpkg-deb -x, без root). scripts/validate_glsl.py — 4 шейдера, glslang OpenGL mode. DEMO v47: 3/4 PASS, kFragmentShaderSrc FAIL (noise3 collision). Протокол: перед !*shader* delivery run validator; errors=blocking, warnings=advisory. meta.auto += [glsl:validator]. noise3 rename → !fix v48 (trace.log).
62 — #proto: НОВЫЙ СИГИЛ `&` + глагол `&suggest` (user #ok). Назначение: обсуждение методов
    оптимизации работы, предложения по улучшению. trace.log НЕ нужен (как ?). Префикс `&` =
    «предложение/обсуждение». Глаголы: &suggest &review &plan. BTB: delta=[] (базовый набор).
63 — code booster: booster_final.json разобран (74 КБ). 3 674 контекста ngram, 7 правил
    (R-01..R-06 hard + S-01 soft), 40 arity-функций, 229 vocab, 40 patterns, 9 test_cases.
    llm_prompt_block (31 строка) — готовый текст для вставки в промпт. Качество: top1=54%,
    top3=77%, top5=85% (leave-one-folder-out, 103 файла, 85 928 токенов). Применение:
    вставляю llm_prompt_block в системный промпт при !feat/!fix *shader* — статистика
    стиля подсказывает вероятные цепочки токенов. НЕ заменяет glslangValidator.
60 — !fix rename noise3→fbmNoise3 (user, trace.log v47 attached, rule 13 ✓): shaders.h — 2 spots
    (definition + fbm3 call). GLSL validator ДО доставки: 4/4 PASS (noise3 collision resolved —
    kFragmentShaderSrc теперь ✓). v47→v48. after: run.contains('[OK] nebula bg rendered') + default.
    after-PASSED ✅ (v48 trace.log: 4/4 predicates ✓ — nebula bg rendered, First frame, no FATAL, Exit code 0). v48=passed. GLSL validator 4/4 + after-predicate 4/4 = full code-booster loop closed (validator catches pre-delivery → fix → validator confirms → after confirms runtime).
61 — #milestone v48 (user): v48 → confirmed (A10). demo_intro_v48_WORKING.zip заморожен (MD5
    0906644ad7d18ac8275e54997a67823c). lastgood → v48 (latest confirmed). Три milestone: v43
    (c0cb…, исторический) + v47 (b0b6413…) + v48 (0906644, latest). Все заморожены. meta.auto += [md5:v48]. BTB: no signature match (!fix on shaders.h not
    covered by !feat*shader*|!fix main.cpp*) → BTB-neutral. GAP: add !fix *shader* to signature (#proto).

---

## 🔖 PROTOCOL sigil+BTB (Task 49)

Язык общения пользователь↔ассистент. Подробно — docx sigil_btb_documentation v1.0.

### 4 сигила (тип строки)
| Сигил | Тип | trace.log |
|------|-----|----------|
| ? | вопрос/обсуждение | нет (rule 13 off) |
| **&** | **предложение/обсуждение методов** (Task 62) | нет |
| ! | действие + глагол | да для fix/feat/remove/diag |
| @ | факт/состояние | — |
| # | мета (правило/milestone/proto) | — |

### 8 глаголов `!`
!fix !feat !remove !revert !diag !snapshot !verify !clean

### Глаголы `&` (предложения, Task 62)
&suggest &review &plan   (обсуждение методов оптимизации; trace.log не нужен)

### Мета-команды `#`
#rule  #milestone  #proto  #stats  #ok   (#stats — отчёт метрик BTB)

### Отклонённые фичи (для протокола)
- !macro (Task 53) — ОТКЛОНЁН. 8 глаголов достаточно.
- !workflow (multi-turn с user-gates) — отложен до реальной потребности.
(сигил обязателен в формальном запросе; глагол обязателен внутри !)

### @ автотокены (вместо чисел/хешей)
@v=maxTask  @md5=latestZip  @md5=milestone  @status=auto  @env=mine  @trace=auto
revert: lastgood

### Файловые артефакты протокола (survive via zip + canonical)
- **meta.auto** — декларативный конфиг автоподстановки (правила + пиннутые
  значения). Ведёт ассистент; substantive-правки (avoid-список, новые токены)
  — через #proto + ack пользователя. Routine (env, milestone-md5) — по прямому
  указанию. Не learning-таблица.
- **btb_stats.json** — состояние BTB: per-сигнатура {hits, misses, confidence,
  last_result, prefetch[]}. Read-modify-write каждый ход.

### BTB = read-modify-write каждый ход (НЕ фоновая магия)
1. Старт хода: read meta.auto + btb_stats.json → match сигнатуры сообщения →
   если confidence≥0.6, запускаю prefetch (read-only, cheap, параллельно).
2. Работа — выполняю запрос.
3. Конец хода (перед ответом): self-assess hit/miss (prefetch accuracy —
   отдельная ось от work outcome в roadmap) → read-modify-write btb_stats.json
   → auto-prune entries confidence<0.3 после N trials.
4. В ответе: `btb: signature X hit→H/M conf C` (прозрачность).

### Синтаксис !feat/!remove
```
!feat|!remove  <описание фичи обычным языком>
  scope:   (опц., default=infer)
  after:   (опц., исполняемый предикат DSL: contains/grep/NOT/AND/OR; default из meta.auto)
  revert:  lastgood  (опц., default)
  prio:    optional|required (опц., default optional)
  notes:   (опц., свободный текст, без номеров задач)
```
Пользователь пишет: описание + иногда after/notes. Остальное — дефолты из meta.auto.

### Правила-предшественники (уже в rules 12-14)
12 — trace.log единый файл-отчёт. 13 — нет trace.log → блок. 14 — ведущий '?' → rule 13 off.
