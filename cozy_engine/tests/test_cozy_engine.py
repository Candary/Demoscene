"""Запуск:  python -m unittest discover -s tests -v   (из корня проекта). Нужен только numpy."""
from __future__ import annotations

import csv
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
sys.path.insert(0, str(OUT))

from color_matrix_python.agent import run_agent  # noqa: E402
from color_matrix_python.reader import FullRGBMatrixReader  # noqa: E402
from color_matrix_python.tools import ColorToolbox  # noqa: E402
from cozy_engine import ingest, primitives, vocab  # noqa: E402
from cozy_engine.colors import ColorLink, extract_phrases  # noqa: E402
from cozy_engine.matrix import CozyMatrix, scan_weights  # noqa: E402
from cozy_engine.parse import parse_text  # noqa: E402
from cozy_engine.scenes import ABSENT, PRESENT, UNKNOWN, SceneStore  # noqa: E402
from cozy_engine.tools import COZY_SCHEMAS, CozyToolbox, UnifiedToolbox  # noqa: E402

V11 = OUT / "color-matrix-full-rgb-v11.npz"
DATA = OUT / "cozy_data"
HAVE_COLOR = V11.exists()
HAVE_DATA = (DATA / "cozy_matrix.npz").exists()


class TestVocab(unittest.TestCase):
    def test_sizes_and_uniqueness(self):
        self.assertEqual(len(vocab.ATOMS), 64)
        self.assertEqual(len(set(vocab.ATOMS)), 64)
        self.assertEqual(len(vocab.RESPONSES), 64)
        self.assertTrue(set(vocab.ALIASES) <= set(vocab.ATOMS))

    def test_label_words_are_not_atoms(self):
        # метки (cozy/inviting/warm/comfortable) не должны быть атомами, иначе матрица «предсказывает слово словом»
        for w in ("cozy", "inviting", "warm", "comfortable", "relaxing"):
            self.assertNotIn(w, vocab.ATOMS)

    def test_old_pipeline_bug_vocab_not_silently_truncated(self):
        # прежний build_dataset.attributes() молча отбрасывал 10 из 74 атомов (в т.ч. 'cozy'); здесь словарь обязан быть ровно 64
        self.assertEqual(sum(len(g) for g in vocab.ATOM_GROUPS.values()), 64)

    def test_rug_and_carpet_floor_are_separate(self):
        self.assertIn("rug", vocab.ATOMS)
        self.assertIn("carpet_floor", vocab.ATOMS)


class TestParser(unittest.TestCase):
    def test_negation(self):
        r = parse_text("The room has no rug and is not cluttered.")["presence"]
        self.assertEqual(r.get("rug"), 0)
        self.assertEqual(r.get("cluttered"), 0)

    def test_warmth_is_not_a_palette(self):
        # прежний парсер: «adding warmth» -> warm_palette
        r = parse_text("The bed adds warmth to the room.")
        self.assertNotIn("warm_palette", r["presence"])
        self.assertEqual(r["responses"]["warm_kw"], 1.0)

    def test_specific_beats_generic(self):
        p = parse_text("A coffee table and a dining table.")["presence"]
        self.assertEqual(p.get("coffee_table"), 1)
        p2 = parse_text("A coffee table in front of the sofa.")["presence"]
        self.assertNotIn("table", p2)

    def test_carpeted_floor_is_not_a_rug(self):
        p = parse_text("A carpeted floor in an office.")["presence"]
        self.assertEqual(p.get("carpet_floor"), 1)
        self.assertNotIn("rug", p)
        self.assertEqual(parse_text("A patterned rug under the bed.")["presence"].get("rug"), 1)

    def test_unmentioned_is_not_listed(self):
        p = parse_text("A wooden desk.")["presence"]
        self.assertNotIn("sofa", p)

    def test_label_leakage_absent_from_atoms(self):
        p = parse_text("A cozy, inviting, warm and comfortable room.")["presence"]
        self.assertEqual(p, {})


class TestSceneStore(unittest.TestCase):
    def _store(self):
        s = SceneStore()
        s.add_from_text("a", "A cozy bedroom with a bed and a blanket.")
        s.add_from_text("b", "An office with a desk and a chair. Not cluttered.")
        return s

    def test_old_bug_all_attributes_active_and_search_broken(self):
        s = self._store()
        g = s.get_scene("a")
        self.assertIn("bed", g["present"])
        self.assertLess(len(g["present"]), 10)            # у прежнего хранилища было 64
        self.assertEqual(s.find(has=["sofa"]), [])        # у прежнего вернулись обе сцены
        self.assertEqual({h["scene_id"] for h in s.find(has=["bed"])}, {"a"})
        self.assertEqual({h["scene_id"] for h in s.find(not_has=["bed"])}, {"b"})

    def test_three_state_presence(self):
        s = self._store()
        i = s._idx["b"]
        self.assertEqual(s.presence[i, vocab.ATOM_INDEX["desk"]], PRESENT)
        self.assertEqual(s.presence[i, vocab.ATOM_INDEX["cluttered"]], ABSENT)
        self.assertEqual(s.presence[i, vocab.ATOM_INDEX["sofa"]], UNKNOWN)
        self.assertEqual({h["scene_id"] for h in s.find(not_has=["cluttered"], strict_absent=True)}, {"b"})

    def test_responses_do_not_overwrite_atoms(self):
        s = self._store()
        i = s._idx["a"]
        before = s.presence[i].copy()
        s.set_responses("a", {"cozy_human": 0.9})
        self.assertTrue(np.array_equal(before, s.presence[i]))

    def test_duplicate_and_unknown(self):
        s = self._store()
        with self.assertRaises(ValueError):
            s.add_from_text("a", "again")
        s.add_scene("c", {"unicorn": 1, "bed": 1}, {"nonexistent": 1.0, "cozy_kw": 1.0})
        self.assertEqual(s.meta["c"]["ignored_atoms"], ["unicorn"])
        self.assertEqual(s.meta["c"]["ignored_responses"], ["nonexistent"])
        with self.assertRaises(ValueError):
            s.add_scene("d", {"bed": 2})

    def test_save_load_roundtrip(self):
        s = self._store()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.npz"
            s.save(p)
            s2 = SceneStore.load(p)
            self.assertEqual(s2.scene_ids, s.scene_ids)
            self.assertEqual(s2.meta["a"]["prompt"], s.meta["a"]["prompt"])
            self.assertTrue(np.array_equal(s2.presence[:2], s.presence[:2]))
            self.assertEqual(s2._idx, s._idx)

    def test_scales_beyond_64_scenes_fast(self):
        s = SceneStore()
        t = time.time()
        for i in range(6000):
            s.add_scene(f"s{i}", {"bed": 1}, {"cozy_kw": float(i % 2)})
        self.assertEqual(len(s), 6000)
        self.assertLess(time.time() - t, 20)   # O(n^2)-поиск индекса на 132 тыс. сцен не укладывался бы в разумное время
        self.assertEqual(s.get_scene("s5999")["responses"]["cozy_kw"], 1.0)


def _synthetic_store():
    """Игрушечный корпус с известной структурой: в гостиных диван повышает долю cozy_kw, в офисах доля мала."""
    rng = np.random.default_rng(0)
    s = SceneStore()
    for scan in range(40):
        room = "living_room" if scan % 2 == 0 else "office"
        for f in range(10):
            has_sofa = rng.random() < 0.5
            p_cozy = (0.7 if has_sofa else 0.2) if room == "living_room" else 0.03
            pres = {room: 1}
            if has_sofa:
                pres["sofa"] = 1
            s.add_scene(f"scan{scan:03d}/{f}", pres, {"cozy_kw": float(rng.random() < p_cozy)}, meta={"scan_id": f"scan{scan:03d}"})
    return s


class TestMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = _synthetic_store()
        cls.m = CozyMatrix().rebuild(cls.s)

    def test_rebuild_equals_incremental(self):
        m2 = CozyMatrix()
        w = scan_weights(self.s)
        for i in range(len(self.s)):
            m2.update(self.s.presence[i], self.s.responses[i], self.s.rmask[i], float(w[i]))
        self.assertTrue(np.allclose(m2.S, self.m.S))
        self.assertTrue(np.allclose(m2.NW, self.m.NW))

    def test_scan_weighting_counts_rooms_not_frames(self):
        c = self.m.cell("living_room", "living_room", "cozy_kw")
        self.assertEqual(c["n_frames"], 200)
        self.assertAlmostEqual(c["n_eff_scans"], 20.0, places=3)

    def test_within_room_lift_recovers_planted_effect(self):
        top = self.m.lifts_within("living_room", "cozy_kw", group="object", min_support=3)
        self.assertEqual(top[0]["a"], "sofa")
        self.assertGreater(top[0]["lift_within_context"], 0.1)

    def test_shrinkage_protects_tiny_support(self):
        s = SceneStore()
        for i in range(30):
            s.add_scene(f"x{i}", {"bed": 1}, {"cozy_kw": 0.0}, meta={"scan_id": f"sc{i}"})
        s.add_scene("lone", {"candle": 1, "bed": 1}, {"cozy_kw": 1.0}, meta={"scan_id": "solo"})
        m = CozyMatrix().rebuild(s)
        c = m.cell("candle", "candle", "cozy_kw")
        self.assertEqual(c["mean"], 1.0)
        self.assertLess(c["estimate"], 0.3)          # 1 сцена не даёт «100% уюта»
        self.assertEqual(m.partners("bed", "cozy_kw", min_support=3), [])

    def test_save_load(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.npz"
            self.m.info = {"x": 1}
            self.m.save(p)
            m2 = CozyMatrix.load(p)
            self.assertTrue(np.allclose(m2.SW, self.m.SW))
            self.assertEqual(m2.info["x"], 1)
            self.assertEqual(m2.info["vocab_version"], vocab.VOCAB_VERSION)


@unittest.skipUnless(HAVE_COLOR, "нет color-matrix-full-rgb-v11.npz")
class TestColors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.link = ColorLink(FullRGBMatrixReader(V11))

    def test_extract(self):
        ph = [p for p, _ in extract_phrases("A dark blue blanket and a beige carpet; wooden desk; light brown chair; dark blue again")]
        self.assertEqual(ph, ["dark blue", "beige", "light brown"])

    def test_modifiers_move_lightness(self):
        self.assertLess(self.link.profile("dark blue").L, self.link.profile("blue").L)
        self.assertGreater(self.link.profile("light blue").L, self.link.profile("blue").L)

    def test_features_ranges_and_unknown(self):
        f, ph = self.link.features("A beige carpet, a dark blue blanket and red cushions.")
        self.assertEqual(len(ph), 3)
        for name, v in f.items():
            self.assertTrue(0.0 <= v <= 3.0, (name, v))
        for name in ("color_empathy_mean", "color_intensity_mean", "color_chroma_mean", "color_warm_fraction"):
            self.assertTrue(0.0 <= f[name] <= 1.0, name)
        f0, ph0 = self.link.features("A wooden desk by the wall.")
        self.assertEqual((f0, ph0), ({}, []))    # цветов нет -> значения НЕИЗВЕСТНЫ, не нули

    def test_ingest_marks_color_source_and_leaves_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            p.write_text(json.dumps({"scene0001_00/color/1.jpg": "A cozy room with a beige carpet and a sofa.",
                                     "scene0001_00/color/2.jpg": "A plain office with a desk."}), encoding="utf-8")
            s = SceneStore()
            rep = ingest.ingest_captions(p, s, self.link, progress_every=0)
            self.assertEqual(rep, {"ingested": 2, "scans": 1})
            j = vocab.RESPONSE_INDEX["color_n_colors"]
            self.assertEqual(int(s.rmask[0, j]), 1)
            self.assertEqual(int(s.rmask[1, j]), 0)
            self.assertEqual(s.meta["scene0001_00/1"]["label_source"]["color"], "color_matrix_prior")
            self.assertEqual(s.meta["__corpus__"]["color_matrix_version"], "prior-v11")

    def test_split_path(self):
        self.assertEqual(ingest.split_path("scene0385_02/color/1020.jpg"), ("scene0385_02", "1020"))


class TestSurveySample(unittest.TestCase):
    def test_one_frame_per_scan_deterministic_and_caption_free(self):
        s = SceneStore()
        rng = np.random.default_rng(1)
        for scan in range(30):
            room = ["living_room", "office"][scan % 2]
            for f in range(8):
                s.add_scene(f"scan{scan:03d}/{f}", {room: 1}, {"cozy_kw": float(rng.random() < 0.4)},
                            meta={"scan_id": f"scan{scan:03d}", "image_path": f"scan{scan:03d}/color/{f}.jpg", "prompt": "SECRET"})
        a, b = ingest.survey_sample(s, n=20, seed=3), ingest.survey_sample(s, n=20, seed=3)
        self.assertEqual(a, b)
        self.assertLessEqual(len(a), 20)
        self.assertEqual(len({r["scan_id"] for r in a}), len(a))      # не более одного кадра на скан
        self.assertTrue(all("prompt" not in r and "SECRET" not in json.dumps(r) for r in a))
        self.assertTrue({r["room"] for r in a} <= {"living_room", "office"})


class TestRatings(unittest.TestCase):
    def _csv(self, rows):
        d = tempfile.mkdtemp()
        p = Path(d) / "r.csv"
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["scene_id", "rater_id", "item", "value", "scale_min", "scale_max", "probe"])
            w.writerows(rows)
        return p

    def test_validation_and_normalisation(self):
        s = SceneStore()
        s.add_from_text("a", "A bedroom.")
        rows = [("a", "r1", "cozy", 7, 0, 7, ""), ("a", "r2", "cozy", 9, 0, 7, ""), ("zzz", "r3", "cozy", 3, 0, 7, ""),
                ("a", "r4", "funky", 3, 0, 7, ""), ("a", "r5", "cozy", 3.5, 0, 7, "")]
        rep = ingest.ingest_ratings(s, self._csv(rows))
        self.assertEqual((rep["rows_added"], rep["rows_rejected"]), (2, 3))
        self.assertAlmostEqual(float(s.rt_value[1]), 0.5)

    def test_failed_probe_excludes_rater_and_min_raters(self):
        s = SceneStore()
        s.add_from_text("a", "A bedroom.")
        rows = [("a", f"r{i}", "cozy", 6, 0, 7, "") for i in range(5)] + [("a", "bad", "cozy", 0, 0, 7, ""), ("a", "bad", "cozy", 0, 0, 7, 0)]
        ingest.ingest_ratings(s, self._csv(rows))
        self.assertEqual(s.recompute_human(min_raters=5)["raters_excluded"], 1)
        j = vocab.RESPONSE_INDEX["cozy_human"]
        self.assertAlmostEqual(float(s.responses[0, j]), 6 / 7, places=5)   # плохой оценщик не повлиял
        self.assertEqual(s.recompute_human(min_raters=6)["scenes_below_min_raters"], 1)
        self.assertEqual(int(s.rmask[0, j]), 0)


class TestPrimitives(unittest.TestCase):
    def test_recipes_consistent(self):
        self.assertEqual(primitives.validate_recipes(), [])

    def test_every_object_has_recipe(self):
        self.assertEqual(set(primitives.atoms_with_recipes()), set(vocab.OBJECTS))

    def test_known_sizes(self):
        self.assertEqual(primitives.RECIPES["sofa"].size, (2.0, 0.85, 0.9))
        self.assertEqual(primitives.RECIPES["bed"].size, (1.6, 1.1, 2.1))

    def test_instantiate_rotation_scale_elevation(self):
        parts = primitives.instantiate("ottoman", x=1.0, z=2.0, rotation_y_deg=90, scale=2.0, colors={"upholstery": "#aa5533"})
        top = next(p for p in parts if p["part"] == "top")
        self.assertEqual(top["color"], "#aa5533")
        self.assertEqual(top["size"], [1.0, 0.6, 1.0])
        self.assertEqual(top["pos"], [1.0, 0.5, 2.0])
        leg = next(p for p in parts if p["part"] == "leg3")     # локально (+0.2, ., +0.2) * 2 -> после поворота на 90°
        self.assertAlmostEqual(leg["pos"][0], 1.0 + 0.4, places=3)
        self.assertAlmostEqual(leg["pos"][2], 2.0 - 0.4, places=3)
        lamp = primitives.instantiate("lamp_table", elevation=0.75)
        self.assertAlmostEqual(min(p["pos"][1] - p["size"][1] / 2 for p in lamp), 0.75, places=3)
        picture = primitives.instantiate("artwork")
        self.assertAlmostEqual(min(p["pos"][1] - p["size"][1] / 2 for p in picture), 1.4, places=3)


@unittest.skipUnless(HAVE_COLOR and HAVE_DATA, "нет собранных данных (python -m cozy_engine.cli build ...)")
class TestToolbox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ct = ColorToolbox(FullRGBMatrixReader(V11))
        cls.cz = CozyToolbox.from_dir(DATA, cls.ct)
        cls.ub = UnifiedToolbox(cls.ct, cls.cz)

    def test_schemas(self):
        json.dumps(self.ub.schemas)
        self.assertEqual(len({s["function"]["name"] for s in self.ub.schemas}), len(self.ub.schemas))
        self.assertEqual({s["function"]["name"] for s in COZY_SCHEMAS}, set(self.cz._tools))

    def test_plan_structure_and_honesty(self):
        r = self.ub.dispatch("cozy_scene_plan", {"room": "living_room", "count": 6})
        self.assertNotIn("error", r)
        self.assertEqual(r["label_source"], "caption_keywords")
        self.assertIn("НЕ оценки людей", r["provenance"])
        for o in r["objects"]:
            self.assertTrue(o["recipes"])
            self.assertGreaterEqual(o["n_eff_scans"], 3)
        self.assertTrue({"door", "window"}.isdisjoint({o["object"] for o in r["objects"]}))

    def test_palette_uses_color_matrix_and_respects_hue_design(self):
        r = self.ub.dispatch("cozy_palette", {"room": "bedroom"})
        self.assertNotIn("error", r)
        self.assertEqual(set(r["roles"]), set(primitives.COLOR_MATRIX_ROLES))
        for role, v in r["roles"].items():
            self.assertTrue(v["hex"].startswith("#"))
            self.assertIn(v["empathy_label"], vocab_empathy())
        h = r["roles"]["floor"]["oklch"]["h"]
        self.assertTrue(35 <= h <= 85, h)         # прежний баг: фиолетовый пол
        self.assertEqual(set(r["slot_colors"]) , set(primitives.SLOT_ROLE))

    def test_slot_colors_feed_instantiate(self):
        pal = self.ub.dispatch("cozy_palette", {"room": "living_room"})
        res = self.ub.dispatch("instantiate_object", {"object": "sofa", "x": 1, "z": 2, "colors": pal["slot_colors"]})
        up = next(p for p in res["parts"] if p["slot"] == "upholstery")
        self.assertEqual(up["color"], pal["slot_colors"]["upholstery"])

    def test_errors_returned_not_raised(self):
        for name, args in [("cozy_scene_plan", {"room": "garage"}), ("get_primitives", {"object": "chair2"}),
                           ("cozy_evidence", {"atoms": ["a", "b", "c"]}), ("nope", {}), ("cozy_scene_plan", "{bad")]:
            self.assertIn("error", self.ub.dispatch(name, args), (name, args))

    def test_routing(self):
        self.assertIn("hex", self.ub.dispatch("describe_color", {"color": "#c08040"}))
        self.assertIn("recipes", self.ub.dispatch("get_primitives", {"object": "sofa"}))

    def test_evidence_flags_low_support(self):
        r = self.ub.dispatch("cozy_evidence", {"atoms": ["candle", "fireplace"]})
        self.assertIn("enough_support", r)

    def test_agent_loop_with_unified_toolbox(self):
        class Fake:
            def __init__(self):
                self.n = 0
                self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

            def create(self, model, messages, tools, **kw):
                self.n += 1
                assert any(t["function"]["name"] == "cozy_scene_plan" for t in tools)
                if self.n == 1:
                    tc = [SimpleNamespace(id="1", function=SimpleNamespace(name="cozy_scene_plan", arguments='{"room":"bedroom"}'))]
                    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=tc))])
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="готово", tool_calls=None))])

        out = run_agent(Fake(), "glm", "уютная спальня", self.ub, system_prompt="p", tools=self.ub.schemas)
        self.assertEqual(out["text"], "готово")
        self.assertNotIn("error", out["tool_calls"][0]["result"])


def vocab_empathy():
    return ["anxiety", "tension", "neutral", "warmth", "delight"]


if __name__ == "__main__":
    unittest.main()
