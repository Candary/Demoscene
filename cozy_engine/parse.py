"""Разбор текстового описания сцены в атомы словаря.

Ключевое отличие от прежнего парсера: различаются три состояния —
  1  атом упомянут как присутствующий,
  0  атом явно отсутствует («no rug», «uncluttered»),
 -1  не упомянут (неизвестно). Неупомянутое НЕ означает «отсутствует».
"""
from __future__ import annotations

import re

from . import vocab

_COMPILED = {atom: [re.compile(p, re.I) for p in pats] for atom, pats in vocab.ALIASES.items()}
_NEG_COMPILED = {atom: [re.compile(p, re.I) for p in pats] for atom, pats in vocab.NEGATIVE_ALIASES.items()}
_KW = {name: re.compile(p, re.I) for name, p in vocab.KEYWORDS.items()}
_PUNCT = re.compile(r"[.,;:!?()\n]")
_NEG_WINDOW = 28


def _negated(text: str, start: int) -> bool:
    window = text[max(0, start - _NEG_WINDOW):start]
    parts = _PUNCT.split(window)
    return bool(vocab.NEGATORS.search(parts[-1])) if parts else False


def find_mentions(text: str) -> list[tuple[str, int, int]]:
    """Все совпадения (atom, start, end) без вложенных в более длинное совпадение той же группы."""
    found: list[tuple[str, int, int]] = []
    for atom, pats in _COMPILED.items():
        for p in pats:
            for m in p.finditer(text):
                found.append((atom, m.start(), m.end()))
    keep = []
    for a, s, e in found:
        shadowed = any(
            b != a and vocab.ATOM_GROUP[b] == vocab.ATOM_GROUP[a] and s2 <= s and e <= e2 and (e2 - s2) > (e - s)
            for b, s2, e2 in found
        )
        if not shadowed:
            keep.append((a, s, e))
    return keep


def parse_text(text: str) -> dict:
    """Возвращает {"presence": {atom: 1|0}, "responses": {name: value}, "label_source": {...}}."""
    text = str(text or "")
    low = text.lower()
    presence: dict[str, int] = {}

    # явные отрицательные формулировки
    for atom, pats in _NEG_COMPILED.items():
        if any(p.search(low) for p in pats):
            presence[atom] = 0

    for atom, s, _e in find_mentions(low):
        if _negated(low, s):
            presence.setdefault(atom, 0)
        else:
            presence[atom] = 1  # положительное упоминание выигрывает у отрицательного

    # «uncluttered» не должен давать cluttered=1: положительное совпадение по слову 'clutter' внутри него невозможно
    # из-за границ слова, но «tidy»/«neat» явно закрывают вопрос, если cluttered не упомянут положительно.
    kw = {name: (1.0 if p.search(low) else 0.0) for name, p in _KW.items()}
    kw["any_cozy_kw"] = max(kw["cozy_kw"], kw["inviting_kw"])

    def count(group: str) -> float:
        return float(sum(1 for a, v in presence.items() if v == 1 and vocab.ATOM_GROUP[a] == group))

    responses = {
        **kw,
        "object_count": count("object"), "material_count": count("material"), "light_count": count("light"),
        "palette_count": count("palette"), "quality_count": count("quality"), "word_count": float(len(low.split())),
    }
    return {"presence": presence, "responses": responses,
            "label_source": {"weak": "caption_keywords", "structure": "derived_from_text"}}
