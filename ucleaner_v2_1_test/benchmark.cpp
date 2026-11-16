// benchmark.cpp — uCleaner v2.1 benchmarks (from Final Qwen.md Step 10)
#include "ucleaner.h"
#include "ulang_parser.h"
#include <chrono>
#include <cstdio>
#include <vector>
#include <string>

using namespace uc;
using Clock = std::chrono::steady_clock;

template<typename F>
double measure_ns(F&& f, int iterations) {
    auto start = Clock::now();
    for (int i = 0; i < iterations; i++) f();
    auto end = Clock::now();
    return std::chrono::duration<double, std::nano>(end - start).count() / iterations;
}

static uint32_t hash(const char* s) {
    uint32_t h = 2166136261u;
    while (*s) { h ^= (uint8_t)*s++; h *= 16777619u; }
    return h;
}

void bm_entity_lookup() {
    Context ctx;
    const int N = 1000;
    for (int i = 0; i < N; i++) {
        char name[32]; snprintf(name, sizeof(name), "@entity_%d", i);
        EntityId id; ctx.create_entity(hash(name), id);
    }
    int iterations = 100000;
    double ns = measure_ns([&]() {
        for (int i = 0; i < N; i++) {
            char name[32]; snprintf(name, sizeof(name), "@entity_%d", i);
            ctx.entities.find_by_name(hash(name));
        }
    }, iterations / N);
    printf("[BM1] Entity lookup (%d entities): %.2f ns/lookup\n", N, ns);
}

void bm_field_get() {
    Context ctx;
    EntityId id; ctx.create_entity(hash("@test"), id);
    FieldId f; ctx.add_field(id, hash("value"), PropType::Float, f);
    ctx.set_float(id, hash("value"), 1.0f);
    int iterations = 1000000;
    double ns = measure_ns([&]() { ctx.get_float(id, hash("value")); }, iterations);
    printf("[BM2] Field get: %.2f ns/read\n", ns);
}

void bm_field_set_lowlevel() {
    Context ctx;
    EntityId id; ctx.create_entity(hash("@test"), id);
    FieldId f; ctx.add_field(id, hash("x"), PropType::Float, f);
    int iterations = 1000000;
    double ns = measure_ns([&]() { ctx.props.set_float(id, hash("x"), 42.0f, 0); }, iterations);
    printf("[BM3] Field set lowlevel (no flow): %.2f ns/write\n", ns);
}

void bm_field_set_highlevel() {
    Context ctx;
    EntityId id; ctx.create_entity(hash("@test"), id);
    FieldId f; ctx.add_field(id, hash("x"), PropType::Float, f);
    int iterations = 100000;
    double ns = measure_ns([&]() { ctx.set_float(id, hash("x"), 42.0f); }, iterations);
    printf("[BM4] Field set highlevel (with flow enqueue): %.2f ns/write\n", ns);
}

void bm_patch_apply() {
    Context ctx;
    EntityId id; ctx.create_entity(hash("@test"), id);
    FieldId f; ctx.add_field(id, hash("x"), PropType::Float, f);
    Patch p = ctx.patches.create_patch();
    ctx.patches.patch_set_float(p, f, hash("x"), 42.0f, 0);
    ctx.patches.validate(p, ctx.entities, ctx.props);
    int iterations = 100000;
    double ns = measure_ns([&]() { p.applied = false; ctx.patches.apply(p, ctx.props); }, iterations);
    printf("[BM5] Patch apply (validated): %.2f ns/apply\n", ns);
}

void bm_dep_chain() {
    Context ctx;
    const int N = 50;
    std::vector<FieldId> fields;
    for (int i = 0; i < N; i++) {
        EntityId id; ctx.create_entity(hash("@e"), id);
        FieldId f; ctx.add_field(id, hash("v"), PropType::Float, f);
        fields.push_back(f);
    }
    for (int i = 0; i < N-1; i++) ctx.deps.add_dependency(fields[i], fields[i+1]);
    int iterations = 10000;
    double ns = measure_ns([&]() {
        ctx.flow.enqueue(fields[0]);
        ctx.flow.run(ctx.props, ctx.deps);
    }, iterations);
    printf("[BM6] Dep chain (N=%d): %.2f ns/cascade\n", N, ns);
}

void bm_dep_fanout() {
    Context ctx;
    const int M = 50;
    EntityId src_id; ctx.create_entity(hash("@src"), src_id);
    FieldId src_f; ctx.add_field(src_id, hash("v"), PropType::Float, src_f);
    for (int i = 0; i < M; i++) {
        EntityId id; ctx.create_entity(hash("@dst"), id);
        FieldId f; ctx.add_field(id, hash("v"), PropType::Float, f);
        ctx.deps.add_dependency(src_f, f);
    }
    int iterations = 10000;
    double ns = measure_ns([&]() {
        ctx.flow.enqueue(src_f);
        ctx.flow.run(ctx.props, ctx.deps);
    }, iterations);
    printf("[BM7] Dep fanout (M=%d): %.2f ns/cascade\n", M, ns);
}

void bm_flow_coalesce() {
    Context ctx;
    EntityId id; ctx.create_entity(hash("@test"), id);
    FieldId f; ctx.add_field(id, hash("x"), PropType::Float, f);
    int iterations = 10000;
    double ns = measure_ns([&]() {
        for (int i = 0; i < 100; i++) ctx.flow.enqueue(f);
        ctx.flow.run(ctx.props, ctx.deps);
    }, iterations);
    printf("[BM8] Flow coalesce (100 enqueue, 1 run): %.2f ns/iteration\n", ns);
}

void bm_cycle_detect() {
    Context ctx;
    const int N = 100;
    std::vector<FieldId> fields;
    for (int i = 0; i < N; i++) {
        EntityId id; ctx.create_entity(hash("@e"), id);
        FieldId f; ctx.add_field(id, hash("v"), PropType::Float, f);
        fields.push_back(f);
    }
    for (int i = 0; i < N-1; i++) ctx.deps.add_dependency(fields[i], fields[i+1]);
    int iterations = 1000;
    double ns = measure_ns([&]() { ctx.deps.has_cycle(); }, iterations);
    printf("[BM9] Cycle detect (N=%d, DAG): %.2f ns/check\n", N, ns);
}

void bm_lang_parse() {
    const char* src = R"UC(
        entity @scene_1 { "start": 0.0, "end": 30.0, "camera": @cam_1 }
        entity @scene_2 { "start": 30.0, "end": 60.0, "camera": @cam_1 }
        entity @cam_1 { "fov": 60.0, "pos": [0.0, 0.0, 5.0] }
        entity @cam_2 { "fov": 75.0, "pos": [0.0, 2.0, 10.0] }
    )UC";
    UlangParser parser;
    int iterations = 1000;
    double ns = measure_ns([&]() { IR ir; parser.compile(src, ir); }, iterations);
    printf("[BM10] Lang parse (4 entities): %.2f ns/parse\n", ns);
}

void bm_full_tick() {
    Context ctx;
    EntityId id; ctx.create_entity(hash("@scene"), id);
    FieldId f1, f2, f3;
    ctx.add_field(id, hash("a"), PropType::Float, f1);
    ctx.add_field(id, hash("b"), PropType::Float, f2);
    ctx.add_field(id, hash("c"), PropType::Float, f3);
    const int K = 10;
    int iterations = 10000;
    double ns = measure_ns([&]() {
        for (int i = 0; i < K; i++) {
            ctx.set_float_batch(id, hash("a"), (float)i);
            ctx.set_float_batch(id, hash("b"), (float)i);
            ctx.set_float_batch(id, hash("c"), (float)i);
        }
        ctx.flow_run();
    }, iterations);
    printf("[BM11] Full tick (K=%d batches + 1 run): %.2f ns/tick\n", K, ns);
}

int main() {
    printf("=== uCleaner v2.1 Benchmarks ===\n\n");
    bm_entity_lookup(); bm_field_get(); bm_field_set_lowlevel();
    bm_field_set_highlevel(); bm_patch_apply(); bm_dep_chain();
    bm_dep_fanout(); bm_flow_coalesce(); bm_cycle_detect();
    bm_lang_parse(); bm_full_tick();
    printf("\n=== Done ===\n");
    return 0;
}
