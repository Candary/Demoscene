"""Хранилище сцен (scene-level). Исправляет архитектуру прежнего CozyStore:

* число сцен не ограничено 64 (агрегированный тензор Cozy Matrix остаётся 64^3 и считается из сцен);
* атрибуты и отклики хранятся в РАЗНЫХ массивах (n x 64), а не в одном тензоре, где запись отклика затирала атрибуты;
* атрибут трёхзначный: 1 есть / 0 явно нет / -1 неизвестно; отклик имеет отдельную маску;
* сырые оценки людей хранятся построчно (кто, что, сколько), человеческие отклики считаются из них, а не пишутся «в тот же слот»;
* запись атомарная (временный файл + replace); allow_pickle не используется.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from . import vocab
from .parse import parse_text

FORMAT_VERSION = "1.0"
UNKNOWN, ABSENT, PRESENT = -1, 0, 1


class SceneStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.scene_ids: list[str] = []
        self._idx: dict[str, int] = {}
        self._cap = 64
        self.presence = np.full((self._cap, 64), UNKNOWN, dtype=np.int8)
        self.responses = np.zeros((self._cap, 64), dtype=np.float32)
        self.rmask = np.zeros((self._cap, 64), dtype=np.uint8)
        self.meta: dict[str, dict[str, Any]] = {}
        # сырые оценки (long form)
        self.rt_scene = np.zeros(0, dtype=np.int32)
        self.rt_rater = np.zeros(0, dtype="U40")
        self.rt_item = np.zeros(0, dtype="U24")
        self.rt_value = np.zeros(0, dtype=np.float32)
        self.rt_probe = np.zeros(0, dtype=np.int8)

    # ---- размеры -----------------------------------------------------------
    def __len__(self) -> int:
        return len(self.scene_ids)

    def _ensure_capacity(self, n: int) -> None:
        if n <= self._cap:
            return
        new = max(n, self._cap * 2)
        pad = new - self._cap
        self.presence = np.vstack([self.presence, np.full((pad, 64), UNKNOWN, dtype=np.int8)])
        self.responses = np.vstack([self.responses, np.zeros((pad, 64), dtype=np.float32)])
        self.rmask = np.vstack([self.rmask, np.zeros((pad, 64), dtype=np.uint8)])
        self._cap = new

    # ---- запись сцен -------------------------------------------------------
    def _index(self, scene_id: str, create: bool, overwrite: bool = False) -> int:
        if scene_id in self._idx:
            if create and not overwrite:
                raise ValueError(f"сцена {scene_id!r} уже существует (overwrite=True, чтобы заменить)")
            return self._idx[scene_id]
        if not create:
            raise KeyError(scene_id)
        i = len(self.scene_ids)
        self._ensure_capacity(i + 1)
        self.scene_ids.append(scene_id)
        self._idx[scene_id] = i
        self.meta[scene_id] = {}
        return i

    def add_scene(self, scene_id: str, presence: dict[str, int] | None = None, responses: dict[str, float] | None = None,
                  meta: dict[str, Any] | None = None, label_source: dict[str, str] | None = None,
                  overwrite: bool = False) -> int:
        i = self._index(scene_id, create=True, overwrite=overwrite)
        self.presence[i, :] = UNKNOWN
        self.responses[i, :] = 0
        self.rmask[i, :] = 0
        unknown_atoms = []
        for name, v in (presence or {}).items():
            if name not in vocab.ATOM_INDEX:
                unknown_atoms.append(name)
                continue
            if v not in (UNKNOWN, ABSENT, PRESENT):
                raise ValueError(f"presence[{name!r}] должен быть 1, 0 или -1, получено {v!r}")
            self.presence[i, vocab.ATOM_INDEX[name]] = int(v)
        unknown_resp = self.set_responses(scene_id, responses or {}, label_source)
        self.meta[scene_id] = {**(meta or {}), "label_source": dict(label_source or {}),
                               "ignored_atoms": sorted(unknown_atoms), "ignored_responses": unknown_resp}
        return i

    def add_from_text(self, scene_id: str, text: str, image_path: str = "", source: str = "", license: str = "",
                      overwrite: bool = False) -> int:
        parsed = parse_text(text)
        return self.add_scene(scene_id, parsed["presence"], parsed["responses"],
                              meta={"prompt": text, "image_path": image_path, "source": source, "license": license},
                              label_source=parsed["label_source"], overwrite=overwrite)

    def set_responses(self, scene_id: str, responses: dict[str, float], label_source: dict[str, str] | None = None) -> list[str]:
        i = self._index(scene_id, create=False)
        ignored = []
        for name, v in responses.items():
            if name not in vocab.RESPONSE_INDEX:
                ignored.append(name)
                continue
            if v is None or (isinstance(v, float) and np.isnan(v)):
                continue
            j = vocab.RESPONSE_INDEX[name]
            self.responses[i, j] = float(v)
            self.rmask[i, j] = 1
        if label_source:
            self.meta[scene_id].setdefault("label_source", {}).update(label_source)
        return sorted(ignored)

    # ---- чтение ------------------------------------------------------------
    def get_scene(self, scene_id: str) -> dict[str, Any]:
        i = self._index(scene_id, create=False)
        return {
            "scene_id": scene_id, "meta": self.meta[scene_id],
            "present": [a for a in vocab.ATOMS if self.presence[i, vocab.ATOM_INDEX[a]] == PRESENT],
            "absent": [a for a in vocab.ATOMS if self.presence[i, vocab.ATOM_INDEX[a]] == ABSENT],
            "n_unknown": int((self.presence[i] == UNKNOWN).sum()),
            "responses": {r: float(self.responses[i, j]) for r, j in vocab.RESPONSE_INDEX.items() if self.rmask[i, j]},
        }

    def find(self, has: Iterable[str] = (), not_has: Iterable[str] = (), min_cozy: float | None = None,
             max_cozy: float | None = None, text: str | None = None, strict_absent: bool = False, limit: int = 20) -> list[dict]:
        """Поиск сцен. has: атом присутствует. not_has: атом не присутствует (strict_absent=True: известно, что отсутствует).
        min/max_cozy относятся к cozy_human (0..1); сцены без человеческих оценок в такой фильтр не попадают."""
        has, not_has = list(has), list(not_has)
        for a in has + not_has:
            if a not in vocab.ATOM_INDEX:
                raise ValueError(f"неизвестный атом {a!r}")
        n = len(self)
        ok = np.ones(n, dtype=bool)
        P = self.presence[:n]
        for a in has:
            ok &= P[:, vocab.ATOM_INDEX[a]] == PRESENT
        for a in not_has:
            col = P[:, vocab.ATOM_INDEX[a]]
            ok &= (col == ABSENT) if strict_absent else (col != PRESENT)
        ch = vocab.RESPONSE_INDEX["cozy_human"]
        if min_cozy is not None:
            ok &= (self.rmask[:n, ch] == 1) & (self.responses[:n, ch] >= min_cozy)
        if max_cozy is not None:
            ok &= (self.rmask[:n, ch] == 1) & (self.responses[:n, ch] <= max_cozy)
        q = text.lower() if text else None
        hits = []
        for i in np.flatnonzero(ok):
            sid = self.scene_ids[int(i)]
            m = self.meta[sid]
            if q and q not in str(m.get("prompt", "")).lower():
                continue
            kw = vocab.RESPONSE_INDEX["cozy_kw"]
            hits.append({
                "scene_id": sid,
                "cozy_human": float(self.responses[i, ch]) if self.rmask[i, ch] else None,
                "cozy_kw_weak": float(self.responses[i, kw]) if self.rmask[i, kw] else None,
                "unknown_among_not_has": [a for a in not_has if P[i, vocab.ATOM_INDEX[a]] == UNKNOWN],
                "prompt": m.get("prompt", ""), "image_path": m.get("image_path", ""), "source": m.get("source", ""),
            })
            if len(hits) >= limit:
                break
        return hits

    def stats(self) -> dict[str, Any]:
        n = len(self)
        ch, kw = vocab.RESPONSE_INDEX["cozy_human"], vocab.RESPONSE_INDEX["cozy_kw"]
        co = vocab.RESPONSE_INDEX["color_empathy_mean"]
        P = self.presence[:n]
        return {
            "path": str(self.path) if self.path else None, "scenes": n,
            "with_human_ratings": int(self.rmask[:n, ch].sum()), "with_weak_keywords": int(self.rmask[:n, kw].sum()),
            "with_color_profile": int(self.rmask[:n, co].sum()), "raw_rating_rows": int(len(self.rt_scene)),
            "mean_known_atoms_per_scene": round(float((P != UNKNOWN).sum(1).mean()), 2) if n else 0.0,
        }

    # ---- сырые оценки ------------------------------------------------------
    def add_rating_rows(self, rows: list[tuple[str, str, str, float, int]]) -> int:
        """rows: (scene_id, rater_id, item, value_normalized_0_1, probe 1/0/-1). Неизвестные сцены отклоняются."""
        idx, rater, item, val, probe = [], [], [], [], []
        for sid, rid, it, v, p in rows:
            if sid not in self._idx:
                raise KeyError(f"оценка для неизвестной сцены {sid!r}")
            idx.append(self._idx[sid]); rater.append(str(rid)); item.append(str(it)); val.append(float(v)); probe.append(int(p))
        self.rt_scene = np.concatenate([self.rt_scene, np.array(idx, dtype=np.int32)])
        self.rt_rater = np.concatenate([self.rt_rater, np.array(rater, dtype="U40")])
        self.rt_item = np.concatenate([self.rt_item, np.array(item, dtype="U24")])
        self.rt_value = np.concatenate([self.rt_value, np.array(val, dtype=np.float32)])
        self.rt_probe = np.concatenate([self.rt_probe, np.array(probe, dtype=np.int8)])
        return len(rows)

    def recompute_human(self, min_raters: int = 5) -> dict[str, int]:
        """Пересчитывает human-отклики сцен из сырых оценок. Оценщики, провалившие хотя бы одну контрольную пробу, исключаются.
        Сцена получает отклики только при >= min_raters валидных оценщиков."""
        items = {"cozy": "cozy_human", "lively": "lively_human", "spacious": "spacious_human", "warm": "warm_human",
                 "valence": "valence_human", "arousal": "arousal_human"}
        failed = set(self.rt_rater[self.rt_probe == 0].tolist())
        ok = ~np.isin(self.rt_rater, list(failed)) & (self.rt_probe != 0)
        n = len(self)
        for name in list(items.values()) + ["n_raters", "rating_sd"]:
            j = vocab.RESPONSE_INDEX[name]
            self.rmask[:n, j] = 0
            self.responses[:n, j] = 0
        summary = {"raters_excluded": len(failed), "scenes_rated": 0, "scenes_below_min_raters": 0}
        for i in np.unique(self.rt_scene[ok]).tolist():
            sel = ok & (self.rt_scene == i)
            raters = set(self.rt_rater[sel].tolist())
            if len(raters) < min_raters:
                summary["scenes_below_min_raters"] += 1
                continue
            summary["scenes_rated"] += 1
            for item, resp in items.items():
                v = self.rt_value[sel & (self.rt_item == item)]
                if len(v):
                    self.responses[i, vocab.RESPONSE_INDEX[resp]] = float(v.mean())
                    self.rmask[i, vocab.RESPONSE_INDEX[resp]] = 1
                    if item == "cozy":
                        self.responses[i, vocab.RESPONSE_INDEX["rating_sd"]] = float(v.std())
                        self.rmask[i, vocab.RESPONSE_INDEX["rating_sd"]] = 1
            self.responses[i, vocab.RESPONSE_INDEX["n_raters"]] = float(len(raters))
            self.rmask[i, vocab.RESPONSE_INDEX["n_raters"]] = 1
            self.meta[self.scene_ids[i]].setdefault("label_source", {})["human"] = "survey"
        return summary

    # ---- NPZ ---------------------------------------------------------------
    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path or self.path or "")
        if not str(target):
            raise ValueError("не указан путь")
        target.parent.mkdir(parents=True, exist_ok=True)
        n = len(self)
        fd, tmp = tempfile.mkstemp(suffix=".npz", dir=str(target.parent))
        os.close(fd)
        try:
            np.savez_compressed(
                tmp, format_version=np.array(FORMAT_VERSION), scene_ids=np.array(self.scene_ids, dtype="U64"),
                atoms=np.array(vocab.ATOMS, dtype="U32"), responses_names=np.array(vocab.RESPONSES, dtype="U32"),
                presence=self.presence[:n], responses=self.responses[:n], rmask=self.rmask[:n],
                meta=np.frombuffer(json.dumps(self.meta, ensure_ascii=False).encode("utf-8"), dtype=np.uint8),
                rt_scene=self.rt_scene, rt_rater=self.rt_rater, rt_item=self.rt_item, rt_value=self.rt_value, rt_probe=self.rt_probe,
            )
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        self.path = target
        return target

    @classmethod
    def load(cls, path: str | Path) -> "SceneStore":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)
        st = cls(path)
        with np.load(path, allow_pickle=False) as z:
            if z["atoms"].tolist() != vocab.ATOMS or z["responses_names"].tolist() != vocab.RESPONSES:
                raise ValueError("словарь файла не совпадает с текущим vocab.py: нужна миграция по именам атомов/откликов")
            n = len(z["scene_ids"])
            st.scene_ids = z["scene_ids"].tolist()
            st._cap = max(64, n)
            st.presence = np.full((st._cap, 64), UNKNOWN, dtype=np.int8)
            st.responses = np.zeros((st._cap, 64), dtype=np.float32)
            st.rmask = np.zeros((st._cap, 64), dtype=np.uint8)
            st.presence[:n], st.responses[:n], st.rmask[:n] = z["presence"], z["responses"], z["rmask"]
            raw = z["meta"]
            st.meta = json.loads(raw.tobytes().decode("utf-8") if raw.dtype == np.uint8 else str(raw))
            st._idx = {sid: k for k, sid in enumerate(st.scene_ids)}
            st.rt_scene, st.rt_rater, st.rt_item = z["rt_scene"], z["rt_rater"], z["rt_item"]
            st.rt_value, st.rt_probe = z["rt_value"], z["rt_probe"]
        return st
