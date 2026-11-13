"""Cozy Matrix: агрегированный тензор C[A, B, R] (64 x 64 x 64).

C[a, b, r] = среднее значение отклика r по сценам, где одновременно присутствуют атомы a и b
(a == b — сцены, где есть a). Для каждой ячейки хранятся:
  * N  — число КАДРОВ (сцен-описаний), S — сумма значений;
  * NW — эффективное число СКАНОВ (комнат): каждый кадр взвешен 1/(число кадров этого скана), SW — взвешенная сумма.
Кадры одной комнаты — не независимые наблюдения (в корпусе ScanNet-captions 132 358 кадров из 1 612 сканов, до 417 кадров
на скан). Сжатие оценки к среднему и пороги поддержки считаются по NW, а не по N, иначе 100 кадров одной комнаты
выглядели бы как 100 доказательств.

Оценка со сжатием (как n/(n+k) в Color Matrix):  est = (SW + k * g) / (NW + k),  g — взвешенное глобальное среднее.
Lift = est - g.  Это ассоциация в подписях, а не причинная связь и не мнение людей (см. RESPONSE_SOURCE в vocab.py).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import numpy as np

from . import vocab
from .scenes import PRESENT, SceneStore

MATRIX_FORMAT = "1.1"
SHRINK_K = 5.0         # «вес» глобального среднего в псевдо-сканах
MIN_PAIR_SUPPORT = 3.0  # меньше эффективных сканов — пара не считается свидетельством


class CozyMatrix:
    def __init__(self):
        self.S = np.zeros((64, 64, 64), dtype=np.float64)
        self.N = np.zeros((64, 64, 64), dtype=np.float64)
        self.SW = np.zeros((64, 64, 64), dtype=np.float64)
        self.NW = np.zeros((64, 64, 64), dtype=np.float64)
        self.gS = np.zeros(64); self.gN = np.zeros(64); self.gSW = np.zeros(64); self.gNW = np.zeros(64)
        self.n_scenes = 0
        self.info: dict = {}

    # ---- накопление --------------------------------------------------------
    def update(self, presence_row, resp_row, rmask_row, weight: float = 1.0) -> None:
        p = (np.asarray(presence_row) == PRESENT).astype(np.float64)
        m = np.asarray(rmask_row).astype(np.float64)
        v = np.asarray(resp_row, dtype=np.float64) * m
        pp = np.outer(p, p)
        self.S += pp[:, :, None] * v[None, None, :]
        self.N += pp[:, :, None] * m[None, None, :]
        self.SW += weight * pp[:, :, None] * v[None, None, :]
        self.NW += weight * pp[:, :, None] * m[None, None, :]
        self.gS += v; self.gN += m; self.gSW += weight * v; self.gNW += weight * m
        self.n_scenes += 1

    def rebuild(self, store: SceneStore, weights: np.ndarray | None = None) -> "CozyMatrix":
        """Полный пересчёт из хранилища. weights: вес сцены (по умолчанию 1/кадров_в_скане, если у сцен есть scan_id).

        perf note (S-03 attempted, reverted): пробовали векторизовать через np.einsum,
        но einsum не dispatch'ит 3-operand contraction в BLAS даже с optimize=True.
        Замер на 31967 сцен: einsum ~19с на одну матрицу (×4 = 76с), а цикл с @ (BLAS) —
        0.7с на матрицу (×4 = 2.8с). Текущая версия (цикл + matmul) ОПТИМАЛЬНА.
        Не пытаться заменить на einsum/tensordot без benchmark'а.
        """
        info = self.info
        self.__init__()
        self.info = info
        n = len(store)
        if weights is None:
            weights = scan_weights(store)
        w = np.asarray(weights, dtype=np.float64)
        P = (store.presence[:n] == PRESENT).astype(np.float64)
        V = store.responses[:n].astype(np.float64)
        M = store.rmask[:n].astype(np.float64)
        for r in range(64):
            m = M[:, r]
            if not m.any():
                continue
            vm = V[:, r] * m
            self.S[:, :, r] = (P * vm[:, None]).T @ P
            self.N[:, :, r] = (P * m[:, None]).T @ P
            self.SW[:, :, r] = (P * (w * vm)[:, None]).T @ P
            self.NW[:, :, r] = (P * (w * m)[:, None]).T @ P
            self.gS[r], self.gN[r], self.gSW[r], self.gNW[r] = vm.sum(), m.sum(), (w * vm).sum(), (w * m).sum()
        self.n_scenes = n
        return self

    # ---- чтение ------------------------------------------------------------
    def global_mean(self, response: str) -> float | None:
        j = vocab.RESPONSE_INDEX[response]
        return float(self.gSW[j] / self.gNW[j]) if self.gNW[j] else None

    def cell(self, a: str, b: str, response: str, k: float = SHRINK_K) -> dict:
        i, j, r = vocab.ATOM_INDEX[a], vocab.ATOM_INDEX[b], vocab.RESPONSE_INDEX[response]
        n, n_eff = int(self.N[i, j, r]), float(self.NW[i, j, r])
        g = self.global_mean(response)
        out = {"a": a, "b": b, "response": response, "n_frames": n, "n_eff_scans": round(n_eff, 2),
               "global_mean": g, "mean": None, "estimate": None, "lift": None}
        if n:
            out["mean"] = float(self.S[i, j, r] / n)
        if g is not None:
            est = (self.SW[i, j, r] + k * g) / (n_eff + k)
            out["estimate"], out["lift"] = float(est), float(est - g)
        return out

    def partners(self, a: str, response: str, min_support: float = MIN_PAIR_SUPPORT, top: int = 10,
                 exclude: set[str] | None = None, group: str | None = None, k: float = SHRINK_K,
                 ascending: bool = False) -> list[dict]:
        """Атомы b, чьё совместное присутствие с a даёт наибольший сдвиг отклика относительно глобального среднего."""
        exclude = exclude or set()
        res = []
        for b in vocab.ATOMS:
            if b == a or b in exclude or b.startswith("reserved") or (group and vocab.ATOM_GROUP[b] != group):
                continue
            c = self.cell(a, b, response, k)
            if c["n_eff_scans"] >= min_support and c["lift"] is not None:
                res.append(c)
        res.sort(key=lambda c: c["lift"], reverse=not ascending)
        return res[:top]

    def lifts_within(self, context: str, response: str, group: str | None = None, min_support: float = MIN_PAIR_SUPPORT,
                     top: int = 10, k: float = SHRINK_K, ascending: bool = False) -> list[dict]:
        """Сдвиг отклика у атомов ВНУТРИ контекста (например, комнаты): est(x, context) - est(context, context).
        Нужен, чтобы отделить эффект предмета от эффекта типа комнаты (в корпусе P(cozy | office)=0.04, P(cozy | bed)=0.36)."""
        base = self.cell(context, context, response, k)
        if base["estimate"] is None or base["n_eff_scans"] < min_support:
            return []
        res = []
        for x in vocab.ATOMS:
            if x == context or x.startswith("reserved") or (group and vocab.ATOM_GROUP[x] != group):
                continue
            c = self.cell(x, context, response, k)
            if c["n_eff_scans"] >= min_support and c["estimate"] is not None:
                c["lift_within_context"] = c["estimate"] - base["estimate"]
                c["context_estimate"] = base["estimate"]
                res.append(c)
        res.sort(key=lambda c: c["lift_within_context"], reverse=not ascending)
        return res[:top]

    def has_evidence(self, response: str, min_scenes: int = 20) -> bool:
        return int(self.gN[vocab.RESPONSE_INDEX[response]]) >= min_scenes

    # ---- NPZ ---------------------------------------------------------------
    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix=".npz", dir=str(path.parent))
        os.close(fd)
        try:
            info = {**self.info, "vocab_version": vocab.VOCAB_VERSION, "matrix_format": MATRIX_FORMAT}
            np.savez_compressed(tmp, format_version=np.array(MATRIX_FORMAT), S=self.S, N=self.N, SW=self.SW, NW=self.NW,
                                gS=self.gS, gN=self.gN, gSW=self.gSW, gNW=self.gNW, n_scenes=np.array(self.n_scenes),
                                atoms=np.array(vocab.ATOMS, dtype="U32"), responses=np.array(vocab.RESPONSES, dtype="U32"),
                                info=np.frombuffer(json.dumps(info, ensure_ascii=False).encode("utf-8"), dtype=np.uint8))
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        return path

    @classmethod
    def load(cls, path: str | Path) -> "CozyMatrix":
        m = cls()
        with np.load(path, allow_pickle=False) as z:
            if z["atoms"].tolist() != vocab.ATOMS or z["responses"].tolist() != vocab.RESPONSES:
                raise ValueError("словарь файла не совпадает с vocab.py: пересоберите матрицу (rebuild) или мигрируйте по именам")
            for k in ("S", "N", "SW", "NW", "gS", "gN", "gSW", "gNW"):
                setattr(m, k, z[k])
            m.n_scenes = int(z["n_scenes"])
            m.info = json.loads(z["info"].tobytes().decode("utf-8"))
        return m

    @property
    def tensor(self) -> np.ndarray:
        """Среднее по ячейкам, float32 (nan, где нет наблюдений)."""
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(self.N > 0, self.S / np.maximum(self.N, 1), np.nan).astype(np.float32)


def scan_weights(store: SceneStore) -> np.ndarray:
    """Вес сцены = 1 / число сцен того же скана (meta['scan_id']). Без scan_id вес 1.

    perf note (C-02 attempted, reverted): пробовали через np.unique + np.searchsorted,
    но np.array(scans, dtype=object) доминирует — создание object-array из списка None+str
    дороже чем сам dict.get в Python-цикле. Замер на 31967 сцен: original 6 мс, np.unique 18 мс.
    Текущая версия (Python-цикл + dict) ОПТИМАЛЬНА для N≤100K. Не «оптимизировать» без benchmark'а.
    """
    n = len(store)
    scans = [store.meta[sid].get("scan_id") for sid in store.scene_ids[:n]]
    counts: dict = {}
    for s in scans:
        if s is not None:
            counts[s] = counts.get(s, 0) + 1
    return np.array([1.0 / counts[s] if s is not None else 1.0 for s in scans], dtype=np.float64)
