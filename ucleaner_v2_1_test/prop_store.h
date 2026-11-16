// prop_store.h — transcribed from Final Qwen.md Step 3
#pragma once
#include "ucleaner_types.h"
#include "entity_store.h"
#include <cstring>
#include <vector>

namespace uc {

struct Field {
    PropType type = PropType::None;
    uint16_t version = 0;
    uint16_t slot = 0;
    uint32_t name_hash = 0;
    union {
        float f;
        int32_t i;
        EntityId id;
        float v3[3];
        uint32_t hash;
    } val;
    Field() { std::memset(&val, 0, sizeof(val)); }
};

class PropStore {
public:
    void set_entity_store(EntityStore* e) { entities_ = e; }

    Status add_field(EntityId entity, uint32_t name_hash, PropType type, FieldId& out_field_id) {
        if (!entities_ || !entities_->is_alive(entity)) return Status::InvalidEntity;
        uint16_t idx = entity_index(entity);
        uint16_t fc = entities_->field_count(entity);
        if (fc >= MAX_FIELDS_PER_ENTITY) return Status::OutOfMemory;
        if (get_field(entity, name_hash)) return Status::AlreadyExists;
        uint16_t slot = static_cast<uint16_t>(idx * MAX_FIELDS_PER_ENTITY + fc);
        if (slot >= fields_.size()) fields_.resize(slot + 1);
        Field& f = fields_[slot];
        f.type = type; f.version = 1; f.slot = slot; f.name_hash = name_hash;
        std::memset(&f.val, 0, sizeof(f.val));
        entities_->inc_field_count(entity);
        out_field_id = make_field_id(entity, slot);
        return Status::Ok;
    }

    Field* get_field(EntityId entity, uint32_t name_hash) {
        if (!entities_ || !entities_->is_alive(entity)) return nullptr;
        uint16_t idx = entity_index(entity);
        uint16_t fc = entities_->field_count(entity);
        uint16_t base = static_cast<uint16_t>(idx * MAX_FIELDS_PER_ENTITY);
        for (uint16_t i = 0; i < fc; i++) {
            if (fields_[base + i].name_hash == name_hash) return &fields_[base + i];
        }
        return nullptr;
    }

    const Field* get_field_const(EntityId entity, uint32_t name_hash) const {
        if (!entities_ || !entities_->is_alive(entity)) return nullptr;
        uint16_t idx = entity_index(entity);
        uint16_t fc = entities_->field_count(entity);
        uint16_t base = static_cast<uint16_t>(idx * MAX_FIELDS_PER_ENTITY);
        for (uint16_t i = 0; i < fc; i++) {
            if (fields_[base + i].name_hash == name_hash) return &fields_[base + i];
        }
        return nullptr;
    }

    Status set_float(EntityId entity, uint32_t name_hash, float value, uint32_t expected_version = 0) {
        Field* f = get_field(entity, name_hash);
        if (!f) return Status::InvalidField;
        if (f->type != PropType::Float) return Status::TypeMismatch;
        if (expected_version != 0 && f->version != expected_version) return Status::VersionMismatch;
        f->val.f = value; f->version++;
        return Status::Ok;
    }
    float get_float(EntityId entity, uint32_t name_hash) const {
        const Field* f = get_field_const(entity, name_hash);
        return (f && f->type == PropType::Float) ? f->val.f : 0.0f;
    }
    Status set_id(EntityId entity, uint32_t name_hash, EntityId ref, uint32_t expected_version = 0) {
        Field* f = get_field(entity, name_hash);
        if (!f) return Status::InvalidField;
        if (f->type != PropType::Id) return Status::TypeMismatch;
        if (expected_version != 0 && f->version != expected_version) return Status::VersionMismatch;
        f->val.id = ref; f->version++;
        return Status::Ok;
    }
    EntityId get_id(EntityId entity, uint32_t name_hash) const {
        const Field* f = get_field_const(entity, name_hash);
        return (f && f->type == PropType::Id) ? f->val.id : ENTITY_NULL;
    }
    Status set_vec3(EntityId entity, uint32_t name_hash, const float v[3], uint32_t expected_version = 0) {
        Field* f = get_field(entity, name_hash);
        if (!f) return Status::InvalidField;
        if (f->type != PropType::Vec3) return Status::TypeMismatch;
        if (expected_version != 0 && f->version != expected_version) return Status::VersionMismatch;
        std::memcpy(f->val.v3, v, sizeof(float)*3); f->version++;
        return Status::Ok;
    }
    void get_vec3(EntityId entity, uint32_t name_hash, float out[3]) const {
        const Field* f = get_field_const(entity, name_hash);
        if (f && f->type == PropType::Vec3) std::memcpy(out, f->val.v3, sizeof(float)*3);
        else { out[0]=out[1]=out[2]=0.0f; }
    }
    uint32_t field_version(EntityId entity, uint32_t name_hash) const {
        const Field* f = get_field_const(entity, name_hash);
        return f ? f->version : 0;
    }
    Field* field_at_slot(uint16_t slot) { return slot < fields_.size() ? &fields_[slot] : nullptr; }
    const Field* field_at_slot(uint16_t slot) const { return slot < fields_.size() ? &fields_[slot] : nullptr; }
    void clear() { fields_.clear(); }

private:
    EntityStore* entities_ = nullptr;
    std::vector<Field> fields_;
};

} // namespace uc
