"""Музыка как мастер-время: карта аудио (темп, такты, маркеры) и офлайн-анализ файла.

AudioMap — чистые функции времени: beat(t), bar(t), phase. Никаких callback'ов: любое t вычислимо, seek точен.
analyze_file() даёт GLM то, чего он не может «услышать»: темп, сетку долей, огибающую энергии, границы секций и
предложения маркеров. Все результаты — ОЦЕНКИ: темп постоянный, первая сильная доля определяется эвристикой, ярлыки
секций (drop/breakdown) — по перепадам энергии. Автор проверяет сетку на слух и правит offset/маркеры.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ENERGY_RATE = 20.0   # Гц, частота дискретизации кривой энергии в анализе


@dataclass
class AudioMap:
    file: str | None = None
    bpm: float = 120.0
    offset: float = 0.0              # время (с) первой доли первого такта («такт 1, доля 1»)
    beats_per_bar: int = 4
    markers: dict[str, float] = field(default_factory=dict)   # имя -> абсолютное время (с)
    duration: float | None = None
    energy: np.ndarray | None = None  # кривая 0..1 с шагом 1/ENERGY_RATE
    sections: list[dict] = field(default_factory=list)

    # ---- время <-> музыкальные единицы ------------------------------------------------------------------------
    @property
    def spb(self) -> float:
        return 60.0 / self.bpm

    def beat(self, t: float) -> float:
        """Дробный номер доли от offset (0 = первая доля). До offset — отрицательный."""
        return (t - self.offset) / self.spb

    def beat_phase(self, t: float) -> float:
        b = self.beat(t)
        return b - math.floor(b)

    def bar(self, t: float) -> float:
        return self.beat(t) / self.beats_per_bar

    def bar_phase(self, t: float) -> float:
        b = self.bar(t)
        return b - math.floor(b)

    def time_of(self, bar: float = 1, beat: float = 1) -> float:
        """Время начала доли `beat` такта `bar` (нумерация с 1, как в музыкальных редакторах)."""
        return self.offset + ((bar - 1) * self.beats_per_bar + (beat - 1)) * self.spb

    def energy_at(self, t: float) -> float:
        if self.energy is None or len(self.energy) == 0:
            return 0.0
        x = t * ENERGY_RATE
        if x <= 0:
            return float(self.energy[0])
        i = int(x)
        if i >= len(self.energy) - 1:
            return float(self.energy[-1])
        f = x - i
        return float(self.energy[i] * (1 - f) + self.energy[i + 1] * f)

    def section_index(self, t: float) -> int:
        idx = -1
        for i, s in enumerate(self.sections):
            if t >= s["start"]:
                idx = i
        return idx

    def marker(self, name: str) -> float:
        if name not in self.markers:
            raise KeyError(f"маркер {name!r} не найден; есть: {sorted(self.markers)}")
        return self.markers[name]

    # ---- (де)сериализация ---------------------------------------------------------------------------------------
    @classmethod
    def from_show(cls, audio: dict | None, base_dir: Path | None = None) -> "AudioMap":
        a = audio or {}
        m = cls(file=a.get("file"), bpm=float(a.get("bpm", 120.0)), offset=float(a.get("offset", 0.0)),
                beats_per_bar=int(a.get("beats_per_bar", 4)), duration=a.get("duration"))
        if m.bpm <= 0 or m.beats_per_bar < 1:
            raise ValueError("audio.bpm должен быть > 0, beats_per_bar >= 1")
        for mk in a.get("markers", []):
            name = mk["name"]
            if "time" in mk:
                m.markers[name] = float(mk["time"])
            elif "bar" in mk:
                m.markers[name] = m.time_of(float(mk["bar"]), float(mk.get("beat", 1))) + float(mk.get("offset", 0.0))
            else:
                raise ValueError(f"маркер {name!r}: нужен time или bar")
        an = a.get("analysis")
        if an:
            p = Path(an) if base_dir is None or Path(an).is_absolute() else Path(base_dir) / an
            if p.exists():
                d = json.loads(p.read_text(encoding="utf-8"))
                m.energy = np.asarray(d.get("energy", []), dtype=np.float64)
                m.sections = d.get("sections", [])
                m.duration = m.duration or d.get("duration")
        return m


# ======================================================================================================================
# Анализ файла
# ======================================================================================================================
SR = 22050
N_FFT = 1024
HOP = 512
ONSET_LATENCY = 0.0     # с: на синтетике пик потока совпадает с ударом в пределах ~5 мс, поправка не нужна


def decode_audio(path: str | Path, sr: int = SR) -> np.ndarray:
    """Моно float32 в [-1, 1]. WAV читается напрямую, остальное (MP3/OGG/FLAC...) — через ffmpeg."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".wav":
        with wave.open(str(path), "rb") as w:
            ch, sw, fr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            if sw == 2:
                x = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32) / 32768.0
                x = x.reshape(-1, ch).mean(1)
                if fr == sr:
                    return x
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("для декодирования нужен ffmpeg (или WAV 16-bit на 22050 Гц)")
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                          capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg: {proc.stderr.decode(errors='replace')[:300]}")
    return np.frombuffer(proc.stdout, dtype="<f4").copy()


def _stft_mag(x: np.ndarray) -> np.ndarray:
    n = 1 + max(0, (len(x) - N_FFT) // HOP)
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n)[:, None]
    frames = x[idx] * np.hanning(N_FFT)[None, :].astype(np.float32)
    return np.abs(np.fft.rfft(frames, axis=1)).astype(np.float32)


def _smooth(v: np.ndarray, w: int) -> np.ndarray:
    if w <= 1:
        return v
    k = np.ones(w) / w
    return np.convolve(v, k, mode="same")


def analyze_samples(x: np.ndarray, sr: int = SR, beats_per_bar: int = 4) -> dict:
    if sr != SR:
        raise ValueError(f"ожидалась частота {SR} Гц")
    if len(x) < SR * 4:
        raise ValueError("слишком короткий сигнал (< 4 с)")
    fps = SR / HOP
    mag = _stft_mag(x)
    nfr = len(mag)
    rms = np.sqrt(np.mean(mag ** 2, axis=1))
    # --- onset strength (спектральный поток по лог-амплитуде)
    logm = np.log1p(10.0 * mag)
    flux = np.maximum(0.0, np.diff(logm, axis=0)).sum(1)
    flux = np.concatenate([[0.0], flux])
    flux = flux - _smooth(flux, int(fps * 0.5))
    flux = np.maximum(flux, 0.0)
    if flux.max() > 0:
        flux /= flux.max()
    # поток в низкой полосе (< 200 Гц, кик): по нему ищем фазу сетки — офбитные хэты/шум не должны её перетягивать
    kb = int(200 / (SR / N_FFT)) + 1
    lflux = np.concatenate([[0.0], np.maximum(0.0, np.diff(np.log1p(10.0 * mag[:, :kb]), axis=0)).sum(1)])
    lflux = np.maximum(lflux - _smooth(lflux, int(fps * 0.5)), 0.0)
    if lflux.max() > 0:
        lflux /= lflux.max()
    pflux = 0.6 * lflux + 0.4 * flux
    # --- темп: автокорреляция потока + гармоническое усиление + мягкий приор около 120 BPM
    ac = np.correlate(flux - flux.mean(), flux - flux.mean(), mode="full")[nfr - 1:]
    ac /= (ac[0] + 1e-12)

    def acv(lag):
        lag = np.asarray(lag, dtype=np.float64)
        i = np.clip(lag, 0, len(ac) - 2).astype(int)
        f = lag - i
        return ac[i] * (1 - f) + ac[i + 1] * f

    bpms = np.arange(60.0, 200.0, 0.1)
    lags = 60.0 / bpms * fps
    score = acv(lags) + 0.5 * acv(2 * lags) + 0.25 * acv(4 * lags)
    prior = np.exp(-0.5 * (np.log2(bpms / 120.0) / 0.8) ** 2)
    s = score * prior
    bi = int(np.argmax(s))
    bpm = float(bpms[bi])
    conf = float(np.clip((s[bi] - np.median(s)) / (s[bi] + 1e-12), 0.0, 1.0))
    # --- уточнение: совместный поиск (темп, фаза) на тонкой сетке по потоку; грубая оценка автокорреляции даёт только окрестность
    ts = (np.arange(nfr) * HOP + N_FFT / 2) / SR + ONSET_LATENCY
    best = (-1.0, bpm, 0.0)
    for cand in np.arange(bpm * 0.97, bpm * 1.03, 0.02):
        per = 60.0 / cand
        phases = np.arange(0.0, per, 0.004)
        n_b = int((ts[-1] - per) / per)
        times = phases[:, None] + per * np.arange(n_b)[None, :]
        sc = np.interp(times, ts, pflux).mean(1)
        k = int(np.argmax(sc))
        if sc[k] > best[0]:
            best = (float(sc[k]), float(cand), float(phases[k]))
    _, bpm, _ = best
    period = 60.0 / bpm
    # фаза: по низкой полосе (кик), если она периодична не слабее широкополосного потока; иначе по широкополосному.
    # (нормировка полос по максимуму несправедлива: шумный хэт даёт широкополосный поток на порядок больше кика)
    phases = np.arange(0.0, period, 0.004)
    n_b = int((ts[-1] - period) / period)
    times = phases[:, None] + period * np.arange(n_b)[None, :]
    scl, scf = np.interp(times, ts, lflux).mean(1), np.interp(times, ts, flux).mean(1)
    cl, cf = scl.max() / (scl.mean() + 1e-12), scf.max() / (scf.mean() + 1e-12)
    phase_src = "low_band" if cl >= 0.7 * cf else "full_band"
    ph0 = float(phases[int(np.argmax(scl if phase_src == "low_band" else scf))])
    n_beats = int((ts[-1] - ph0) / period)
    low = mag[:, : int(150 / (SR / N_FFT)) + 1].sum(1)
    low = low / (low.max() + 1e-12)
    beat_times = ph0 + period * np.arange(n_beats)
    beat_times = beat_times[beat_times < ts[-1]]
    lowb = np.interp(beat_times, ts, low)
    per_pos = np.array([lowb[j::beats_per_bar].mean() if len(lowb[j::beats_per_bar]) else 0.0 for j in range(beats_per_bar)])
    j = int(np.argmax(per_pos))
    ordered = np.sort(per_pos)[::-1]
    down_conf = float(ordered[0] / (ordered[1] + 1e-12)) if len(ordered) > 1 else 1.0
    offset = ph0 + j * period
    # --- энергия: RMS, сглаживание 0.25 с, ресемплинг до ENERGY_RATE, нормировка по 99-му перцентилю
    e = _smooth(rms, max(1, int(fps * 0.25)))
    dur = len(x) / SR
    grid = np.arange(0.0, dur, 1.0 / ENERGY_RATE)
    e = np.interp(grid, ts, e)
    e = np.clip(e / (np.percentile(e, 99) + 1e-9), 0.0, 1.0)
    # --- секции: новизна по поэтактовым признакам (энергия + яркость) ядром-«шахматкой»
    bar_len = period * beats_per_bar
    n_bars = int((dur - offset) / bar_len) if dur > offset else 0
    sections, markers = [], []
    if n_bars >= 8:
        cent = (mag * np.arange(mag.shape[1])[None, :]).sum(1) / (mag.sum(1) + 1e-9)
        feats = []
        for b in range(n_bars):
            a0, a1 = int((offset + b * bar_len) * fps), int((offset + (b + 1) * bar_len) * fps)
            a1 = max(a1, a0 + 1)
            feats.append([rms[a0:a1].mean(), cent[a0:a1].mean()])
        F = np.array(feats)
        F = (F - F.mean(0)) / (F.std(0) + 1e-9)
        def novelty(L: int) -> np.ndarray:
            n_ = np.zeros(n_bars)
            for b in range(L, n_bars - L + 1):
                n_[b - 1] = np.linalg.norm(F[b:b + L].mean(0) - F[b - L:b].mean(0))
            return n_

        # два масштаба: окно 4 такта видит крупные секции, окно 2 — короткие подъёмы (8 тактов) рядом с длинными
        nov = np.maximum(novelty(min(4, n_bars // 4)), novelty(2))
        thr = max(0.6, 0.25 * nov.max())
        peaks = []
        for b in np.argsort(-nov):
            if nov[b] < thr or len(peaks) >= 16:
                break
            if all(abs(b - q) >= 4 for q in peaks):
                peaks.append(int(b))
        bounds = sorted({0, *[p + 1 for p in peaks], n_bars})
        for k in range(len(bounds) - 1):
            t0, t1 = offset + bounds[k] * bar_len, offset + bounds[k + 1] * bar_len
            me = float(np.mean(e[int(t0 * ENERGY_RATE):max(int(t1 * ENERGY_RATE), int(t0 * ENERGY_RATE) + 1)]))
            sections.append({"index": k, "start": round(t0, 3), "end": round(t1, 3), "bars": bounds[k + 1] - bounds[k],
                             "mean_energy": round(me, 3)})
        ref = max(sx["mean_energy"] for sx in sections) or 1.0      # пороги относительные: у кик-дорожки средняя энергия ~0.4 от пика
        for k in range(1, len(sections)):
            prev, cur = sections[k - 1]["mean_energy"], sections[k]["mean_energy"]
            if cur <= 0.6 * prev:
                label = "outro" if (k == len(sections) - 1 and sections[k]["start"] > 0.8 * dur and cur < 0.4 * ref) else "breakdown"
            elif cur >= 1.25 * max(prev, 0.02):
                label = "drop" if cur >= 0.8 * ref else "build"   # drop — приход на (почти) максимальную энергию трека; иначе подъём — build
            else:
                label = "change"
            sections[k]["label"] = label
            markers.append({"name": f"{label}_{k}", "time": sections[k]["start"], "bar": 1 + bounds[k], "label": label})
    onset_idx = np.argsort(-flux)[:200]
    onsets = sorted(round(float(ts[i]), 3) for i in onset_idx if flux[i] > 0.5)
    return {"duration": round(dur, 3), "bpm": round(bpm, 2), "bpm_confidence": round(conf, 3), "offset": round(offset, 3),
            "downbeat_confidence": round(down_conf, 3), "phase_source": phase_src, "beats_per_bar": beats_per_bar,
            "energy_rate": ENERGY_RATE, "energy": [round(float(v), 3) for v in e],
            "sections": sections, "markers_suggested": markers, "strong_onsets": onsets[:100],
            "caveats": ("Темп считается постоянным. offset — оценка первой сильной доли по низким частотам; проверьте на слух. "
                        "Ярлыки секций (drop/breakdown/build) — эвристика по перепадам энергии.")}


def analyze_file(path: str | Path, beats_per_bar: int = 4) -> dict:
    return analyze_samples(decode_audio(path), SR, beats_per_bar)
