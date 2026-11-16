// demo_v63.uc — v63 demo (45s, 3 scenes + 2 transitions) in uLang format
// Maps to existing demo_v63.smt structure

entity @timeline {
    "duration": 45.0
    "bpm": 128
}

entity @pal_dawn {
    "base_r": 0.10, "base_g": 0.05, "base_b": 0.02
    "accent1_r": 1.0, "accent1_g": 0.55, "accent1_b": 0.10
    "accent2_r": 0.0, "accent2_g": 0.0, "accent2_b": 0.0
    "mood": "warm"
}

entity @pal_spire {
    "base_r": 0.02, "base_g": 0.05, "base_b": 0.02
    "accent1_r": 0.85, "accent1_g": 1.0, "accent1_b": 0.10
    "accent2_r": 0.0, "accent2_g": 0.0, "accent2_b": 0.0
    "mood": "tense"
}

entity @pal_fall {
    "base_r": 0.03, "base_g": 0.03, "base_b": 0.04
    "accent1_r": 1.0, "accent1_g": 0.35, "accent1_b": 0.05
    "accent2_r": 0.0, "accent2_g": 0.0, "accent2_b": 0.0
    "mood": "warm"
}

entity @cam_static {
    "fov": 60.0
    "pos": [0.0, 0.0, 5.0]
    "target": [0.0, 0.0, 0.0]
}

entity @scene_dawn {
    "type": "scene"
    "start": 0.0
    "end": 12.0
    "shader": "dawn"
    "palette": @pal_dawn
    "camera": @cam_static
    "intensity": 1.1
    "motion_speed": 0.6
    "pulse": 0.15
    "transition_in": "fade"
    "transition_out": "crossfade"
}

entity @scene_spire {
    "type": "scene"
    "start": 16.5
    "end": 28.5
    "shader": "spire"
    "palette": @pal_spire
    "camera": @cam_static
    "intensity": 1.3
    "motion_speed": 1.0
    "pulse": 0.4
    "transition_in": "crossfade"
    "transition_out": "bloom"
}

entity @scene_fall {
    "type": "scene"
    "start": 33.0
    "end": 45.0
    "shader": "fall"
    "palette": @pal_fall
    "camera": @cam_static
    "intensity": 1.0
    "motion_speed": 0.5
    "pulse": 0.2
    "transition_in": "bloom"
    "transition_out": "fade"
}
