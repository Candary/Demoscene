// defaults.h — конфигурация nxGen по умолчанию.
//
// Данные, а не логика: файл config/nxgen.json (если он есть) перекрывает любую
// секцию. Без файла проект работает из любого каталога.
#pragma once

namespace nxgen {

inline const char* kDefaultConfig = R"JSON({
  "version": "1.0",
  "paths": { "output": "out", "report": "report.json", "cache": ".nxgen_cache" },
  "intent": { "default_mood": "calm", "seed": 7 },
  "keywords": {
    "mood": {
      "calm": ["calm", "quiet", "cozy", "soft", "спокойный", "тихий", "уютный"],
      "tense": ["tense", "anxious", "dark", "cold", "тревожный", "тёмный", "холодный"],
      "epic": ["epic", "vast", "huge", "monumental", "эпичный", "огромный"],
      "playful": ["playful", "bright", "toy", "fun", "игривый", "яркий"]
    }
  },
  "palettes": {
    "calm": ["#101820", "#5b7f8c", "#d9e6e8"],
    "tense": ["#0b0b12", "#5a1f2a", "#c94f4f"],
    "epic": ["#070b16", "#2a4f8c", "#f2d479"],
    "playful": ["#241033", "#ff6f91", "#ffe66d"]
  },
  "texture": { "size": 256, "octaves": 5 },
  "mesh": { "default_shape": "box", "segments": 16 },
  "animation": { "mood_speed": { "calm": 0.7, "tense": 1.6, "epic": 1.0, "playful": 1.3 } },
  "postfx": {
    "default_chain": "soft",
    "mood_gain": { "calm": 0.8, "tense": 1.3, "epic": 1.1, "playful": 1.0 },
    "chains": {
      "soft": [
        { "id": "bloom", "amount": 0.4, "threshold": 0.7 },
        { "id": "vignette", "amount": 0.6 },
        { "id": "grain", "amount": 0.15 }
      ],
      "punchy": [
        { "id": "bloom", "amount": 1.2, "threshold": 0.5 },
        { "id": "chromatic_aberration", "amount": 0.35 },
        { "id": "vignette", "amount": 1.0 },
        { "id": "grain", "amount": 0.3 }
      ],
      "glitch": [
        { "id": "scanlines", "amount": 0.5 },
        { "id": "chromatic_aberration", "amount": 0.8 },
        { "id": "grain", "amount": 0.45 },
        { "id": "vignette", "amount": 0.9 }
      ]
    }
  },
  "presets": {
    "text_to_texture": {
      "pipeline": [
        { "id": "intent", "plugin": "input.text", "params": { "text": "{{text}}" } },
        { "id": "tex", "plugin": "texture.fbm", "params": { "size": "{{size}}" }, "inputs": { "palette": "intent.intent" } }
      ],
      "outputs": { "tex": "texture.png" }
    },
    "text_to_obj": {
      "pipeline": [
        { "id": "intent", "plugin": "input.text", "params": { "text": "{{text}}" } },
        { "id": "mesh", "plugin": "mesh.primitive", "params": { "shape": "{{shape}}", "segments": 16 } },
        { "id": "tex", "plugin": "texture.fbm", "params": { "size": 128 }, "inputs": { "palette": "intent.intent" } }
      ],
      "outputs": { "mesh": "model.obj", "tex": "albedo.png" }
    },
    "image_to_obj": {
      "pipeline": [
        { "id": "image", "plugin": "input.image", "params": { "path": "{{image}}", "grid": 32 } },
        { "id": "mesh", "plugin": "mesh.from_image", "params": { "height": "{{height}}", "width": 2.0 }, "inputs": { "image": "image.image" } }
      ],
      "outputs": { "mesh": "relief.obj" }
    },
    "text_to_anim": {
      "pipeline": [
        { "id": "intent", "plugin": "input.text", "params": { "text": "{{text}}" } },
        { "id": "anim", "plugin": "anim.track", "params": { "duration": 8.0, "segments": 6 }, "inputs": { "intent": "intent.intent" } }
      ],
      "outputs": { "anim": "anim.uc" }
    },
    "text_to_postfx": {
      "pipeline": [
        { "id": "intent", "plugin": "input.text", "params": { "text": "{{text}}" } },
        { "id": "fx", "plugin": "postfx.chain", "params": { "chain": "{{chain}}" }, "inputs": { "intent": "intent.intent" } }
      ],
      "outputs": { "fx": "postfx.uc" }
    },
    "text_to_scene": {
      "pipeline": [
        { "id": "intent", "plugin": "input.text", "params": { "text": "{{text}}" } },
        { "id": "tex", "plugin": "texture.fbm", "params": { "size": 256 }, "inputs": { "palette": "intent.intent" } },
        { "id": "mesh", "plugin": "mesh.primitive", "params": { "shape": "{{shape}}", "segments": 16 } },
        { "id": "anim", "plugin": "anim.track", "params": { "duration": 8.0, "segments": 6 }, "inputs": { "intent": "intent.intent" } },
        { "id": "fx", "plugin": "postfx.chain", "params": { "chain": "{{chain}}" }, "inputs": { "intent": "intent.intent" } },
        {
          "id": "scene",
          "plugin": "scene.assemble",
          "params": { "duration": 8.0, "fps": 60.0 },
          "inputs": { "texture": "tex.texture", "mesh": "mesh.mesh", "animation": "anim.animation", "postfx": "fx.postfx" }
        }
      ],
      "outputs": { "tex": "texture.png", "mesh": "model.obj", "anim": "anim.uc", "fx": "postfx.uc", "scene": "scene.uc" }
    }
  }
})JSON";

}  // namespace nxgen
