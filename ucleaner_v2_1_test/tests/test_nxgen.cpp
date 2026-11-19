// test_nxgen.cpp — тесты C++ генератора: реестр, граф, пайплайны, имена файлов.
//
// Проверки идут до конца: сгенерированный uLang загружается в uCleaner, OBJ
// разбирается обратно, текстура проверяется на детерминизм.
#include <cstdio>
#include <filesystem>
#include <string>

#include "../nxgen/job.h"
#include "../nxgen/plugins.h"
#include "loader.h"

namespace {

int g_failed = 0;
int g_passed = 0;

void check(bool condition, const char* what, int line) {
    if (condition) {
        ++g_passed;
    } else {
        ++g_failed;
        std::printf("[FAIL] line %d: %s\n", line, what);
    }
}

#define CHECK(cond) check((cond), #cond, __LINE__)

std::filesystem::path temp_dir(const char* tag) {
    auto path = std::filesystem::temp_directory_path() / (std::string("nxgen_test_") + tag);
    std::filesystem::remove_all(path);
    std::filesystem::create_directories(path);
    return path;
}

nxgen::Json values_of(std::initializer_list<std::pair<const char*, nxgen::Json>> items) {
    nxgen::Json values = nxgen::Json::object();
    for (const auto& kv : items) values.set(kv.first, kv.second);
    return values;
}

std::string read_text(const std::filesystem::path& path) { return nxgen::read_file(path.string()); }

int count_prefix(const std::string& text, const std::string& prefix) {
    int count = 0;
    size_t pos = 0;
    while ((pos = text.find(prefix, pos)) != std::string::npos) { ++count; pos += prefix.size(); }
    return count;
}

void test_registry() {
    nxgen::Registry registry = nxgen::default_registry();
    CHECK(registry.ids().size() >= 9);
    for (const char* id : {"input.text", "input.image", "texture.fbm", "texture.stripes",
                           "mesh.primitive", "mesh.from_image", "anim.track", "postfx.chain",
                           "scene.assemble"}) {
        CHECK(registry.has(id));
    }
    CHECK(registry.get("texture.fbm").produces == "texture");
}

void test_text_to_scene() {
    nxgen::Json config = nxgen::Json::parse(nxgen::kDefaultConfig);
    nxgen::Registry registry = nxgen::default_registry();
    nxgen::Job job = nxgen::job_from_preset(config, "text_to_scene", values_of({{"text", "epic cold city"}}));
    (void)job;
    auto results = job.graph->execute(registry, config, false);

    CHECK(results.count("tex") == 1);
    CHECK(results.count("mesh") == 1);
    CHECK(results.count("scene") == 1);
    CHECK(results.at("tex").bytes.rfind("\x89PNG", 0) == 0);
    CHECK(results.at("mesh").bytes.find("\nv ") != std::string::npos);

    // Сцена обязана загружаться в uCleaner
    uc::Context context;
    std::string error;
    uc::Status status = uc::Loader::load_text(context, results.at("scene").bytes.c_str(), &error);
    CHECK(status == uc::Status::Ok);
    if (status != uc::Status::Ok) std::printf("  loader: %s\n", error.c_str());

    uc::EntityId scene = context.entities.find_by_name(uc::fnv1a("@scene"));
    CHECK(scene != uc::ENTITY_NULL);
    CHECK(context.props.idlist_length(scene, uc::fnv1a("anim")) > 0);
    CHECK(context.props.idlist_length(scene, uc::fnv1a("fx")) > 0);
    CHECK(context.entities.entity_count() > 5);

    // Файлы пишутся по именам из пресета, без литералов в коде
    auto out = temp_dir("scene");
    auto written = nxgen::write_outputs(job, results, out.string());
    CHECK(written.size() == job.outputs.size());
    for (const auto& name : written) CHECK(std::filesystem::file_size(out / name) > 0);
    std::filesystem::remove_all(out);
}

void test_texture_determinism() {
    nxgen::Json config = nxgen::Json::parse(nxgen::kDefaultConfig);
    nxgen::Registry registry = nxgen::default_registry();
    nxgen::Json values = values_of({{"text", "calm fog"}, {"size", 96}});
    auto first = nxgen::job_from_preset(config, "text_to_texture", values);
    auto second = nxgen::job_from_preset(config, "text_to_texture", values);
    auto a = first.graph->execute(registry, config, false);
    auto b = second.graph->execute(registry, config, false);
    CHECK(a.at("tex").bytes == b.at("tex").bytes);

    auto bigger = nxgen::job_from_preset(config, "text_to_texture",
                                         values_of({{"text", "calm fog"}, {"size", 128}}));
    auto c = bigger.graph->execute(registry, config, false);
    CHECK(a.at("tex").bytes != c.at("tex").bytes);
}

void test_image_to_obj() {
    auto dir = temp_dir("image");
    auto ppm = dir / "input.ppm";
    // P6 32x32: круг на фоне
    std::string data = "P6\n32 32\n255\n";
    for (int y = 0; y < 32; ++y) {
        for (int x = 0; x < 32; ++x) {
            float dx = (x - 16) / 10.0f, dy = (y - 16) / 7.0f;
            unsigned char value = (dx * dx + dy * dy < 1.0f) ? 240 : 30;
            data.push_back(char(value));
            data.push_back(char(value / 2));
            data.push_back(char(90));
        }
    }
    nxgen::write_file(ppm.string(), data);

    nxgen::Json config = nxgen::Json::parse(nxgen::kDefaultConfig);
    nxgen::Registry registry = nxgen::default_registry();
    nxgen::Json values = values_of({{"image", ppm.string()}, {"height", 0.6}});
    auto job = nxgen::job_from_preset(config, "image_to_obj", values);
    auto results = job.graph->execute(registry, config, false);

    const nxgen::Artifact& mesh = results.at("mesh");
    CHECK(mesh.meta.at("vertices").as_int(0) > 100);
    CHECK(mesh.meta.at("faces").as_int(0) > 100);
    // высота выдавливания масштабируется параметром
    auto taller = nxgen::job_from_preset(
        config, "image_to_obj", values_of({{"image", ppm.string()}, {"height", 1.2}}));
    auto tall_results = taller.graph->execute(registry, config, false);
    float small = mesh.meta.at("size").at(1).as_float();
    float big = tall_results.at("mesh").meta.at("size").at(1).as_float();
    CHECK(small > 0.0f);
    CHECK(std::fabs(big - small * 2.0f) < 1e-3f);
    std::filesystem::remove_all(dir);
}

void test_output_names() {
    std::string why;
    CHECK(nxgen::safe_output_name("meshes/{node}.obj"));
    CHECK(!nxgen::safe_output_name("../escape.obj", &why));
    CHECK(!nxgen::safe_output_name("/abs.obj", &why));
    CHECK(!nxgen::safe_output_name("bad name.obj", &why));

    nxgen::Json config = nxgen::Json::parse(nxgen::kDefaultConfig);
    nxgen::Registry registry = nxgen::default_registry();
    auto job = nxgen::job_from_preset(config, "text_to_texture",
                                      values_of({{"text", "cozy"}, {"size", 32}}));
    job.outputs["tex"] = "{node}_{kind}.bin";
    auto results = job.graph->execute(registry, config, false);
    auto dir = temp_dir("names");
    auto written = nxgen::write_outputs(job, results, dir.string());
    CHECK(written.size() == 1);
    CHECK(written[0] == "tex_texture.bin");
    std::filesystem::remove_all(dir);
}

void test_unknown_preset() {
    nxgen::Json config = nxgen::Json::parse(nxgen::kDefaultConfig);
    bool thrown = false;
    try {
        nxgen::job_from_preset(config, "no_such_preset", nxgen::Json::object());
    } catch (const std::exception&) {
        thrown = true;
    }
    CHECK(thrown);
}

void test_animation_counts() {
    nxgen::Json config = nxgen::Json::parse(nxgen::kDefaultConfig);
    nxgen::Registry registry = nxgen::default_registry();
    auto job = nxgen::job_from_preset(config, "text_to_anim",
                                      values_of({{"text", "tense dark city"}}));
    auto results = job.graph->execute(registry, config, false);
    CHECK(count_prefix(results.at("anim").bytes, "entity @seg_") == 6);

    uc::Context context;
    std::string error;
    CHECK(uc::Loader::load_text(context, results.at("anim").bytes.c_str(), &error) == uc::Status::Ok);
    uc::EntityId seg = context.entities.find_by_name(uc::fnv1a("@seg_0"));
    CHECK(seg != uc::ENTITY_NULL);
    CHECK(context.props.get_float(seg, uc::fnv1a("duration")) > 0.0f);
}

}  // namespace

int main() {
    std::printf("nxGen (C++) — tests\n\n");
    test_registry();
    test_text_to_scene();
    test_texture_determinism();
    test_image_to_obj();
    test_output_names();
    test_unknown_preset();
    test_animation_counts();
    std::printf("\n%d passed, %d failed\n", g_passed, g_failed);
    return g_failed == 0 ? 0 : 1;
}
