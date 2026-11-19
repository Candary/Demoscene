// job.h — задание nxGen: пресет или явный граф, подстановки, выходные файлы.
//
// Имена файлов не зашиты: они приходят из config.presets[*].outputs или из
// самого задания. Шаблоны {node}/{kind}/{index} разворачиваются здесь.
#pragma once

#include <filesystem>
#include <set>

#include "defaults.h"
#include "nxgen.h"

namespace nxgen {

// ---------------------------------------------------------------- конфигурация
inline Json load_config(const std::string& path, bool explicit_path) {
    if (!path.empty()) {
        if (std::filesystem::is_regular_file(path)) return Json::parse(read_file(path));
        if (explicit_path) throw std::runtime_error("config file not found: " + path);
    }
    return Json::parse(kDefaultConfig);
}

// ---------------------------------------------------------------- подстановки
inline std::string json_scalar_to_string(const Json& value) {
    if (value.is_string()) return value.as_string();
    if (value.is_number()) {
        double v = value.as_double();
        if (v == double(int(v))) return std::to_string(int(v));
        char buf[32];
        std::snprintf(buf, sizeof(buf), "%g", v);
        return buf;
    }
    if (value.is_bool()) return value.as_bool() ? "true" : "false";
    return "";
}

inline std::string substitute_string(const std::string& text, const Json& values) {
    std::string out;
    size_t pos = 0;
    while (pos < text.size()) {
        size_t open = text.find("{{", pos);
        if (open == std::string::npos) {
            out.append(text, pos, std::string::npos);
            break;
        }
        out.append(text, pos, open - pos);
        size_t close = text.find("}}", open + 2);
        if (close == std::string::npos) throw std::runtime_error("job: unclosed '{{' in " + text);
        std::string key = text.substr(open + 2, close - open - 2);
        while (!key.empty() && (key.front() == ' ' || key.front() == '\t')) key.erase(key.begin());
        while (!key.empty() && (key.back() == ' ' || key.back() == '\t')) key.pop_back();
        if (!values.has(key)) throw std::runtime_error("job: unknown placeholder '{{" + key + "}}'");
        out += json_scalar_to_string(values.at(key));
        pos = close + 2;
    }
    return out;
}

inline Json substitute_value(const Json& value, const Json& values) {
    if (value.is_string()) {
        const std::string& text = value.as_string();
        // Строка целиком из одного плейсхолдера сохраняет тип значения.
        if (text.size() > 4 && text.rfind("{{", 0) == 0 && text.compare(text.size() - 2, 2, "}}") == 0) {
            std::string key = text.substr(2, text.size() - 4);
            while (!key.empty() && key.front() == ' ') key.erase(key.begin());
            while (!key.empty() && key.back() == ' ') key.pop_back();
            if (values.has(key)) return values.at(key);
        }
        return Json(substitute_string(text, values));
    }
    if (value.is_array()) {
        std::vector<Json> out;
        for (const auto& item : value.items()) out.push_back(substitute_value(item, values));
        return Json(std::move(out));
    }
    if (value.is_object()) {
        Json out = Json::object();
        for (const auto& kv : value.fields()) out.set(kv.first, substitute_value(kv.second, values));
        return out;
    }
    return value;
}

// ---------------------------------------------------------------- задание
struct Job {
    std::string name;
    std::unique_ptr<Graph> graph;
    std::map<std::string, std::string> outputs;   // node_id -> имя файла
    Json values = Json::object();
};

inline Json job_defaults(const Json& config) {
    Json values = Json::object();
    values.set("text", config.at("intent").at("default_text").as_string(""));
    values.set("size", config.at("texture").at("size").as_int(256));
    values.set("shape", config.at("mesh").at("default_shape").as_string("box"));
    values.set("chain", config.at("postfx").at("default_chain").as_string("soft"));
    values.set("image", "");
    values.set("height", 0.5);
    values.set("fps", 60.0);
    return values;
}

inline void merge_values(Json& target, const Json& source) {
    for (const auto& kv : source.fields()) target.set(kv.first, kv.second);
}

inline Job job_from_preset(const Json& config, const std::string& preset_name, const Json& overrides) {
    const Json& presets = config.at("presets");
    if (!presets.has(preset_name)) throw std::runtime_error("unknown preset: " + preset_name);
    const Json& preset = presets.at(preset_name);

    Json values = job_defaults(config);
    merge_values(values, overrides);

    std::vector<Node> nodes;
    for (const auto& item : preset.at("pipeline").items()) {
        Json expanded = substitute_value(item, values);
        nodes.push_back(node_from_json(expanded));
    }

    Job job;
    job.name = preset_name;
    job.values = values;
    job.graph = std::make_unique<Graph>(std::move(nodes));
    for (const auto& kv : preset.at("outputs").fields()) job.outputs[kv.first] = kv.second.as_string();
    return job;
}

inline Job job_from_file(const Json& config, const std::string& path) {
    Json data = Json::parse(read_file(path));
    if (data.has("preset")) {
        Json values = data.at("values");
        if (!values.is_object()) values = Json::object();
        return job_from_preset(config, data.at("preset").as_string(), values);
    }
    if (!data.has("nodes")) throw std::runtime_error("job must contain 'preset' or 'nodes'");

    Json values = job_defaults(config);
    merge_values(values, data.at("values"));

    std::vector<Node> nodes;
    for (const auto& item : data.at("nodes").items()) nodes.push_back(node_from_json(substitute_value(item, values)));

    Job job;
    job.name = data.has("name") ? data.at("name").as_string() : "job";
    job.values = values;
    job.graph = std::make_unique<Graph>(std::move(nodes));
    for (const auto& kv : data.at("outputs").fields()) job.outputs[kv.first] = kv.second.as_string();
    return job;
}

// ---------------------------------------------------------------- имена файлов
inline bool safe_output_name(const std::string& name, std::string* why = nullptr) {
    if (name.empty()) { if (why) *why = "empty name"; return false; }
    if (name[0] == '/' || name[0] == '\\') { if (why) *why = "absolute path"; return false; }
    if (name.find("..") != std::string::npos) { if (why) *why = "'..' is not allowed"; return false; }
    for (char c : name) {
        // '{' и '}' допустимы: это шаблон, который раскроется в write_outputs,
        // и уже раскрытое имя проверяется повторно.
        const bool allowed = std::isalnum(static_cast<unsigned char>(c)) || c == '.' || c == '_' ||
                             c == '-' || c == '/' || c == '{' || c == '}';
        if (!allowed) { if (why) *why = std::string("bad character '") + c + "'"; return false; }
    }
    return true;
}

inline std::string expand_output(const std::string& pattern, const std::string& node, const std::string& kind, int index) {
    std::string out;
    for (size_t i = 0; i < pattern.size();) {
        if (pattern.compare(i, 6, "{node}") == 0) { out += node; i += 6; continue; }
        if (pattern.compare(i, 6, "{kind}") == 0) { out += kind; i += 6; continue; }
        if (pattern.compare(i, 7, "{index}") == 0) { out += std::to_string(index); i += 7; continue; }
        out += pattern[i++];
    }
    return out;
}

inline std::vector<std::string> write_outputs(const Job& job, const std::map<std::string, Artifact>& results,
                                              const std::string& directory) {
    std::filesystem::create_directories(directory);
    std::vector<std::string> written;
    std::map<std::string, std::string> used;
    int index = 0;
    for (const auto& kv : job.outputs) {
        auto it = results.find(kv.first);
        if (it == results.end()) throw std::runtime_error("output references unknown node '" + kv.first + "'");
        std::string name = expand_output(kv.second, kv.first, it->second.kind, index++);
        std::string why;
        if (!safe_output_name(name, &why)) throw std::runtime_error("bad output name '" + name + "': " + why);
        if (used.count(name)) throw std::runtime_error("output collision: '" + used[name] + "' and '" + kv.first + "' write '" + name + "'");
        used[name] = kv.first;

        std::filesystem::path path = std::filesystem::path(directory) / name;
        std::filesystem::create_directories(path.parent_path());
        write_file(path.string(), it->second.bytes);
        written.push_back(name);
    }
    return written;
}

}  // namespace nxgen
