// nxgen.h — «комбайн» генерации на C++: граф, плагины, артефакты.
//
// Тот же контракт, что был в Python-версии, но без интерпретатора: плагин —
// функция, задача — JSON, артефакт — байты + метаданные. Ни одного имени файла
// в коде: имена выходов приходят из конфигурации или задания.
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <functional>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "json.h"

namespace nxgen {

// ---------------------------------------------------------------- артефакт
struct Artifact {
    std::string kind;
    std::string bytes;   // содержимое: PNG, OBJ, uLang, JSON
    Json meta = Json::object();

    bool empty() const { return bytes.empty(); }
};

// ---------------------------------------------------------------- плагин
struct Plugin {
    std::string id;
    std::string version;
    std::string produces;
    std::vector<std::string> consumes;
    std::string doc;
    std::function<Artifact(const Json& params, const std::map<std::string, Artifact>& inputs, const Json& config)> run;
};

class Registry {
public:
    void add(Plugin plugin) {
        if (plugins_.count(plugin.id)) throw std::runtime_error("duplicate plugin: " + plugin.id);
        plugins_[plugin.id] = std::move(plugin);
    }

    const Plugin& get(const std::string& id) const {
        auto it = plugins_.find(id);
        if (it == plugins_.end()) throw std::runtime_error("unknown plugin: " + id);
        return it->second;
    }

    bool has(const std::string& id) const { return plugins_.count(id) > 0; }

    std::vector<std::string> ids() const {
        std::vector<std::string> out;
        for (const auto& kv : plugins_) out.push_back(kv.first);
        return out;
    }

    Json describe() const {
        Json arr = Json::array();
        for (const auto& kv : plugins_) {
            Json item = Json::object();
            item.set("id", kv.second.id);
            item.set("version", kv.second.version);
            item.set("produces", kv.second.produces);
            item.set("doc", kv.second.doc);
            Json consumes = Json::array();
            for (const auto& c : kv.second.consumes) consumes.push(c);
            item.set("consumes", consumes);
            arr.push(item);
        }
        return arr;
    }

private:
    std::map<std::string, Plugin> plugins_;
};

// ---------------------------------------------------------------- узел и граф
struct Node {
    std::string id;
    std::string plugin;
    Json params = Json::object();
    std::map<std::string, std::string> inputs;   // порт -> "node.port"
    bool enabled = true;
};

inline Node node_from_json(const Json& data) {
    Node node;
    node.id = data.at("id").as_string();
    node.plugin = data.at("plugin").as_string();
    if (node.id.empty() || node.plugin.empty()) throw std::runtime_error("node needs 'id' and 'plugin'");
    node.params = data.at("params");
    if (!node.params.is_object()) node.params = Json::object();
    for (const auto& kv : data.at("inputs").fields()) node.inputs[kv.first] = kv.second.as_string();
    node.enabled = data.has("enabled") ? data.at("enabled").as_bool(true) : true;
    return node;
}

class Graph {
public:
    explicit Graph(std::vector<Node> nodes) : nodes_(std::move(nodes)) {
        for (auto& node : nodes_) by_id_[node.id] = &node;
        if (by_id_.size() != nodes_.size()) throw std::runtime_error("duplicate node id");
    }

    const std::vector<Node>& nodes() const { return nodes_; }

    // Проверка ссылок и порядок выполнения (топологическая сортировка).
    std::vector<std::string> validate(const Registry& registry) const {
        for (const auto& node : nodes_) {
            const Plugin& plugin = registry.get(node.plugin);
            for (const auto& kv : node.inputs) {
                const std::string& ref = kv.second;
                size_t dot = ref.find('.');
                if (dot == std::string::npos) throw std::runtime_error("node '" + node.id + "': input must be 'node.port'");
                std::string source = ref.substr(0, dot);
                std::string port = ref.substr(dot + 1);
                auto it = by_id_.find(source);
                if (it == by_id_.end()) throw std::runtime_error("node '" + node.id + "': unknown input node '" + source + "'");
                const Plugin& source_plugin = registry.get(it->second->plugin);
                if (port != source_plugin.produces)
                    throw std::runtime_error("node '" + node.id + "': '" + source + "' produces '" +
                                             source_plugin.produces + "', not '" + port + "'");
                bool accepted = std::find(plugin.consumes.begin(), plugin.consumes.end(), kv.first) != plugin.consumes.end();
                if (!accepted) throw std::runtime_error("node '" + node.id + "': plugin '" + node.plugin +
                                                        "' does not accept input '" + kv.first + "'");
            }
        }
        return order();
    }

    std::vector<std::string> order() const {
        std::map<std::string, int> indegree;
        std::map<std::string, std::vector<std::string>> edges;
        for (const auto& node : nodes_) indegree[node.id] = 0;
        for (const auto& node : nodes_) {
            for (const auto& kv : node.inputs) {
                std::string source = kv.second.substr(0, kv.second.find('.'));
                edges[source].push_back(node.id);
                indegree[node.id]++;
            }
        }
        std::vector<std::string> queue, out;
        for (const auto& node : nodes_) if (indegree[node.id] == 0) queue.push_back(node.id);
        while (!queue.empty()) {
            const std::string current = queue.front();
            queue.erase(queue.begin());
            out.push_back(current);
            for (const auto& next : edges[current]) if (--indegree[next] == 0) queue.push_back(next);
        }
        if (out.size() != nodes_.size()) throw std::runtime_error("cycle in generation graph");
        return out;
    }

    std::map<std::string, Artifact> execute(
        const Registry& registry,
        const Json& config,
        bool use_cache,
        const std::function<void(const std::string&, const std::string&, bool)>& progress = nullptr) const {
        std::map<std::string, Artifact> results;
        for (const auto& id : validate(registry)) {
            const Node& node = *by_id_.at(id);
            const Plugin& plugin = registry.get(node.plugin);

            std::map<std::string, Artifact> inputs;
            for (const auto& kv : node.inputs) {
                std::string source = kv.second.substr(0, kv.second.find('.'));
                inputs[kv.first] = results.at(source);
            }

            if (use_cache) {
                auto it = cache_.find(id);
                if (it != cache_.end()) {
                    results[id] = it->second;
                    if (progress) progress(id, plugin.id, true);
                    continue;
                }
            }
            Artifact artifact = plugin.run(node.params, inputs, config);
            if (artifact.kind != plugin.produces)
                throw std::runtime_error("plugin '" + plugin.id + "' declared '" + plugin.produces +
                                         "' but produced '" + artifact.kind + "'");
            results[id] = artifact;
            if (progress) progress(id, plugin.id, false);
        }
        return results;
    }

private:
    std::vector<Node> nodes_;
    std::map<std::string, const Node*> by_id_;
    mutable std::map<std::string, Artifact> cache_;
};

// ---------------------------------------------------------------- PNG (без zlib)
namespace detail {

inline uint32_t crc32_bytes(const uint8_t* data, size_t len) {
    static uint32_t table[256];
    static bool ready = false;
    if (!ready) {
        for (uint32_t i = 0; i < 256; ++i) {
            uint32_t c = i;
            for (int k = 0; k < 8; ++k) c = (c & 1) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
            table[i] = c;
        }
        ready = true;
    }
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; ++i) crc = table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8);
    return crc ^ 0xFFFFFFFFu;
}

inline uint32_t adler32_bytes(const uint8_t* data, size_t len) {
    uint32_t a = 1, b = 0;
    for (size_t i = 0; i < len; ++i) {
        a = (a + data[i]) % 65521u;
        b = (b + a) % 65521u;
    }
    return (b << 16) | a;
}

inline void put_u32(std::string& out, uint32_t v) {
    out.push_back(char(v >> 24));
    out.push_back(char((v >> 16) & 0xFF));
    out.push_back(char((v >> 8) & 0xFF));
    out.push_back(char(v & 0xFF));
}

// deflate «stored»: PNG валиден, но без сжатия. Компромисс осознанный:
// проект не тянет zlib, а размер текстуры не критичен.
inline std::string deflate_stored(const std::string& raw) {
    std::string out;
    out.push_back(char(0x78));
    out.push_back(char(0x01));
    size_t pos = 0;
    while (pos < raw.size()) {
        size_t chunk = std::min<size_t>(65535, raw.size() - pos);
        bool final_block = pos + chunk >= raw.size();
        out.push_back(char(final_block ? 1 : 0));
        out.push_back(char(chunk & 0xFF));
        out.push_back(char((chunk >> 8) & 0xFF));
        out.push_back(char(~chunk & 0xFF));
        out.push_back(char((~chunk >> 8) & 0xFF));
        out.append(raw, pos, chunk);
        pos += chunk;
    }
    put_u32(out, adler32_bytes(reinterpret_cast<const uint8_t*>(raw.data()), raw.size()));
    return out;
}

}  // namespace detail

// pixels: RGB, row-major
inline std::string make_png(int width, int height, const std::vector<uint8_t>& rgb) {
    if (int(rgb.size()) != width * height * 3) throw std::runtime_error("png: bad pixel buffer");
    std::string raw;
    raw.reserve(size_t(height) * (size_t(width) * 3 + 1));
    for (int y = 0; y < height; ++y) {
        raw.push_back('\0');
        raw.append(reinterpret_cast<const char*>(&rgb[size_t(y) * size_t(width) * 3]), size_t(width) * 3);
    }
    std::string out = "\x89PNG\r\n\x1a\n";
    auto chunk = [&](const char* tag, const std::string& payload) {
        detail::put_u32(out, uint32_t(payload.size()));
        std::string body = std::string(tag) + payload;
        out += body;
        detail::put_u32(out, detail::crc32_bytes(reinterpret_cast<const uint8_t*>(body.data()), body.size()));
    };
    std::string ihdr;
    detail::put_u32(ihdr, uint32_t(width));
    detail::put_u32(ihdr, uint32_t(height));
    ihdr.push_back(8);   // bit depth
    ihdr.push_back(2);   // truecolor
    ihdr.push_back(0);
    ihdr.push_back(0);
    ihdr.push_back(0);
    chunk("IHDR", ihdr);
    chunk("IDAT", detail::deflate_stored(raw));
    chunk("IEND", "");
    return out;
}

// ---------------------------------------------------------------- OBJ
struct Mesh {
    std::vector<std::array<float, 3>> vertices;
    std::vector<std::array<int, 3>> faces;

    std::string obj(const std::string& name) const {
        std::ostringstream out;
        out << "# nxgen OBJ\n" << "o " << name << "\n";
        for (const auto& v : vertices) out << "v " << v[0] << ' ' << v[1] << ' ' << v[2] << "\n";
        for (const auto& f : faces) out << "f " << (f[0] + 1) << ' ' << (f[1] + 1) << ' ' << (f[2] + 1) << "\n";
        return out.str();
    }

    void bounds(float out_min[3], float out_max[3]) const {
        for (int i = 0; i < 3; ++i) { out_min[i] = 1e30f; out_max[i] = -1e30f; }
        for (const auto& v : vertices) {
            for (int i = 0; i < 3; ++i) {
                out_min[i] = std::min(out_min[i], v[i]);
                out_max[i] = std::max(out_max[i], v[i]);
            }
        }
        if (vertices.empty()) { for (int i = 0; i < 3; ++i) { out_min[i] = out_max[i] = 0.0f; } }
    }
};

// ---------------------------------------------------------------- утилиты
inline uint64_t fnv1a64(const std::string& data) {
    uint64_t h = 1469598103934665603ull;
    for (unsigned char c : data) { h ^= c; h *= 1099511628211ull; }
    return h;
}

inline uint32_t fnv1a32(const std::string& data) {
    uint32_t h = 2166136261u;
    for (unsigned char c : data) { h ^= c; h *= 16777619u; }
    return h;
}

inline std::string hex64(uint64_t v) {
    static const char* digits = "0123456789abcdef";
    std::string out(16, '0');
    for (int i = 15; i >= 0; --i) { out[size_t(i)] = digits[v & 0xF]; v >>= 4; }
    return out;
}

inline uint32_t hash01(uint32_t seed, int32_t x, int32_t y) {
    uint32_t h = seed * 0x9E3779B1u ^ uint32_t(x) * 0x85EBCA77u ^ uint32_t(y) * 0xC2B2AE3Du;
    h ^= h >> 15; h *= 0x2545F491u; h ^= h >> 13;
    return h & 0x00FFFFFFu;
}

inline float noise01(uint32_t seed, int32_t x, int32_t y) {
    return float(hash01(seed, x, y)) / float(0x01000000u);
}

inline float smooth(float t) { return t * t * (3.0f - 2.0f * t); }

inline float value_noise(uint32_t seed, float x, float y) {
    int32_t ix = int32_t(std::floor(x)), iy = int32_t(std::floor(y));
    float fx = smooth(x - ix), fy = smooth(y - iy);
    float a = noise01(seed, ix, iy), b = noise01(seed, ix + 1, iy);
    float c = noise01(seed, ix, iy + 1), d = noise01(seed, ix + 1, iy + 1);
    float top = a + (b - a) * fx;
    float bottom = c + (d - c) * fx;
    return top + (bottom - top) * fy;
}

inline float fbm(uint32_t seed, float x, float y, int octaves) {
    float total = 0.0f, amplitude = 1.0f, frequency = 1.0f, norm = 0.0f;
    for (int i = 0; i < std::max(1, octaves); ++i) {
        total += amplitude * value_noise(seed + uint32_t(i) * 101u, x * frequency, y * frequency);
        norm += amplitude;
        amplitude *= 0.5f;
        frequency *= 2.0f;
    }
    return total / norm;
}

inline std::string read_file(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("cannot read " + path);
    std::ostringstream ss;
    ss << in.rdbuf();
    return ss.str();
}

inline void write_file(const std::string& path, const std::string& data) {
    std::ofstream out(path, std::ios::binary);
    if (!out) throw std::runtime_error("cannot write " + path);
    out.write(data.data(), std::streamsize(data.size()));
}

}  // namespace nxgen
