// generate_aesthetics_docx.js — render aesthetics.md as Word document
// Source: /home/z/my-project/download/aesthetics.md (v0.4, 316 lines)
// Output: /home/z/my-project/download/aesthetics.docx

const {
  Document, Packer, Paragraph, TextRun, Header, Footer,
  AlignmentType, HeadingLevel, PageNumber, PageBreak,
  Table, TableRow, TableCell, WidthType, BorderStyle,
  ShadingType, TableLayoutType, ImageRun, LevelFormat,
} = require("docx");
const fs = require("fs");
const { imageSize } = require("image-size");

// ============================================================
// PALETTE — DRAMATIC_DARK (matches doc §3.4)
// ============================================================
const P = {
  bg:           "0A0A14",   // cover dark background
  titleColor:   "E8E8F0",   // cover title light
  subtitleColor:"A0A0C0",
  metaColor:    "808090",
  accent:       "8090FF",   // cyan-blue accent
  footerColor:  "606070",
  body:         "1A1A28",   // body text dark
  primary:      "0F0F1A",   // headings
  secondary:    "505070",
  code_bg:      "F4F4F8",   // code block light background
  code_text:    "1A1A28",
  table_header: "E8E8F0",
  table_row_alt:"F8F8FC",
};
const c = (hex) => hex.replace("#", "");

// ============================================================
// HELPERS
// ============================================================
const NB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const allNoBorders = { top: NB, bottom: NB, left: NB, right: NB,
                       insideHorizontal: NB, insideVertical: NB };

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 480, after: 200, line: 312 },
    children: [new TextRun({ text, bold: true, size: 32, color: c(P.primary),
      font: { ascii: "Calibri", eastAsia: "SimHei" } })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 360, after: 160, line: 312 },
    children: [new TextRun({ text, bold: true, size: 26, color: c(P.primary),
      font: { ascii: "Calibri", eastAsia: "SimHei" } })],
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 280, after: 120, line: 312 },
    children: [new TextRun({ text, bold: true, size: 22, color: c(P.secondary),
      font: { ascii: "Calibri", eastAsia: "SimHei" } })],
  });
}

function body(text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: 312, after: 120 },
    children: [new TextRun({ text, size: 22, color: c(P.body),
      font: { ascii: "Calibri", eastAsia: "Microsoft YaHei" } })],
  });
}

function bodyBold(text) {
  // Body paragraph with bold first segment (for **bold:** prefixes)
  return new Paragraph({
    alignment: AlignmentType.LEFT,
    spacing: { line: 312, after: 100 },
    children: [new TextRun({ text, size: 22, bold: true, color: c(P.body),
      font: { ascii: "Calibri", eastAsia: "Microsoft YaHei" } })],
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    spacing: { line: 312, after: 60 },
    indent: { left: 360 + level * 360, hanging: 240 },
    children: [
      new TextRun({ text: "•  ", size: 22, color: c(P.accent), bold: true }),
      new TextRun({ text, size: 22, color: c(P.body),
        font: { ascii: "Calibri", eastAsia: "Microsoft YaHei" } }),
    ],
  });
}

function bulletBold(boldPart, rest, level = 0) {
  return new Paragraph({
    spacing: { line: 312, after: 60 },
    indent: { left: 360 + level * 360, hanging: 240 },
    children: [
      new TextRun({ text: "•  ", size: 22, color: c(P.accent), bold: true }),
      new TextRun({ text: boldPart, size: 22, bold: true, color: c(P.body),
        font: { ascii: "Calibri", eastAsia: "Microsoft YaHei" } }),
      new TextRun({ text: rest, size: 22, color: c(P.body),
        font: { ascii: "Calibri", eastAsia: "Microsoft YaHei" } }),
    ],
  });
}

function code(textLines) {
  // Render code block as monospace paragraphs with light shading
  return textLines.map((line, idx) => new Paragraph({
    spacing: { line: 280, after: 0 },
    indent: { left: 240 },
    shading: { type: ShadingType.CLEAR, fill: c(P.code_bg) },
    children: [new TextRun({ text: line || " ", size: 20,
      color: c(P.code_text), font: { ascii: "Consolas", eastAsia: "Consolas" } })],
  }));
}

function tableCell(text, opts = {}) {
  const isHeader = opts.header || false;
  const align = opts.align || AlignmentType.LEFT;
  return new TableCell({
    width: opts.width ? { size: opts.width, type: WidthType.PERCENTAGE } : undefined,
    shading: { type: ShadingType.CLEAR,
      fill: isHeader ? c(P.table_header) : (opts.alt ? c(P.table_row_alt) : "FFFFFF") },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({
      alignment: align,
      spacing: { line: 280, after: 0 },
      children: [new TextRun({
        text: String(text || ""),
        size: 20,
        bold: isHeader || opts.bold,
        color: c(P.body),
        font: { ascii: "Calibri", eastAsia: "Microsoft YaHei" },
      })],
    })],
  });
}

function makeTable(headers, rows, colWidths) {
  const headerRow = new TableRow({
    tableHeader: true,
    cantSplit: true,
    children: headers.map((h, i) =>
      tableCell(h, { header: true, width: colWidths ? colWidths[i] : undefined })),
  });
  const bodyRows = rows.map((row, idx) => new TableRow({
    cantSplit: true,
    children: row.map((cell, i) => {
      // Handle cell objects with bold flag
      if (typeof cell === "object" && cell !== null && cell.text !== undefined) {
        return tableCell(cell.text, {
          alt: idx % 2 === 1,
          bold: cell.bold,
          width: colWidths ? colWidths[i] : undefined,
        });
      }
      return tableCell(cell, { alt: idx % 2 === 1, width: colWidths ? colWidths[i] : undefined });
    }),
  }));
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    layout: TableLayoutType.FIXED,
    rows: [headerRow, ...bodyRows],
  });
}

function embedImage(path, caption, displaySize = 380) {
  const buf = fs.readFileSync(path);
  const dim = imageSize(buf);
  // Preserve aspect ratio — all 3 ref images are 768×768 (square)
  const ratio = dim.height / dim.width;
  const w = displaySize;
  const h = Math.round(displaySize * ratio);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 200, after: 100 },
      children: [new ImageRun({
        data: buf,
        transformation: { width: w, height: h },
        type: "jpg",
      })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 200, line: 280 },
      children: [new TextRun({
        text: caption, size: 18, italics: true,
        color: c(P.secondary),
        font: { ascii: "Calibri", eastAsia: "Microsoft YaHei" },
      })],
    }),
  ];
}

function spacer(height = 200) {
  return new Paragraph({ spacing: { before: height, after: 0 } });
}

// ============================================================
// CONTENT — render aesthetics.md v0.4 sections
// ============================================================

const children = [];

// ===== TITLE PAGE (simple, no formal cover recipe) =====
children.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { before: 4000, after: 400 },
  children: [new TextRun({
    text: "A E S T H E T I C   P R I N C I P L E S",
    size: 18, color: c(P.accent), characterSpacing: 60, bold: true,
    font: { ascii: "Calibri" },
  })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { after: 300, line: 480 },
  children: [new TextRun({
    text: "Aesthetic principles",
    size: 64, bold: true, color: c(P.primary),
    font: { ascii: "Calibri" },
  })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { after: 800 },
  children: [new TextRun({
    text: "Principles, не taste. Between vec3(0.10, 0.40, 0.80) and vec3(0.15, 0.42, 0.85) — choice by principle, not by preference.",
    size: 22, italics: true, color: c(P.secondary),
    font: { ascii: "Calibri" },
  })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { before: 200, after: 100 },
  border: { top: { style: BorderStyle.SINGLE, size: 6, color: c(P.accent), space: 8 } },
  children: [new TextRun({
    text: "Version: v0.4  •  Date: 2026-10-31  •  Status: cleaned (project-specific refs removed)",
    size: 18, color: c(P.secondary), font: { ascii: "Calibri" },
  })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { after: 100 },
  children: [new TextRun({
    text: "Reference images: 3 (warehouse surreal / mage combat / zombie horse graveyard)",
    size: 18, color: c(P.secondary), font: { ascii: "Calibri" },
  })],
}));
children.push(new Paragraph({
  children: [new PageBreak()],
}));

// ===== §1 КОНТЕКСТ =====
children.push(h1("1. Контекст"));
children.push(body("Principles, не taste. Между vec3(0.10, 0.40, 0.80) и vec3(0.15, 0.42, 0.85) выбор делается по принципам. Без явных principles default = «разумно, но не вдохновенно»."));
children.push(body("Этот документ — checklist для application, не рецепт креативности."));

// ===== §2 ЭСТЕТИЧЕСКИЙ ПРОФИЛЬ =====
children.push(h1("2. Эстетический профиль"));
children.push(...code([
  "70 / 25 / 5  ratio",
  "│    │   └─ focal point (single light source, narrative anchor)",
  "│    └───── vivid color accents (contrast against dominant)",
  "└────────── dominant dark space (mood, breathing room)",
]));
children.push(spacer(120));
children.push(bodyBold("Anti-pattern:"));
children.push(body("uniform saturation (всё ярко) — теряет depth, выглядит flat/amateur."));

// ===== §3 COLOR THEORY =====
children.push(h1("3. Color theory"));

children.push(h2("3.1. 60-30-10 rule"));
children.push(makeTable(
  ["Role", "Доля пикселей", "Luminance", "Saturation"],
  [
    ["Dominant",  "60%", "0.05-0.20", "0.3-0.5"],
    ["Secondary", "30%", "0.20-0.50", "0.5-0.7"],
    ["Accent",    "10%", "0.50-0.90", "0.7-1.0"],
  ],
  [22, 22, 28, 28]
));

children.push(h2("3.2. Color harmony (выбрать ОДНУ, не смешивать)"));
children.push(makeTable(
  ["Harmony", "Colors", "Когда"],
  [
    [{text: "Complementary", bold: true}, "2 colors напротив (cyan↔magenta, blue↔orange, purple↔yellow)", "dramatic contrast, tension"],
    ["Analogous",            "3 соседних цвета (blue→cyan→teal)",                                       "calm, serene, mood-driven"],
    ["Triadic",              "3 равноудалённых (red/yellow/blue)",                                     "vibrant, playful"],
    ["Split-complementary",  "1 base + 2 neighbors of opposite",                                       "balanced drama"],
  ],
  [25, 45, 30]
));

children.push(h2("3.3. Saturation/luminance balance"));
children.push(bulletBold("Core (dark) regions: ", "saturation 0.6-0.8, luminance 0.15-0.25"));
children.push(bulletBold("Mid regions: ",         "saturation 0.4-0.5, luminance 0.30-0.50"));
children.push(bulletBold("Rim/accent regions: ",  "saturation 0.3-0.4, luminance 0.60-0.80"));
children.push(spacer(120));
children.push(bodyBold("Anti-pattern:"));
children.push(body("saturated core + saturated rim = muddy. Saturated core + desaturated rim = depth."));

children.push(h2("3.4. Sample palette (DRAMATIC_DARK)"));
children.push(...code([
  "deep_purple_core:  rgb(0.08, 0.05, 0.20)  HSL(255, 0.60, 0.13)",
  "cyan_mid:          rgb(0.10, 0.40, 0.80)  HSL(215, 0.78, 0.45)",
  "magenta_rim:       rgb(0.80, 0.30, 0.50)  HSL(340, 0.55, 0.55)",
  "star_white_pure:   rgb(1.00, 1.00, 0.95)  HSL(50, 1.00, 0.97)",
  "void_black:        rgb(0.02, 0.02, 0.03)",
]));
children.push(spacer(120));
children.push(body("Mood: cold/dramatic/deep. Use cases: core glow, atmospheric depth, rim light."));

// ===== §4 COMPOSITION =====
children.push(h1("4. Composition"));

children.push(h2("4.1. Focal point singularity"));
children.push(bulletBold("1 focal point per frame. ", "Если >1 — competing attention, eye fatigue."));
children.push(bullet("Focal = brightest single element OR highest saturation OR center-most."));
children.push(bullet("Other elements supporting, НЕ competing."));

children.push(h2("4.2. Rule of thirds"));
children.push(bullet("Camera target / focal element на пересечении thirds (не в центре кадра)."));
children.push(bullet("Для static camera: shift focal to (0.33, 0.50) или (0.66, 0.50)."));
children.push(bullet("Для moving camera: target trajectory проходит через thirds."));

children.push(h2("4.3. Background-foreground density contrast"));
children.push(bullet("Background density < foreground density. НЕ заполняйте кадр равномерно."));
children.push(bullet("Background noise subtle (amplitude 0.3-0.5), foreground accents яркие (amplitude 0.6-1.0)."));

children.push(h2("4.4. Vignette as attention director"));
children.push(bullet("Gentle vignette: 0.7-0.85 at edges"));
children.push(bullet("Strong vignette = amateur, eye senses manipulation"));
children.push(bullet("No vignette = flat, lacks depth"));

// ===== §5 MOTION =====
children.push(h1("5. Motion (Disney 12 simplified для real-time)"));

children.push(h2("5.1. Easing"));
children.push(bulletBold("smoothstep(t) ", "для organic motion (НЕ linear)"));
children.push(bullet("Linear только для mechanical rotation (gears, clock hands)"));
children.push(bullet("mix(a, b, smoothstep(0.0, 1.0, t)) — standard pattern"));

children.push(h2("5.2. Anticipation (10% перед main motion)"));
children.push(bullet("Перед «впрыгиванием» camera — slight pull-back (10% amplitude, 100ms)"));
children.push(bullet("В GLSL: pos += sin(t * 5.0) * 0.02 перед основным motion"));

children.push(h2("5.3. Follow-through (15% после main motion)"));
children.push(bullet("После резкой остановки — slight overshoot + dampened oscillation"));
children.push(bullet("pos = target + sin((t - t_stop) * 8.0) * exp(-(t - t_stop) * 3.0) * 0.05"));

children.push(h2("5.4. Camera motion: 1 primary axis"));
children.push(bullet("1 axis primary (largest amplitude)"));
children.push(bullet("Other axes secondary (≤30% of primary amplitude)"));
children.push(bullet("Anti-pattern: chaotic 3-axis motion = nausea, not aesthetic"));

children.push(h2("5.5. Phase offsets для variety"));
children.push(bullet("Multiple light sources: each phase offset by ~1.7 radians (golden angle 2.3998 / 2 ≈ 1.7)"));
children.push(bullet("Avoid synchronized pulsing — looks mechanical"));

// ===== §6 DENSITY =====
children.push(h1("6. Density"));

children.push(h2("6.1. FBM octaves"));
children.push(bulletBold("4-5 max. ", "После 5 — mush, lost detail."));
children.push(bullet("amplitude half per octave (standard fbm)"));
children.push(bullet("frequency double per octave"));

children.push(h2("6.2. Light nodes count"));
children.push(bulletBold("3-5 max. ", "Больше — competing, less impact."));
children.push(bullet("Если добавить ещё — удалить или объединить существующие."));

children.push(h2("6.3. Star field density"));
children.push(bullet("1 star per ~50×50 pixel area max"));
children.push(bullet("Brighter stars rarer (logarithmic distribution)"));
children.push(bullet("Anti-pattern: dense star field = noise, not depth"));

children.push(h2("6.4. Detail vs scale"));
children.push(bullet("Big shapes first, small details last"));
children.push(bullet("3-tier hierarchy: macro (composition) / meso (light nodes) / micro (noise detail)"));
children.push(bullet("All three tiers needed; missing one = flat"));

// ===== §7 CONTRAST =====
children.push(h1("7. Contrast & luminance balance"));

children.push(h2("7.1. Dynamic range"));
children.push(bullet("Min luminance in frame: 0.02-0.05 (deep shadow)"));
children.push(bullet("Max luminance in frame: 0.85-1.00 (HDR accent)"));
children.push(bullet("Ratio: 20:1 to 50:1 — cinematic"));
children.push(bullet("< 10:1 = flat / TV-broadcast look"));
children.push(bullet("> 100:1 = HDR display required, иначе crushed blacks"));

children.push(h2("7.2. Tone mapping (ACES recommended)"));
children.push(bullet("finalColor = ACESFilm(color) — preserves highlights, lifts shadows"));
children.push(bullet("ACES: color = (color * (2.51 * color + 0.03)) / (color * (2.43 * color + 0.59) + 0.14)"));

children.push(h2("7.3. Color contrast (S-channel in HSL)"));
children.push(bullet("Average saturation in frame: 0.4-0.6"));
children.push(bullet("Peak saturation (accents): 0.8-1.0"));
children.push(bullet("Anti-pattern: average saturation > 0.7 = eye strain"));

// ===== §8 SELF-CRITIQUE CHECKLIST =====
children.push(h1("8. Self-critique checklist"));
children.push(...code([
  "aesthetic_notes:",
  "  color:",
  "    - palette: <name>",
  "    - dominant/secondary/accent ratio: <60/30/10 | other>",
  "    - harmony: <complementary | analogous | triadic>",
  "  composition:",
  "    - focal_point: <which element>",
  "    - rule_of_thirds: <yes/no, where>",
  "    - bg/fg_density_contrast: <yes/no>",
  "  motion:",
  "    - easing: <smoothstep | linear | mixed>",
  "    - anticipation: <yes/no>",
  "    - follow_through: <yes/no>",
  "    - primary_axis: <x | y | z>",
  "  density:",
  "    - fbm_octaves: <N>",
  "    - light_nodes: <N>",
  "    - star_density: <low | med | high>",
  "  contrast:",
  "    - dynamic_range: <min/max luminance>",
  "    - tone_mapping: <ACES | raw | other>",
  "  reference_target:",
  "    - which reference image this aims for: <path or description>",
  "    - delta from reference: <what's different>",
  "  self_critique:",
  "    - 1-2 sentences: what works, what doesn't, what to try next",
]));
children.push(spacer(120));
children.push(bodyBold("Если любой пункт empty — task не закрыт, вернуться к generation."));

// ===== §9 COMPARATIVE ANALYSIS — 3 images =====
children.push(h1("9. Comparative analysis — Image 1 vs Image 2 vs Image 3"));

// §9.1 Image 1
children.push(h2("9.1 Image 1: dark surreal warehouse"));
children.push(...embedImage(
  "/home/z/my-project/upload/8474358583453.jpg",
  "Image 1 — upload/8474358583453.jpg"
));
children.push(bodyBold("Content:"));
children.push(body("dim warehouse, concrete walls, red bulb hanging, figure wrapped in cables, floor densely covered with colorful plastic bottles (pink/blue/green/orange/purple)."));
children.push(bodyBold("Aesthetic profile:"));
children.push(bullet("Ratio: ~65/30/5 (dark dominant / bottle accents / red bulb focal)"));
children.push(bulletBold("Color harmony: ", "chaotic multicolor (6+ colors, no single harmony)"));
children.push(bullet("Focal: red bulb (single, clear, directional lighting)"));
children.push(bullet("Composition: figure center, bottles distributed — no rule of thirds"));
children.push(bullet("Motion: static (gallery installation aesthetic)"));
children.push(bullet("Dynamic range: ~30:1"));
children.push(bullet("Narrative: figure eerie but passive"));
children.push(spacer(80));
children.push(bodyBold("Strongest principle: ") + body(" focal singularity (red bulb)."));
children.push(bodyBold("Weakest: ") + body(" color harmony (chaotic multicolor)."));
children.push(bodyBold("Archetype: ") + body(" static surreal (gallery)."));

// §9.2 Image 2
children.push(h2("9.2 Image 2: fantasy mage with lightning whip"));
children.push(...embedImage(
  "/home/z/my-project/upload/Без названия - 2026-05-09T101224.022.jpg",
  "Image 2 — upload/Без названия - 2026-05-09T101224.022.jpg"
));
children.push(bodyBold("Content:"));
children.push(body("old mage white hair/beard, red-purple glowing eyes, dark worn robes, combat pose. Right hand wields energy whip made of purple-pink lightning (S-shape around body). Dark scene, twisted dead trees background, floating debris, orange-red sparks and embers, ground fire glow."));
children.push(bodyBold("Aesthetic profile:"));
children.push(bullet("Ratio: ~60/30/10 (dark scene / whip+sparks accent / mage+eyes focal)"));
children.push(bulletBold("Color harmony: ", "complementary (purple-pink whip HSL ~320° ↔ orange-red sparks HSL ~25°)"));
children.push(bullet("Focal: mage eyes + whip S-curve (dual, but whip leads eye)"));
children.push(bullet("Composition: mage center — no rule of thirds, BUT whip S-curve creates dynamic flow"));
children.push(bullet("Motion: strong implied (combat pose, whip S-curve, sparks trajectory)"));
children.push(bullet("Dynamic range: ~50:1 (cinematic)"));
children.push(bullet("Narrative: mage active combat — clear subject"));
children.push(spacer(80));
children.push(bodyBold("Strongest principle: ") + body(" complementary color harmony + implied motion."));
children.push(bodyBold("Weakest: ") + body(" ratio (10% accent > ideal 5%)."));
children.push(bodyBold("Archetype: ") + body(" dynamic dramatic (cinematic action)."));

// §9.3 Image 3
children.push(h2("9.3 Image 3: skeletal zombie horse in graveyard"));
children.push(...embedImage(
  "/home/z/my-project/upload/Без названия - 2026-02-24T195643.383.jpg",
  "Image 3 — upload/Без названия - 2026-02-24T195643.383.jpg"
));
children.push(bodyBold("Content:"));
children.push(body("skeletal zombie horse with exposed bones, visible ribs, decayed flesh and blood traces, purple-red mane hanging in strands, halter on head, walking with head down. Night graveyard scene, tombstones and stones scattered, stone cross on right side, distant blurred tombstones. Purple-blue tone overall, crescent moon in sky, dead branches from upper left, hazy moonlight, Halloween horror atmosphere."));
children.push(bodyBold("Aesthetic profile:"));
children.push(bulletBold("Ratio: ", "~75/20/5 (dark graveyard dominant / purple-blue tone / crescent moon focal) — closest to ideal 70/25/5 of all 3"));
children.push(bulletBold("Color harmony: ", "analogous (purple-blue-violet, single harmony, focused but less dramatic than complementary)"));
children.push(bullet("Focal: dual (crescent moon + zombie horse) — horse is subject, moon is light source"));
children.push(bulletBold("Composition: ", "horse walking diagonally, off-center — rule of thirds ✓ (best of 3)"));
children.push(bullet("Motion: implied walking (horse stride) — between Image 1 (static) and Image 2 (combat)"));
children.push(bulletBold("Dynamic range: ", "~20:1 — lowest of 3 (atmospheric, not cinematic)"));
children.push(bullet("Narrative: strong (zombie horse + graveyard + Halloween mood, clear subject + setting)"));
children.push(bullet("Tone: muted, atmospheric, fog/moonlight — distinct от flat (Img 1) и HDR (Img 2)"));
children.push(spacer(80));
children.push(bodyBold("Strongest principles: ") + body(" ratio (closest to ideal) + rule of thirds + density control."));
children.push(bodyBold("Weakest: ") + body(" dynamic range (low even for atmospheric style)."));
children.push(bodyBold("Archetype: ") + body(" atmospheric horror (mood-driven)."));

// §9.4 Score table
children.push(h2("9.4 Score (9 principles, 3-way)"));
children.push(makeTable(
  ["Principle", "Img 1 (warehouse)", "Img 2 (mage)", "Img 3 (horse)", "Winner"],
  [
    ["70/25/5 ratio",     "65/30/5 ✓",         "60/30/10",            {text:"75/20/5 ✓✓",bold:true}, {text:"Img 3",bold:true}],
    ["Color harmony",    "chaotic",            {text:"complementary",bold:true}, "analogous",         {text:"Img 2",bold:true}],
    ["Focal singularity",{text:"single (bulb)",bold:true}, "dual",     "dual",                          {text:"Img 1",bold:true}],
    ["Rule of thirds",   "no",                 "no (S-curve flow)",   {text:"yes (off-center) ✓",bold:true}, {text:"Img 3",bold:true}],
    ["Density balance",  "bottles very dense", "sparks distributed",  {text:"sparse, controlled",bold:true}, {text:"Img 3",bold:true}],
    ["Dynamic range",    "~30:1",              {text:"~50:1",bold:true}, "~20:1",                       {text:"Img 2",bold:true}],
    ["Motion",           "static",             {text:"strong implied",bold:true}, "implied (walking)", {text:"Img 2",bold:true}],
    ["Narrative",        "passive",            {text:"active combat",bold:true}, "active walking + setting", {text:"Img 2",bold:true}],
    ["Tone mapping",     "flat",               {text:"HDR/ACES feel",bold:true}, "muted atmospheric", {text:"Img 2",bold:true}],
  ],
  [22, 22, 22, 22, 12]
));
children.push(spacer(120));
children.push(bodyBold("First places: ") + body(" Image 1 = 1/9. Image 2 = 5/9. Image 3 = 3/9."));

// §9.5 Verdict
children.push(h2("9.5 Principled verdict (3-way)"));
children.push(bodyBold("Image 2 wins") + body(" by principles (5/9 first places). Image 3 is strong second (3/9), Image 1 is weakest (1/9)."));
children.push(spacer(80));
children.push(bodyBold("Image 2 wins on: ") + body(" color harmony, dynamic range, motion, narrative, tone."));
children.push(bodyBold("Image 3 wins on: ") + body(" ratio, rule of thirds, density."));
children.push(bodyBold("Image 1 wins on: ") + body(" focal singularity (only)."));
children.push(spacer(80));
children.push(bodyBold("Image 2 vs Image 3 head-to-head: ") + body(" Image 2 wins on drama (complementary harmony, HDR, motion). Image 3 wins on calm (ratio, composition, density). Different aesthetic targets — Image 2 for action, Image 3 for atmosphere."));

// §9.6 Three archetypes
children.push(h2("9.6 Three aesthetic archetypes"));
children.push(makeTable(
  ["Archetype", "Image", "Defining traits", "Best for"],
  [
    [{text:"Static surreal",bold:true},      "Img 1", "chaotic color, static, single focal, gallery mood",            "ambient / menu / title screens"],
    [{text:"Dynamic dramatic",bold:true},    "Img 2", "complementary harmony, motion, HDR, narrative action",         "action scenes, combat, climactic moments"],
    [{text:"Atmospheric horror",bold:true},  "Img 3", "analogous harmony, muted tone, sparse density, mood-driven",    "exploration, mystery, somber scenes"],
  ],
  [22, 12, 42, 24]
));

// §9.7 Honest caveat
children.push(h2("9.7 Honest caveat"));
children.push(body("This is principled verdict, не taste. Principles in this doc favor:"));
children.push(bullet("Complementary over multicolor OR analogous harmony (drama > calm)"));
children.push(bullet("Motion over static"));
children.push(bullet("Cinematic dynamic range over muted"));
children.push(bullet("Narrative action over ambient mood"));
children.push(spacer(80));
children.push(body("If your taste prefers Image 3's atmospheric horror (calm, muted, mood-driven) — that's valid. Different aesthetics serve different contexts (gallery vs action film vs horror film vs illustration)."));
children.push(body("The 3 archetypes are not ranked absolutely — they serve different goals. Image 2 wins by these principles, but Image 3 might be the right choice for a different mood."));

// ============================================================
// DOCUMENT ASSEMBLY
// ============================================================
const doc = new Document({
  creator: "Z.ai assistant",
  title: "Aesthetic principles",
  description: "Concrete aesthetic principles + 3-image comparative analysis (v0.4 cleaned)",
  styles: {
    default: {
      document: {
        run: { font: { ascii: "Calibri", eastAsia: "Microsoft YaHei" }, size: 22, color: c(P.body) },
        paragraph: { spacing: { line: 312 } },
      },
    },
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1440, bottom: 1440, left: 1701, right: 1417 },
        },
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [
              new TextRun({ text: "— ", size: 18, color: c(P.secondary) }),
              new TextRun({ children: [PageNumber.CURRENT], size: 18, color: c(P.secondary) }),
              new TextRun({ text: " —", size: 18, color: c(P.secondary) }),
            ],
          })],
        }),
      },
      children,
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  const out = "/home/z/my-project/download/aesthetics.docx";
  fs.writeFileSync(out, buf);
  console.log("=== generate_aesthetics_docx.js ===");
  console.log("output: " + out);
  console.log("size:   " + buf.length + " bytes (" + (buf.length / 1024).toFixed(1) + " KB)");
}).catch((err) => {
  console.error("ERROR:", err);
  process.exit(1);
});
