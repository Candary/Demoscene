// ucleaner_c.cpp — C ABI implementation (transcribed from Step 9)
#include "ucleaner_c.h"
#include "ucleaner.h"
#include <new>
#include <cstring>

struct uc_ctx { uc::Context core; };

extern "C" {

uc_ctx* uc_ctx_create(void) { return new (std::nothrow) uc_ctx(); }
void    uc_ctx_destroy(uc_ctx* ctx) { delete ctx; }

int uc_create_entity(uc_ctx* ctx, uint32_t name_hash, uint32_t* out_id) {
    if (!ctx || !out_id) return UC_INVALID_ENTITY;
    uc::EntityId id;
    uc::Status s = ctx->core.create_entity(name_hash, id);
    if (s == uc::Status::Ok) *out_id = id;
    return (int)s;
}
int uc_destroy_entity(uc_ctx* ctx, uint32_t entity_id) {
    if (!ctx) return UC_INVALID_ENTITY;
    return (int)ctx->core.destroy_entity(entity_id);
}
int uc_find_entity(uc_ctx* ctx, uint32_t name_hash, uint32_t* out_id) {
    if (!ctx || !out_id) return UC_INVALID_ENTITY;
    uc::EntityId id = ctx->core.entities.find_by_name(name_hash);
    if (id == uc::ENTITY_NULL) return UC_NOT_FOUND;
    *out_id = id; return UC_OK;
}
int uc_add_field(uc_ctx* ctx, uint32_t entity_id, uint32_t name_hash, int prop_type, uint64_t* out_field_id) {
    if (!ctx || !out_field_id) return UC_INVALID_FIELD;
    uc::FieldId fid;
    uc::Status s = ctx->core.add_field(entity_id, name_hash, (uc::PropType)prop_type, fid);
    if (s == uc::Status::Ok) *out_field_id = fid;
    return (int)s;
}
int uc_set_float(uc_ctx* ctx, uint32_t entity_id, uint32_t name_hash, float value, uint32_t expected_version) {
    if (!ctx) return UC_INVALID_ENTITY;
    return (int)ctx->core.set_float(entity_id, name_hash, value, expected_version);
}
int uc_get_float(uc_ctx* ctx, uint32_t entity_id, uint32_t name_hash, float* out) {
    if (!ctx || !out) return UC_INVALID_FIELD;
    *out = ctx->core.get_float(entity_id, name_hash);
    return UC_OK;
}
int uc_set_vec3(uc_ctx* ctx, uint32_t entity_id, uint32_t name_hash, const float v[3], uint32_t expected_version) {
    if (!ctx || !v) return UC_INVALID_FIELD;
    uc::Field* f = ctx->core.props.get_field(entity_id, name_hash);
    if (!f) return UC_INVALID_FIELD;
    if (f->type != uc::PropType::Vec3) return UC_TYPE_MISMATCH;
    if (expected_version != 0 && f->version != expected_version) return UC_VERSION_MISMATCH;
    std::memcpy(f->val.v3, v, sizeof(float)*3);
    f->version++;
    return UC_OK;
}
int uc_get_vec3(uc_ctx* ctx, uint32_t entity_id, uint32_t name_hash, float out[3]) {
    if (!ctx || !out) return UC_INVALID_FIELD;
    const uc::Field* f = ctx->core.props.get_field_const(entity_id, name_hash);
    if (!f || f->type != uc::PropType::Vec3) { out[0]=out[1]=out[2]=0.0f; return UC_OK; }
    std::memcpy(out, f->val.v3, sizeof(float)*3);
    return UC_OK;
}
int uc_add_dependency(uc_ctx* ctx, uint64_t src, uint64_t dst) {
    if (!ctx) return UC_INVALID_FIELD;
    return (int)ctx->core.add_dependency(src, dst);
}
int uc_validate_graph(uc_ctx* ctx) {
    if (!ctx) return UC_INVALID_ENTITY;
    return ctx->core.validate_graph() ? 0 : 1;
}
int uc_flow_enqueue(uc_ctx* ctx, uint64_t field_id) {
    if (!ctx) return UC_INVALID_FIELD;
    return (int)ctx->core.flow.enqueue(field_id);
}
int uc_flow_run(uc_ctx* ctx) {
    if (!ctx) return UC_INVALID_ENTITY;
    return (int)ctx->core.flow.run(ctx->core.props, ctx->core.deps);
}

} // extern "C"
