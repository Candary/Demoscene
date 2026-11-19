// compo.uc — пример в синтаксисе uLang v2.1: сущности, ссылки, списки ссылок.
// Проверяется командой:  nxgen check examples/compo.uc

entity @timeline {
    "duration": 45.0
    "bpm": 128
    "beat_intensity": 0.0
}

entity @pal_cold {
    "base_r": 0.05, "base_g": 0.07, "base_b": 0.12
    "accent_r": 0.35, "accent_g": 0.75, "accent_b": 1.0
    "mood": "cold"
}

entity @cam_wide {
    "fov": 82.0
    "pos": [0.0, 0.0, 6.0]
    "target": [0.0, 0.0, -10.0]
}

entity @box_a {
    "size": [1.5, 2.0, 1.5]
    "spin": 0.2
}

entity @scene_intro {
    "start": 0.0
    "end": 24.0
    "camera": @cam_wide
    "palette": @pal_cold
    "objects": [@box_a]
    "shader": "nebula"
}

entity @scene_main {
    "start": 24.0
    "end": 45.0
    "camera": @cam_wide
    "palette": @pal_cold
    "objects": [@box_a]
    "shader": "cozy_room"
}
