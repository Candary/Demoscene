"""Запуск:  python -m unittest discover -s tests -v   (из корня проекта). Нужен numpy; g++ — для проверки C++ рантайма (иначе пропуск)."""
from __future__ import annotations

import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "output"))

from scene_manager import audio as A  # noqa: E402
from scene_manager.adapters import check_layout, cozy_asset  # noqa: E402
from scene_manager.bake import bake, golden_lines, source_hash, to_smt  # noqa: E402
from scene_manager.effects import EffectCatalog, effect_from_dict  # noqa: E402
from scene_manager.expr import FUNCS, ExprError, compile_expr, eval_rpn, evaluate, fold_constant  # noqa: E402
from scene_manager.graph import memory_report, plan  # noqa: E402
from scene_manager.session import ShowSession, empty_show, merge_patch  # noqa: E402
from scene_manager.timeline import BASE_VARS, compile_show, curve_expr  # noqa: E402
from scene_manager.tools import SHOW_SCHEMAS, FullToolbox, ShowToolbox  # noqa: E402

HAVE_GPP = shutil.which("g++") is not None
EXAMPLE = ROOT / "examples" / "out" / "demo.show.json"


def catalog() -> EffectCatalog:
    c = EffectCatalog()
    for d in [
        {"id": "scene_a", "kind": "scene", "cost": 3, "atoms": {"energy": 0.5}, "uniforms": {
            "uColor": {"type": "vec3", "role": "color", "bind": "palette.primary"},
            "uI": {"type": "float", "min": 0, "max": 2, "default": 1, "bind": "energy"},
            "uReq": {"type": "float", "required": True}}},
        {"id": "scene_b", "kind": "scene", "cost": 2, "uniforms": {"uX": {"type": "float", "default": 0.0}}},
        {"id": "spark", "kind": "overlay", "direct_blend": True, "cost": 1, "uniforms": {}},
        {"id": "credits", "kind": "overlay", "text": True, "direct_blend": True, "uniforms": {}},
        {"id": "prims", "kind": "scene", "uniforms": {"uP": {"type": "farray", "max": 8}}},
    ]:
        c.add(effect_from_dict(d))
    return c


def base_show(**over) -> dict:
    show = {"format": "scene-manager/1", "meta": {"duration": "auto", "seed": 5}, "audio": {"bpm": 120.0, "offset": 0.0, "markers": [{"name": "m", "bar": 5}]},
            "palettes": {"p": {"primary": "#ff8000", "text": "#ffffff", "bg": "#000000"}},
            "tracks": [{"id": "main", "order": 10}, {"id": "post", "order": 25}, {"id": "ov", "order": 30}], "clips": []}
    show.update(over)
    return show


def clip(id_, effect="scene_a", start=0, duration=8, track="main", kind="scene", **kw) -> dict:
    c = {"id": id_, "track": track, "kind": kind, "effect": effect, "start": start, "duration": duration, "map": {"uReq": 1.0}, "palette": "p"}
    if effect != "scene_a":
        c["map"] = {}
    c.update(kw)
    return c


def codes(res, level=None):
    return sorted({i.code for i in res.issues if level is None or i.level == level})


# ======================================================================================================================
class TestExpr(unittest.TestCase):
    def test_precedence_and_unary(self):
        self.assertEqual(evaluate("1 + 2 * 3", {}), 7.0)
        self.assertEqual(evaluate("(1 + 2) * 3", {}), 9.0)
        self.assertEqual(evaluate("-2 * -3", {}), 6.0)
        self.assertEqual(evaluate("1 < 2 && 2 < 3 || 0", {}), 1.0)
        self.assertEqual(evaluate("!0 + !5", {}), 1.0)
        self.assertEqual(evaluate("10 - 4 - 3", {}), 3.0)           # левоассоциативность
        self.assertEqual(evaluate("2 * 3 % 4", {}), 2.0)

    def test_total_semantics(self):
        self.assertEqual(evaluate("1 / 0", {}), 0.0)
        self.assertEqual(evaluate("5 % 0", {}), 0.0)
        self.assertEqual(evaluate("sqrt(-4)", {}), 0.0)
        self.assertEqual(evaluate("pow(-8, 0.5)", {}), 0.0)
        self.assertEqual(evaluate("pow(0, -1)", {}), 0.0)
        self.assertEqual(evaluate("exp(10000)", {}) > 0, True)
        self.assertEqual(evaluate("mod(-1, 4)", {}), 3.0)
        self.assertEqual(evaluate("if(1, 10, 1/0)", {}), 10.0)       # все аргументы вычисляются, но безопасно
        for src in ("sqrt(0-1) / 0", "pow(10, 1000)", "exp(1000) * exp(1000)"):
            self.assertTrue(math.isfinite(evaluate(src, {})), src)

    def test_functions(self):
        e = {"x": 0.25}
        self.assertEqual(evaluate("clamp(x * 8, 0, 1)", e), 1.0)
        self.assertEqual(evaluate("mix(10, 20, x)", e), 12.5)
        self.assertAlmostEqual(evaluate("smoothstep(0, 1, 0.5)", {}), 0.5)
        self.assertEqual(evaluate("step(0.5, 0.4)", {}), 0.0)
        self.assertEqual(evaluate("fract(-0.25)", {}), 0.75)
        self.assertEqual(evaluate("sign(0-3) + sign(2)", {}), 0.0)

    def test_errors(self):
        for bad in ["", "1 +", "foo(1)", "min(1)", "a b", "x = 1", "__import__('os')", "1 ** 2", "sin(", "()", "t.x.y.z.", "1 2"]:
            with self.assertRaises(ExprError, msg=bad):
                compile_expr(bad)
        with self.assertRaises(ExprError):
            compile_expr("unknown + 1", allowed_names={"t"})
        with self.assertRaises(ExprError):
            compile_expr("+".join(["1"] * 150))                       # длиннее 200 токенов
        with self.assertRaises(ExprError):
            compile_expr("(" * 40 + "1" + ")" * 40)                   # слишком глубокая вложенность

    def test_names_and_folding(self):
        c = compile_expr("t * 2 + audio.energy", {"t", "audio.energy"})
        self.assertEqual(c.names, frozenset({"t", "audio.energy"}))
        self.assertTrue(fold_constant(compile_expr("2 * 3 + sin(0)")).rpn == (("n", 6.0),))
        self.assertEqual(fold_constant(c).rpn, c.rpn)

    def test_rpn_matches_string_eval_on_random_corpus(self):
        rng = random.Random(1)
        for _ in range(200):
            f = rng.choice(sorted(FUNCS))
            src = f"{f}({', '.join(repr(round(rng.uniform(-3, 3), 2)) for _ in range(FUNCS[f]))})"
            c = compile_expr(src)
            self.assertEqual(eval_rpn(c.rpn, {}), evaluate(src, {}))
            self.assertTrue(math.isfinite(eval_rpn(c.rpn, {})))


class TestCurves(unittest.TestCase):
    def ev(self, keys, t):
        return evaluate(curve_expr(keys), {"t": t})

    def test_linear_and_clamping(self):
        k = [[0, 1.0], [10, 3.0]]
        self.assertAlmostEqual(self.ev(k, -5), 1.0)
        self.assertAlmostEqual(self.ev(k, 5), 2.0)
        self.assertAlmostEqual(self.ev(k, 99), 3.0)

    def test_easings_and_hold(self):
        self.assertAlmostEqual(self.ev([[0, 0], [10, 1, "smoothstep"]], 2.5), 0.15625)
        self.assertAlmostEqual(self.ev([[0, 0], [10, 1, "ease_in"]], 5), 0.25)
        self.assertAlmostEqual(self.ev([[0, 5], [10, 9, "hold"]], 9.99), 5.0)
        self.assertAlmostEqual(self.ev([[0, 5], [10, 9, "hold"]], 10), 9.0)

    def test_multi_segment(self):
        k = [[0, 0], [4, 1], [8, 0.5], [12, 2]]
        for t, v in [(0, 0), (4, 1), (6, 0.75), (8, 0.5), (12, 2)]:
            self.assertAlmostEqual(self.ev(k, t), v, msg=t)

    def test_long_curves_compile_and_match_interp(self):
        # регрессия: кривая с 10+ ключами раньше упиралась в лимит 200 токенов
        rng = random.Random(9)
        for n in (10, 40, 300):
            keys = [[i * 0.5, round(rng.uniform(0, 1), 3)] for i in range(n)]
            c = compile_expr(curve_expr(keys), {"t"}, max_tokens=40000)
            ts, vs = [k[0] for k in keys], [k[1] for k in keys]
            for _ in range(50):
                t = rng.uniform(-1, 0.5 * n + 1)
                self.assertAlmostEqual(eval_rpn(c.rpn, {"t": t}), float(np.interp(t, ts, vs)), places=12)

    def test_validation(self):
        for bad in ([], [[0]], [[0, 1], [0, 2]], [[1, 1], [0, 2]], [[0, 1, "wobble"]], "x"):
            with self.assertRaises(ExprError, msg=bad):
                curve_expr(bad)


# ======================================================================================================================
def synth(bpm, off, dur=50.0, hats=True, levels=None, sr=A.SR, seed=0):
    spb = 60 / bpm
    x = np.zeros(int(sr * dur), dtype=np.float32)
    rng = np.random.default_rng(seed)
    for b in range(int((dur - off) / spb)):
        t0 = off + b * spb
        lvl = 1.0 if levels is None else levels(t0)
        i = int(t0 * sr)
        seg = np.arange(min(int(0.15 * sr), len(x) - i)) / sr
        x[i:i + len(seg)] += lvl * (1.0 if b % 4 == 0 else 0.7) * np.sin(2 * np.pi * (55 + 90 * np.exp(-seg * 40)) * seg) * np.exp(-seg * 18)
        if hats and lvl > 0.5:
            j = int((t0 + spb / 2) * sr)
            m = min(int(0.05 * sr), len(x) - j)
            if m > 0:
                x[j:j + m] += 0.25 * rng.standard_normal(m) * np.exp(-np.arange(m) / sr * 80)
    return np.clip(x, -1, 1).astype(np.float32)


class TestAudio(unittest.TestCase):
    def test_musical_time_math(self):
        m = A.AudioMap(bpm=120, offset=0.5, beats_per_bar=4)
        self.assertAlmostEqual(m.time_of(1, 1), 0.5)
        self.assertAlmostEqual(m.time_of(3, 2), 0.5 + (8 + 1) * 0.5)
        self.assertAlmostEqual(m.bar(0.5 + 8.0), 4.0)           # 8 с при 120 BPM = 16 долей = 4 такта от offset
        self.assertAlmostEqual(m.beat_phase(0.5 + 0.25), 0.5)
        self.assertLess(m.beat(0.0), 0)

    def test_markers_by_bar_and_energy(self):
        m = A.AudioMap.from_show({"bpm": 120, "offset": 0.0, "markers": [{"name": "d", "bar": 9}, {"name": "t", "time": 3.5}]})
        self.assertAlmostEqual(m.marker("d"), 16.0)
        self.assertEqual(m.marker("t"), 3.5)
        with self.assertRaises(KeyError):
            m.marker("nope")
        m.energy = np.array([0.0, 1.0, 0.0])
        self.assertAlmostEqual(m.energy_at(1 / A.ENERGY_RATE), 1.0)
        self.assertAlmostEqual(m.energy_at(0.5 / A.ENERGY_RATE), 0.5)
        with self.assertRaises(ValueError):
            A.AudioMap.from_show({"bpm": 0})

    def test_tempo_and_downbeat_on_synthetic_tracks(self):
        for bpm, off, hats in [(96, 0.2, True), (128, 0.35, True), (128, 0.0, False), (140, 0.7, True)]:
            r = A.analyze_samples(synth(bpm, off, hats=hats))
            per = 60 / bpm * 4
            err = ((r["offset"] - off + per / 2) % per) - per / 2
            self.assertLess(abs(r["bpm"] - bpm), 0.05, (bpm, r["bpm"]))
            self.assertLess(abs(err), 0.03, (bpm, off, r["offset"]))

    def test_sections_found_with_labels(self):
        bar = 4 * 60 / 128
        off = 0.35

        def lvl(t):                      # такты: 1-8 тихо, 9-16 громко, 17-24 тихо, 25-32 громко
            b = int((t - off) // bar)
            return [0.3, 1.0, 0.3, 1.0][min(b // 8, 3)]
        r = A.analyze_samples(synth(128, off, dur=off + 32 * bar, levels=lvl))
        starts = [round((s["start"] - r["offset"]) / bar + 1) for s in r["sections"]]
        self.assertEqual(starts[1:], [9, 17, 25])
        self.assertEqual([s.get("label") for s in r["sections"][1:]], ["drop", "breakdown", "drop"])

    def test_too_short_and_missing_file(self):
        with self.assertRaises(ValueError):
            A.analyze_samples(np.zeros(1000, dtype=np.float32))
        with self.assertRaises(FileNotFoundError):
            A.decode_audio("/no/such/file.mp3")

    @unittest.skipUnless(shutil.which("ffmpeg"), "нет ffmpeg")
    def test_mp3_roundtrip_decode_and_analysis(self):
        d = Path(tempfile.mkdtemp())
        import wave
        x = synth(128, 0.35, dur=40.0, sr=22050)
        with wave.open(str(d / "t.wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes((x * 32767).astype("<i2").tobytes())
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(d / "t.wav"), "-b:a", "128k", str(d / "t.mp3")], check=True)
        r = A.analyze_file(d / "t.mp3")
        self.assertLess(abs(r["bpm"] - 128), 0.05)
        per = 60 / 128 * 4
        self.assertLess(abs(((r["offset"] - 0.35 + per / 2) % per) - per / 2), 0.06)   # допуск шире: MP3-кодек вносит задержку


# ======================================================================================================================
class TestTimeline(unittest.TestCase):
    cat = catalog()

    def compile(self, clips, **over):
        return compile_show(base_show(clips=clips, **over), self.cat)

    def test_anchor_kinds(self):
        r = self.compile([
            clip("a", start=0, duration={"bars": 2}),                                   # 2 такта = 4 с
            clip("b", start={"after": "a", "offset": 1.0}, duration={"beats": 4}),       # 5..7
            clip("c", start={"marker": "m", "offset_beats": 2}, duration=1.0),           # бар 5 = 8 с, +2 доли = 9 с
            clip("d", start={"bar": 3, "beat": 2}, end={"start_of": "c"}),               # бар 3 дол 2 = 4.5 с .. 9
            clip("e", start={"with": "d", "offset": 0.5}, duration={"until": {"end_of": "c"}}),
        ])
        self.assertEqual(r.errors, [])
        t = {c.id: (round(c.nom_start, 6), round(c.nom_end, 6)) for c in r.clips}
        self.assertEqual(t["a"], (0.0, 4.0))
        self.assertEqual(t["b"], (5.0, 7.0))
        self.assertEqual(t["c"], (9.0, 10.0))
        self.assertEqual(t["d"], (4.5, 9.0))
        self.assertEqual(t["e"], (5.0, 10.0))

    def test_retiming_marker_moves_dependents_only(self):
        mk = lambda bar: [{"name": "m", "bar": bar}]  # noqa: E731
        clips = [clip("a", start=0, duration={"until": {"marker": "m"}}), clip("b", start={"marker": "m"}, duration=4), clip("c", start=100, duration=4)]
        r1 = compile_show(base_show(clips=clips, audio={"bpm": 120, "markers": mk(5)}), self.cat)
        r2 = compile_show(base_show(clips=clips, audio={"bpm": 120, "markers": mk(9)}), self.cat)
        g = lambda r, i: r.clip(i).nom_start  # noqa: E731
        self.assertEqual((g(r1, "b"), g(r2, "b")), (8.0, 16.0))
        self.assertEqual(r2.clip("a").nom_end, 16.0)
        self.assertEqual(g(r1, "c"), g(r2, "c"))

    def test_cycle_and_all_errors_reported_together(self):
        r = self.compile([clip("a", start={"after": "b"}), clip("b", start={"after": "a"}),
                          clip("c", effect="nope"), clip("d", track="ghost"), clip("e", map={"uBad": 1})])
        cs = codes(r, "error")
        self.assertIn("E_TIME", cs)
        self.assertIn("E_EFFECT_REF", cs)
        self.assertIn("E_TRACK_REF", cs)
        self.assertIn("E_UNIFORM_UNKNOWN", cs)
        self.assertTrue(any("циклическая" in i.message and "a -> b -> a" in i.message for i in r.errors))

    def test_duplicate_and_bad_ids(self):
        r = self.compile([clip("a"), clip("a"), clip("bad id!")])
        self.assertEqual(sum(1 for i in r.errors if i.code == "E_ID"), 2)

    def test_transition_windows(self):
        for align, win in [("center", (7.0, 9.0)), ("end", (6.0, 8.0)), ("start", (8.0, 10.0))]:
            r = self.compile([clip("a", start=0, duration=8), clip("b", start=8, duration=8),
                              {"id": "t", "kind": "transition", "effect": "crossfade", "between": ["a", "b"], "duration": 2.0, "align": align}])
            self.assertEqual(r.errors, [], align)
            t = r.clip("t")
            self.assertEqual((t.eff_start, t.eff_end), win, align)
            self.assertEqual(r.clip("a").eff_end, max(8.0, win[1]))      # A продлён до конца окна
            self.assertEqual(r.clip("b").eff_start, min(8.0, win[0]))    # B начинается с начала окна
            self.assertEqual((r.clip("a").nom_start, r.clip("a").nom_end), (0.0, 8.0))   # номинал не тронут
            self.assertEqual(r.clip("t").track, "main")                  # переход наследует дорожку A
            self.assertEqual(r.clip("t").inputs, ("a", "b"))

    def test_transition_errors_and_cut(self):
        r = self.compile([clip("a", start=0, duration=1), clip("b", start=1, duration=8),
                          {"id": "t", "kind": "transition", "effect": "crossfade", "between": ["a", "b"], "duration": 4.0}])
        self.assertIn("E_TRANSITION_LONG", codes(r, "error"))
        r = self.compile([clip("a"), clip("b", start=8), {"id": "t", "kind": "transition", "effect": "cut", "between": ["a", "b"], "duration": 2}])
        self.assertEqual([c.id for c in r.clips], ["a", "b"])           # cut не создаёт клип
        r = self.compile([clip("a"), clip("b", start=8, track="ov"), {"id": "t", "kind": "transition", "effect": "crossfade", "between": ["a", "b"], "duration": 1}])
        self.assertTrue(any(i.code == "E_TRANSITION" and "одной дорожке" in i.message for i in r.errors))
        r = self.compile([clip("a"), clip("b", start=8), {"id": "t", "kind": "transition", "effect": "bloom", "between": ["a", "b"], "duration": 1}])
        self.assertIn("E_EFFECT_REF", codes(r, "error"))

    def test_atoms_curves_inlined_into_programs(self):
        c = clip("a", atoms={"energy": {"keys": [[0, 0.0], [8, 2.0]]}, "boost": {"expr": "energy * 2"}}, map={"uReq": 1, "uI": "boost + 1"})
        r = self.compile([c])
        self.assertEqual(r.errors, [])
        rc = r.clip("a")
        self.assertTrue(rc.uniforms["uI"][1][0].names <= BASE_VARS)     # атомы подставлены: в программе только базовые переменные
        self.assertAlmostEqual(eval_rpn(rc.uniforms["uI"][1][0].rpn, r.env_at(rc, 4.0)), 3.0)   # energy(4)=1 -> boost=2 -> 3

    def test_broken_atom_does_not_cascade(self):
        r = self.compile([clip("a", atoms={"energy": {"keys": [[0, 0], [0, 1]]}})])      # ключи не возрастают
        self.assertEqual([i.code for i in r.errors], ["E_EXPR"])                          # одна ошибка, без «неизвестная переменная energy»

    def test_curve_too_long_message_is_actionable(self):
        keys = [[i * 0.1, 0.5] for i in range(2000)]
        r = self.compile([clip("a", atoms={"energy": {"keys": keys}}, duration=300)])
        self.assertTrue(any("разбейте кривую" in i.message for i in r.errors))

    def test_atom_errors(self):
        r = self.compile([clip("a", atoms={"x": {"expr": "y"}, "y": {"expr": "x"}})])
        self.assertIn("E_ATOM_CYCLE", codes(r, "error"))
        r = self.compile([clip("a", atoms={"t": 1})])
        self.assertIn("E_ATOM_NAME", codes(r, "error"))
        r = self.compile([clip("a", atoms={"feel": "anxiety", "energy": 0.3})])       # категориальные строки не мешают
        self.assertEqual(r.errors, [])

    def test_uniform_binding_precedence_and_required(self):
        r = self.compile([clip("a", map={})])                                         # uReq обязателен и не задан
        self.assertIn("E_REQUIRED_UNIFORM", codes(r, "error"))
        r = self.compile([clip("a", palette="p", atoms={"energy": 0.5}, map={"uReq": 1, "uI": 0.7})])
        u = r.clip("a").uniforms
        self.assertEqual(u["uI"][1][0].rpn, (("n", 0.7),))                            # map > bind
        self.assertAlmostEqual(u["uColor"][1][0].rpn[0][1], 1.0)                      # bind palette.primary = #ff8000
        r = self.compile([clip("a", palette="p", map={"uReq": 1, "uColor": {"color": "palette.nope"}})])
        self.assertTrue(any("нет роли" in i.message for i in r.errors))
        r = self.compile([clip("a", map={"uReq": 1, "uTime": 1})])
        self.assertIn("E_UNIFORM_RESERVED", codes(r, "error"))

    def test_linear_color_space_conversion(self):
        c = EffectCatalog()
        c.add(effect_from_dict({"id": "lin", "kind": "scene", "uniforms": {"uC": {"type": "vec3", "space": "linear", "default": [0, 0, 0]}}}))
        s = base_show(clips=[{"id": "a", "track": "main", "kind": "scene", "effect": "lin", "start": 0, "duration": 1, "palette": "p",
                              "map": {"uC": {"color": "#808080"}}}])
        r = compile_show(s, c)
        self.assertAlmostEqual(r.clip("a").uniforms["uC"][1][0].rpn[0][1], 0.2158605, places=5)   # sRGB 0.502 -> линейное 0.2159

    def test_range_warning_is_sampled_over_clip(self):
        r = self.compile([clip("a", duration=10, map={"uReq": 1, "uI": "t * 0.5"})])  # до 5 при max=2
        self.assertIn("W_RANGE", codes(r, "warning"))
        r = self.compile([clip("a", duration=10, map={"uReq": 1, "uI": "t * 0.1"})])
        self.assertNotIn("W_RANGE", codes(r))

    def test_lint_overlap_gap_uncovered(self):
        r = self.compile([clip("a", start=0, duration=8), clip("b", start=6, duration=8)], meta={"duration": 20})
        self.assertIn("W_OVERLAP", codes(r))
        r = self.compile([clip("a", start=0, duration=4), clip("b", start=6, duration=4)])
        self.assertIn("W_GAP", codes(r))
        r = self.compile([clip("a", start=0, duration=4), clip("b", start=6, duration=4, allow_gap=True)])
        self.assertNotIn("W_GAP", codes(r))
        r = self.compile([clip("a", start=2, duration=4)], meta={"duration": 10})
        self.assertIn("W_UNCOVERED", codes(r))

    def test_lint_budget_truncation_text_contrast(self):
        r = self.compile([clip("a", duration=10), clip("b", effect="scene_b", start=0, duration=10, track="ov", allow_overlap=True)], meta={"duration": 10, "budget": 4})
        self.assertIn("W_BUDGET", codes(r))
        r = self.compile([clip("a", duration=10)], meta={"duration": 6})
        self.assertIn("W_TRUNCATED", codes(r))
        s = base_show(clips=[clip("a", duration=8), clip("cr", effect="credits", track="ov", kind="overlay", palette="weak", duration=4)],
                      palettes={"weak": {"text": "#777777", "bg": "#808080"}, "p": {"primary": "#fff"}})
        self.assertIn("W_TEXT_CONTRAST", codes(compile_show(s, self.cat)))

    def test_strict_rejects_proposed(self):
        s = base_show(clips=[clip("a", status="proposed")])
        self.assertEqual(compile_show(s, self.cat).errors, [])
        self.assertIn("E_PROPOSED", codes(compile_show(s, self.cat, strict=True), "error"))

    def test_farray_sources(self):
        s = base_show(clips=[clip("a", effect="prims", map={"uP": {"asset": "x"}})], assets={"x": {"floats": [1, 2, 3]}})
        r = compile_show(s, self.cat)
        self.assertEqual(r.errors, [])
        self.assertEqual(r.clip("a").arrays["uP"], [1.0, 2.0, 3.0])
        s["clips"][0]["map"]["uP"] = {"asset": "x", "array": [1]}
        self.assertTrue(any("и asset, и array" in i.message for i in compile_show(s, self.cat).errors))
        s["clips"][0]["map"]["uP"] = {"array": [0.0] * 9}
        self.assertTrue(any("> допустимой 8" in i.message for i in compile_show(s, self.cat).errors))
        s["clips"][0]["map"]["uP"] = {"asset": "ghost"}
        self.assertTrue(any("нет ассета" in i.message for i in compile_show(s, self.cat).errors))

    def test_duration_auto_and_finish(self):
        r = self.compile([clip("a", duration=10), clip("f", effect="finish", kind="event", track="post", start=7)])
        self.assertEqual(r.duration, 7.0)
        r = self.compile([clip("a", duration=10)])
        self.assertEqual(r.duration, 10.0)


# ======================================================================================================================
class TestGraph(unittest.TestCase):
    cat = catalog()

    def segs(self, clips, **over):
        r = compile_show(base_show(clips=clips, **over), self.cat)
        self.assertEqual(r.errors, [], [str(e) for e in r.errors])
        return r, plan(r, self.cat)

    def test_single_scene_renders_straight_to_screen(self):
        _, s = self.segs([clip("a", duration=8)])
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0].n_physical, 0)
        self.assertEqual([o["op"] for o in s[0].physical_ops()], ["RENDER", "PRESENT"])
        self.assertEqual(s[0].physical_ops()[0]["write"], "screen")

    def test_post_chain_uses_two_textures_regardless_of_length(self):
        posts = [clip(f"p{i}", effect=e, kind="post", track="post", start=0, duration=8) for i, e in enumerate(["bloom", "grain", "vignette", "bloom"] if False else ["bloom", "grain", "vignette"])]
        _, s = self.segs([clip("a", duration=8)] + posts)
        self.assertEqual(s[0].n_physical, 2)
        self.assertEqual(s[0].physical_ops()[-2]["write"], "screen")

    def test_transition_first_layer_writes_screen_directly(self):
        _, s = self.segs([clip("a", duration=8), clip("b", start=8, duration=8), {"id": "t", "kind": "transition", "effect": "crossfade", "between": ["a", "b"], "duration": 2}])
        mid = [x for x in s if x.start < 8 < x.end][0]
        self.assertEqual(mid.n_physical, 2)                                          # A и B; результат сразу на экран
        ops = mid.physical_ops()
        self.assertEqual([o["op"] for o in ops], ["RENDER", "RENDER", "TRANSITION", "PRESENT"])
        self.assertEqual(ops[2]["write"], "screen")

    def test_direct_blend_overlay_needs_no_fbo_and_post_order_matters(self):
        clips = [clip("a", duration=8), clip("sp", effect="spark", kind="overlay", track="main", start=0, duration=8, blend="add"),
                 clip("bl", effect="bloom", kind="post", track="post", start=0, duration=8),
                 clip("cr", effect="credits", kind="overlay", track="ov", start=0, duration=8)]
        _, s = self.segs(clips)
        ops = s[0].physical_ops()
        names = [(o["op"], o.get("clip")) for o in ops]
        self.assertEqual(names[:4], [("RENDER", "a"), ("DRAW", "sp"), ("POST", "bl"), ("DRAW", "cr")])   # титры после post, поверх, без bloom
        self.assertEqual(ops[3]["dest"], "screen")
        self.assertEqual(s[0].n_physical, 1)                                          # единственный FBO — вход bloom

    def test_non_opaque_layer_gets_fbo_and_composite(self):
        _, s = self.segs([clip("a", duration=8), clip("b", effect="scene_b", track="ov", duration=8, opacity=0.5, allow_overlap=True)])
        self.assertIn("COMPOSITE", [o["op"] for o in s[0].physical_ops()])

    def test_no_live_physical_target_is_shared(self):
        r, segs = self.segs([clip("a", duration=8), clip("b", start=8, duration=8), {"id": "t", "kind": "transition", "effect": "flash", "between": ["a", "b"], "duration": 2},
                             clip("bl", effect="bloom", kind="post", track="post", start=0, duration=16), clip("g", effect="grain", kind="post", track="post", start=0, duration=16)])
        for sg in segs:
            first, last = {}, {}
            for i, o in enumerate(sg.ops):
                for v in o.refs():
                    first.setdefault(v, i); last[v] = i
            phys: dict[str, list] = {}
            for v, p in sg.targets.items():
                if p != "screen":
                    phys.setdefault(p, []).append((first[v], last[v]))
            for p, spans in phys.items():
                spans.sort()
                for (a0, a1), (b0, b1) in zip(spans, spans[1:]):
                    self.assertLess(a1, b0, (sg.start, p))                            # интервалы жизни одной текстуры не пересекаются

    def test_equal_neighbours_are_merged_and_memory_report(self):
        r, s = self.segs([clip("a", duration=8), clip("sp", effect="spark", kind="overlay", start=3, duration=2), clip("sp2", effect="spark", kind="overlay", start=5, duration=1)])
        self.assertTrue(all(x.end > x.start for x in s))
        rep = memory_report(s, 1920, 1080, 8)
        self.assertEqual(rep["fbo_bytes_each"], 1920 * 1080 * 8)
        self.assertEqual(rep["peak_fbos"], max(x.n_physical for x in s))


# ======================================================================================================================
class TestBake(unittest.TestCase):
    cat = catalog()

    def setUp(self):
        self.show = base_show(clips=[clip("a", palette="p", atoms={"energy": {"expr": "0.5 + 0.5 * audio.energy"}}, map={"uReq": 1, "uI": "energy + sin(t)"}),
                                     clip("b", effect="scene_b", start=8, duration=8), {"id": "t", "kind": "transition", "effect": "wipe", "between": ["a", "b"], "duration": 1}])
        self.res = compile_show(self.show, self.cat)
        self.assertEqual(self.res.errors, [])

    def test_baked_programs_use_only_base_variables(self):
        b = bake(self.res, self.cat, self.show)
        names = set()
        for c in b["clips"]:
            for p in [c["opacity"], c["progress"], *[q for u in c["uniforms"] for q in u["programs"]]]:
                names |= {t[2:] for t in p if t.startswith("v:")}
        self.assertTrue(names <= BASE_VARS, names - BASE_VARS)
        self.assertNotIn("energy", names)

    def test_source_hash_tracks_content(self):
        h1 = source_hash(self.show)
        self.assertEqual(h1, source_hash(json.loads(json.dumps(self.show))))
        s2 = json.loads(json.dumps(self.show)); s2["clips"][0]["duration"] = 9
        self.assertNotEqual(h1, source_hash(s2))

    def test_bake_refuses_errors(self):
        bad = compile_show(base_show(clips=[clip("a", effect="nope")]), self.cat)
        with self.assertRaises(ValueError):
            bake(bad, self.cat)

    def test_smt_is_whitespace_tokenisable(self):
        smt = to_smt(bake(self.res, self.cat, self.show))
        self.assertTrue(smt.startswith("SMT 1\n") and smt.rstrip().endswith("end"))
        for line in smt.splitlines():
            if line.startswith("prog"):
                parts = line.split()
                k = 3 if parts[1] in ("opacity", "progress") else 2
                self.assertEqual(int(parts[k - 1]), len(parts) - k, line[:60])

    def test_transition_progress_curve_baked(self):
        b = bake(self.res, self.cat, self.show)
        t = next(c for c in b["clips"] if c["id"] == "t")
        self.assertIn("f:smoothstep", t["progress"])


# ======================================================================================================================
class TestSession(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.s = ShowSession(empty_show("T"), catalog(), self.d)
        r = self.s.edit([{"op": "add_track", "id": "main", "order": 10},
                         {"op": "set_palette", "name": "p", "colors": {"primary": "#ff8000"}},
                         {"op": "add_clip", "clip": clip("a", palette="p", duration=8)},
                         {"op": "add_clip", "clip": clip("b", effect="scene_b", start={"after": "a"}, duration=8)}])
        self.assertTrue(r["ok"], r)

    def test_atomic_rejection(self):
        before = json.dumps(self.s.show, sort_keys=True)
        r = self.s.edit([{"op": "update_clip", "id": "a", "patch": {"atoms": {"energy": 0.9}}}, {"op": "remove_clip", "id": "ghost"}])
        self.assertFalse(r["ok"])
        self.assertIn("операция #1", r["error"])
        self.assertEqual(before, json.dumps(self.s.show, sort_keys=True))

    def test_merge_patch_semantics(self):
        self.assertEqual(merge_patch({"a": 1, "n": {"x": 1, "y": 2}}, {"n": {"y": None, "z": 3}, "b": 2, "a": None}), {"n": {"x": 1, "z": 3}, "b": 2})
        self.s.edit([{"op": "update_clip", "id": "a", "patch": {"atoms": {"energy": 0.9, "k": 1}}}])
        self.s.edit([{"op": "update_clip", "id": "a", "patch": {"atoms": {"k": None}}}])
        self.assertEqual(self.s.show["clips"][0]["atoms"], {"energy": 0.9})

    def test_undo_redo_and_dry_run(self):
        n = len(self.s.show["clips"])
        r = self.s.edit([{"op": "remove_clip", "id": "b"}], dry_run=True)
        self.assertTrue(r["ok"] and r["dry_run"])
        self.assertEqual(len(self.s.show["clips"]), n)
        self.s.edit([{"op": "remove_clip", "id": "b"}])
        self.assertEqual(len(self.s.show["clips"]), n - 1)
        self.assertTrue(self.s.undo()["ok"])
        self.assertEqual(len(self.s.show["clips"]), n)
        self.assertTrue(self.s.redo()["ok"])
        self.assertEqual(len(self.s.show["clips"]), n - 1)
        self.assertFalse(ShowSession(empty_show(), catalog()).undo()["ok"])

    def test_locks_and_force(self):
        self.s.edit([{"op": "lock", "id": "a"}])
        r = self.s.edit([{"op": "update_clip", "id": "a", "patch": {"duration": 4}}])
        self.assertFalse(r["ok"])
        self.assertIn("locked", r["error"])
        self.assertTrue(self.s.edit([{"op": "update_clip", "id": "a", "force": True, "patch": {"duration": 4}}])["ok"])
        self.assertFalse(self.s.edit([{"op": "remove_clip", "id": "a"}])["ok"])

    def test_remove_guards_references(self):
        r = self.s.edit([{"op": "remove_clip", "id": "a"}])
        self.assertFalse(r["ok"])
        self.assertIn("ссылаются", r["error"])
        self.assertTrue(self.s.edit([{"op": "remove_clip", "id": "a", "cascade": True}])["ok"])

    def test_new_issues_diff_includes_message(self):
        r = self.s.edit([{"op": "update_clip", "id": "a", "patch": {"map": {"uI": "t * 9"}}}])
        self.assertIn("W_RANGE", [i["code"] for i in r["new_issues"]])
        r2 = self.s.edit([{"op": "update_clip", "id": "a", "patch": {"map": {"uI": "t * 8"}}}])
        self.assertIn("W_RANGE", [i["code"] for i in r2["new_issues"]])               # тот же код и путь, другой текст -> новое замечание

    def test_require_valid(self):
        before = json.dumps(self.s.show)
        r = self.s.edit([{"op": "update_clip", "id": "a", "patch": {"effect": "ghost"}}], require_valid=True)
        self.assertFalse(r["ok"])
        self.assertEqual(before, json.dumps(self.s.show))
        self.assertTrue(self.s.edit([{"op": "update_clip", "id": "a", "patch": {"effect": "ghost"}}])["ok"])    # без require_valid — допускается

    def test_move_with_ripple(self):
        self.s.edit([{"op": "add_clip", "clip": clip("c", start=100, duration=2)}, {"op": "update_clip", "id": "b", "patch": {"start": 8}}])
        r = self.s.edit([{"op": "move_clip", "id": "b", "start": 10, "ripple": True}])
        self.assertTrue(r["ok"])
        starts = {c["id"]: c["start"] for c in self.s.show["clips"]}
        self.assertEqual(starts["b"], 10)
        self.assertEqual(starts["c"], 102)

    def test_accept_all(self):
        self.s.edit([{"op": "add_clip", "clip": clip("p1", effect="scene_b", start=16, duration=2, status="proposed")}])
        self.assertTrue(any(e["code"] == "E_PROPOSED" for e in self.s.lint(strict=True)["errors"]))
        self.s.edit([{"op": "accept", "all": True}])
        self.assertFalse(any(e["code"] == "E_PROPOSED" for e in self.s.lint(strict=True)["errors"]))

    def test_storyboard_and_resolve_at(self):
        sb = self.s.storyboard()
        self.assertIn("a: scene/scene_a", sb)
        self.assertIn("такт", sb)
        r = self.s.resolve_at(4.0)
        self.assertIn("a", r["active"])
        self.assertEqual(r["passes"][-1]["op"], "PRESENT")
        self.assertAlmostEqual(r["active"]["a"]["uniforms"]["uColor"][0], 1.0, places=3)

    def test_save_load_roundtrip(self):
        p = self.s.save(Path(self.d) / "x.show.json")
        s2 = ShowSession.load(p, catalog())
        self.assertEqual(s2.show, self.s.show)

    def test_suggest_transitions_follows_energy(self):
        energy = np.concatenate([np.full(int(10 * A.ENERGY_RATE), 0.1), np.full(int(10 * A.ENERGY_RATE), 0.9)])
        self.s.edit([{"op": "update_clip", "id": "a", "patch": {"duration": 10}}])
        res = self.s.compile()
        res.audio.energy = energy
        self.s._cache = (self.s._cache[0], res)
        r = self.s.suggest_transitions("a", "b")
        self.assertIn(r["candidates"][0]["effect"], ("flash", "glitch", "cut"))
        res.audio.energy = energy[::-1].copy()
        self.assertEqual(self.s.suggest_transitions("a", "b")["candidates"][0]["effect"], "fade_to_black")
        self.assertIn("error", self.s.suggest_transitions("a", "ghost"))

    def test_import_audio_writes_analysis_and_sets_markers(self):
        import wave
        x = synth(128, 0.35, dur=30.0)
        p = Path(self.d) / "t.wav"
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(A.SR); w.writeframes((x * 32767).astype("<i2").tobytes())
        r = self.s.import_audio(p)
        self.assertTrue(r["ok"])
        self.assertAlmostEqual(self.s.show["audio"]["bpm"], 128.0, places=1)
        self.assertTrue((Path(self.d) / "t.analysis.json").exists())
        self.assertGreater(len(self.s.compile().audio.energy), 100)                    # анализ подхвачен через audio.analysis

    def test_bake_writes_files(self):
        out = self.s.bake(Path(self.d) / "out")
        self.assertTrue(out["ok"])
        for f in out["files"]:
            self.assertTrue(Path(f).exists())


class TestSessionWithColorMatrix(unittest.TestCase):
    V11 = ROOT / "output" / "color-matrix-full-rgb-v11.npz"

    @unittest.skipUnless(V11.exists(), "нет Color Matrix v11")
    def test_suggest_palette_temperature_and_contrast(self):
        from color_matrix_python.reader import FullRGBMatrixReader
        from color_matrix_python.tools import ColorToolbox
        s = ShowSession(empty_show(), catalog(), tempfile.mkdtemp(), color_toolbox=ColorToolbox(FullRGBMatrixReader(self.V11)))
        warm = s.suggest_palette("warmth", temperature="warm")
        cool = s.suggest_palette("warmth", temperature="cool")
        self.assertEqual(warm["primary_profile"]["empathy_label"], "warmth")
        self.assertIn(warm["primary_profile"]["temperature"], ("warm", "hot"))
        self.assertIn(cool["primary_profile"]["temperature"], ("cold", "cool"))
        self.assertGreaterEqual(warm["checks"]["text_on_bg_contrast"], 7)
        self.assertEqual(warm["source"]["tool"], "color_matrix")
        self.assertIn("error", s.suggest_palette("warmth", temperature="lukewarm"))
        self.assertIn("error", ShowSession(empty_show(), catalog()).suggest_palette("warmth"))


# ======================================================================================================================
class TestTools(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.sess = ShowSession(empty_show("T"), catalog(), self.d)
        self.tb = ShowToolbox(self.sess, autosave=self.d / "auto.show.json")

    def test_schemas_valid_and_match_tools(self):
        json.dumps(SHOW_SCHEMAS)
        self.assertEqual({s["function"]["name"] for s in SHOW_SCHEMAS}, set(self.tb._tools))
        for s in SHOW_SCHEMAS:
            self.assertTrue(s["function"]["description"])

    def test_edit_autosaves_and_dispatch_errors(self):
        r = self.tb.dispatch("edit_show", {"ops": [{"op": "add_track", "id": "main"}]})
        self.assertTrue(r["ok"])
        self.assertTrue((self.d / "auto.show.json").exists())
        for name, args in [("nope", {}), ("edit_show", {"ops": [{"op": "bogus"}]}), ("resolve_at", {}), ("describe_effect", {"id": "ghost"}), ("edit_show", "{bad")]:
            res = self.tb.dispatch(name, args)
            self.assertTrue("error" in res or res.get("ok") is False, (name, res))

    def test_list_and_describe_effects(self):
        r = self.tb.dispatch("list_effects", {"kind": "transition"})
        self.assertTrue({"crossfade", "flash", "wipe"} <= {e["id"] for e in r["effects"]})
        self.assertEqual(self.tb.dispatch("list_effects", {"max_cost": 1, "text": "bloom"})["count"], 0)
        d = self.tb.dispatch("describe_effect", {"id": "scene_a"})
        self.assertEqual(d["uniforms"]["uI"]["bind"], "energy")

    def test_history_tool(self):
        self.tb.dispatch("edit_show", {"ops": [{"op": "add_track", "id": "x"}]})
        self.assertTrue(self.tb.dispatch("history", {"action": "undo"})["ok"])
        self.assertEqual(self.sess.show["tracks"], [])

    def test_full_toolbox_has_unique_names_and_routes(self):
        from color_matrix_python.tools import ColorToolbox
        V11 = ROOT / "output" / "color-matrix-full-rgb-v11.npz"
        if not V11.exists():
            self.skipTest("нет Color Matrix")
        from color_matrix_python.reader import FullRGBMatrixReader
        color = ColorToolbox(FullRGBMatrixReader(V11))
        ft = FullToolbox(self.tb, color)
        names = [s["function"]["name"] for s in ft.schemas]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("hex", ft.dispatch("describe_color", {"color": "#c08040"}))
        self.assertIn("storyboard", ft.dispatch("show_overview", {}))
        self.assertIn("error", ft.dispatch("ghost", {}))

    def test_build_cozy_asset_tool_and_layout_check(self):
        self.tb.dispatch("edit_show", {"ops": [{"op": "add_track", "id": "main"}]})
        pl = [{"object": "sofa", "x": 0, "z": -1.5}, {"object": "coffee_table", "x": 0, "z": -0.3}, {"object": "plant", "x": 2.0, "z": 1.0}]
        r = self.tb.dispatch("build_cozy_asset", {"name": "room", "placements": pl, "room_size": [5, 4.5], "slot_colors": {"upholstery": "#aa5533"}})
        self.assertTrue(r["ok"] and r["layout_check"]["ok"])
        self.assertEqual(self.sess.show["assets"]["room"]["stride"], 12)
        self.assertEqual(len(self.sess.show["assets"]["room"]["floats"]), r["parts"] * 12)
        bad = check_layout([{"object": "sofa", "x": 0, "z": 0}, {"object": "armchair", "x": 0.3, "z": 0.1}, {"object": "bed", "x": 2.4, "z": 0}], (5, 5))
        self.assertFalse(bad["ok"])
        self.assertTrue(bad["overlaps"] and bad["out_of_room"])
        ok_rug = check_layout([{"object": "rug", "x": 0, "z": 0}, {"object": "sofa", "x": 0, "z": 0}], (6, 6))
        self.assertTrue(ok_rug["ok"])                                                 # ковёр лежит под мебелью
        on_surface = check_layout([{"object": "sofa", "x": 0, "z": 0}, {"object": "cushion", "x": 0, "z": 0, "elevation": 0.5}], (6, 6))
        self.assertTrue(on_surface["ok"])
        with self.assertRaises(ValueError):
            cozy_asset([{"object": "unicorn"}])


# ======================================================================================================================
@unittest.skipUnless(HAVE_GPP, "нет g++")
class TestCppConformance(unittest.TestCase):
    """C++ рантайм (runtime_ref) обязан совпасть с Python: значения uniform'ов, активные клипы, массивы и план проходов."""

    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp())
        r = subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-pedantic", "-Werror", "-o", str(cls.d / "conf"),
                            str(ROOT / "runtime_ref" / "conformance.cpp")], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

    @staticmethod
    def parse(txt):
        out, T = {}, None
        for ln in txt.splitlines():
            if ln.startswith("T "):
                T = ln[2:]; out[T] = {"clips": {}, "other": []}
            elif ln.startswith("clip "):
                p = ln.split()
                out[T]["clips"][p[1]] = {kv.split("=")[0]: [float(x) for x in kv.split("=")[1].split(",")] for kv in p[2:]}
            else:
                out[T]["other"].append(ln.strip())
        return out

    def run_cpp(self, res, cat, show, times):
        segs = plan(res, cat)
        (self.d / "x.smt").write_text(to_smt(bake(res, cat, show, segs)))
        (self.d / "t.txt").write_text("\n".join(repr(t) for t in times) + "\n")
        out = subprocess.run([str(self.d / "conf"), str(self.d / "x.smt"), str(self.d / "t.txt")], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return golden_lines(res, segs, times), out.stdout

    def assert_same(self, py, cpp, tol=1e-9):
        a, b = self.parse(py), self.parse(cpp)
        self.assertEqual(set(a), set(b))
        n = 0
        for T in a:
            self.assertEqual(set(a[T]["clips"]), set(b[T]["clips"]), f"активные клипы в T={T}")
            self.assertEqual(a[T]["other"], b[T]["other"], f"план/массивы в T={T}")
            for cid, vals in a[T]["clips"].items():
                self.assertEqual(set(vals), set(b[T]["clips"][cid]))
                for k, v in vals.items():
                    for x, y in zip(v, b[T]["clips"][cid][k]):
                        n += 1
                        self.assertLessEqual(abs(x - y), tol * max(1.0, abs(x)), (T, cid, k, x, y))
        return n

    def test_fuzz_expressions(self):
        rng = random.Random(777)
        V = sorted(BASE_VARS)
        BIN = ["+", "-", "*", "/", "%", "<", ">", "<=", ">=", "==", "!=", "&&", "||"]

        def num():
            return rng.choice(["0", "1", "2", "0.5", "-1", "100", "1000000", "0.0001", repr(round(rng.uniform(-6, 6), rng.choice([0, 1, 3, 6])))])

        def gen(d):
            if d == 0 or rng.random() < 0.15:
                return rng.choice([num, lambda: rng.choice(V)])()
            r = rng.random()
            if r < 0.12:
                return f"(0-{gen(d - 1)})"
            if r < 0.20:
                return f"(!{gen(d - 1)})"
            if r < 0.60:
                return f"({gen(d - 1)} {rng.choice(BIN)} {gen(d - 1)})"
            f = rng.choice(sorted(FUNCS))
            return f"{f}({', '.join(gen(d - 1) for _ in range(FUNCS[f]))})"
        exprs = [gen(rng.randint(1, 5)) for _ in range(250)]
        cat = EffectCatalog()
        cat.add(effect_from_dict({"id": "fz", "kind": "scene", "uniforms": {f"uX{i}": {"type": "float"} for i in range(len(exprs))}}))
        show = {"format": "scene-manager/1", "meta": {"duration": 50, "seed": 1}, "audio": {"bpm": 123.4, "offset": 0.31}, "tracks": [{"id": "m", "order": 0}],
                "clips": [{"id": "c", "track": "m", "kind": "scene", "effect": "fz", "start": 2, "duration": 45, "map": {f"uX{i}": e for i, e in enumerate(exprs)}}]}
        res = compile_show(show, cat)
        self.assertEqual(res.errors, [])
        res.audio.energy = np.array([abs(math.sin(i / 7)) * 0.9 for i in range(1200)])
        res.audio.sections = [{"start": 10.0}, {"start": 25.5}, {"start": 40.0}]
        times = [0.0, 1.9, 2.0, 2.0001, 12.345, 25.5, 33.3, 46.99, 49.0, 50.0] + [round(rng.uniform(2, 47), 4) for _ in range(30)]
        py, cpp = self.run_cpp(res, cat, show, times)
        self.assertGreater(self.assert_same(py, cpp), 8000)

    def test_long_curve_parity(self):
        rng = random.Random(11)
        keys = [[i * 0.25, round(rng.uniform(0, 1), 3), rng.choice(["linear", "smoothstep", "ease_in", "ease_out", "hold"])] for i in range(400)]
        cat = catalog()
        show = base_show(clips=[clip("a", duration=100, atoms={"energy": {"keys": keys}}, map={"uReq": 1, "uI": "energy * 0.5"})], meta={"duration": 100})
        res = compile_show(show, cat)
        self.assertEqual(res.errors, [])
        times = [round(rng.uniform(0, 100), 4) for _ in range(60)] + [0.0, 0.25, 99.75, 50.0]
        py, cpp = self.run_cpp(res, cat, show, times)
        self.assertGreater(self.assert_same(py, cpp), 200)

    @unittest.skipUnless(EXAMPLE.exists(), "нет examples/out/demo.show.json (запустите examples/build_demo.py)")
    def test_full_example_demo(self):
        cat = EffectCatalog.from_dir(ROOT / "examples" / "effects")
        sess = ShowSession.load(EXAMPLE, cat)
        res = sess.compile(strict=True)
        self.assertEqual(res.errors, [])
        pts = {0.0, res.duration, res.duration - 1e-3}
        for c in res.clips:
            pts |= {c.eff_start, c.eff_end, c.eff_start - 1e-4, c.eff_start + 1e-4, c.eff_end - 1e-4, (c.eff_start + c.eff_end) / 2}
        times = sorted(round(t, 6) for t in pts if 0 <= t <= res.duration) + [round(random.Random(3).uniform(0, res.duration), 4) for _ in range(40)]
        py, cpp = self.run_cpp(res, cat, sess.show, times)
        n = self.assert_same(py, cpp)
        self.assertGreater(n, 1000)
        self.assertIn("arr room uPrimitives", py)                                      # массив Cozy Engine прошёл через запекание


if __name__ == "__main__":
    unittest.main()
