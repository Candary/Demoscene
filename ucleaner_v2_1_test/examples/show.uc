// show.uc — таймлайн в синтаксисе v2.1: мета шоу и клипы со ссылками на эффекты.

entity @show {
    "duration": 360.0
    "fps": 60.0
    "bpm": 128.0
    "offset": 0.352
    "seed": 2026
}

entity @fx_bloom {
    "kind": "bloom"
    "amount": 0.4
    "threshold": 0.7
}

entity @fx_grain {
    "kind": "grain"
    "amount": 0.15
}

entity @clip_intro {
    "start": 0.0
    "end": 45.35
    "layer": 10
    "locked": 1
    "effect": @fx_bloom
    "fx": [@fx_bloom, @fx_grain]
}

entity @clip_drop {
    "start": 45.35
    "end": 112.7
    "layer": 10
    "locked": 0
    "effect": @fx_grain
    "fx": [@fx_grain]
}
