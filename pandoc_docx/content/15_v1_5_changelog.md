# 15. v1.5 changelog --- что нового (Tasks 57-66)

Краткий список изменений v1.4 → v1.5:

**1. Сигил & (Task 62).** Новый 5-й сигил --- & --- для предложений и обсуждения методов. 3 глагола: &suggest, &review, &plan. trace.log не нужен. BTB delta=\[\].

**2. Code booster v1.0 разобран (Task 63).** booster_final.json (74 КБ) --- ngram-статистика GLSL/Cg стиля, 3 674 контекста, 7 правил. top1=54%, top3=77%, top5=85%.

**3. Code booster v1.1 --- 6 расширений (Task 64).** compat_layer + llm_layers + query_api + llm_self_test + not_for_llm_prompt + validation_pipeline. Schema 1.0 → 1.1. Scripts: apply_booster_v2.py (patcher) + query_booster.py (dynamic lookup).

**4. Kill-switch ОТКЛОНЁН.** Сигил × с глаголами ×disallow/×allow, Rules 16-18, disallowed/ папка --- предложены в reqs_killswitch.md, REJECTED пользователем. Принцип: не плодить инфраструктуру «про запас» (как с !macro в Task 53).

**5. First booster v1.1 cycle closed (Task 65).** !fix \*shader\* nebula upper-cyan на v49: L1 loaded + L2 2/2 HIT + L3 skip + L4 4/4 PASS + L5 5/5 PASS. BTB !fix \*shader\* first measured entry, conf=0.75.

**6. v49 milestone (Task 66).** demo_intro_v49_WORKING.zip заморожен (MD5 6539b119..., 171 КБ). Четвёртый milestone (v43/v47/v48/v49). lastgood → v49.

**7. Aesthetics doc создан.** aesthetics.md v0.4 (316 строк) --- pure principles без project-specific refs. 3-image comparative analysis (warehouse surreal / mage combat / zombie horse graveyard). docx generated (508 КБ, 10 pages, 3 embedded images).

**8. GLSL validator pipeline formalised (Task 59).** glslangValidator 15.2.0 через scripts/validate_glsl.py. Pre-delivery blocking layer. meta.auto += \[glsl:validator\]. Live: caught noise3 collision в v47 → v48 fix.

**9. meta.auto расширена.** + \[booster:v2\], \[booster:canonical\], \[booster:query\], \[booster:patcher\], \[booster:first-measured\], \[v:49\], \[md5:v49\], \[md5:v48\] (milestone frozen).

**10. Документация расширена.** §3 Сигилы: 4 → 5. §4.2: новый подраздел для & глаголов. §10.1: note про kill-switch REJECTED. §11: +12 новых терминов. §13.1: v1.5 extension (Tasks 57-66). §14: НОВЫЙ раздел про code booster v1.1 (6 подразделов). §15: этот changelog.

Протокол остаётся lean: 5 сигилов (? ! @ \# &), 8+3 глаголов, без макросов, без автоматизированной инфраструктуры отказа. Принцип «не расширять про запас» соблюдён.
