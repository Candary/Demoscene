"""Загрузка данных в Cozy Engine.

1. ingest_captions   — корпус scannet-captions-gpt4o (подписи GPT-4o к кадрам ScanNet) -> SceneStore.
   Берутся ВСЕ подписи, а не только «cozy»: фильтр по слову cozy лишает матрицу контраста (нечему сравнивать).
2. audit             — частоты атомов (мёртвые атомы словаря видны сразу).
3. color_stats       — какие названия цветов чаще встречаются в «уютных» подписях (с профилем из Color Matrix).
4. holdout_report    — проверка с разбиением ПО СКАНАМ (кадры одной комнаты не должны попасть и в train, и в test).
5. ingest_ratings    — настоящие оценки людей (CSV long-form) с проверкой и нормировкой шкалы.
"""
from __future__ import annotations

import csv
import json
import re
import zlib
from pathlib import Path
from typing import Any

import numpy as np

from . import vocab
from .colors import ColorLink
from .parse import parse_text
from .scenes import PRESENT, SceneStore

CAPTION_SOURCE = "scannet-captions-gpt4o"
LABEL_NOTE = ("cozy_kw и другие *_kw — слова в подписи, сгенерированной GPT-4o; это НЕ оценки людей и не survey. "
              "Матрица на них описывает, как GPT-4o говорит об интерьерах, а не как их воспринимают люди.")

_PATH = re.compile(r"^(?P<scan>scene\d{4}_\d{2})/color/(?P<frame>[^/]+?)(?:\.\w+)?$")


def load_captions(path: str | Path) -> dict[str, str]:
    raw = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))  # висячие запятые (были в исходном файле у прежнего пайплайна)
    if not isinstance(data, dict):
        raise ValueError("ожидался JSON-объект {путь_к_кадру: подпись}")
    return {str(k): str(v) for k, v in data.items()}


def split_path(image_path: str) -> tuple[str, str]:
    m = _PATH.match(image_path)
    if m:
        return m["scan"], m["frame"]
    parts = image_path.rsplit("/", 1)
    return (parts[0] if len(parts) == 2 else "unknown"), Path(image_path).stem


def ingest_captions(path: str | Path, store: SceneStore, color_link: ColorLink | None = None, limit: int | None = None,
                    progress_every: int = 10000, log=print) -> dict[str, Any]:
    caps = load_captions(path)
    n = 0
    for image_path, caption in caps.items():
        scan, frame = split_path(image_path)
        sid = f"{scan}/{frame}"
        if sid in store._idx:
            continue
        parsed = parse_text(caption)
        responses = dict(parsed["responses"])
        label_source = dict(parsed["label_source"])
        phrases: list[str] = []
        if color_link is not None:
            cf, phrases = color_link.features(caption)
            responses.update(cf)
            if cf:
                label_source["color"] = vocab.RESPONSE_SOURCE["color"]
        store.add_scene(sid, parsed["presence"], responses,
                        meta={"prompt": caption.strip(), "image_path": image_path, "scan_id": scan, "frame": frame,
                              "source": CAPTION_SOURCE, "license": "см. условия ScanNet и набора подписей", "colors": "|".join(phrases)},
                        label_source=label_source)
        n += 1
        if progress_every and n % progress_every == 0:
            log(f"  {n} сцен...")
        if limit and n >= limit:
            break
    store.meta["__corpus__"] = {"source": CAPTION_SOURCE, "label_note": LABEL_NOTE, "n_ingested": n,
                                "color_matrix_version": color_link.color_matrix_version if color_link else None}
    return {"ingested": n, "scans": len({m.get("scan_id") for k, m in store.meta.items() if k != "__corpus__"})}


# --- аудит и статистика --------------------------------------------------------------------------------------------------
def audit(store: SceneStore) -> dict[str, Any]:
    n = len(store)
    P = store.presence[:n]
    present = (P == PRESENT).sum(0)
    absent = (P == 0).sum(0)
    freq = {a: int(present[i]) for i, a in enumerate(vocab.ATOMS)}
    dead = [a for a, c in freq.items() if c < 0.0015 * n and not a.startswith("reserved")]
    return {"scenes": n, "atom_frames": freq, "explicit_absent": {a: int(absent[i]) for i, a in enumerate(vocab.ATOMS) if absent[i]},
            "rare_atoms(<0.15%)": dead, "frames_with_no_atoms": int(((P == PRESENT).sum(1) == 0).sum())}


def color_stats(store: SceneStore, color_link: ColorLink, min_n: int = 100) -> dict[str, Any]:
    """Для каждой цветовой фразы: сколько кадров, доля кадров с cozy_kw, lift к общей доле; + профиль из Color Matrix.
    Дополнительно по комнатам (living_room, bedroom, office): лучше сравнивать внутри комнаты, а не с общим фоном."""
    n = len(store)
    kw = vocab.RESPONSE_INDEX["cozy_kw"]
    cozy = (store.rmask[:n, kw] == 1) & (store.responses[:n, kw] > 0.5)
    base = float(cozy.mean())
    sids = store.scene_ids[:n]
    phrase_lists = [store.meta[s].get("colors", "").split("|") if store.meta[s].get("colors") else [] for s in sids]
    rooms = {r: (store.presence[:n, vocab.ATOM_INDEX[r]] == PRESENT) for r in ("living_room", "bedroom", "office", "kitchen", "bathroom")}
    from collections import Counter
    cnt, cnt_c = Counter(), Counter()
    room_cnt = {r: Counter() for r in rooms}; room_cnt_c = {r: Counter() for r in rooms}
    for i, ph in enumerate(phrase_lists):
        for p in set(ph):
            cnt[p] += 1
            cnt_c[p] += int(cozy[i])
            for r, mask in rooms.items():
                if mask[i]:
                    room_cnt[r][p] += 1
                    room_cnt_c[r][p] += int(cozy[i])
    out: dict[str, Any] = {"baseline_p_cozy_kw": round(base, 4), "label_note": LABEL_NOTE,
                           "color_matrix_version": color_link.color_matrix_version, "phrases": {}, "by_room": {}}
    for p, c in cnt.items():
        if c < min_n:
            continue
        prof = color_link.profile(p)
        pc = cnt_c[p] / c
        out["phrases"][p] = {"hex": prof.hex, "n_frames": c, "p_cozy_kw": round(pc, 4), "lift": round(pc / base, 3),
                             "color_matrix": {"empathy": prof.empathy, "empathy_label": prof.empathy_label,
                                              "intensity": prof.intensity, "temperature": prof.temperature,
                                              "oklch": [round(prof.L, 3), round(prof.C, 3), round(prof.h, 1)]}}
    for r in rooms:
        room_base = float(cozy[rooms[r]].mean()) if rooms[r].any() else None
        out["by_room"][r] = {"n_frames": int(rooms[r].sum()), "baseline_p_cozy_kw": round(room_base, 4) if room_base is not None else None, "phrases": {}}
        for p, c in room_cnt[r].items():
            if c >= min_n // 2 and room_base:
                pc = room_cnt_c[r][p] / c
                out["by_room"][r]["phrases"][p] = {"n_frames": c, "p_cozy_kw": round(pc, 4), "lift_in_room": round(pc / room_base, 3)}
    return out


def _auc_np(score: np.ndarray, y: np.ndarray) -> float:
    order = np.argsort(score, kind="mergesort")
    s, yy = score[order], y[order]
    ranks = np.empty(len(s)); i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        ranks[i:j + 1] = (i + j) / 2 + 1
        i = j + 1
    n1, n0 = int(yy.sum()), int((1 - yy).sum())
    return float((ranks[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def scan_fold(scan_id: str, folds: int = 5) -> int:
    return zlib.crc32(str(scan_id).encode()) % folds


def holdout_report(store: SceneStore, folds: int = 5, alpha: float = 1.0) -> dict[str, Any]:
    """Предсказывает cozy_kw по атомам (наивный Байес с log-lift) на ОТЛОЖЕННЫХ СКАНАХ. Это проверка того, что в атомах есть
    сигнал относительно слов GPT-4o, а не доказательство «что вызывает уют». Метки-слова в атомы не входят."""
    n = len(store)
    kw = vocab.RESPONSE_INDEX["cozy_kw"]
    y = ((store.rmask[:n, kw] == 1) & (store.responses[:n, kw] > 0.5)).astype(np.int8)
    scans = [store.meta[s].get("scan_id") for s in store.scene_ids[:n]]
    fold = np.array([scan_fold(s, folds) for s in scans])
    test = fold == 0
    train = ~test
    P = (store.presence[:n] == PRESENT).astype(np.float64)
    live = [i for i, a in enumerate(vocab.ATOMS) if not a.startswith("reserved")]
    rooms = [vocab.ATOM_INDEX[r] for r in vocab.ROOMS]

    def fit(cols):
        yt, Pt = y[train], P[train][:, cols]
        pos = (Pt[yt == 1].sum(0) + alpha) / ((yt == 1).sum() + 2 * alpha)
        neg = (Pt[yt == 0].sum(0) + alpha) / ((yt == 0).sum() + 2 * alpha)
        return np.log(pos / neg) - np.log((1 - pos) / (1 - neg)), np.log((1 - pos) / (1 - neg))

    out: dict[str, Any] = {"n_frames": n, "n_test_frames": int(test.sum()), "n_test_scans": len({s for s, f in zip(scans, fold) if f == 0}),
                           "positive_rate_test": round(float(y[test].mean()), 4), "split": "по сканам (crc32(scan_id) % 5 == 0 -> test)"}
    for name, cols in (("room_only", rooms), ("all_atoms", live)):
        w, w0 = fit(cols)
        score = P[test][:, cols] @ w
        out[f"auc_{name}"] = round(_auc_np(score, y[test]), 4)
    # согласованность prior Color Matrix с метками GPT-4o: AUC одиночных color_* признаков (без обучения)
    col = {}
    for name in vocab.RESPONSE_GROUPS["color"]:
        j = vocab.RESPONSE_INDEX[name]
        m = (store.rmask[:n, j] == 1) & test
        if m.sum() > 500 and 0 < y[m].mean() < 1:
            col[name] = {"auc": round(_auc_np(store.responses[:n, j][m].astype(np.float64), y[m]), 4), "n": int(m.sum())}
    out["single_color_feature_auc_(0.5=no signal)"] = col
    return out


def color_agreement(store: SceneStore, rooms=("living_room", "bedroom", "office", "bathroom")) -> dict[str, Any]:
    """Согласуются ли признаки из Color Matrix (prior) с метками cozy_kw ВНУТРИ типа комнаты (AUC, 0.5 = нет связи)?
    Внутри комнаты, потому что между комнатами цвет и «уют» смешаны (белое/чёрное чаще в офисах)."""
    n = len(store)
    kw = vocab.RESPONSE_INDEX["cozy_kw"]
    y = ((store.rmask[:n, kw] == 1) & (store.responses[:n, kw] > 0.5)).astype(np.int8)
    out: dict[str, Any] = {"note": "AUC ~0.5 = связи нет; метка — слово cozy в подписи GPT-4o; цвета — прототипы названий -> Color Matrix prior"}
    for name in vocab.RESPONSE_GROUPS["color"]:
        j = vocab.RESPONSE_INDEX[name]
        row = {}
        for room in (None,) + tuple(rooms):
            m = store.rmask[:n, j] == 1
            if room:
                m &= store.presence[:n, vocab.ATOM_INDEX[room]] == PRESENT
            if m.sum() > 300 and 0 < y[m].mean() < 1:
                row[room or "all"] = {"auc": round(_auc_np(store.responses[:n, j][m].astype(np.float64), y[m]), 3), "n": int(m.sum())}
        out[name] = row
    return out


def survey_sample(store: SceneStore, n: int = 400, seed: int = 0) -> list[dict[str, Any]]:
    """Выборка кадров для настоящего опроса: не более ОДНОГО кадра на скан (кадры одной комнаты не независимы),
    поровну из страт (тип комнаты x слабая метка cozy_kw), чтобы оценки людей можно было сравнить с метками GPT-4o.
    Подпись раздавать оценщикам НЕЛЬЗЯ (она подскажет ответ); показывается только изображение по image_path."""
    rng = np.random.default_rng(seed)
    N = len(store)
    kw = vocab.RESPONSE_INDEX["cozy_kw"]
    room_cols = [vocab.ATOM_INDEX[r] for r in vocab.ROOMS]
    by_scan: dict[str, list[int]] = {}
    for i, sid in enumerate(store.scene_ids[:N]):
        by_scan.setdefault(store.meta[sid]["scan_id"], []).append(i)
    strata: dict[tuple[str, int], list[int]] = {}
    for scan in sorted(by_scan):
        i = int(rng.choice(by_scan[scan]))
        pres = store.presence[i, room_cols] == PRESENT
        room = vocab.ROOMS[int(np.argmax(pres))] if pres.any() else "other"
        strata.setdefault((room, int(store.responses[i, kw] > 0.5)), []).append(i)
    keys = sorted(k for k, v in strata.items() if v)
    per = max(1, n // max(len(keys), 1))
    out: list[dict[str, Any]] = []
    for k in keys:
        idx = strata[k]
        take = rng.permutation(len(idx))[:per]
        for t in take:
            i = idx[int(t)]
            sid = store.scene_ids[i]
            out.append({"scene_id": sid, "image_path": store.meta[sid]["image_path"], "scan_id": store.meta[sid]["scan_id"],
                        "room": k[0], "cozy_kw": k[1]})
    return out[:n] if len(out) > n else out


# --- настоящие оценки людей -----------------------------------------------------------------------------------------------
RATING_ITEMS = ("cozy", "lively", "spacious", "warm", "valence", "arousal")


def ingest_ratings(store: SceneStore, csv_path: str | Path) -> dict[str, Any]:
    """CSV (long-form), колонки: scene_id, rater_id, item, value, scale_min, scale_max, probe
       probe: пусто — обычная оценка; 1 — контрольная проба пройдена; 0 — провалена (оценщик исключается).
       Строки с ошибками не загружаются, а перечисляются в отчёте."""
    rows, errors = [], []
    with open(csv_path, encoding="utf-8", newline="") as f:
        for ln, r in enumerate(csv.DictReader(f), start=2):
            try:
                sid, rater, item = r["scene_id"].strip(), r["rater_id"].strip(), r["item"].strip().lower()
                if sid not in store._idx:
                    raise ValueError(f"неизвестная сцена {sid!r}")
                if item not in RATING_ITEMS:
                    raise ValueError(f"item {item!r} не из {RATING_ITEMS}")
                lo, hi, v = float(r["scale_min"]), float(r["scale_max"]), float(r["value"])
                if not hi > lo or not lo <= v <= hi:
                    raise ValueError(f"значение {v} вне шкалы [{lo}, {hi}]")
                probe = -1 if (r.get("probe") or "").strip() == "" else int(r["probe"])
                if probe not in (-1, 0, 1):
                    raise ValueError("probe должен быть пустым, 0 или 1")
                rows.append((sid, rater, item, (v - lo) / (hi - lo), probe))
            except (KeyError, ValueError) as exc:
                errors.append({"line": ln, "error": str(exc)})
    added = store.add_rating_rows(rows) if rows else 0
    return {"rows_added": added, "rows_rejected": len(errors), "errors": errors[:20]}
