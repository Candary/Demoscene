"""Оценка: помогает ли Color Matrix модели принимать цветовые решения.

Три режима:
  python eval/run_eval.py --baseline random                 # проверка самого харнесса: случайные цвета должны проваливаться
  python eval/run_eval.py --reference                       # эталонные решения (eval/reference_solutions.json) должны проходить
  python eval/run_eval.py --results results_with.json       # ответы вашей модели; формат ниже

Формат results.json: {"<task_id>": {"text": "<финальный ответ модели>", "tool_calls": [{"name": "find_colors"}, ...]}}
Такой словарь удобно собирать из `run_agent(...)` (поля text и tool_calls).

Рекомендуемый протокол сравнения: прогнать модель на всех задачах дважды (с инструментами и политикой / без инструментов),
сравнить pass-rate по категориям и tool-поведению; затем человек оценивает human_rubric вслепую.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "output"))
from color_matrix_python.colorspace import (CVD_MATRICES, contrast_ratio, delta_e_ok, lab_to_lch,  # noqa: E402
                                            parse_color, rgb_to_oklab, simulate_cvd)

TASKS = json.loads((ROOT / "eval" / "tasks.json").read_text(encoding="utf-8"))["tasks"]


def parse_answer(text: str) -> dict[str, str]:
    """Берёт последний JSON-блок с ключом colors."""
    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text or "", flags=re.S)
    if not blocks:
        blocks = re.findall(r"(\{[^{}]*\"colors\"[^{}]*\{.*?\}[^{}]*\})", text or "", flags=re.S)
    for raw in reversed(blocks):
        try:
            data = json.loads(raw)
            if isinstance(data.get("colors"), dict):
                return {k: str(v) for k, v in data["colors"].items()}
        except json.JSONDecodeError:
            continue
    return {}


def _resolve(ref: str, palette: dict[str, tuple]) -> tuple:
    if ref in palette:
        return palette[ref]
    return parse_color(ref)


def _lch(rgb):
    return lab_to_lch(rgb_to_oklab(np.array(rgb, dtype=float)))


def evaluate(task: dict, answer_text: str, tool_calls: list[dict]) -> dict:
    checks_out: list[dict] = []

    def add(name, ok, detail=""):
        checks_out.append({"check": name, "ok": bool(ok), "detail": detail})

    spec = task["checks"]
    palette: dict[str, tuple] = {k: parse_color(v) for k, v in task.get("given", {}).items()}
    answer = parse_answer(answer_text)
    parse_errors = []
    for role, val in answer.items():
        try:
            palette[role] = parse_color(val)
        except ValueError as exc:
            parse_errors.append(f"{role}: {exc}")

    for role in spec.get("required_roles", []):
        add(f"role:{role}", role in answer and not any(e.startswith(role + ":") for e in parse_errors),
            "" if role in answer else "роль отсутствует в ответе")

    def have(*roles):
        return all(r in palette or _is_hex(r) for r in roles)

    for fg, bg, minimum in spec.get("contrast", []):
        if not have(fg, bg):
            add(f"contrast:{fg}/{bg}>={minimum}", False, "нет цвета")
            continue
        ratio = float(contrast_ratio(_resolve(fg, palette), _resolve(bg, palette)))
        add(f"contrast:{fg}/{bg}>={minimum}", ratio >= minimum, f"{ratio:.2f}")

    for role, (lo, hi) in spec.get("hue_ranges", {}).items():
        if not have(role):
            add(f"hue:{role}", False, "нет цвета")
            continue
        h = float(_lch(palette[role])[2])
        ok = lo <= h <= hi if lo <= hi else (h >= lo or h <= hi)
        add(f"hue:{role}in[{lo},{hi}]", ok, f"{h:.0f}°")

    for role, mx in spec.get("max_chroma", {}).items():
        if not have(role):
            add(f"chroma:{role}", False, "нет цвета")
            continue
        c = float(_lch(palette[role])[1])
        add(f"chroma:{role}<={mx}", c <= mx, f"{c:.3f}")

    for role, hexv in spec.get("fixed", {}).items():
        add(f"fixed:{role}", role in palette and palette[role] == parse_color(hexv),
            f"получено {answer.get(role)}")

    if "monotone_lightness" in spec:
        roles = spec["monotone_lightness"]
        if have(*roles):
            Ls = [float(_lch(palette[r])[0]) for r in roles]
            diffs = np.diff(Ls)
            add("monotone_lightness", bool(np.all(diffs < 0) or np.all(diffs > 0)), ",".join(f"{v:.2f}" for v in Ls))
        else:
            add("monotone_lightness", False, "нет цветов")

    for d in spec.get("distinct", []):
        roles = d["roles"]
        if not have(*roles):
            add(f"distinct:{len(roles)}", False, "нет цветов")
            continue
        arr = np.array([palette[r] for r in roles], dtype=float)
        iu = np.triu_indices(len(roles), 1)

        def min_de(view):
            lab = rgb_to_oklab(view)
            return float(delta_e_ok(lab[iu[0]], lab[iu[1]]).min())

        m = min_de(arr)
        add(f"distinct:{len(roles)}>={d['min_delta_e']}", m >= d["min_delta_e"], f"{m:.3f}")
        if "cvd_min_delta_e" in d:
            worst = min(min_de(simulate_cvd(arr, k)) for k in CVD_MATRICES)
            add(f"distinct_cvd:{len(roles)}>={d['cvd_min_delta_e']}", worst >= d["cvd_min_delta_e"], f"{worst:.3f}")

    # поведение с инструментами оценивается отдельно от качества цвета
    tool_names = [t["name"] for t in tool_calls]
    tool_checks = []
    tspec = task.get("tools", {})
    if tspec.get("expect_any"):
        tool_checks.append({"check": "tools:used", "ok": bool(tool_names), "detail": str(tool_names)})
    forbid = tspec.get("forbid")
    if forbid:
        banned = tool_names if forbid == "all" else [n for n in tool_names if n in forbid]
        tool_checks.append({"check": "tools:forbidden_not_used", "ok": not banned, "detail": str(banned)})

    return {"id": task["id"], "category": task["category"], "color_checks": checks_out, "tool_checks": tool_checks,
            "color_pass": all(c["ok"] for c in checks_out), "tool_pass": all(c["ok"] for c in tool_checks),
            "parse_errors": parse_errors}


def _is_hex(s):
    try:
        parse_color(s)
        return True
    except ValueError:
        return False


def summarize(evals: list[dict]) -> dict:
    by_cat: dict[str, list[dict]] = {}
    for e in evals:
        by_cat.setdefault(e["category"], []).append(e)
    rate = lambda xs, k: round(sum(x[k] for x in xs) / max(len(xs), 1), 3)  # noqa: E731
    return {
        "tasks": len(evals),
        "color_pass_rate": rate(evals, "color_pass"), "tool_behavior_pass_rate": rate(evals, "tool_pass"),
        "by_category": {c: {"n": len(xs), "color_pass_rate": rate(xs, "color_pass"), "tool_pass_rate": rate(xs, "tool_pass")}
                        for c, xs in by_cat.items()},
        "failed": [{"id": e["id"], "failed_checks": [c for c in e["color_checks"] + e["tool_checks"] if not c["ok"]]}
                   for e in evals if not (e["color_pass"] and e["tool_pass"])],
    }


def random_baseline(seed: int = 0) -> dict:
    rng = random.Random(seed)
    out = {}
    for t in TASKS:
        roles = t["checks"].get("required_roles", [])
        colors = {r: "#%02x%02x%02x" % (rng.randrange(256), rng.randrange(256), rng.randrange(256)) for r in roles}
        out[t["id"]] = {"text": "```json\n" + json.dumps({"colors": colors}) + "\n```", "tool_calls": []}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", choices=["random"])
    ap.add_argument("--reference", action="store_true")
    ap.add_argument("--results")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)
    if a.baseline == "random":
        results = random_baseline()
    elif a.reference:
        results = json.loads((ROOT / "eval" / "reference_solutions.json").read_text(encoding="utf-8"))
    elif a.results:
        results = json.loads(Path(a.results).read_text(encoding="utf-8"))
    else:
        ap.error("укажи --baseline random, --reference или --results FILE")
    evals = []
    for t in TASKS:
        r = results.get(t["id"], {"text": "", "tool_calls": []})
        evals.append(evaluate(t, r.get("text", ""), r.get("tool_calls", [])))
    summary = summarize(evals)
    print(json.dumps(summary if not a.verbose else {"summary": summary, "evals": evals}, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    main()
