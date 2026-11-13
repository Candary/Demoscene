#!/usr/bin/env python3
"""
anim_parser.py — parser for %anim[...] shortcut syntax.

Expands: %anim[cold/anxiety/high-hot/delight/low],(5)
To:      !feat *shader* animate color transition from (synesthesia=cold, empathy=anxiety, intensity=high) to (synesthesia=hot, empathy=delight, intensity=low) speed=5

Usage:
  python3 scripts/anim_parser.py '%anim[cold/anxiety/high-hot/delight/low],(5)'

  Or import:
  from anim_parser import parse_anim
  result = parse_anim('%anim[cold/anxiety/high-hot/delight/low],(5)')
"""
import re
import sys
from pathlib import Path

# Valid values
SYNESTHESIA_VALUES = {"cold", "cool", "neutral", "warm", "hot"}
EMPATHY_VALUES = {"anxiety", "tension", "neutral", "warmth", "delight"}
ENTROPY_VALUES = {"very_low", "low", "medium", "high", "very_high"}

# Russian aliases
SYNESTHESIA_ALIASES = {
    "холодный": "cold", "холодно": "cold",
    "прохладный": "cool",
    "нейтрально": "neutral", "нейтральный": "neutral",
    "теплый": "warm", "тепло": "warm",
    "горячий": "hot", "жаркий": "hot",
}
EMPATHY_ALIASES = {
    "тревога": "anxiety", "тревожный": "anxiety",
    "напряжение": "tension", "напряженный": "tension",
    "нейтрально": "neutral", "нейтральный": "neutral",
    "тепло": "warmth", "теплый": "warmth",
    "радость": "delight", "радостный": "delight",
}
ENTROPY_ALIASES = {
    "очень_низкая": "very_low", "очень_низкий": "very_low",
    "низкая": "low", "низкий": "low",
    "средняя": "medium", "средний": "medium",
    "высокая": "high", "высокий": "high",
    "очень_высокая": "very_high", "очень_высокий": "very_high",
}


def normalize(value, valid_set, aliases, field_name):
    """Normalize a value using aliases, validate against valid set."""
    if value is None:
        return None
    v = str(value).lower().strip()
    if v in aliases:
        v = aliases[v]
    if v not in valid_set:
        raise ValueError(
            f"{field_name}: invalid value '{value}'. "
            f"Valid: {sorted(valid_set)} (or Russian aliases)"
        )
    return v


# Regex for %anim[S1/E1/N1-S2/E2/N2],(speed)
ANIM_PATTERN = re.compile(
    r'^%anim\['
    r'([^/]+)/([^/]+)/([^/]+)'   # S1/E1/N1
    r'-'
    r'([^/]+)/([^/]+)/([^/]+)'   # S2/E2/N2
    r'\]'
    r',\((\d+)\)'                 # (speed)
    r'$'
)


def parse_anim(input_str):
    """Parse %anim[...] syntax and expand to !feat *shader* command.

    Returns dict with:
      - 'valid': bool
      - 'error': str (if invalid)
      - 'expanded': str (the !feat *shader* command)
      - 'parsed': dict with from_state, to_state, speed
      - 'input': str
    """
    s = input_str.strip()
    m = ANIM_PATTERN.match(s)
    if not m:
        return {
            "valid": False,
            "error": (
                f"Syntax error. Expected: "
                f"%anim[S1/E1/N1-S2/E2/N2],(speed). Got: {input_str}"
            ),
            "input": input_str,
        }

    s1, e1, n1, s2, e2, n2, speed = m.groups()

    try:
        s1 = normalize(s1, SYNESTHESIA_VALUES, SYNESTHESIA_ALIASES, "synesthesia1")
        e1 = normalize(e1, EMPATHY_VALUES, EMPATHY_ALIASES, "empathy1")
        n1 = normalize(n1, ENTROPY_VALUES, ENTROPY_ALIASES, "entropy1")
        s2 = normalize(s2, SYNESTHESIA_VALUES, SYNESTHESIA_ALIASES, "synesthesia2")
        e2 = normalize(e2, EMPATHY_VALUES, EMPATHY_ALIASES, "empathy2")
        n2 = normalize(n2, ENTROPY_VALUES, ENTROPY_ALIASES, "entropy2")
    except ValueError as ex:
        return {"valid": False, "error": str(ex), "input": input_str}

    speed_int = int(speed)
    if not 0 <= speed_int <= 10:
        return {
            "valid": False,
            "error": f"speed must be 0-10, got {speed_int}",
            "input": input_str,
        }

    expanded = (
        f"!feat *shader* animate color transition "
        f"from (synesthesia={s1}, empathy={e1}, intensity={n1}) "
        f"to (synesthesia={s2}, empathy={e2}, intensity={n2}) "
        f"speed={speed_int}"
    )

    return {
        "valid": True,
        "expanded": expanded,
        "parsed": {
            "from": {"synesthesia": s1, "empathy": e1, "intensity": n1},
            "to": {"synesthesia": s2, "empathy": e2, "intensity": n2},
            "speed": speed_int,
        },
        "input": input_str,
    }


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python3 anim_parser.py "
            "'%anim[cold/anxiety/high-hot/delight/low],(5)'"
        )
        sys.exit(1)

    input_str = sys.argv[1]
    result = parse_anim(input_str)

    if result["valid"]:
        print("✅ Valid")
        print(f"Expanded: {result['expanded']}")
        print(f"Parsed: {result['parsed']}")
    else:
        print(f"❌ Invalid: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
