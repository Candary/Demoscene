// patch_engine.h — transcribed from Final Qwen.md Step 5
// FIX: validate() uses get_field_const instead of get_field (const correctness)
#pragma once
#include "ucleaner_types.h"
#include "entity_store.h"
#include "prop_store.h"
#include <vector>
#include <cstring>

namespace uc {

struct PatchOp {
    FieldId field;
    uint32_t name_hash;
    PropType type;
    float f_val = 0.0f;
    int32_t i_val = 0;
    EntityId id_val = ENTITY_NULL;
    float v3_val[3] = {0,0,0};
    uint32_t expected_version = 0;
};

struct Patch {
    uint32_t id = 0;
    std::vector<PatchOp> ops;
    bool applied = false;
};

class PatchEngine {
public:
    Patch create_patch() { Patch p; p.id = next_patch_id_++; return p; }

    void patch_set_float(Patch& p, FieldId field, uint32_t name_hash,
                         float value, uint32_t expected_version = 0) {
        PatchOp op; op.field = field; op.name_hash = name_hash;
        op.type = PropType::Float; op.f_val = value; op.expected_version = expected_version;
        p.ops.push_back(op);
    }
    void patch_set_id(Patch& p, FieldId field, uint32_t name_hash,
                      EntityId ref, uint32_t expected_version = 0) {
        PatchOp op; op.field = field; op.name_hash = name_hash;
        op.type = PropType::Id; op.id_val = ref; op.expected_version = expected_version;
        p.ops.push_back(op);
    }
    void patch_set_vec3(Patch& p, FieldId field, uint32_t name_hash,
                        const float v[3], uint32_t expected_version = 0) {
        PatchOp op; op.field = field; op.name_hash = name_hash;
        op.type = PropType::Vec3; std::memcpy(op.v3_val, v, 12);
        op.expected_version = expected_version;
        p.ops.push_back(op);
    }

    // FIX: uses get_field_const for const PropStore&
    Status validate(const Patch& p, const EntityStore& entities, const PropStore& props) const {
        for (const auto& op : p.ops) {
            EntityId e = field_entity(op.field);
            if (!entities.is_alive(e)) return Status::InvalidEntity;
            const Field* f = props.get_field_const(e, op.name_hash);
            if (!f) return Status::InvalidField;
            if (f->type != op.type) return Status::TypeMismatch;
            if (op.expected_version != 0 && f->version != op.expected_version)
                return Status::VersionMismatch;
            if (op.type == PropType::Id && op.id_val != ENTITY_NULL && !entities.is_alive(op.id_val))
                return Status::InvalidReference;
        }
        return Status::Ok;
    }

    Status apply(Patch& p, PropStore& props) {
        if (p.applied) return Status::Ok;
        for (const auto& op : p.ops) {
            Field* f = props.get_field(field_entity(op.field), op.name_hash);
            if (!f) return Status::InvalidField;
            switch (op.type) {
                case PropType::Float: f->val.f = op.f_val; break;
                case PropType::Int:   f->val.i = op.i_val; break;
                case PropType::Id:    f->val.id = op.id_val; break;
                case PropType::Vec3:  std::memcpy(f->val.v3, op.v3_val, 12); break;
                case PropType::Hash:  f->val.hash = op.i_val; break;
                default: break;
            }
            f->version++;
        }
        p.applied = true;
        return Status::Ok;
    }

    static std::vector<FieldId> get_changed_fields(const Patch& p) {
        std::vector<FieldId> fields;
        fields.reserve(p.ops.size());
        for (const auto& op : p.ops) fields.push_back(op.field);
        return fields;
    }

private:
    uint32_t next_patch_id_ = 1;
};

} // namespace uc
