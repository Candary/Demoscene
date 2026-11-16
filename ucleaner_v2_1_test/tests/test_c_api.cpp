#include "../ucleaner_c.h"
#include <cassert>
#include <cstdio>
#include <cstring>

static uint32_t hash(const char* s) {
    uint32_t h = 2166136261u;
    while (*s) { h ^= (uint8_t)*s++; h *= 16777619u; }
    return h;
}

void test_lifecycle() {
    uc_ctx* ctx = uc_ctx_create();
    assert(ctx);
    uint32_t entity;
    assert(uc_create_entity(ctx, hash("@test"), &entity) == UC_OK);
    assert(entity != 0);
    uint64_t field;
    assert(uc_add_field(ctx, entity, hash("x"), UC_PROP_FLOAT, &field) == UC_OK);
    assert(uc_set_float(ctx, entity, hash("x"), 42.0f, 0) == UC_OK);
    float val;
    assert(uc_get_float(ctx, entity, hash("x"), &val) == UC_OK);
    assert(val == 42.0f);
    uc_ctx_destroy(ctx);
    uc_ctx_destroy(nullptr);
    printf("[PASS] T24: lifecycle\n");
}
void test_version_mismatch() {
    uc_ctx* ctx = uc_ctx_create();
    uint32_t entity;
    uc_create_entity(ctx, hash("@test"), &entity);
    uint64_t field;
    uc_add_field(ctx, entity, hash("x"), UC_PROP_FLOAT, &field);
    uc_set_float(ctx, entity, hash("x"), 1.0f, 0);
    assert(uc_set_float(ctx, entity, hash("x"), 2.0f, 999) == UC_VERSION_MISMATCH);
    float val;
    uc_get_float(ctx, entity, hash("x"), &val);
    assert(val == 1.0f);
    uc_ctx_destroy(ctx);
    printf("[PASS] T25: version_mismatch\n");
}
void test_closed_context() {
    uc_ctx* ctx = uc_ctx_create();
    uc_ctx_destroy(ctx);
    ctx = nullptr;  // standard C pattern: null after free
    uint32_t dummy;
    assert(uc_create_entity(ctx, hash("@x"), &dummy) == UC_INVALID_ENTITY);
    assert(uc_set_float(ctx, 1, hash("x"), 1.0f, 0) == UC_INVALID_ENTITY);
    assert(uc_flow_run(ctx) == UC_INVALID_ENTITY);
    printf("[PASS] T24b: closed_context_raises\n");
}

int main() {
    test_lifecycle();
    test_version_mismatch();
    test_closed_context();
    printf("\nAll C API tests passed.\n"); return 0;
}
