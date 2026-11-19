// plugins.h — генераторы nxGen: текст/рисунок -> текстура, OBJ, анимация, эффекты.
//
// Каждый плагин — функция (params, inputs, config) -> Artifact. Реестр собирает
// их в одном месте; добавление нового генератора не требует правок ядра.
#pragma once

#include "nxgen.h"

namespace nxgen {

// ---------------------------------------------------------------- helpers
inline std::string hex_of(const Artifact& a) { return hex64(fnv1a64(a.bytes)); }

inline std::string param_string(const Json& params, const char* key, const std::string& def = "") {
    const Json& v = params.at(key);
    return v.is_string() ? v.as_string() : def;
}

inline int param_int(const Json& params, const char* key, int def) { return params.at(key).as_int(def); }
inline float param_float(const Json& params, const char* key, float def) { return params.at(key).as_float(def); }

// Строка палитры из намерения: ["#101820", ...]
inline std::vector<std::array<uint8_t, 3>> palette_from(const Json& intent) {
    std::vector<std::array<uint8_t, 3>> out;
    for (const auto& item : intent.at("palette").items()) {
        std::string hex = item.as_string();
        if (hex.size() != 7 || hex[0] != '#') continue;
        auto parse = [&](int at) {
            auto nib = [](char c) { return uint8_t(c <= '9' ? c - '0' : (c | 0x20) - 'a' + 10); };
            return uint8_t((nib(hex[size_t(at)]) << 4) | nib(hex[size_t(at) + 1]));
        };
        out.push_back({parse(1), parse(3), parse(5)});
    }
    return out;
}

inline std::array<uint8_t, 3> mix_rgb(const std::array<uint8_t, 3>& a, const std::array<uint8_t, 3>& b, float t) {
    t = std::max(0.0f, std::min(1.0f, t));
    return {uint8_t(a[0] + (b[0] - a[0]) * t), uint8_t(a[1] + (b[1] - a[1]) * t),
            uint8_t(a[2] + (b[2] - a[2]) * t)};
}

inline Json intent_of(const std::map<std::string, Artifact>& inputs, const char* port) {
    auto it = inputs.find(port);
    if (it == inputs.end()) return Json::object();
    try {
        return Json::parse(it->second.bytes);
    } catch (const std::exception&) {
        return Json::object();
    }
}

// ---------------------------------------------------------------- вход: текст
inline void add_input_text(Registry& registry) {
    Plugin plugin;
    plugin.id = "input.text";
    plugin.version = "1.0.0";
    plugin.produces = "intent";
    plugin.doc = "Разбирает описание на семантические оси по словарю из конфигурации.";
    plugin.run = [](const Json& params, const std::map<std::string, Artifact>&, const Json& config) {
        std::string text = param_string(params, "text");
        std::istringstream words(text);
        std::set<std::string> tokens;
        std::string word;
        while (words >> word) {
            for (auto& c : word) c = char(std::tolower(static_cast<unsigned char>(c)));
            tokens.insert(word);
        }

        std::string mood;
        std::vector<std::string> hits;
        const Json& keywords = config.at("keywords").at("mood");
        for (const auto& kv : keywords.fields()) {
            for (const auto& synonym : kv.second.items()) {
                if (tokens.count(synonym.as_string())) {
                    if (mood.empty()) mood = kv.first;
                    hits.push_back(synonym.as_string());
                }
            }
        }
        if (mood.empty()) mood = config.at("intent").at("default_mood").as_string("calm");

        Json intent = Json::object();
        intent.set("text", text);
        intent.set("mood", mood);
        Json palette = Json::array();
        for (const auto& color : config.at("palettes").at(mood).items()) palette.push(color.as_string());
        intent.set("palette", palette);
        Json hit_list = Json::array();
        for (const auto& hit : hits) hit_list.push(hit);
        intent.set("hits", hit_list);
        return Artifact{"intent", intent.dump(), Json::object()};
    };
    registry.add(std::move(plugin));
}

// ---------------------------------------------------------------- вход: рисунок (PPM/PGM)
inline void add_input_image(Registry& registry) {
    Plugin plugin;
    plugin.id = "input.image";
    plugin.version = "1.0.0";
    plugin.produces = "image";
    plugin.doc = "Читает PPM/PGM: палитра, яркость, поле яркости для выдавливания.";
    plugin.run = [](const Json& params, const std::map<std::string, Artifact>&, const Json& config) {
        std::string path = param_string(params, "path");
        if (path.empty()) throw std::runtime_error("input.image: 'path' is required");
        std::string data = read_file(path);

        // P6/P5: "P6\n<w> <h>\n<max>\n" + binary payload
        if (data.size() < 2 || data[0] != 'P' || (data[1] != '6' && data[1] != '5'))
            throw std::runtime_error("input.image: only PPM(P6)/PGM(P5) are supported");
        const bool color = data[1] == '6';
        size_t pos = 2;
        auto next_int = [&]() {
            while (pos < data.size() && !std::isdigit(static_cast<unsigned char>(data[pos]))) ++pos;
            int value = 0;
            while (pos < data.size() && std::isdigit(static_cast<unsigned char>(data[pos]))) {
                value = value * 10 + (data[pos] - '0');
                ++pos;
            }
            return value;
        };
        int width = next_int(), height = next_int(), maxval = next_int();
        if (width <= 0 || height <= 0 || maxval <= 0) throw std::runtime_error("input.image: bad header");
        // После maxval — РОВНО один пробельный символ. Пропускать всю серию
        // нельзя: пиксели начинаются сразу и могут совпасть с \t или \n.
        if (pos < data.size() && std::isspace(static_cast<unsigned char>(data[pos]))) ++pos;

        const int channels = color ? 3 : 1;
        if (data.size() < pos + size_t(width) * size_t(height) * size_t(channels))
            throw std::runtime_error("input.image: truncated pixel data");

        const int grid = std::max(2, param_int(params, "grid", 24));
        std::vector<float> field(size_t(grid) * size_t(grid), 0.0f);
        std::map<uint32_t, int> counts;

        for (int y = 0; y < height; ++y) {
            for (int x = 0; x < width; ++x) {
                size_t at = pos + (size_t(y) * size_t(width) + size_t(x)) * size_t(channels);
                uint8_t r = uint8_t(data[at]);
                uint8_t g = color ? uint8_t(data[at + 1]) : r;
                uint8_t b = color ? uint8_t(data[at + 2]) : r;
                uint32_t key = (uint32_t(r / 32) << 10) | (uint32_t(g / 32) << 5) | uint32_t(b / 32);
                counts[key]++;
                int gx = std::min(grid - 1, x * grid / width);
                int gy = std::min(grid - 1, y * grid / height);
                float luminance = (0.2126f * r + 0.7152f * g + 0.0722f * b) / 255.0f;
                field[size_t(gy) * size_t(grid) + size_t(gx)] += luminance;
            }
        }
        for (auto& value : field) value /= float(std::max(1, (width / grid) * (height / grid)));

        std::vector<std::pair<int, uint32_t>> ranked;
        for (const auto& kv : counts) ranked.push_back({kv.second, kv.first});
        std::sort(ranked.begin(), ranked.end(), [](auto& a, auto& b) { return a.first > b.first; });

        Json intent = Json::object();
        Json palette = Json::array();
        for (size_t i = 0; i < ranked.size() && i < 5; ++i) {
            uint32_t key = ranked[i].second;
            int r = int((key >> 10) & 31) * 8 + 4;
            int g = int((key >> 5) & 31) * 8 + 4;
            int b = int(key & 31) * 8 + 4;
            char buf[8];
            std::snprintf(buf, sizeof(buf), "#%02x%02x%02x", r, g, b);
            palette.push(std::string(buf));
        }
        intent.set("palette", palette);
        intent.set("width", width);
        intent.set("height", height);
        Json grid_json = Json::array();
        for (float value : field) grid_json.push(double(value));
        intent.set("field", grid_json);
        intent.set("grid", grid);
        intent.set("source", path);
        return Artifact{"image", intent.dump(), Json::object()};
    };
    registry.add(std::move(plugin));
}

// ---------------------------------------------------------------- текстуры
inline void add_texture_fbm(Registry& registry) {
    Plugin plugin;
    plugin.id = "texture.fbm";
    plugin.version = "1.1.0";
    plugin.produces = "texture";
    plugin.consumes = {"palette"};
    plugin.doc = "Фрактальный шум с искажением координат; палитра из intent.";
    plugin.run = [](const Json& params, const std::map<std::string, Artifact>& inputs, const Json&) {
        int size = std::max(16, std::min(1024, param_int(params, "size", 256)));
        int octaves = std::max(1, std::min(8, param_int(params, "octaves", 5)));
        float scale = param_float(params, "scale", 4.0f) / float(size);
        float contrast = param_float(params, "contrast", 1.0f);
        uint32_t seed = uint32_t(param_int(params, "seed", 1));

        auto palette = palette_from(intent_of(inputs, "palette"));
        std::array<uint8_t, 3> a = palette.size() > 0 ? palette[0] : std::array<uint8_t, 3>{16, 24, 32};
        std::array<uint8_t, 3> b = palette.size() > 1 ? palette[1] : std::array<uint8_t, 3>{217, 230, 232};

        std::vector<uint8_t> pixels(size_t(size) * size_t(size) * 3);
        for (int y = 0; y < size; ++y) {
            for (int x = 0; x < size; ++x) {
                float u = float(x) * scale, v = float(y) * scale;
                float value = fbm(seed, u, v, octaves);
                value = std::min(1.0f, std::max(0.0f, (value - 0.5f) * contrast + 0.5f));
                auto rgb = mix_rgb(a, b, value);
                size_t at = (size_t(y) * size_t(size) + size_t(x)) * 3;
                pixels[at] = rgb[0];
                pixels[at + 1] = rgb[1];
                pixels[at + 2] = rgb[2];
            }
        }
        Artifact out{"texture", make_png(size, size, pixels), Json::object()};
        out.meta.set("width", size);
        out.meta.set("height", size);
        out.meta.set("bytes", int(out.bytes.size()));
        return out;
    };
    registry.add(std::move(plugin));
}

inline void add_texture_stripes(Registry& registry) {
    Plugin plugin;
    plugin.id = "texture.stripes";
    plugin.version = "1.0.0";
    plugin.produces = "texture";
    plugin.consumes = {"palette"};
    plugin.doc = "Диагональные полосы с мягким краем.";
    plugin.run = [](const Json& params, const std::map<std::string, Artifact>& inputs, const Json&) {
        int size = std::max(16, std::min(1024, param_int(params, "size", 256)));
        float period = std::max(2.0f, param_float(params, "period", 16.0f));
        float angle = param_float(params, "angle", 45.0f) * 3.14159265f / 180.0f;
        float softness = std::max(0.001f, param_float(params, "softness", 0.15f));

        auto palette = palette_from(intent_of(inputs, "palette"));
        std::array<uint8_t, 3> a = palette.size() > 0 ? palette[0] : std::array<uint8_t, 3>{16, 24, 32};
        std::array<uint8_t, 3> b = palette.size() > 1 ? palette[1] : std::array<uint8_t, 3>{255, 230, 109};

        float ca = std::cos(angle), sa = std::sin(angle);
        std::vector<uint8_t> pixels(size_t(size) * size_t(size) * 3);
        for (int y = 0; y < size; ++y) {
            for (int x = 0; x < size; ++x) {
                float u = (float(x) * ca + float(y) * sa) / period;
                float phase = u - std::floor(u);
                float value = phase > 0.5f ? 1.0f : 0.0f;
                auto rgb = mix_rgb(a, b, value);
                size_t at = (size_t(y) * size_t(size) + size_t(x)) * 3;
                pixels[at] = rgb[0];
                pixels[at + 1] = rgb[1];
                pixels[at + 2] = rgb[2];
            }
        }
        (void)softness;
        Artifact out{"texture", make_png(size, size, pixels), Json::object()};
        out.meta.set("width", size);
        out.meta.set("height", size);
        out.meta.set("bytes", int(out.bytes.size()));
        return out;
    };
    registry.add(std::move(plugin));
}

// ---------------------------------------------------------------- меши
inline void add_mesh_primitive(Registry& registry) {
    Plugin plugin;
    plugin.id = "mesh.primitive";
    plugin.version = "1.0.0";
    plugin.produces = "mesh";
    plugin.doc = "Параметрическая фигура: box, sphere, torus, plane.";
    plugin.run = [](const Json& params, const std::map<std::string, Artifact>&, const Json&) {
        std::string shape = param_string(params, "shape", "box");
        float sx = 1.0f, sy = 1.0f, sz = 1.0f;
        if (params.at("size").is_array() && params.at("size").size() == 3) {
            sx = params.at("size").at(0).as_float(1.0f);
            sy = params.at("size").at(1).as_float(1.0f);
            sz = params.at("size").at(2).as_float(1.0f);
        }
        int segments = std::max(3, std::min(64, param_int(params, "segments", 16)));

        Mesh mesh;
        if (shape == "box") {
            float hx = sx * 0.5f, hy = sy * 0.5f, hz = sz * 0.5f;
            mesh.vertices = {{-hx, -hy, -hz}, {hx, -hy, -hz}, {hx, hy, -hz}, {-hx, hy, -hz},
                             {-hx, -hy, hz},  {hx, -hy, hz},  {hx, hy, hz},  {-hx, hy, hz}};
            mesh.faces = {{0, 2, 1}, {0, 3, 2}, {4, 5, 6}, {4, 6, 7}, {0, 1, 5}, {0, 5, 4},
                          {1, 2, 6}, {1, 6, 5}, {2, 3, 7}, {2, 7, 6}, {3, 0, 4}, {3, 4, 7}};
        } else if (shape == "plane") {
            for (int j = 0; j <= segments; ++j) {
                for (int i = 0; i <= segments; ++i) {
                    float u = float(i) / segments - 0.5f, v = float(j) / segments - 0.5f;
                    mesh.vertices.push_back({u * sx, 0.0f, v * sz});
                }
            }
            for (int j = 0; j < segments; ++j) {
                for (int i = 0; i < segments; ++i) {
                    int a = j * (segments + 1) + i, b = a + 1, c = a + segments + 1, d = c + 1;
                    mesh.faces.push_back({a, c, b});
                    mesh.faces.push_back({b, c, d});
                }
            }
        } else if (shape == "sphere") {
            int rings = std::max(3, segments / 2);
            for (int r = 0; r <= rings; ++r) {
                float theta = 3.14159265f * float(r) / float(rings);
                for (int s = 0; s < segments; ++s) {
                    float phi = 6.2831853f * float(s) / float(segments);
                    mesh.vertices.push_back({sx * 0.5f * std::sin(theta) * std::cos(phi),
                                             sy * 0.5f * std::cos(theta),
                                             sz * 0.5f * std::sin(theta) * std::sin(phi)});
                }
            }
            for (int r = 0; r < rings; ++r) {
                for (int s = 0; s < segments; ++s) {
                    int a = r * segments + s;
                    int b = r * segments + (s + 1) % segments;
                    int c = (r + 1) * segments + s;
                    int d = (r + 1) * segments + (s + 1) % segments;
                    mesh.faces.push_back({a, c, b});
                    mesh.faces.push_back({b, c, d});
                }
            }
        } else {  // torus
            float major = std::max(sx, sz) * 0.35f, minor = std::max(0.01f, std::min(sx, sy) * 0.25f);
            int rings = std::max(6, segments), sides = std::max(6, segments);
            for (int i = 0; i < rings; ++i) {
                float u = 6.2831853f * float(i) / float(rings);
                for (int j = 0; j < sides; ++j) {
                    float v = 6.2831853f * float(j) / float(sides);
                    mesh.vertices.push_back({(major + minor * std::cos(v)) * std::cos(u),
                                             minor * std::sin(v),
                                             (major + minor * std::cos(v)) * std::sin(u)});
                }
            }
            for (int i = 0; i < rings; ++i) {
                for (int j = 0; j < sides; ++j) {
                    int a = i * sides + j;
                    int b = i * sides + (j + 1) % sides;
                    int c = ((i + 1) % rings) * sides + j;
                    int d = ((i + 1) % rings) * sides + (j + 1) % sides;
                    mesh.faces.push_back({a, c, b});
                    mesh.faces.push_back({b, c, d});
                }
            }
        }

        float lo[3], hi[3];
        mesh.bounds(lo, hi);
        Artifact out{"mesh", mesh.obj(shape), Json::object()};
        out.meta.set("shape", shape);
        out.meta.set("vertices", int(mesh.vertices.size()));
        out.meta.set("faces", int(mesh.faces.size()));
        Json size = Json::array();
        for (int i = 0; i < 3; ++i) size.push(double(hi[i] - lo[i]));
        out.meta.set("size", size);
        return out;
    };
    registry.add(std::move(plugin));
}

inline void add_mesh_from_image(Registry& registry) {
    Plugin plugin;
    plugin.id = "mesh.from_image";
    plugin.version = "1.0.0";
    plugin.produces = "mesh";
    plugin.consumes = {"image"};
    plugin.doc = "Выдавливает карту яркости рисунка в поверхность.";
    plugin.run = [](const Json& params, const std::map<std::string, Artifact>& inputs, const Json&) {
        auto it = inputs.find("image");
        if (it == inputs.end()) throw std::runtime_error("mesh.from_image: image input is required");
        Json image = Json::parse(it->second.bytes);
        int grid = image.at("grid").as_int(24);
        float height = param_float(params, "height", 0.5f);
        float width = param_float(params, "width", 2.0f);
        bool invert = params.at("invert").as_bool(false);

        const auto& field = image.at("field").items();
        if (int(field.size()) != grid * grid) throw std::runtime_error("mesh.from_image: bad field");
        float step = width / float(std::max(1, grid - 1));

        Mesh mesh;
        for (int j = 0; j < grid; ++j) {
            for (int i = 0; i < grid; ++i) {
                float value = field[size_t(j) * size_t(grid) + size_t(i)].as_float();
                if (invert) value = 1.0f - value;
                mesh.vertices.push_back({(float(i) - grid * 0.5f) * step, value * height,
                                         (float(j) - grid * 0.5f) * step});
            }
        }
        for (int j = 0; j < grid - 1; ++j) {
            for (int i = 0; i < grid - 1; ++i) {
                int a = j * grid + i, b = a + 1, c = a + grid, d = c + 1;
                mesh.faces.push_back({a, c, b});
                mesh.faces.push_back({b, c, d});
            }
        }
        float lo[3], hi[3];
        mesh.bounds(lo, hi);
        Artifact out{"mesh", mesh.obj("relief"), Json::object()};
        out.meta.set("shape", "heightfield");
        out.meta.set("vertices", int(mesh.vertices.size()));
        out.meta.set("faces", int(mesh.faces.size()));
        Json size = Json::array();
        for (int i = 0; i < 3; ++i) size.push(double(hi[i] - lo[i]));
        out.meta.set("size", size);
        return out;
    };
    registry.add(std::move(plugin));
}

// ---------------------------------------------------------------- анимация и эффекты
inline void add_anim_track(Registry& registry) {
    Plugin plugin;
    plugin.id = "anim.track";
    plugin.version = "1.0.0";
    plugin.produces = "animation";
    plugin.consumes = {"intent"};
    plugin.doc = "Сегменты анимации в uLang: канал, время, от-до, сглаживание.";
    plugin.run = [](const Json& params, const std::map<std::string, Artifact>& inputs, const Json& config) {
        Json intent = intent_of(inputs, "intent");
        std::string channel = param_string(params, "channel", "pos_y");
        float duration = param_float(params, "duration", 8.0f);
        int segments = std::max(1, std::min(32, param_int(params, "segments", 4)));
        float amplitude = param_float(params, "amplitude", 1.0f);
        float tempo = 1.0f;
        const Json& speeds = config.at("animation").at("mood_speed");
        if (intent.has("mood") && speeds.has(intent.at("mood").as_string())) {
            tempo = speeds.at(intent.at("mood").as_string()).as_float(1.0f);
        }
        duration /= std::max(0.1f, tempo);

        std::ostringstream out;
        out << "// nxgen: анимация\n";
        for (int i = 0; i < segments; ++i) {
            float start = duration * float(i) / float(segments);
            float low = (i % 2 == 0) ? amplitude : 0.0f;
            float high = (i % 2 == 0) ? 0.0f : amplitude;
            out << "entity @seg_" << i << " {\n"
                << "    \"channel\": \"" << channel << "\"\n"
                << "    \"start\": " << start << "\n"
                << "    \"duration\": " << duration / float(segments) << "\n"
                << "    \"from_value\": " << low << "\n"
                << "    \"to_value\": " << high << "\n"
                << "    \"ease\": 1.0\n"
                << "}\n";
        }
        Artifact out_artifact{"animation", out.str(), Json::object()};
        out_artifact.meta.set("segments", segments);
        out_artifact.meta.set("channel", channel);
        return out_artifact;
    };
    registry.add(std::move(plugin));
}

inline void add_postfx_chain(Registry& registry) {
    Plugin plugin;
    plugin.id = "postfx.chain";
    plugin.version = "1.0.0";
    plugin.produces = "postfx";
    plugin.consumes = {"intent"};
    plugin.doc = "Цепочка постэффектов в uLang (порядок, сила, порог).";
    plugin.run = [](const Json& params, const std::map<std::string, Artifact>& inputs, const Json& config) {
        Json intent = intent_of(inputs, "intent");
        std::string chain = param_string(params, "chain", config.at("postfx").at("default_chain").as_string("soft"));
        float intensity = param_float(params, "intensity", 1.0f);
        const Json& chains = config.at("postfx").at("chains");
        if (!chains.has(chain)) throw std::runtime_error("postfx.chain: unknown chain '" + chain + "'");

        float gain = 1.0f;
        if (intent.has("mood")) {
            const Json& mood_gain = config.at("postfx").at("mood_gain");
            if (mood_gain.has(intent.at("mood").as_string()))
                gain = mood_gain.at(intent.at("mood").as_string()).as_float(1.0f);
        }

        std::ostringstream out;
        out << "// nxgen: постэффекты\n";
        int order = 0;
        for (const auto& effect : chains.at(chain).items()) {
            std::string id = effect.at("id").as_string();
            float amount = effect.at("amount").as_float(1.0f) * intensity * gain;
            float threshold = effect.at("threshold").as_float(0.0f);
            out << "entity @fx_" << id << " {\n"
                << "    \"kind\": \"" << id << "\"\n"
                << "    \"order\": " << float(order++) << "\n"
                << "    \"amount\": " << amount << "\n"
                << "    \"threshold\": " << threshold << "\n"
                << "}\n";
        }
        Artifact artifact{"postfx", out.str(), Json::object()};
        artifact.meta.set("chain", chain);
        artifact.meta.set("count", order);
        return artifact;
    };
    registry.add(std::move(plugin));
}

// ---------------------------------------------------------------- сборка сцены
inline std::vector<std::string> entity_names(const std::string& ulang) {
    std::vector<std::string> names;
    size_t pos = 0;
    while ((pos = ulang.find("entity @", pos)) != std::string::npos) {
        pos += 8;
        size_t end = pos;
        while (end < ulang.size() && (std::isalnum(static_cast<unsigned char>(ulang[end])) || ulang[end] == '_')) ++end;
        names.push_back("@" + ulang.substr(pos, end - pos));
        pos = end;
    }
    return names;
}

inline void add_scene_assemble(Registry& registry) {
    Plugin plugin;
    plugin.id = "scene.assemble";
    plugin.version = "1.0.0";
    plugin.produces = "scene";
    plugin.consumes = {"texture", "mesh", "animation", "postfx"};
    plugin.doc = "Сводит ассет, анимацию и эффекты в один uLang-файл.";
    plugin.run = [](const Json& params, const std::map<std::string, Artifact>& inputs, const Json&) {
        std::string animation, postfx;
        auto anim_it = inputs.find("animation");
        if (anim_it != inputs.end()) animation = anim_it->second.bytes;
        auto fx_it = inputs.find("postfx");
        if (fx_it != inputs.end()) postfx = fx_it->second.bytes;

        std::string texture_hash = "0000000000000000", mesh_hash = "0000000000000000";
        int vertices = 0, faces = 0;
        auto tex_it = inputs.find("texture");
        if (tex_it != inputs.end()) texture_hash = hex_of(tex_it->second);
        auto mesh_it = inputs.find("mesh");
        if (mesh_it != inputs.end()) {
            mesh_hash = hex_of(mesh_it->second);
            vertices = mesh_it->second.meta.at("vertices").as_int(0);
            faces = mesh_it->second.meta.at("faces").as_int(0);
        }

        std::ostringstream out;
        out << "// nxgen: сцена\n";
        out << animation;
        out << postfx;
        out << "entity @asset_0 {\n"
            << "    \"texture\": \"" << texture_hash << "\"\n"
            << "    \"mesh\": \"" << mesh_hash << "\"\n"
            << "    \"vertices\": " << float(vertices) << "\n"
            << "    \"faces\": " << float(faces) << "\n"
            << "}\n";
        out << "entity @scene {\n"
            << "    \"duration\": " << param_float(params, "duration", 8.0f) << "\n"
            << "    \"fps\": " << param_float(params, "fps", 60.0f) << "\n"
            << "    \"asset\": @asset_0\n";
        std::vector<std::string> anim_names = entity_names(animation);
        std::vector<std::string> fx_names = entity_names(postfx);
        out << "    \"anim\": [";
        for (size_t i = 0; i < anim_names.size(); ++i) out << (i ? ", " : "") << anim_names[i];
        out << "]\n    \"fx\": [";
        for (size_t i = 0; i < fx_names.size(); ++i) out << (i ? ", " : "") << fx_names[i];
        out << "]\n}\n";

        Artifact artifact{"scene", out.str(), Json::object()};
        artifact.meta.set("vertices", vertices);
        artifact.meta.set("anim", int(anim_names.size()));
        artifact.meta.set("fx", int(fx_names.size()));
        return artifact;
    };
    registry.add(std::move(plugin));
}

inline Registry default_registry() {
    Registry registry;
    add_input_text(registry);
    add_input_image(registry);
    add_texture_fbm(registry);
    add_texture_stripes(registry);
    add_mesh_primitive(registry);
    add_mesh_from_image(registry);
    add_anim_track(registry);
    add_postfx_chain(registry);
    add_scene_assemble(registry);
    return registry;
}

}  // namespace nxgen
