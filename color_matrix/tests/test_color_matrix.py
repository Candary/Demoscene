"""Запуск:  python -m unittest discover -s tests -v   (из корня проекта). Внешних зависимостей, кроме numpy, нет."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
sys.path.insert(0, str(OUT))

from color_matrix_python import colorspace as cs  # noqa: E402
from color_matrix_python.agent import run_agent  # noqa: E402
from color_matrix_python.reader import FullRGBMatrixReader  # noqa: E402
from color_matrix_python.search import SearchIndex  # noqa: E402
from color_matrix_python.tools import TOOL_SCHEMAS, ColorToolbox  # noqa: E402

V10 = OUT / "color-matrix-full-rgb-v10.npz"
V11 = OUT / "color-matrix-full-rgb-v11.npz"


class TestColorspace(unittest.TestCase):
    def test_known_oklch_red(self):
        L, C, h = cs.rgb_to_oklch((255, 0, 0))
        self.assertAlmostEqual(L, 0.628, delta=0.002)
        self.assertAlmostEqual(C, 0.2577, delta=0.002)
        self.assertAlmostEqual(h, 29.23, delta=0.3)

    def test_oklch_roundtrip(self):
        for rgb in [(37, 99, 235), (250, 220, 60), (10, 10, 10), (200, 190, 180), (0, 255, 0)]:
            L, C, h = cs.lab_to_lch(cs.rgb_to_oklab(np.array(rgb, dtype=float)))
            back = cs.oklch_to_rgb(float(L), float(C), float(h))
            self.assertTrue(all(abs(a - b) <= 1 for a, b in zip(rgb, back)), (rgb, back))

    def test_gamut_mapping_keeps_hue_and_lightness(self):
        rgb = cs.oklch_to_rgb(0.7, 0.4, 150)  # заведомо вне sRGB
        L, C, h = cs.lab_to_lch(cs.rgb_to_oklab(np.array(rgb, dtype=float)))
        self.assertAlmostEqual(float(L), 0.7, delta=0.02)
        self.assertLess(abs(float(h) - 150), 3)

    def test_wcag(self):
        self.assertAlmostEqual(float(cs.contrast_ratio((0, 0, 0), (255, 255, 255))), 21.0, places=2)
        self.assertAlmostEqual(float(cs.contrast_ratio((119, 119, 119), (255, 255, 255))), 4.48, delta=0.02)

    def test_fix_contrast(self):
        fixed = cs.fix_contrast((156, 163, 175), (255, 255, 255), 4.5)
        self.assertIsNotNone(fixed)
        self.assertGreaterEqual(float(cs.contrast_ratio(fixed, (255, 255, 255))), 4.5)

    def test_parse_color(self):
        self.assertEqual(cs.parse_color("#2563eb"), (37, 99, 235))
        self.assertEqual(cs.parse_color("26e"), (34, 102, 238))
        self.assertEqual(cs.parse_color([1, 2, 3]), (1, 2, 3))
        for bad in ["blue", "#12345", [256, 0, 0], [1, 2]]:
            with self.assertRaises(ValueError):
                cs.parse_color(bad)

    def test_cvd_keeps_white_and_collapses_red_green(self):
        for kind in cs.CVD_MATRICES:
            self.assertTrue(np.allclose(cs.simulate_cvd([255, 255, 255], kind), 255, atol=1.5), kind)
        lab = cs.rgb_to_oklab(cs.simulate_cvd(np.array([[255, 0, 0], [0, 170, 0]]), "deutan"))
        self.assertLess(float(cs.delta_e_ok(lab[0], lab[1])), 0.06)


@unittest.skipUnless(V11.exists(), "нет color-matrix-full-rgb-v11.npz (запусти scripts/build_v11.py)")
class TestReader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = FullRGBMatrixReader(V11)

    def test_documented_control_colors(self):
        c = self.r.get_cell((255, 0, 0))
        self.assertEqual((c.empathy.label, c.empathy.score, c.entropy.score), ("anxiety", -82.0, 58.0))
        self.assertEqual(self.r.get_cell((37, 99, 235)).empathy.score, 22.0)
        self.assertEqual(self.r.get_cell((255, 190, 150)).empathy.label, "delight")

    def test_version_detected(self):
        self.assertEqual(self.r.dataset_version, "prior-v11")

    def test_grays_are_not_hot(self):
        for v in range(256):
            t = self.r.get_cell((v, v, v)).synesthesia_tags[0]
            self.assertEqual(t["word"], "neutral", v)

    def test_saturated_temperature_unchanged(self):
        self.assertEqual(self.r.get_cell((255, 0, 0)).synesthesia_tags[0]["word"], "hot")
        self.assertEqual(self.r.get_cell((0, 200, 255)).synesthesia_tags[0]["word"], "cold")

    def test_entropy_label_styles(self):
        self.assertEqual(self.r.get_cell((128, 128, 128)).entropy.label, "very_low")
        legacy = FullRGBMatrixReader(V11, entropy_labels="legacy")
        self.assertEqual(legacy.get_cell((128, 128, 128)).entropy.label, "very_dark")
        self.assertEqual(self.r.get_cell((128, 128, 128)).entropy.legacy_label, "very_dark")

    def test_unverified_words_are_not_invented(self):
        tags = {t["dimension"]: t for t in self.r.get_cell((255, 0, 0)).synesthesia_tags}
        self.assertIsNone(tags["texture"]["word"])
        self.assertIsNone(tags["spatial_depth"]["word"])
        self.assertEqual(tags["texture"]["word_status"], "unverified")

    def test_get_many_matches_get_cell(self):
        pts = np.array([[255, 0, 0], [12, 200, 99], [0, 0, 0]])
        m = self.r.get_many(pts)
        for k, p in enumerate(pts):
            c = self.r.get_cell(tuple(p))
            self.assertEqual(float(m["empathy_score"][k]), c.empathy.score)
            self.assertEqual(int(m["synesthesia"][k][0]), c.synesthesia_tags[0]["value"])

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            self.r.get_cell((256, 0, 0))

    @unittest.skipUnless(V10.exists(), "нет v10 для сравнения")
    def test_v11_differs_from_v10_only_in_low_chroma_temperature(self):
        a, b = np.load(V10), np.load(V11)
        for k in ["empathy_score", "empathy_label", "entropy_score", "entropy_label"]:
            self.assertTrue(np.array_equal(a[k], b[k]), k)
        rng = np.random.default_rng(0)
        idx = rng.choice(1 << 24, 200_000, replace=False)
        rgb = np.stack([(idx >> 16) & 255, (idx >> 8) & 255, idx & 255], axis=-1)
        C = cs.lab_to_lch(cs.rgb_to_oklab(rgb))[:, 1]
        same = np.array_equal(a["synesthesia_packed"][idx][C >= 0.03], b["synesthesia_packed"][idx][C >= 0.03])
        self.assertTrue(same)
        # старое поведение действительно было багом: все серые 'hot'
        ra = FullRGBMatrixReader(V10)
        self.assertEqual(ra.get_cell((128, 128, 128)).synesthesia_tags[0]["word"], "hot")


@unittest.skipUnless(V11.exists(), "нет v11")
class TestSearchAndTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tb = ColorToolbox(FullRGBMatrixReader(V11))

    def test_find_respects_constraints(self):
        res = self.tb.dispatch("find_colors", {"feel": "warmth", "background": "#0f172a", "min_contrast": 7,
                                               "temperature": ["warm_side"], "count": 6})
        self.assertGreater(len(res["candidates"]), 0)
        for c in res["candidates"]:
            self.assertEqual(c["empathy"]["label"], "warmth")
            self.assertGreaterEqual(c["contrast_vs_background"], 7)
            self.assertIn(c["temperature"], ("warm", "hot"))

    def test_find_is_deterministic_and_diverse(self):
        args = {"feel": "tension", "count": 5, "min_delta_e": 0.08}
        a, b = self.tb.dispatch("find_colors", args), self.tb.dispatch("find_colors", args)
        self.assertEqual(a["candidates"], b["candidates"])
        labs = cs.rgb_to_oklab(np.array([c["rgb"] for c in a["candidates"]], dtype=float))
        for i in range(len(labs)):
            for j in range(i):
                self.assertGreaterEqual(float(cs.delta_e_ok(labs[i], labs[j])), 0.075)

    def test_impossible_query_returns_diagnostics(self):
        res = self.tb.dispatch("find_colors", {"feel": "anxiety", "background": "#ffffff", "min_contrast": 21})
        self.assertEqual(res["n_matches"], 0)
        self.assertEqual(res["diagnostics"][-1]["remaining"], 0)
        self.assertIn("hint", res)

    def test_delight_target_avoids_plateau(self):
        res = self.tb.dispatch("find_colors", {"feel": "delight", "count": 8})
        self.assertTrue(all(c["empathy"]["score"] < 100 for c in res["candidates"][:3]))

    def test_check_palette_flags_red_green_for_deutan(self):
        res = self.tb.dispatch("check_palette", {"colors": ["#ff0000", "#00aa00"]})
        self.assertFalse(res["ok"])
        self.assertTrue(res["distinguishability"]["deutan"]["too_similar_pairs"])

    def test_check_contrast_suggests_fix(self):
        res = self.tb.dispatch("check_contrast", {"foreground": "#9ca3af", "background": "#ffffff"})
        self.assertFalse(res["passes"]["AA_normal_text"])
        self.assertGreaterEqual(res["suggested_ratio"], 4.5)

    def test_build_palette_is_valid(self):
        for scheme in ["analogous", "complementary", "triadic", "split_complementary", "tonal"]:
            res = self.tb.dispatch("build_palette", {"base": "#2563eb", "scheme": scheme, "size": 5})
            self.assertEqual(len(res["colors"]), 5, scheme)

    def test_errors_are_returned_not_raised(self):
        for name, args in [("nope", {}), ("describe_color", {"color": "blue"}), ("find_colors", {"min_contrast": 4.5}),
                           ("find_colors", {"feel": "joy"}), ("describe_color", "{broken")]:
            self.assertIn("error", self.tb.dispatch(name, args), (name, args))

    def test_schemas_are_valid_json_and_match_tools(self):
        json.dumps(TOOL_SCHEMAS)
        self.assertEqual({t["function"]["name"] for t in TOOL_SCHEMAS}, set(self.tb._tools))


class _FakeClient:
    """Скриптованный клиент: 1-й ответ — вызов инструментов, 2-й — финальный текст."""

    def __init__(self):
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, tools, **kw):
        self.calls += 1
        if self.calls == 1:
            tc = [SimpleNamespace(id="c1", function=SimpleNamespace(name="describe_color", arguments='{"color":"#2563eb"}')),
                  SimpleNamespace(id="c2", function=SimpleNamespace(name="check_contrast",
                                                                    arguments='{"foreground":"#ffffff","background":"#2563eb"}'))]
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=tc))])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="готово", tool_calls=None))])


@unittest.skipUnless(V11.exists(), "нет v11")
class TestAgent(unittest.TestCase):
    def test_loop_executes_tools_and_returns_text(self):
        tb = ColorToolbox(FullRGBMatrixReader(V11))
        out = run_agent(_FakeClient(), "glm", "подбери кнопку", tb, system_prompt="policy")
        self.assertEqual(out["text"], "готово")
        self.assertEqual([t["name"] for t in out["tool_calls"]], ["describe_color", "check_contrast"])
        roles = [m["role"] for m in out["messages"]]
        self.assertEqual(roles, ["system", "user", "assistant", "tool", "tool", "assistant"])
        self.assertEqual(out["messages"][3]["tool_call_id"], "c1")

    def test_default_policy_loads(self):
        from color_matrix_python.agent import load_policy
        text = load_policy()
        self.assertIn("Порядок решений", text)
        for tool in ["describe_color", "find_colors", "check_contrast", "build_palette", "check_palette"]:
            self.assertIn(tool, text)

    def test_step_limit(self):
        class Loop(_FakeClient):
            def _create(self, model, messages, tools, **kw):
                self.calls = 0  # каждый раз снова «первый» ответ = вызов инструментов
                return super()._create(model, messages, tools, **kw)

        tb = ColorToolbox(FullRGBMatrixReader(V11))
        out = run_agent(Loop(), "glm", "x", tb, system_prompt="p", max_steps=2)
        self.assertIn("error", out)


sys.path.insert(0, str(ROOT / "eval"))


class TestEvalHarness(unittest.TestCase):
    """Харнесс должен различать хорошие и плохие ответы, иначе его результаты ничего не значат."""

    def test_reference_solutions_pass_everything(self):
        import run_eval as ev
        results = json.loads((ROOT / "eval" / "reference_solutions.json").read_text(encoding="utf-8"))
        summary = ev.summarize([ev.evaluate(t, results[t["id"]]["text"], results[t["id"]]["tool_calls"]) for t in ev.TASKS])
        self.assertEqual(summary["color_pass_rate"], 1.0, summary["failed"])
        self.assertEqual(summary["tool_behavior_pass_rate"], 1.0, summary["failed"])

    def test_random_baseline_fails_most_color_tasks(self):
        import run_eval as ev
        res = ev.random_baseline(seed=1)
        summary = ev.summarize([ev.evaluate(t, res[t["id"]]["text"], []) for t in ev.TASKS])
        self.assertLess(summary["color_pass_rate"], 0.4)

    def test_tool_use_on_abstain_task_is_flagged(self):
        import run_eval as ev
        t = next(x for x in ev.TASKS if x["id"] == "abstain-sql")
        self.assertFalse(ev.evaluate(t, "SELECT 1", [{"name": "describe_color"}])["tool_pass"])

    def test_parse_answer_takes_last_block(self):
        import run_eval as ev
        text = 'a ```json\n{"colors": {"x": "#000000"}}\n``` b ```json\n{"colors": {"x": "#ffffff"}}\n```'
        self.assertEqual(ev.parse_answer(text), {"x": "#ffffff"})


if __name__ == "__main__":
    unittest.main()
