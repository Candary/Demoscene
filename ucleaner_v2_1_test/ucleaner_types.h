// ucleaner_types.h — transcribed from Final Qwen.md Step 1
#pragma once
#include <cstdint>
#include <cstddef>

namespace uc {

using EntityId = uint32_t;
constexpr EntityId ENTITY_NULL = 0;

inline uint16_t entity_index(EntityId id) { return static_cast<uint16_t>(id & 0xFFFF); }
inline uint16_t entity_generation(EntityId id) { return static_cast<uint16_t>(id >> 16); }
inline EntityId make_entity_id(uint16_t generation, uint16_t index) {
    return (static_cast<EntityId>(generation) << 16) | static_cast<EntityId>(index);
}

using FieldId = uint64_t;
constexpr FieldId FIELD_NULL = 0;

inline EntityId field_entity(FieldId id) { return static_cast<EntityId>(id >> 32); }
inline uint16_t field_slot(FieldId id) { return static_cast<uint16_t>((id >> 16) & 0xFFFF); }
inline FieldId make_field_id(EntityId entity, uint16_t slot) {
    return (static_cast<FieldId>(entity) << 32) | (static_cast<FieldId>(slot) << 16);
}

enum class PropType : uint8_t {
    None=0, Float=1, Int=2, Id=3, Vec3=4, Hash=5,
};

enum class Status : int {
    Ok=0, InvalidEntity=1, InvalidField=2, VersionMismatch=3,
    CycleDetected=4, DepthExceeded=5, NotFound=6, ParseError=7,
    TypeMismatch=8, SelfReference=9, AlreadyExists=10, OutOfMemory=11,
    InvalidReference=12,
};

constexpr size_t MAX_ENTITIES = 4096;
constexpr size_t MAX_FIELDS_PER_ENTITY = 32;

inline uint32_t fnv1a(const char* s) {
    uint32_t h = 2166136261u;
    while (*s) { h ^= static_cast<uint8_t>(*s++); h *= 16777619u; }
    return h;
}

} // namespace uc
