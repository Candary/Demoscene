// main.cpp — CLI nxGen: run / plugins / check.
//
//   nxgen run --preset text_to_scene --text "epic cold city" --out out/demo
//   nxgen run --job examples/job_text_to_scene.json
//   nxgen plugins
//   nxgen check examples/compo.uc
#include <cstring>
#include <iostream>

#include "loader.h"
#include "job.h"
#include "plugins.h"

using nxgen::Json;

namespace {

struct Options {
    std::string command;
    std::string config;
    bool config_explicit = false;
    std::string preset;
    std::string job;
    std::string text;
    std::string image;
    std::string out;
    std::string report;
    std::string file;
    bool no_cache = false;
    bool quiet = false;
    bool no_check = false;
    Json values = Json::object();
};

void usage() {
    std::cout <<
        "nxgen — генератор текстур, мешей, анимации и постэффектов\n\n"
        "  nxgen run --preset <имя> [--text ...] [--image ...] [--out dir]\n"
        "            [--set key=value] [--report name] [--config path]\n"
        "            [--job file.json] [--no-cache] [--no-check] [--quiet]\n"
        "  nxgen plugins\n"
        "  nxgen check <file.uc>\n";
}

Json parse_scalar(const std::string& raw) {
    if (raw == "true") return Json(true);
    if (raw == "false") return Json(false);
    if (raw == "null") return Json();
    char* end = nullptr;
    double number = std::strtod(raw.c_str(), &end);
    if (end && *end == '\0' && !raw.empty()) return Json(number);
    return Json(raw);
}

bool parse_args(int argc, char** argv, Options& options) {
    if (argc < 2) { usage(); return false; }

    // Команда — первый аргумент, не начинающийся с '-': глобальные флаги
    // (--config) можно ставить и до неё.
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (!arg.empty() && arg[0] != '-') {
            options.command = arg;
            break;
        }
        if (arg == "--help" || arg == "-h") { usage(); return false; }
        // значение глобального флага пропускаем
        if (arg == "--config") ++i;
    }
    if (options.command.empty()) { usage(); return false; }

    for (int i = 1; i < argc; ++i) {
        if (argv[i] == options.command) continue;
        std::string arg = argv[i];
        auto next = [&](const char* what) -> std::string {
            if (i + 1 >= argc) throw std::runtime_error(std::string("missing value for ") + what);
            return argv[++i];
        };
        if (arg == "--config") { options.config = next("--config"); options.config_explicit = true; }
        else if (arg == "--preset") options.preset = next("--preset");
        else if (arg == "--job") options.job = next("--job");
        else if (arg == "--text") options.text = next("--text");
        else if (arg == "--image") options.image = next("--image");
        else if (arg == "--out") options.out = next("--out");
        else if (arg == "--report") options.report = next("--report");
        else if (arg == "--no-cache") options.no_cache = true;
        else if (arg == "--no-check") options.no_check = true;
        else if (arg == "--quiet") options.quiet = true;
        else if (arg == "--set") {
            std::string kv = next("--set");
            size_t eq = kv.find('=');
            if (eq == std::string::npos) throw std::runtime_error("--set expects key=value");
            options.values.set(kv.substr(0, eq), parse_scalar(kv.substr(eq + 1)));
        } else if (arg == "--help" || arg == "-h") { usage(); return false; }
        else if (options.command == "check" && arg[0] != '-') options.file = arg;
        else throw std::runtime_error("unknown argument: " + arg);
    }
    return true;
}

int command_plugins(const Options& options) {
    Json config = nxgen::load_config(options.config, options.config_explicit);
    (void)config;
    nxgen::Registry registry = nxgen::default_registry();
    for (const auto& id : registry.ids()) {
        const nxgen::Plugin& plugin = registry.get(id);
        std::cout << (id.size() < 20 ? id + std::string(20 - id.size(), ' ') : id)
                  << " v" << plugin.version << "  -> " << plugin.produces << "  " << plugin.doc << "\n";
    }
    return 0;
}

int command_check(const Options& options) {
    if (options.file.empty()) { std::cerr << "check: pass a .uc file\n"; return 2; }
    uc::Context context;
    std::string error;
    uc::Status status = uc::Loader::load_file(context, options.file, &error);
    if (status != uc::Status::Ok) {
        std::cerr << "check: " << uc::status_name(status) << ": " << error << "\n";
        return 1;
    }
    std::cout << "ok: " << context.entities.entity_count() << " entities\n";
    return 0;
}

int command_run(const Options& options) {
    Json config = nxgen::load_config(options.config, options.config_explicit);
    nxgen::Registry registry = nxgen::default_registry();

    nxgen::Job job;
    if (!options.job.empty()) {
        job = nxgen::job_from_file(config, options.job);
    } else if (!options.preset.empty()) {
        Json values = options.values;
        if (!options.text.empty()) values.set("text", options.text);
        if (!options.image.empty()) values.set("image", options.image);
        job = nxgen::job_from_preset(config, options.preset, values);
    } else {
        std::cerr << "run: pass --preset or --job\n";
        return 2;
    }

    auto results = job.graph->execute(registry, config, !options.no_cache,
                                      [&](const std::string& node, const std::string& plugin, bool cached) {
                                          if (options.quiet) return;
                                          std::cout << "  [" << (cached ? "cache" : "run  ") << "] "
                                                    << node << "  " << plugin << "\n";
                                      });
    if (results.empty()) { std::cerr << "run: nothing produced\n"; return 3; }

    const std::string out_dir = options.out.empty() ? config.at("paths").at("output").as_string("out") : options.out;
    std::vector<std::string> written = nxgen::write_outputs(job, results, out_dir);

    Json report = Json::object();
    report.set("job", job.name);
    Json outputs = Json::array();
    for (const auto& name : written) outputs.push(name);
    report.set("outputs", outputs);
    Json artifacts = Json::object();
    for (const auto& kv : results) {
        Json item = kv.second.meta;
        item.set("kind", kv.second.kind);
        artifacts.set(kv.first, item);
    }
    report.set("artifacts", artifacts);

    if (!options.no_check && results.count("scene")) {
        uc::Context context;
        std::string error;
        uc::Status status = uc::Loader::load_text(context, results.at("scene").bytes.c_str(), &error);
        Json check = Json::object();
        check.set("ok", status == uc::Status::Ok);
        check.set("entities", int(context.entities.entity_count()));
        if (status != uc::Status::Ok) check.set("error", error.empty() ? uc::status_name(status) : error);
        report.set("ucleaner", check);
    }

    const std::string report_name = options.report.empty()
        ? config.at("paths").at("report").as_string("report.json")
        : options.report;
    std::string why;
    if (!nxgen::safe_output_name(report_name, &why)) throw std::runtime_error("bad report name: " + why);
    std::filesystem::create_directories(out_dir);
    nxgen::write_file((std::filesystem::path(out_dir) / report_name).string(), report.dump(2) + "\n");

    if (!options.quiet) {
        std::cout << "\noutput: " << out_dir << "\n";
        for (const auto& name : written) {
            std::cout << "  " << name << "  "
                      << std::filesystem::file_size(std::filesystem::path(out_dir) / name) << " bytes\n";
        }
        std::cout << "  " << report_name << "\n";
        if (report.has("ucleaner")) {
            const Json& check = report.at("ucleaner");
            std::cout << "  uCleaner: " << (check.at("ok").as_bool() ? "ok" : "FAILED")
                      << " (" << check.at("entities").as_int(0) << " entities)\n";
        }
    }
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        Options options;
        if (!parse_args(argc, argv, options)) return 2;
        if (options.command == "run") return command_run(options);
        if (options.command == "plugins") return command_plugins(options);
        if (options.command == "check") return command_check(options);
        usage();
        return 2;
    } catch (const std::exception& exc) {
        std::cerr << "error: " << exc.what() << "\n";
        return 1;
    }
}
