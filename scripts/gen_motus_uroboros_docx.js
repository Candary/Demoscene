const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
        Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
        PageBreak, Footer, Header, PageNumber, NumberFormat,
        TableOfContents, SectionType, TabStopType, TabStopPosition,
        convertInchesToTwip, convertMillimetersToTwip } = require('docx');
const fs = require('fs');

// Dawn Mist Tech palette
const C = {
  primary: "0A1628", body: "1A2B40", secondary: "6878A0",
  accent: "5B8DB8", surface: "F4F8FC", white: "FFFFFF"
};

const noBorders = { top: {style: BorderStyle.NONE}, bottom: {style: BorderStyle.NONE}, left: {style: BorderStyle.NONE}, right: {style: BorderStyle.NONE} };

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 200 },
    children: [new TextRun({ text, bold: true, color: C.primary, size: 32 })] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 160 },
    children: [new TextRun({ text, bold: true, color: C.accent, size: 26 })] });
}
function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 120 },
    children: [new TextRun({ text, bold: true, color: C.body, size: 22 })] });
}
function p(text) {
  return new Paragraph({ spacing: { after: 120, line: 312 }, alignment: AlignmentType.JUSTIFIED,
    children: [new TextRun({ text, color: C.body, size: 21 })] });
}
function code(text) {
  return new Paragraph({ spacing: { after: 80, line: 280 },
    shading: { type: ShadingType.CLEAR, fill: C.surface },
    children: [new TextRun({ text, font: "Courier New", size: 18, color: C.primary })] });
}
function bullet(text) {
  return new Paragraph({ spacing: { after: 60, line: 312 }, bullet: { level: 0 },
    children: [new TextRun({ text, color: C.body, size: 21 })] });
}
function tableRow(cells, isHeader) {
  return new TableRow({ tableHeader: isHeader, cantSplit: true,
    children: cells.map(c => new TableCell({ width: { size: Math.floor(100/cells.length), type: WidthType.PERCENTAGE },
      margins: { top: 40, bottom: 40, left: 80, right: 80 },
      shading: isHeader ? { type: ShadingType.CLEAR, fill: C.accent } : undefined,
      children: [new Paragraph({ spacing: { after: 0 },
        children: [new TextRun({ text: c, bold: isHeader, color: isHeader ? C.white : C.body, size: 20 })] })] })) });
}
function makeTable(headers, rows) {
  return new Table({ width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [tableRow(headers, true), ...rows.map(r => tableRow(r, false))] });
}

const doc = new Document({
  creator: "Z.ai", title: "Motus & Uroboros",
  description: "Техническая документация",
  styles: { default: { document: { run: { font: "Calibri", size: 21 } } } },
  sections: [
    // === COVER ===
    { properties: { type: SectionType.NEXT_PAGE },
      children: [
        new Paragraph({ spacing: { before: 4000 } }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
          children: [new TextRun({ text: "Motus & Uroboros", bold: true, size: 52, color: C.primary })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
          children: [new TextRun({ text: "Техническая документация", size: 28, color: C.accent })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 },
          children: [new TextRun({ text: "v0.3.0 / v0.1.0", size: 20, color: C.secondary })] }),
        new Paragraph({ alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "2026-11-14", size: 20, color: C.secondary })] }),
        new Paragraph({ children: [new PageBreak()] }),
      ]
    },
    // === TOC ===
    { properties: { type: SectionType.NEXT_PAGE },
      children: [
        new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { after: 200 },
          children: [new TextRun({ text: "Содержание", bold: true, color: C.primary, size: 32 })] }),
        new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }),
        new Paragraph({ children: [new PageBreak()] }),
      ]
    },
    // === BODY ===
    { properties: { type: SectionType.NEXT_PAGE,
        page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
      footers: { default: { children: [new Paragraph({ alignment: AlignmentType.CENTER,
        children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: C.secondary })] })] } },
      children: [
        // 1. Uroboros
        h1("1. Uroboros"),
        p("Uroboros — это patch-driven, file-backed итеративный pipeline с human approval. Пакет uroboros v0.3.0 предоставляет механизм: plan -> patches -> state mutations -> memory -> approval. Основные компоненты: engine, registry, memory, formats, plan, adapters, glm, cli."),
        h2("1.1 Архитектура"),
        p("Uroboros работает по модели: план (JSON) -> DAG узлов -> исполнение патчей -> кэширование -> approval gate -> memory journal. Каждый узел плана — операция с target, operation, params, needs (зависимости)."),
        code('plan = {"format": "uroboros.patch/2", "name": "demo",\n  "nodes": [\n    {"id": "geometry", "target": "scene", "operation": "geometry.generate",\n     "params": {"width": 5.0, "depth": 4.0}},\n    {"id": "palette", "target": "color", "operation": "color.palette",\n     "params": {"mood": "quiet_warm"}},\n    {"id": "compose", "target": "scene", "operation": "scene.compose",\n     "needs": ["geometry", "palette"]}\n  ]}'),
        h2("1.2 Ключевые модули"),
        makeTable(["Модуль", "Ответственность"], [
          ["engine.py", "Uroboros class: run(), _execute_one(), _checklist(), approval logic"],
          ["registry.py", "PatchRegistry: загрузка .py патчей из директории, apply()"],
          ["memory.py", "FileMemory: blob storage, cache_put/get, save_run, event journal"],
          ["formats.py", "FORMAT, PatchError, canonical, digest — сериализация"],
          ["plan.py", "simple_room_plan, full_plan, load_plan, save_plan"],
          ["adapters.py", "Мосты к Color Matrix, Cozy Engine, motus"],
          ["cyclic.py", "CyclicPipeline: iterative solver с convergence detection"],
          ["feedback.py", "ConvergenceChecker + FeedbackProposer"],
          ["intro_cache.py", "IntroCache: итерации, metrics, deltas, blobs"],
          ["gpu_eval.py", "GPUEvaluator: demo_runtime.exe -> BMP -> CV analysis"],
          ["smt_patch.py", "inject_params: .smt param injection"],
        ]),
        h2("1.3 Approval gate (P0 fix)"),
        p("После внешнего ревью (2026-11-12) добавлен validation gate: _checklist() сканирует outputs патчей на {ok: false}. require_approval=False больше не активируется при провале валидации. Три состояния: execution_status, validation_status, approval_status — разделены."),
        h2("1.4 Strict mode (P1.4)"),
        p("Uroboros(strict=True) — патчи с output {_fallback: True} вызывают PatchError. Demo mode (default) — fallback принимается. Запрещает маскирование неработающих интеграций fallback-поведением."),
        h2("1.5 Data dependencies в кэше (P1.5)"),
        p("params.data_dependencies: list[str] — пути к внешним файлам. mtime_ns + size включаются в cache key. Замена .npz матрицы вызывает cache miss -> пересчёт."),

        // 2. Motus
        new Paragraph({ children: [new PageBreak()] }),
        h1("2. Motus"),
        p("Motus v0.1.0 — детерминированный motion-core, управляемый текстовым запросом. submit(text) -> events with absolute time -> frame(t) replays from scratch. Ядро — только stdlib. numpy — опционально для частиц. Рендер вне пакета: FramePlan — данные."),
        h2("2.1 Инварианты (I1-I10)"),
        makeTable(["#", "Инвариант", "Формулировка"], [
          ["I1", "Determinism", "frame(t) дважды даёт идентичный план"],
          ["I2", "Purity", "процедурный шум зависит только от (t, seed)"],
          ["I3", "Framerate", "значения при 60 и 240 fps совпадают"],
          ["I4", "Boundaries", "t вне диапазона, NaN, +-inf, пустой трек — clamp"],
          ["I5", "Identity", "scale (1,1,1), rot (0,0,0,1), pos (0,0,0)"],
          ["I6", "Blend", "weight=0 — базовая поза; фазы REPLACE->ADD->MUL"],
          ["I7", "Hierarchy", "preorder O(N) совпадает с перемножением родителей"],
          ["I8", "Replay", "перемотка назад переигрывает события"],
          ["I9", "Offline", "offline-сетка и realtime дают один результат"],
          ["I10", "Quat", "slerp по кратчайшей дуге, результат нормализован"],
        ]),
        h2("2.2 Модули"),
        makeTable(["Файл", "Ответственность"], [
          ["core.py", "MotusError, QueryError, Registry"],
          ["mathx.py", "vec3/quat/mat4, slerp, hash01 (column-major)"],
          ["clock.py", "Transport (bpm/beats_per_bar), fixed_frames, LiveClock"],
          ["track.py", "Track (keyframes), EASINGS, safe sampling"],
          ["scene.py", "Scene, Entity, Transform, preorder, dirty flags"],
          ["anim.py", "Animator, Binding, CHANNELS, PROCS, Mode"],
          ["effects.py", "EffectSpec, Emitter, compute_field (closed-form)"],
          ["query.py", "Lexer, DSL, free language, mode router"],
          ["runtime.py", "Runtime: submit(), frame() -> FramePlan"],
          ["bake.py", "Playback (mmap), bake()"],
          ["glsl.py", "Опциональные шейдеры 330 core"],
        ]),
        h2("2.3 DSL синтаксис"),
        code('new ball pos=(0,0,0) param.color=(1.0,0.6,0.2)\nanim ball.position from=(0,0,0) to=(3,0,0) over=2 ease=smooth\nproc ball.rotation spin rate=180\nfx burst on=ball at=2 for=1.5 count=600 seed=7'),
        h2("2.4 Free language"),
        p("Rules-based, не NLU. Сегментация по найденным глаголам. RU+EN. Case-insensitive fuzzy matching (LCP>=4, >=60%). Неизвестная фраза -> QueryError с подсказками. Атомарность: любой issue -> весь запрос отклонён."),
        h2("2.5 Исправленные баги (5)"),
        makeTable(["#", "Баг", "Исправление"], [
          ["1", "field name collision (dataclass vs effects)", "Rename field() -> compute_field()"],
          ["2", "_static class-level (shared state)", "Move to __init__ as self._static"],
          ["3", "No pyproject.toml", "Created with setuptools + packages.find"],
          ["4", "Uppercase Cyrillic stripped by regex", "[а-я] -> [а-яА-Яa-zA-Z], case-insensitive _fuzzy"],
          ["5", "Test expects entity before frame()", "Added rt.frame(0.0) before assertion"],
        ]),

        // 3. Integration
        new Paragraph({ children: [new PageBreak()] }),
        h1("3. Интеграция Uroboros + Motus"),
        h2("3.1 Adapter pattern"),
        p("motus не вторгается в Uroboros core. Добавляется как операция motus.scene через patches/motus_scene.py. Adapter в uroboros/adapters.py: motus_available(), motus_scene(query, times) -> JSON frames. Optional dependency: fallback если motus не установлен."),
        h2("3.2 Контракт motus.scene"),
        makeTable(["Параметр", "Тип", "Default", "Описание"], [
          ["query", "str", "(обязательный)", "Текст motus DSL/free"],
          ["times", "list[float]", "[0.0]", "Моменты кадров"],
          ["particles", "bool", "false", "Считать ли частицы (нужен numpy)"],
          ["bpm", "float", "120.0", "Музыкальная сетка"],
          ["mode", "str", "auto", "dsl | free | auto"],
          ["include_upstream", "bool", "true", "Добавить upstream_keys"],
        ]),
        h2("3.3 Pipeline"),
        code('Uroboros plan\n  geometry.generate -> room dims\n  color.palette -> mood colors (Color Matrix)\n  scene.compose -> scene graph\n  cozy.plan_room -> room primitives\n  motus.scene -> JSON frame snapshots\n  validate.scene -> check'),
        p("Data flow: Color Matrix -> color.palette -> palette colors. Cozy Engine -> cozy.plan_room -> uPrimitives. Scene Manager -> scene.compose -> scene graph. motus -> motus.scene -> JSON frames (entities, transforms, particles)."),

        // 4. Cyclic Pipeline
        new Paragraph({ children: [new PageBreak()] }),
        h1("4. Cyclic Pipeline"),
        p("Превращение линейного пайплайна в циклический feedback-loop. Iterative solver: forward -> evaluate -> decide -> delta -> repeat until convergence."),
        h2("4.1 Phase 1: Python-side loop"),
        p("IntroCache stores iterations (meta.json + frames.bin). ConvergenceChecker: tolerance, max_iterations, oscillation detection, insufficient improvement. FeedbackProposer: brightness -> uIntensity delta with damping factor 0.5."),
        code('CyclicPipeline.run(forward_fn, evaluate_fn, initial_params)\n  for iteration in 0..max:\n    1. FORWARD:   forward_fn(params) -> state\n    2. EVALUATE:  evaluate_fn(state) -> List[SceneMetric]\n    3. DECIDE:    ConvergenceChecker -> approve | feedback | abort\n    4. CACHE:     IntroCache.save_iteration(record)\n    5. DELTA:     FeedbackProposer -> param deltas -> apply'),
        h2("4.2 Phase 2: GPU-side loop"),
        p("GPUEvaluator: вызывает demo_runtime.exe --still T -> BMP -> PIL CV analysis -> SceneMetric[]. smt_patch.inject_params: .smt param injection (find clip/uniform/prog, replace value). create_gpu_forward_fn: factory function for CyclicPipeline."),
        h2("4.3 intro_cache формат"),
        makeTable(["Формат", "Скорость", "Zero-copy", "Зависимости"], [
          ["Custom binary + mmap + JSON", "Good", "mmap", "0 (stdlib)"],
          ["FlatBuffers", "OK", "read", "+200KB"],
          ["Cap'n Proto", "Excellent", "full", "+500KB"],
          ["LMDB", "Good", "mmap", "+100KB lib"],
        ]),
        p("Выбран: Hybrid (JSON metadata + content-addressed binary blobs). Причины: demoscene binary budget, уже доказано в motus bake.py, reuses Uroboros FileMemory blob storage, diff-friendly JSON."),

        // 5. Tests
        new Paragraph({ children: [new PageBreak()] }),
        h1("5. Тесты и верификация"),
        makeTable(["Suite", "Пройдено", "Не пройдено", "Пропущено"], [
          ["Uroboros engine", "8", "0", "0"],
          ["Uroboros formats", "3", "0", "0"],
          ["Uroboros memory", "5", "0", "0"],
          ["Uroboros patches", "6", "0", "0"],
          ["Uroboros registry", "3", "0", "0"],
          ["P0/P1 fixes", "8", "0", "0"],
          ["Motus adapter", "10", "0", "3"],
          ["Cyclic pipeline", "22", "0", "0"],
          ["GPU evaluation", "18", "0", "0"],
          ["Motus selfcheck", "15", "0", "0"],
          ["ИТОГО", "98", "0", "3"],
        ]),
        h2("5.1 Инвариантные тесты motus"),
        bullet("I1 Determinism: frame(t) дважды — идентичный результат"),
        bullet("I2 Hash purity: hash01(seed, i) не зависит от истории вызовов"),
        bullet("I3 Framerate independence: 60fps == 240fps в общих точках"),
        bullet("I4 Boundaries: NaN, +-inf, пустой трек — clamp, не падение"),
        bullet("I8 Replay: scrub назад переигрывает события с нуля"),
        h2("5.2 Cyclic pipeline тесты"),
        bullet("Converges in 1 iteration (metrics already at target)"),
        bullet("Converges in 2 iterations (feedback adjusts params)"),
        bullet("Aborts on max_iterations (never converges)"),
        bullet("Forward failure -> abort with error"),
        bullet("Oscillation detection (sign flips in deltas)"),
        bullet("Insufficient improvement detection"),
        bullet("Cache records all iterations + final marker"),
        bullet("Params updated between iterations (damping applied)"),

        // 6. API Reference
        new Paragraph({ children: [new PageBreak()] }),
        h1("6. API Reference"),
        h2("6.1 Uroboros"),
        code('from uroboros import Uroboros, FORMAT, PatchError\n\nu = Uroboros(root=".uroboros", patches="patches", workers=2)\nstate = u.run(plan, max_iterations=3, require_approval=False)'),
        h2("6.2 Motus"),
        code('from motus import Runtime, Transport\n\nrt = Runtime(Transport(bpm=120), mode="dsl", particles=False)\nreport = rt.submit("new ball\\nanim ball.position from=(0,0,0) to=(3,0,0) over=2")\nplan = rt.frame(1.0)'),
        h2("6.3 Adapter"),
        code('from uroboros.adapters import motus_scene\n\nres = motus_scene("new ball\\nanim ball.position from=(0,0,0) to=(1,0,0) over=1",\n                   [0.0, 0.5, 1.0], particles=False, mode="dsl")'),
        h2("6.4 Cyclic Pipeline"),
        code('from uroboros.cyclic import CyclicPipeline, CyclicConfig\nfrom uroboros.gpu_eval import GPUEvaluator, create_gpu_forward_fn\n\nconfig = CyclicConfig(max_iterations=5, tolerance=0.005, damping=0.5)\npipe = CyclicPipeline(config)\nforward = create_gpu_forward_fn("demo.smt", "/tmp/work")\nevaluator = GPUEvaluator(smt_path="demo.smt")\nresult = pipe.run(forward_fn=forward, evaluate_fn=evaluator.evaluate,\n                  initial_params={"s1.uIntensity": 1.5})'),
        h2("6.5 .smt param injection"),
        code('from uroboros.smt_patch import extract_params, inject_params\n\nparams = extract_params("demo.smt")\n# {"s1.uIntensity": 0.8, "s4.uIntensity": 1.2, ...}\ninject_params("demo.smt", {"s1.uIntensity": 1.5}, "modified.smt")'),
      ]
    }
  ]
});

Packer.toBuffer(doc).then(buf => {
  const out = "/home/z/my-project/download/motus_uroboros_documentation.docx";
  fs.writeFileSync(out, buf);
  console.log("Written: " + out + " (" + buf.length + " bytes)");
});
