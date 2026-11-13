"""Словари меток. Здесь же зафиксировано, что в словарях проверено по данным v10/v11, а что нет."""
from __future__ import annotations

EMPATHY = ["anxiety", "tension", "neutral", "warmth", "delight"]
# Границы меток в данных (проверено): -100..-61, -60..-21, -20..19, 20..59, 60..100
EMPATHY_RANGES = {
    "anxiety": (-100, -61),
    "tension": (-60, -21),
    "neutral": (-20, 19),
    "warmth": (20, 59),
    "delight": (60, 100),
}
# Целевые значения для поиска. Для delight берём 80, а не 100: у 2.4% цветов эмпатия упёрлась в потолок +100,
# и поиск «по максимуму» вернул бы случайный цвет из этого плато.
EMPATHY_TARGET = {"anxiety": -80, "tension": -40, "neutral": 0, "warmth": 40, "delight": 80}
EMPATHY_DESC = {
    "anxiety": "Тревога, опасность, настороженность.",
    "tension": "Напряжение, давление, собранность.",
    "neutral": "Нейтральное восприятие.",
    "warmth": "Тепло, безопасность, мягкий позитив.",
    "delight": "Радость, лёгкость, выраженный позитив.",
}

# Метки энтропии в v10 назывались very_dark..very_bright, но шкала считается из насыщенности и удалённости
# светлоты от середины (середина-серый = 0). «dark» для среднего серого вводит в заблуждение, поэтому в v11
# основные имена — intensity-шкала; старые имена доступны как legacy.
ENTROPY_LEGACY = ["very_dark", "dark", "medium", "bright", "very_bright"]
ENTROPY_INTENSITY = ["very_low", "low", "medium", "high", "very_high"]
ENTROPY_RANGES = {"very_low": (0, 19), "low": (20, 39), "medium": (40, 59), "high": (60, 79), "very_high": (80, 100)}
ENTROPY_DESC = {
    "very_low": "Минимальная визуальная интенсивность: малонасыщенный цвет у середины светлоты, почти не привлекает внимание.",
    "low": "Сдержанный, визуально тихий.",
    "medium": "Сбалансированный, читаемый.",
    "high": "Энергичный, привлекающий внимание.",
    "very_high": "Очень интенсивный: насыщенный и/или далёкий от середины светлоты; возможен визуальный шум.",
}

DIMS = ["temperature", "weight", "texture", "sound", "motion", "spatial_depth"]

# status:
#   "ok"         — порядок слов согласуется с поведением данных (проверено на выборке);
#   "unverified" — слова из документации НЕ удалось сопоставить уровням данных; отдаём только числовой уровень.
SYNESTHESIA = {
    "temperature": {
        "words": ["cold", "cool", "neutral", "warm", "hot"], "levels": 5, "status": "ok",
        "driver": "тон (hue); в v11 ослабляется у малохроматичных цветов",
    },
    "weight": {
        "words": ["light", "medium", "heavy"], "levels": 3, "status": "ok",
        "driver": "светлота (светлое -> light, тёмное -> heavy)",
    },
    "texture": {
        "words": None, "doc_words": ["smooth", "matte", "rough", "sharp", "soft"], "levels": 5, "status": "unverified",
        "driver": "насыщенность (0 = малонасыщенный ... 4 = максимально насыщенный)",
        "note": "В документации 'soft' стоит последним, но уровень 4 соответствует самым насыщенным цветам. Порядок слов не подтверждён.",
    },
    "sound": {
        "words": ["silent", "low", "mid", "high", "harsh"], "levels": 5, "status": "ok",
        "driver": "насыщенность и удалённость светлоты от середины",
    },
    "motion": {
        "words": ["still", "slow", "flowing", "pulse", "agitated"], "levels": 5, "status": "ok",
        "driver": "насыщенность и удалённость светлоты от середины",
    },
    "spatial_depth": {
        "words": None, "doc_words": ["flat", "shallow", "deep", "infinite"], "levels": 5, "status": "unverified",
        "driver": "светлота (0 = очень светлый ... 4 = очень тёмный)",
        "note": "В данных 5 уровней, в документации 4 слова. Сопоставление неизвестно.",
    },
}

# Номинальная уверенность prior-модели. Это НЕ статистическая оценка: данных людей пока нет.
# Значения вынесены в конфиг, чтобы blender мог заменять их по мере накопления crowd-выборки (n / (n + k)).
PRIOR_CONFIDENCE = {"empathy": 0.3, "entropy": 0.4, "synesthesia": 0.3}

# Russian → English aliases for bilingual queries
EMPATHY_ALIASES = {
    "тревога": "anxiety", "тревожный": "anxiety",
    "напряжение": "tension", "напряженный": "tension",
    "нейтрально": "neutral", "нейтральный": "neutral",
    "тепло": "warmth", "теплый": "warmth",
    "радость": "delight", "радостный": "delight",
}

TEMPERATURE_ALIASES = {
    "холодный": "cold", "холодно": "cold",
    "прохладный": "cool",
    "нейтрально": "neutral",
    "теплый": "warm", "тепло": "warm",
    "горячий": "hot", "жаркий": "hot",
}

INTENSITY_ALIASES = {
    "очень_низкая": "very_low", "очень_низкий": "very_low",
    "низкая": "low", "низкий": "low",
    "средняя": "medium", "средний": "medium",
    "высокая": "high", "высокий": "high",
    "очень_высокая": "very_high", "очень_высокий": "very_high",
}

def normalize_empathy(value):
    """Normalize empathy input — accept Russian or English, return English."""
    if value is None:
        return None
    v = str(value).lower()
    if v in EMPATHY:
        return v
    return EMPATHY_ALIASES.get(v, v)

def normalize_temperature(value):
    """Normalize temperature input — accept Russian or English."""
    if value is None:
        return None
    v = str(value).lower()
    return TEMPERATURE_ALIASES.get(v, v)
