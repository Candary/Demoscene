# 13. v2 reforms summary (Tasks 49-56)

Краткая сводка эволюции протокола с v1.3 → v1.4. Подробности --- в roadmap.md (Tasks 49-56).

  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Реформа**                           **Task**                **Что изменилось**
  ------------------------------------- ----------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  BTB v2: delta-only prefetch           55 (A5)                 base_set \[meta.auto, btb_stats, roadmap\] убран из BTB-entries; BTB трекает только signature-specific delta. ?\* и #stats retired (base-only).

  BTB v2: shadow_mode                   55 (A2)                 evaluate на каждом matчатом ходе, даже ниже порога 0.6 → нет мёртвой зоны 0.3-0.6.

  BTB v2: Laplace confidence            55 (A2)                 (seed_h + meas_h + 1)/(seed_n + meas_n + 2). seed vs measured разделены.

  BTB = round-trip batching             55 (A4)                 reframe: не parallel-with-parsing (LLM читает сообщение целиком, потом tool-calls), а batching. Выигрыш скромный, не 3-4×.

  md5:canonical (chat-printed)          55 (A6)                 md5 в #ack-блоке = checkpoint; sandbox-md5 сверяется с последним напечатанным. Chat не откатывается. \'Нет памяти\' → \'нет cross-session памяти; within-chat history видна\'.

  after-DSL v2.1: fixed-string          55/56 (A7)              grep -F (fixed-string) БЕЗ regex-экранирования; scoped (run.contains/build.contains); run.line CRLF-fragile → deprecated; precedence NOT\>AND\>OR.

  status: unverified→passed→confirmed   55 (A10)                lastgood = only confirmed (user \@status=confirmed или #milestone), НЕ after-passed. Защита от \'log-passed но чёрный экран\'.

  BTB v2 live-validated                 56                      !feat probe: md5 MATCH, delta-only, shadow-eval recall 1.0/precision 0.75 HIT, Laplace 0.63→0.667. 2 execution-бага пойманы (L1, L2) → v2.1.
  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

*Таблица 11. v2 reforms (Tasks 49-56) --- что изменилось с v1.3.*

v1.5: задачи 57-66 продолжают эволюцию протокола. См. таблицу ниже.

## 13.1. v1.5 расширение (Tasks 57-66)

Сводка изменений с v1.4 → v1.5. Подробности --- в roadmap.md (Tasks 57-66).

  --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Task**                **Что сделано**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        **Влияние на протокол**
  ----------------------- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ -------------------------------------------------------------------------------------------------------------------------------------
  57                      docx v1.4: cover v1.4; meta.auto example → v2.1 (run.contains + status:levels + md5:canonical + btb:source); Table 10 → after-DSL v2.1 (fixed-string -F, scoped run.contains CRLF-robust, run.line deprecated, precedence NOT\>AND\>OR) + L1/L2 lessons; cheat sheet per-verb trace.log + \@v=lastBuild/@task=maxTask; section 13 \'v2 reforms summary\' (Таблица 11). 20 стр, 12 табл.                                                                                                                Документация v1.4 formalised everything from Tasks 49-56.

  58                      #milestone v47 (user): v47 → confirmed (A10). demo_intro_v47_WORKING.zip заморожен (MD5 b0b6413...). lastgood → v47.                                                                                                                                                                                                                                                                                                                                                                                   Второй замороженный milestone (после v43).

  59                      GLSL validator pipeline (code booster, user #ok): glslangValidator 15.2.0 (apt-get download + dpkg-deb -x, без root). scripts/validate_glsl.py --- 4 шейдера, glslang OpenGL mode. Протокол: перед !\*shader\* delivery run validator; errors=blocking, warnings=advisory. meta.auto += \[glsl:validator\]. noise3 rename → !fix v48.                                                                                                                                                                  Pre-delivery syntax validation pipeline formalised. Catches built-in collisions (как noise3 в v47).

  60                      !fix rename noise3→fbmNoise3 (user, trace.log v47, rule 13 ✓): shaders.h --- 2 spots (def + fbm3 call). GLSL validator ДО доставки: 4/4 PASS (noise3 collision resolved). v47→v48. after-PASSED ✅ (4/4 predicates).                                                                                                                                                                                                                                                                                   First full code-booster loop closed (validator catches pre-delivery → fix → validator confirms → after confirms runtime).

  61                      #milestone v48 (user): v48 → confirmed (A10). demo_intro_v48_WORKING.zip заморожен (MD5 0906644...). lastgood → v48.                                                                                                                                                                                                                                                                                                                                                                                   Третий замороженный milestone. BTB GAP identified: !fix \*shader\* signature не покрыта.

  62                      #proto: НОВЫЙ СИГИЛ \`&\` + глагол \`&suggest\` (user #ok). Назначение: обсуждение методов оптимизации работы, предложения по улучшению. trace.log НЕ нужен (как ?). Глаголы: &suggest &review &plan. BTB: delta=\[\] (base-only).                                                                                                                                                                                                                                                                     Протокол расширен с 4 до 5 сигилов (? ! @ \# &). 3 новых глагола для &.

  63                      code booster v1.0: booster_final.json разобран (74 КБ). 3 674 контекста ngram, 7 правил (R-01..R-06 hard + S-01 soft), 40 arity-функций, 229 vocab, 40 patterns, 9 test_cases. llm_prompt_block (31 строка) --- готовый текст для вставки в промпт. Качество: top1=54%, top3=77%, top5=85%.                                                                                                                                                                                                            Code booster v1.0 добавлен в протокол как advisory layer для !\*shader\* задач.

  64                      #ok booster-still-on (user): 6 расширений booster_final.json реализованы БЕЗ kill-switch. booster v1.0 → v1.1: compat_layer + llm_layers + query_api + llm_self_test + not_for_llm_prompt + validation_pipeline. scripts/apply_booster_v2.py (patcher) + scripts/query_booster.py (dynamic ngram lookup). Self-test: 4/5 complete-case HIT. Kill-switch ОТКЛОНЁН (reqs_killswitch.md REJECTED).                                                                                                        Code booster v1.1 full integration. 6 new JSON sections + 2 Python scripts. Kill-switch rejected (no × sigil, no Rules 16-18).

  65                      !fix \*shader\* nebula upper-cyan (user, trace.log v48, rule 13 ✓): NebulaBackground diagnosis --- upper half (uv.y\>0.5) имела только q1 orange + q2 magenta, NO cyan node. Fix: (1) col-mix smoothstep(0.4, 0.8, n\*n) → smoothstep(0.3, 0.7, n), (2) added q5 cyan node at (0.5, 0.75). v48→v49. Booster pipeline v1.1 first end-to-end run: L1 loaded + L2 2 calls HIT (hit_rate 2/2) + L3 mental skip + L4 validator 4/4 PASS + L5 after-predicate PENDING. after-PASSED 5/5 ✓ (trace.log v49).   First real !\*shader\* task on booster v1.1. Full pipeline cycle closed. BTB !fix \*shader\* first measured entry, confidence 0.75.

  66                      #milestone v49 (user): v49 → confirmed (A10). demo_intro_v49_WORKING.zip заморожен (MD5 6539b119..., 171 КБ). lastgood → v49.                                                                                                                                                                                                                                                                                                                                                                          Четвёртый замороженный milestone. Booster v1.1 first cycle archived in frozen zip.
  --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

*Таблица 11b. v1.5 расширение (Tasks 57-66) --- что изменилось с v1.4.*

Итог v1.4 → v1.5: +1 сигил (&), +3 глагола (&suggest/&review/&plan), +code booster v1.1 (6 JSON секций + 2 Python scripts + first end-to-end cycle closed), +GLSL validator pipeline (glslangValidator 15.2.0), +3 новых milestone (v47/v48/v49), +aesthetics.md/docx (v0.4 cleaned, 3-image comparative analysis), kill-switch ОТКЛОНЁН. Protocol остаётся lean: 5 сигилов, 8+3 глаголов, без макросов и без автоматизированной инфраструктуры отказа.
