"""Синтетический саундтрек для примера (замена вашего MP3): 128 BPM, 192 такта = 6:00, секции с разной энергией.
Запуск: python make_soundtrack.py [out.mp3]. Нужен ffmpeg. Структура (такты): intro 1-24, build 25-32, drop 33-72, breakdown 73-96,
build 97-104, drop 105-152, climax 153-168, outro 169-192."""
import subprocess, sys, wave
import numpy as np

SR, BPM, OFFSET = 44100, 128.0, 0.35
SECTIONS = [(1, 24, 0.25, False), (25, 32, 0.6, True), (33, 72, 1.0, True), (73, 96, 0.3, False), (97, 104, 0.65, True), (105, 152, 1.0, True), (153, 168, 1.0, True), (169, 192, 0.2, False)]


def build() -> np.ndarray:
    spb = 60 / BPM
    n_bars = 192
    dur = OFFSET + n_bars * 4 * spb + 1.0
    x = np.zeros(int(SR * dur), dtype=np.float32)
    rng = np.random.default_rng(1)
    for bar in range(1, n_bars + 1):
        lvl, hats = next((l, h) for a, b, l, h in SECTIONS if a <= bar <= b)
        for beat in range(4):
            t0 = OFFSET + ((bar - 1) * 4 + beat) * spb
            i = int(t0 * SR); seg = np.arange(min(int(0.15 * SR), len(x) - i)) / SR
            x[i:i + len(seg)] += (lvl * (1.0 if beat == 0 else 0.7)) * np.sin(2 * np.pi * (55 + 90 * np.exp(-seg * 40)) * seg) * np.exp(-seg * 18)
            if hats:
                j = int((t0 + spb / 2) * SR); m = min(int(0.05 * SR), len(x) - j)
                if m > 0:
                    x[j:j + m] += 0.18 * lvl * rng.standard_normal(m) * np.exp(-np.arange(m) / SR * 80)
    return np.clip(x, -1, 1)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "soundtrack.mp3"
    x = build()
    wav = out.rsplit(".", 1)[0] + ".wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x * 32767).astype("<i2").tobytes())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-b:a", "128k", out], check=True)
    print("written", out, f"{len(x) / SR:.1f} s")
