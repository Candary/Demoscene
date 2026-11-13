# 14. Code booster v1.1 --- GLSL style statistics

Code booster --- это ngram-статистика GLSL/Cg стиля, вычисленная по реальному репозиторию (Demoscene project, 103 уникальных файла, 85 928 токенов). На основе booster\'а я делаю advisory hints при генерации шейдерного кода. Booster НЕ заменяет glslangValidator (blocking) --- это мягкий слой для style alignment.

## 14.1. Booster v1.0 → v1.1 --- 6 расширений (Task 64)

Booster v1.0 содержал только llm_prompt_block (31 строка) --- готовый текст для вставки в промпт. Booster v1.1 (Task 64, user #ok booster-still-on) добавил 6 новых секций, чтобы использовать файл целиком, а не только одну секцию:

  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Секция**              **Назначение**                                                                                                                                  **Применение**
  ----------------------- ----------------------------------------------------------------------------------------------------------------------------------------------- ---------------------------------------------------------------------------------------------
  compat_layer            Mapping Cg → GLSL 3.3 (14 entries: tex2D→texture, float4→vec4, mul(a,b)→((a)\*(b)), :COLOR→out vec4 fragColor и т.д.)                           Применяется ДО интерпретации hints. Cg-лексемы в patterns/nesting auto-translate.

  llm_layers              Consolidated LLM-facing data: static_block (31) + rules_compact (7) + patterns_full (40) + nesting_full (28) + arity_full (40) + meta_quality   L1 layer --- загружается в prompt как \~2500 токенов. Static advisory hints.

  query_api               Dynamic lookup spec: interface, triggers T1-T4, hard_cap 15 calls/task, fallback path                                                           L2 layer --- динамические queries через scripts/query_booster.py. NOT for prompt injection.

  llm_self_test           9 compact test cases (T-C1..T-C5 complete + T-K6..T-K9 check) для mental self-check                                                             L5 layer --- post-generation mental check на known patterns.

  not_for_llm_prompt      Exclusion notes: ngram.contexts (\~150KB, too large для prompt), algorithm, normalization, vocab_full                                           Документация: что НЕ вставлять в prompt, даже если хочется.

  validation_pipeline     5-layer diagram: L1 style + L2 dynamic + L3 syntax (validator) + L4 runtime (after) + L5 self_test                                              Карта pipeline. Precedence: layer N+1 overrides layer N.
  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

*Таблица 12. Code booster v1.1 --- 6 новых секций (schema_version 1.0 → 1.1).*

Canonical path: download/demo_intro/booster_final.json (948 КБ, working copy). Original upload/booster_final.json (328 КБ, v1.0) сохранён как read-only source. Patcher: scripts/apply_booster_v2.py (idempotent, воспроизводит v1.1 из v1.0).

## 14.2. 5-layer validation pipeline

Booster v1.1 встраивается в существующий pipeline валидации. 5 слоёв, каждый со своей ролью и severity:

  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Слой**    **Имя**     **Tool**                                        **Когда**                                          **Severity**   **Cost**
  ----------- ----------- ----------------------------------------------- -------------------------------------------------- -------------- ---------------------------------
  L1          style       llm_layers.static_block + compat_layer          pre-generation (loaded once per \*shader\* task)   advisory       \~2500 tok

  L2          dynamic     query_api → scripts/query_booster.py            mid-generation, per-statement at triggers T1-T4    advisory       0-750 tok (50 per query × 0-15)

  L3          syntax      glslangValidator via scripts/validate_glsl.py   pre-delivery                                       blocking       0

  L4          runtime     after-predicate DSL v2.1 on trace.log           post-execution (user sends trace.log)              verification   0

  L5          self_test   llm_self_test (9 cases, mental check)           post-generation, before delivery                   advisory       0
  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------

*Таблица 13. 5-layer validation pipeline (booster v1.1 integration).*

Precedence: L3 (blocking) overrides L1+L2 (advisory). L4 (runtime verification) overrides всё. L5 --- sanity check, не blocking.

## 14.3. query_booster.py --- CLI interface

Dynamic ngram lookup реализован Python-скриптом. Tokenize partial GLSL → lookup ngram.contexts (3674 entries) с Katz backoff → apply hard rules R-01..R-06 + soft S-01 → return top-k candidates с probabilities.

> python3 scripts/query_booster.py \--code \'\<partial GLSL\>\' \\
>
> \[\--stage fragment\|vertex\|compute\] \[\--top 5\] \[\--self-test\] \[\--show-context\]

Triggers T1-T4 (когда запускать query в ходе генерации):

  ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Trigger**             **Когда срабатывает**                               **Пример**
  ----------------------- --------------------------------------------------- --------------------------------------------------------------------------------------------------------------
  T1                      Choice point с ≥3 plausible candidates              После \`clamp(\` --- может быть VAR/expr/pow/sin. Query даёт top-3: expression 77%, pow 8%, sin 7%

  T2                      Unfamiliar context (function/pattern не в memory)   New SDF primitive --- не помню стиль проекта. Query подсказывает вероятное continuation.

  T3                      Deep nesting ≥ 3 levels of parens                   mix(clamp(dot(N,L),0,1), ...) --- 3+ уровня. ngram-4 даёт real signals.

  T4                      После !fix root-cause = style anomaly               noise3 collision в v47. После fix\'а query на 2-3 ключевых местах, чтобы убедиться, что других аномалий нет.
  ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

*Таблица 14. query_booster.py triggers --- когда запускать L2 dynamic lookup.*

Hard cap: 15 calls per !\*shader\* task. Если превышен --- pause, перепроверить подход (возможно, нужен &plan с пользователем, а не гадать через query). Fallback: если script недоступен --- продолжать с L1 static + L5 self-test только.

## 14.4. GLSL validator pipeline (Task 59)

Pre-delivery blocking layer. glslangValidator 15.2.0 (Khronos official). Установка: apt-get download + dpkg-deb -x (без root). Запуск: scripts/validate_glsl.py --- извлекает 4 shader source (kVertexShaderSrc, kFragmentShaderSrc, kFireVertexShaderSrc, kFireFragmentShaderSrc) из shaders.h, передаёт each в glslangValidator в OpenGL mode.

> \# Протокол: перед каждым !\*shader\* delivery
>
> python3 scripts/validate_glsl.py
>
> \# output:
>
> \# ✓ kVertexShaderSrc \[vert\] PASS
>
> \# ✓ kFragmentShaderSrc \[frag\] PASS
>
> \# ✓ kFireVertexShaderSrc \[vert\] PASS
>
> \# ✓ kFireFragmentShaderSrc \[frag\] PASS
>
> \# === ALL PASS ===
>
> \# errors = BLOCKING (delivery отменяется)
>
> \# warnings = advisory (delivery продолжается, отмечается в ответе)

Live demo: поймал noise3 collision в v47 (kFragmentShaderSrc FAIL --- noise3 это GLSL built-in). v48 rename noise3→fbmNoise3 → 4/4 PASS. Первый full code-booster loop closed (validator catches pre-delivery → fix → validator confirms → after confirms runtime).

## 14.5. First end-to-end cycle (Task 65 --- v49 upper-cyan-fix)

Первая реальная !\*shader\* задача на booster v1.1. v49 upper-cyan-fix --- diagnosed NebulaBackground upper half (uv.y\>0.5) имела только q1 orange + q2 magenta, NO cyan node. Fix: col-mix smoothstep change + new q5 cyan node at (0.5, 0.75).

  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Слой**                **Result**              **Detail**
  ----------------------- ----------------------- -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  L1 static               ✅ LOADED               llm_layers (31 static_block + 7 rules + 40 patterns + 28 nesting + 40 arity + meta_quality) + compat_layer. \~2500 tok в working context

  L2 dynamic              ✅ 2 calls HIT          T1 trigger (choice point for fix approach). Query #1: confirmed \<NUM\> (0.34) typical after \`\*\` → my \`\* 0.5\` matches existing pattern HIT. Query #2: verified q5 line → top-1 \<NUM\> (0.42) → my \`0.5\` HIT. hit_rate 2/2 = 1.000

  L3 self-test            ⏸ mental skip           9 cases T-C1..T-C5 syntax-level, не relevant для color placement fix. T-K6..T-K9 check-action, не запускаются. Skip обоснован

  L4 syntax               ✅ BLOCKING PASS        glslangValidator 15.2.0 --- 4/4 PASS (kFragmentShaderSrc with q5 added OK)

  L5 runtime              ✅ 5/5 PASS             after-predicate run.contains(\'\[OK\] nebula bg rendered\') AND NOT run.contains(\'\[FATAL\]\') --- trace.log v49 contains both markers (×2 for 2 RUN START sections), no FATAL. Default predicate: FirstFrame ✓ + Exit code 0 ✓ + no FATAL ✓
  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

*Таблица 15. First end-to-end booster v1.1 cycle (Task 65, v49 upper-cyan-fix).*

Booster pipeline v1.1 --- FULL CYCLE CLOSED. BTB !fix \*shader\* first measured entry: delta = \[shaders.h:kFragmentShaderSrc, booster_final.json, scripts/validate_glsl.py, md5:latestZip\], seed = 1h/0m, measured = 1h/0m, confidence = 0.75 (Laplace), last_result = hit.

## 14.6. BTB entry для !fix \*shader\* (first measured)

BTB v2 entry для сигнатуры !fix \*shader\* (создана в Task 65, first measured). 5 entries total в btb_stats.json v2 после Task 65.

> {
>
> \"signature\": \"!fix \*shader\*\",
>
> \"delta\": \[\"shaders.h:kFragmentShaderSrc\", \"booster_final.json\",
>
> \"scripts/validate_glsl.py\", \"md5:latestZip\"\],
>
> \"seed\": {\"hits\": 1, \"misses\": 0},
>
> \"measured\": {\"hits\": 1, \"misses\": 0},
>
> \"confidence\": 0.75, \# Laplace: (1+1+1)/(1+1+2) = 3/4
>
> \"last_result\": \"hit\",
>
> \"note\": \"First !fix \*shader\* measured entry (Task 65). Booster L1+L2+L4+L5 closed.\"
>
> }

GAP (Task 61 note): existing signature «!feat \*shader\* \| !fix main.cpp \*» не покрывает !fix \*shader\*. Suggested #proto (future): extend to «!feat \*shader\* \| !fix \*shader\*» (same delta --- shaders.h + booster + validator). Pending refinement via Task 52 signature split/merge mechanism.
