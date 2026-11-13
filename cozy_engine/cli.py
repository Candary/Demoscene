"""CLI Cozy Engine.  Запуск из каталога output/:  python -m cozy_engine.cli <команда> ...

  build     --captions FILE [--limit N]   собрать данные из корпуса подписей (сцены + матрица + отчёты)
  ratings   --csv FILE                    добавить оценки людей и пересчитать human-отклики и матрицу
  info                                    сводка по данным
  survey-sample --n 400                   выборка кадров для настоящего опроса (1 кадр на скан, страты комната x cozy_kw)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # output/ — чтобы нашёлся color_matrix_python

from color_matrix_python.reader import FullRGBMatrixReader  # noqa: E402

from cozy_engine import ingest, vocab  # noqa: E402
from cozy_engine.colors import ColorLink  # noqa: E402
from cozy_engine.matrix import CozyMatrix, scan_weights  # noqa: E402
from cozy_engine.scenes import SceneStore  # noqa: E402

DEFAULT_COLOR = HERE.parent / "color-matrix-full-rgb-v11.npz"
DEFAULT_DATA = HERE.parent / "cozy_data"


def cmd_build(a):
    t0 = time.time()
    link = ColorLink(FullRGBMatrixReader(a.color_matrix))
    store = SceneStore()
    print("Загрузка подписей и разбор...")
    rep = ingest.ingest_captions(a.captions, store, link, limit=a.limit)
    print(rep, f"{time.time() - t0:.0f} c")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    store.save(out / "cozy_scenes.npz")
    m = CozyMatrix(); m.info = {"built_from": ingest.CAPTION_SOURCE, "color_matrix_version": link.color_matrix_version,
                                "label_note": ingest.LABEL_NOTE, "n_scans": rep["scans"]}
    m.rebuild(store); m.save(out / "cozy_matrix.npz")
    reports = {"audit": ingest.audit(store), "holdout": ingest.holdout_report(store), "color_agreement": ingest.color_agreement(store)}
    (out / "audit_and_holdout.json").write_text(json.dumps(reports, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "cozy_color_stats.json").write_text(json.dumps(ingest.color_stats(store, link), ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"holdout": reports["holdout"], "rare_atoms": reports["audit"]["rare_atoms(<0.15%)"]}, ensure_ascii=False, indent=1))
    print(f"Готово за {time.time() - t0:.0f} c -> {out}")


def cmd_ratings(a):
    data = Path(a.data)
    store = SceneStore.load(data / "cozy_scenes.npz")
    rep = ingest.ingest_ratings(store, a.csv)
    rep["recompute"] = store.recompute_human(min_raters=a.min_raters)
    store.save(data / "cozy_scenes.npz")
    m = CozyMatrix.load(data / "cozy_matrix.npz"); m.rebuild(store); m.save(data / "cozy_matrix.npz")
    print(json.dumps(rep, ensure_ascii=False, indent=1))


def cmd_survey_sample(a):
    import csv
    store = SceneStore.load(Path(a.data) / "cozy_scenes.npz")
    rows = ingest.survey_sample(store, n=a.n, seed=a.seed)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scene_id", "image_path", "scan_id", "room", "cozy_kw"])
        w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} кадров -> {a.out} (подписи оценщикам не показывать)")


def cmd_info(a):
    data = Path(a.data)
    store = SceneStore.load(data / "cozy_scenes.npz")
    m = CozyMatrix.load(data / "cozy_matrix.npz")
    print(json.dumps({"scenes": store.stats(), "matrix": {"n_scenes": m.n_scenes, **m.info}}, ensure_ascii=False, indent=1))


def main(argv=None):
    p = argparse.ArgumentParser(prog="cozy_engine")
    s = p.add_subparsers(dest="cmd", required=True)
    b = s.add_parser("build"); b.add_argument("--captions", required=True); b.add_argument("--limit", type=int)
    b.add_argument("--out", default=str(DEFAULT_DATA)); b.add_argument("--color-matrix", default=str(DEFAULT_COLOR))
    r = s.add_parser("ratings"); r.add_argument("--csv", required=True); r.add_argument("--data", default=str(DEFAULT_DATA))
    r.add_argument("--min-raters", type=int, default=5)
    i = s.add_parser("info"); i.add_argument("--data", default=str(DEFAULT_DATA))
    q = s.add_parser("survey-sample"); q.add_argument("--n", type=int, default=400); q.add_argument("--seed", type=int, default=0)
    q.add_argument("--data", default=str(DEFAULT_DATA)); q.add_argument("--out", default="survey_sample.csv")
    a = p.parse_args(argv)
    {"build": cmd_build, "ratings": cmd_ratings, "info": cmd_info, "survey-sample": cmd_survey_sample}[a.cmd](a)


if __name__ == "__main__":
    main()
