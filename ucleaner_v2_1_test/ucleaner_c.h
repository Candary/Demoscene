// ucleaner_c.h — C ABI (transcribed from Step 9)
#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct uc_ctx uc_ctx;
enum uc_prop_type { UC_PROP_NONE=0, UC_PROP_FLOAT=1, UC_PROP_INT=2, UC_PROP_ID=3, UC_PROP_VEC3=4, UC_PROP_HASH=5 };
enum uc_status { UC_OK=0, UC_INVALID_ENTITY=1, UC_INVALID_FIELD=2, UC_VERSION_MISMATCH=3, UC_CYCLE_DETECTED=4, UC_DEPTH_EXCEEDED=5, UC_NOT_FOUND=6, UC_PARSE_ERROR=7, UC_TYPE_MISMATCH=8, UC_SELF_REFERENCE=9, UC_ALREADY_EXISTS=10, UC_OUT_OF_MEMORY=11, UC_INVALID_REFERENCE=12 };

uc_ctx* uc_ctx_create(void);
void    uc_ctx_destroy(uc_ctx* ctx);
int uc_create_entity(uc_ctx* ctx, uint32_t name_hash, uint32_t* out_id);
int uc_destroy_entity(uc_ctx* ctx, uint32_t entity_id);
int uc_find_entity(uc_ctx* ctx, uint32_t name_hash, uint32_t* out_id);
int uc_add_field(uc_ctx* ctx, uint32_t entity_id, uint32_t name_hash, int prop_type, uint64_t* out_field_id);
int uc_set_float(uc_ctx* ctx, uint32_t entity_id, uint32_t name_hash, float value, uint32_t expected_version);
int uc_get_float(uc_ctx* ctx, uint32_t entity_id, uint32_t name_hash, float* out);
int uc_set_vec3(uc_ctx* ctx, uint32_t entity_id, uint32_t name_hash, const float v[3], uint32_t expected_version);
int uc_get_vec3(uc_ctx* ctx, uint32_t entity_id, uint32_t name_hash, float out[3]);
int uc_add_dependency(uc_ctx* ctx, uint64_t src_field, uint64_t dst_field);
int uc_validate_graph(uc_ctx* ctx);
int uc_flow_enqueue(uc_ctx* ctx, uint64_t field_id);
int uc_flow_run(uc_ctx* ctx);
#ifdef __cplusplus
}
#endif
