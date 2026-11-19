// prop_store.h — transcribed from Final Qwen.md Step 3
#pragma once
#include "ucleaner_types.h"
#include "entity_store.h"
#include <cstring>
#include <vector>

namespace uc {

struct Field {
    PropType type = PropType::None;
    uint32_t version = 0;               // Fix #5: uint32_t (was uint16_t)
    uint32_t slot = 0;                  // local slot 0..31 (unified naming with nxGen)
    uint32_t name_hash = 0;
    union {
        float f;
        int32_t i;
        EntityId id;
        float v3[3];
        uint32_t hash;
        uint16_t idlist_idx;
    } val;
    Field() { std::memset(&val, 0, sizeof(val)); }
};

// R3 fix: динамический IdListPool вместо жёсткого POOL_SIZE=256.
// Раньше при > 256 IdList-полей возвращался OutOfMemory без диагностики.
// Теперь pool растёт по мере необходимости, capacity = POOL_INITIAL * growth.
struct IdListPool {
    static constexpr size_t POOL_INITIAL = 64;
    std::vector<EntityId> data;   // segments of MAX_IDLIST_LEN
    std::vector<uint8_t>  len;
    uint32_t next = 0;            // R1: uint32_t (was uint16_t)

    IdListPool() = default;

    Status alloc(uint16_t& out_idx) {
        if (next >= 0xFFFF) return Status::OutOfMemory;  // uint16_t index limit
        size_t needed = next + 1;
        if (needed * MAX_IDLIST_LEN > data.size()) {
            size_t new_cap = data.size() / MAX_IDLIST_LEN;
            new_cap = new_cap == 0 ? POOL_INITIAL : new_cap * 2;
            while (new_cap < needed) new_cap *= 2;
            data.resize(new_cap * MAX_IDLIST_LEN, ENTITY_NULL);
            len.resize(new_cap, 0);
        }
        out_idx = static_cast<uint16_t>(next++);
        len[out_idx] = 0;
        return Status::Ok;
    }
    Status set(uint16_t idx, const EntityId* ids, uint8_t count) {
        if (idx >= next) return Status::InvalidField;
        if (count > MAX_IDLIST_LEN) return Status::OutOfMemory;
        std::memcpy(&data[static_cast<size_t>(idx) * MAX_IDLIST_LEN], ids, sizeof(EntityId) * count);
        len[idx] = count;
        return Status::Ok;
    }
    uint8_t get(uint16_t idx, EntityId* out_ids) const {
        if (idx >= next) return 0;
        uint8_t n = len[idx];
        std::memcpy(out_ids, &data[static_cast<size_t>(idx) * MAX_IDLIST_LEN], sizeof(EntityId) * n);
        return n;
    }
    uint8_t length(uint16_t idx) const {
        return idx < next ? len[idx] : 0;
    }
    size_t capacity() const { return data.size() / MAX_IDLIST_LEN; }
};

class PropStore {
public:
    IdListPool idlists;

    void set_entity_store(EntityStore* e) { entities_ = e; }

    // Fix #2: compute storage index from entity_index + local_slot.
    static size_t field_storage_index(EntityId entity, uint16_t local_slot) {
        return static_cast<size_t>(entity_index(entity)) * MAX_FIELDS_PER_ENTITY + local_slot;
    }

    Status add_field(EntityId entity, uint32_t name_hash, PropType type, FieldId& out_field_id) {
        if (!entities_ || !entities_->is_alive(entity)) return Status::InvalidEntity;
        uint16_t fc = entities_->field_count(entity);
        if (fc >= MAX_FIELDS_PER_ENTITY) return Status::OutOfMemory;
        if (get_field(entity, name_hash)) return Status::AlreadyExists;
        // Fix #2: use local slot (0..31) in FieldId, not global index.
        uint16_t slot = fc;
        size_t storage_index = field_storage_index(entity, slot);
        if (storage_index >= fields_.size()) fields_.resize(storage_index + 1);
        Field& f = fields_[storage_index];
        f.type = type; f.version = 1; f.slot = slot; f.name_hash = name_hash;
        std::memset(&f.val, 0, sizeof(f.val));
        if (type == PropType::IdList) {
            Status s = idlists.alloc(f.val.idlist_idx);
            if (s != Status::Ok) return s;
        }
        entities_->inc_field_count(entity);
        out_field_id = make_field_id(entity, slot);
        return Status::Ok;
    }

    Field* get_field(EntityId entity, uint32_t name_hash) {
        if (!entities_ || !entities_->is_alive(entity)) return nullptr;
        uint16_t idx = entity_index(entity);
        uint16_t fc = entities_->field_count(entity);
        uint32_t base = static_cast<uint32_t>(idx) * static_cast<uint32_t>(MAX_FIELDS_PER_ENTITY);
        for (uint16_t i = 0; i < fc; i++) {
            if (fields_[base + i].name_hash == name_hash) return &fields_[base + i];
        }
        return nullptr;
    }

    const Field* get_field_const(EntityId entity, uint32_t name_hash) const {
        if (!entities_ || !entities_->is_alive(entity)) return nullptr;
        uint16_t idx = entity_index(entity);
        uint16_t fc = entities_->field_count(entity);
        uint32_t base = static_cast<uint32_t>(idx) * static_cast<uint32_t>(MAX_FIELDS_PER_ENTITY);
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

    // ── IdList API ──────────────────────────────────────────────
    Status set_idlist(EntityId entity, uint32_t name_hash,
                      const EntityId* ids, uint8_t count,
                      uint32_t expected_version = 0) {
        Field* f = get_field(entity, name_hash);
        if (!f) return Status::InvalidField;
        if (f->type != PropType::IdList) return Status::TypeMismatch;
        if (expected_version != 0 && f->version != expected_version) return Status::VersionMismatch;
        // Validate every referenced entity is alive (caller-side responsibility
        // at the parser level; here we only store the IDs).
        Status s = idlists.set(f->val.idlist_idx, ids, count);
        if (s != Status::Ok) return s;
        f->version++;
        return Status::Ok;
    }
    uint8_t get_idlist(EntityId entity, uint32_t name_hash, EntityId* out_ids) const {
        const Field* f = get_field_const(entity, name_hash);
        if (!f || f->type != PropType::IdList) return 0;
        return idlists.get(f->val.idlist_idx, out_ids);
    }
    uint8_t idlist_length(EntityId entity, uint32_t name_hash) const {
        const Field* f = get_field_const(entity, name_hash);
        if (!f || f->type != PropType::IdList) return 0;
        return idlists.length(f->val.idlist_idx);
    }
    // Fix #3: validate that a FieldId correctly points to an existing field.
    // Checks: entity alive, slot < field_count, name_hash matches.
    Status validate_field_id(EntityId entity, FieldId field_id, uint32_t expected_name_hash) const {
        if (!entities_ || !entities_->is_alive(entity)) return Status::InvalidEntity;
        if (field_entity(field_id) != entity) return Status::InvalidField;
        uint16_t slot = static_cast<uint16_t>(field_slot(field_id));
        if (slot >= entities_->field_count(entity)) return Status::InvalidField;
        size_t storage_idx = field_storage_index(entity, slot);
        if (storage_idx >= fields_.size()) return Status::InvalidField;
        const Field& f = fields_[storage_idx];
        if (f.name_hash != expected_name_hash) return Status::InvalidField;
        return Status::Ok;
    }

    // Access field by local slot (for Patch Engine internal use).
    Field* field_at_local_slot(EntityId entity, uint16_t local_slot) {
        if (!entities_ || !entities_->is_alive(entity)) return nullptr;
        if (local_slot >= entities_->field_count(entity)) return nullptr;
        size_t idx = field_storage_index(entity, local_slot);
        return idx < fields_.size() ? &fields_[idx] : nullptr;
    }
    const Field* field_at_local_slot(EntityId entity, uint16_t local_slot) const {
        if (!entities_ || !entities_->is_alive(entity)) return nullptr;
        if (local_slot >= entities_->field_count(entity)) return nullptr;
        size_t idx = field_storage_index(entity, local_slot);
        return idx < fields_.size() ? &fields_[idx] : nullptr;
    }

    void clear() { fields_.clear(); }

private:
    EntityStore* entities_ = nullptr;
    std::vector<Field> fields_;
};

} // namespace uc
