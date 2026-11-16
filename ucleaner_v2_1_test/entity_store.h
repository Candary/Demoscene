// entity_store.h — transcribed from Final Qwen.md Step 2
// BUG FIX: gen starts at 1 (not 0) to avoid EntityId=0=ENTITY_NULL collision
#pragma once
#include "ucleaner_types.h"
#include <vector>
#include <unordered_map>

namespace uc {

struct EntitySlot {
    uint16_t generation = 0;
    uint16_t field_count = 0;
    uint32_t name_hash = 0;
    bool alive = false;
};

class EntityStore {
public:
    Status create_entity(uint32_t name_hash, EntityId& out_id) {
        auto it = name_to_id_.find(name_hash);
        if (it != name_to_id_.end()) {
            uint16_t idx = entity_index(it->second);
            if (idx < slots_.size() && slots_[idx].alive &&
                slots_[idx].generation == entity_generation(it->second)) {
                return Status::AlreadyExists;
            }
        }
        uint16_t idx;
        uint16_t gen;
        if (!free_list_.empty()) {
            idx = free_list_.back();
            free_list_.pop_back();
            gen = slots_[idx].generation + 1;
        } else {
            if (slots_.size() >= MAX_ENTITIES) return Status::OutOfMemory;
            idx = static_cast<uint16_t>(slots_.size());
            gen = 1;  // FIX: was 0, caused id=0=ENTITY_NULL for first entity
            slots_.emplace_back();
        }
        EntitySlot& slot = slots_[idx];
        slot.generation = gen;
        slot.field_count = 0;
        slot.name_hash = name_hash;
        slot.alive = true;
        EntityId id = make_entity_id(gen, idx);
        name_to_id_[name_hash] = id;
        out_id = id;
        return Status::Ok;
    }

    Status destroy_entity(EntityId id) {
        if (id == ENTITY_NULL) return Status::InvalidEntity;
        uint16_t idx = entity_index(id);
        if (idx >= slots_.size()) return Status::InvalidEntity;
        EntitySlot& slot = slots_[idx];
        if (!slot.alive) return Status::InvalidEntity;
        if (slot.generation != entity_generation(id)) return Status::InvalidEntity;
        slot.alive = false;
        slot.field_count = 0;
        free_list_.push_back(idx);
        name_to_id_.erase(slot.name_hash);
        return Status::Ok;
    }

    bool is_alive(EntityId id) const {
        if (id == ENTITY_NULL) return false;
        uint16_t idx = entity_index(id);
        if (idx >= slots_.size()) return false;
        const EntitySlot& slot = slots_[idx];
        return slot.alive && slot.generation == entity_generation(id);
    }

    EntityId find_by_name(uint32_t name_hash) const {
        auto it = name_to_id_.find(name_hash);
        if (it == name_to_id_.end()) return ENTITY_NULL;
        if (!is_alive(it->second)) return ENTITY_NULL;
        return it->second;
    }

    uint32_t name_hash_of(EntityId id) const {
        if (!is_alive(id)) return 0;
        return slots_[entity_index(id)].name_hash;
    }
    uint16_t field_count(EntityId id) const {
        if (!is_alive(id)) return 0;
        return slots_[entity_index(id)].field_count;
    }
    void inc_field_count(EntityId id) {
        if (is_alive(id)) slots_[entity_index(id)].field_count++;
    }
    size_t entity_count() const {
        size_t c = 0; for (const auto& s : slots_) if (s.alive) c++; return c;
    }
    void clear() { slots_.clear(); free_list_.clear(); name_to_id_.clear(); }

private:
    std::vector<EntitySlot> slots_;
    std::vector<uint16_t> free_list_;
    std::unordered_map<uint32_t, EntityId> name_to_id_;
};

} // namespace uc
