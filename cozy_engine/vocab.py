"""Словарь Cozy Engine: 64 атома (что есть в сцене) и 64 отклика (как сцену оценили/измерили).

Оси Cozy Matrix: [атом A, атом B, отклик R] -> 64 x 64 x 64. Значение ячейки — среднее отклика R по всем сценам,
где одновременно присутствуют A и B (диагональ A==B — сцены, где есть A). Сами сцены хранятся отдельно (scenes.py),
поэтому их число не ограничено 64.

Версия 1.2 (1.1 + разделение rug / carpet_floor: «carpeted» — напольное покрытие почти всех комнат ScanNet, а не декор;
в 1.1 оно делало rug антиуютным в спальнях). Версия 1.1: словарь сверен с корпусом scannet-captions-gpt4o (132 358 подписей). Правила отбора атомов:
  * атом должен встречаться не менее чем в ~0.15% подписей (иначе ячейки матрицы пусты) — исключение: fireplace/candle,
    они редки, но дают самый сильный сигнал «уюта» и нужны как примитивы сцены;
  * атомы «уют/тепло/уютно» (cozy, inviting, warm, comfortable...) в словарь НЕ входят: это метки (responses), иначе матрица
    «предсказывала» бы слово словом;
  * цвета не атомы: они входят через Color Matrix (colors.py, группа откликов color_*).
Мёртвые атомы черновика (velvet 32 вхождения, knit 31, wool 1, linen 0 из 132 358) заменены на table, door, cabinet, books,
которых в черновике не было, хотя они стоят в первой десятке по частоте.
"""
from __future__ import annotations

import re

VOCAB_VERSION = "1.2"

# --- 64 атома -------------------------------------------------------------------------------------------------------
OBJECTS = [
    "sofa", "armchair", "ottoman", "bed", "cushion", "blanket", "rug", "curtain", "table", "coffee_table", "chair",
    "desk", "bookshelf", "shelf", "cabinet", "books", "lamp", "fireplace", "candle", "plant", "window", "door",
    "artwork", "mirror", "basket", "tv", "computer",
]  # 27
MATERIALS = ["wood", "fabric", "leather", "rattan", "glass", "metal", "stone", "tile", "brick", "carpet_floor"]  # 10
LIGHT = ["warm_light", "natural_light", "dim_light", "soft_light", "bright_light"]  # 5
PALETTE = ["warm_palette", "neutral_palette", "earth_tones", "colorful", "dark_palette"]  # 5
QUALITY = ["cluttered", "tidy", "minimal", "spacious", "soft", "patterned", "modern", "rustic", "small"]  # 9
ROOMS = ["living_room", "bedroom", "kitchen", "bathroom", "office", "dining_room", "hallway", "laundry"]  # 8
RESERVED: list[str] = []  # свободных слотов нет: следующий атом — только вместо редкого (например brick)

ATOM_GROUPS = {"object": OBJECTS, "material": MATERIALS, "light": LIGHT, "palette": PALETTE, "quality": QUALITY,
               "room": ROOMS, "reserved": RESERVED}
ATOMS: list[str] = [a for g in ATOM_GROUPS.values() for a in g]
ATOM_GROUP = {a: g for g, items in ATOM_GROUPS.items() for a in items}
ATOM_INDEX = {a: i for i, a in enumerate(ATOMS)}
assert len(ATOMS) == 64 and len(set(ATOMS)) == 64, len(ATOMS)

# --- 64 откликов ----------------------------------------------------------------------------------------------------
# Шкалы человеческих оценок нормируются в [0, 1] при загрузке (в опросах шкалы разные: 1-7, 0-7, 1-9).
RESPONSE_GROUPS = {
    "human": ["cozy_human", "lively_human", "spacious_human", "warm_human", "valence_human", "arousal_human",
              "n_raters", "rating_sd"],
    "weak": ["cozy_kw", "inviting_kw", "comfortable_kw", "warm_kw", "relaxing_kw", "any_cozy_kw"],
    "structure": ["object_count", "material_count", "light_count", "palette_count", "quality_count", "word_count"],
    # Все color_* — производные от Color Matrix (prior-модель) по названиям цветов в тексте. Это НЕ измерение цвета сцены.
    # empathy/intensity/chroma нормированы в [0, 1]: empathy (x+100)/200, intensity x/100, chroma C/0.37, lightness как есть.
    "color": ["color_empathy_mean", "color_empathy_min", "color_intensity_mean", "color_intensity_max",
              "color_chroma_mean", "color_lightness_mean", "color_warm_fraction", "color_cold_fraction",
              "color_tension_fraction", "color_positive_fraction", "color_n_colors", "color_dark_fraction"],
    "image": [f"image_feature_{i:02d}" for i in range(24)],
    "reserved": [f"reserved_{i:02d}" for i in range(8)],
}
RESPONSES: list[str] = [r for g in RESPONSE_GROUPS.values() for r in g]
RESPONSE_GROUP = {r: g for g, items in RESPONSE_GROUPS.items() for r in items}
RESPONSE_INDEX = {r: i for i, r in enumerate(RESPONSES)}
assert len(RESPONSES) == 64 and len(set(RESPONSES)) == 64, len(RESPONSES)

# Откуда берётся значение — это решает, можно ли ему доверять при выводах «что вызывает уют».
RESPONSE_SOURCE = {
    "human": "survey",              # оценки людей (после проверки внимания)
    "weak": "caption_keywords",     # слова в подписи/промпте; подписи генерирует модель (GPT-4o), это НЕ мнение людей
    "structure": "derived",         # счётчики из разбора сцены
    "color": "color_matrix_prior",  # профиль цветов по Color Matrix (prior-модель, не измерение)
    "image": "image_features",
    "reserved": "none",
}

# Нормировочная константа для color_chroma_mean (см. комментарий выше).
CHROMA_MAX = 0.37


# --- Синонимы для разбора текстовых описаний ------------------------------------------------------------------------
def _w(*words: str) -> list[str]:
    return [rf"\b{w}\b" for w in words]


ALIASES: dict[str, list[str]] = {
    "sofa": _w("sofas?", "couch(?:es)?", "loveseat", "sectional"),
    "armchair": _w("armchairs?", "arm chairs?", "recliner", "lounge chairs?", "accent chairs?"),
    "ottoman": _w("ottomans?", "footstool", "pouf"),
    "bed": _w("beds?", "mattress", "bedframe"),
    "cushion": _w("cushions?", "pillows?"),
    "blanket": _w("blankets?", "throws?", "quilts?", "duvets?", "comforters?"),
    "rug": _w("rugs?", "area rugs?"),
    "carpet_floor": _w("carpets?", "carpeted", "wall-to-wall"),
    "curtain": _w("curtains?", "drapes?", "blinds?"),
    "table": _w("tables?"),
    "coffee_table": _w("coffee tables?", "side tables?", "end tables?"),
    "chair": _w("chairs?", "stools?", "benches?"),
    "desk": _w("desks?"),
    "bookshelf": _w("bookshelf", "bookshelves", "bookcases?"),
    "shelf": _w("shelf", "shelves"),
    "cabinet": _w("cabinets?", "wardrobes?", "cupboards?", "closets?"),
    "books": _w("books?"),
    "lamp": _w("lamps?", "floor lamps?", "table lamps?", "pendant lights?", "chandeliers?"),
    "fireplace": _w("fireplaces?", "hearth"),
    "candle": _w("candles?", "lanterns?"),
    "plant": _w("plants?", "houseplants?", "flowers?", "greenery"),
    "window": _w("windows?", "skylights?"),
    "door": _w("doors?"),
    "artwork": _w("artworks?", "paintings?", "posters?", "pictures?", "framed"),
    "mirror": _w("mirrors?"),
    "basket": _w("baskets?", "wicker baskets?"),
    "tv": _w("tv", "televisions?", "monitors?"),
    "computer": _w("computers?", "laptops?", "keyboards?"),
    "wood": _w("wood", "wooden", "oak", "walnut", "timber"),
    "fabric": _w("fabric", "upholster(?:y|ed)", "textiles?", "cloth"),
    "leather": _w("leather"),
    "rattan": _w("rattan", "wicker", "bamboo", "jute"),
    "glass": _w("glass"),
    "metal": _w("metal(?:lic)?", "steel", "iron", "brass"),
    "stone": _w("stone", "marble", "granite", "concrete"),
    "tile": _w("tiled?"),
    "brick": _w("brick"),
    "warm_light": _w("warm(?:ly)? (?:light(?:ing)?|glow|lit|illuminat\\w*)", "golden", "amber"),
    "natural_light": _w("natural light(?:ing)?", "daylight", "sunlight", "sunlit", "sunny"),
    "dim_light": _w("dim(?:ly)?", "low light", "moody", "subdued"),
    "soft_light": _w("soft(?:ly)?[ -]?(?:light(?:ing)?|lit|glow)", "softly"),
    "bright_light": _w("bright(?:ly)? (?:light(?:ing)?|lit)", "fluorescent", "harsh", "overhead light(?:s|ing)?"),
    "warm_palette": _w("warm(?:-toned)? (?:palette|colou?rs?|tones?|hues?)", "warm-toned"),
    "neutral_palette": _w("neutral", "beige", "cream", "off-white", "greige", "tan"),
    "earth_tones": _w("earth(?:y)? tones?", "earthy", "terracotta", "olive", "rust", "ochre", "clay"),
    "colorful": _w("colou?rful", "vibrant", "multicolou?red", "bold colou?rs?"),
    "dark_palette": _w("dark (?:palette|colou?rs?|tones?|walls?)", "charcoal", "navy"),
    "cluttered": _w("clutter(?:ed)?", "messy", "crowded", "cramped", "overcrowded"),
    "tidy": _w("tidy", "neat", "orderly", "organi[sz]ed", "uncluttered", "clutter-free", "decluttered", "clean"),
    "minimal": _w("minimal(?:ist|istic)?", "sparse", "bare", "empty", "simple"),
    "spacious": _w("spacious", "airy", "roomy", "open"),
    "soft": _w("soft", "plush", "fluffy", "snug"),
    "patterned": _w("patterned", "floral", "striped", "plaid"),
    "modern": _w("modern", "contemporary"),
    "rustic": _w("rustic", "vintage", "farmhouse", "cabin"),
    "small": _w("small"),
    "living_room": _w("living rooms?", "lounge", "sitting (?:room|area)"),
    "bedroom": _w("bedrooms?"),
    "kitchen": _w("kitchens?", "kitchenette"),
    "bathroom": _w("bathrooms?", "restroom", "washroom"),
    "office": _w("offices?", "workspace", "study", "classroom", "lecture (?:hall|room)", "conference room", "meeting room"),
    "dining_room": _w("dining (?:room|area)", "dining"),
    "hallway": _w("hallways?", "corridor", "entryway", "lobby"),
    "laundry": _w("laundry", "utility room"),
}
assert set(ALIASES) <= set(ATOMS), sorted(set(ALIASES) - set(ATOMS))

# Слова, которые при совпадении означают ЯВНОЕ отсутствие атома (а не «не упомянут»).
NEGATIVE_ALIASES: dict[str, list[str]] = {
    "cluttered": _w("uncluttered", "clutter-free", "decluttered", "tidy", "neat"),
}

NEGATORS = re.compile(r"\b(?:no|without|lacks?|lacking|not|never|free of|absence of|devoid of)\b", re.I)

# Слабые метки по ключевым словам (источник: подпись/промпт, НЕ мнение людей).
KEYWORDS = {
    "cozy_kw": r"\bcoz(?:y|ier|iest)\b|\bcos(?:y|ier|iest)\b|\bcosiness\b|\bcoziness\b|\bhygge\b",
    "inviting_kw": r"\binviting\b|\bwelcoming\b",
    "comfortable_kw": r"\bcomfort(?:able|ing)?\b",
    "warm_kw": r"\bwarm(?:th|ly)?\b",
    "relaxing_kw": r"\brelax(?:ing|ed|ation)?\b|\bcalm(?:ing)?\b|\bserene\b|\btranquil\b",
}
