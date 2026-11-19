// ucleaner.h — transcribed from Final Qwen.md Step 7 (Context)
#pragma once
#include "ucleaner_types.h"
#include "entity_store.h"
#include "prop_store.h"
#include "dep_graph.h"
#include "patch_engine.h"
#include "flow_scheduler.h"

namespace uc {

class Context {
public:
    EntityStore entities;
    PropStore props;
    DepGraph deps;
    PatchEngine patches;
    FlowScheduler flow;

    Context() { props.set_entity_store(&entities); }

    Status create_entity(uint32_t name_hash, EntityId& out_id) {
        return entities.create_entity(name_hash, out_id);
    }
    Status destroy_entity(EntityId id) {
        Status s = entities.destroy_entity(id);
        if (s == Status::Ok) deps.remove_entity_dependencies(id);
        return s;
    }
    Status add_field(EntityId entity, uint32_t name_hash, PropType type, FieldId& out_field_id) {
        return props.add_field(entity, name_hash, type, out_field_id);
    }

    Status set_float(EntityId entity, uint32_t name_hash, float value, uint32_t expected_version = 0) {
        Field* f = props.get_field(entity, name_hash);
        if (!f) return Status::InvalidField;
        // Fix #2: use local_slot (0..31) for FieldId, not global index
        FieldId field_id = make_field_id(entity, f->slot);
        Patch p = patches.create_patch();
        patches.patch_set_float(p, field_id, name_hash, value, expected_version);
        Status s = patches.validate(p, entities, props);
        if (s != Status::Ok) return s;
        s = patches.apply(p, props);
        if (s != Status::Ok) return s;
        s = flow.enqueue(field_id);
        if (s != Status::Ok) return s;
        return flow.run(props, deps);
    }

    Status set_float_batch(EntityId entity, uint32_t name_hash, float value, uint32_t expected_version = 0) {
        Field* f = props.get_field(entity, name_hash);
        if (!f) return Status::InvalidField;
        // Fix #2: use local_slot
        FieldId field_id = make_field_id(entity, f->slot);
        Patch p = patches.create_patch();
        patches.patch_set_float(p, field_id, name_hash, value, expected_version);
        Status s = patches.validate(p, entities, props);
        if (s != Status::Ok) return s;
        s = patches.apply(p, props);
        if (s != Status::Ok) return s;
        return flow.enqueue(field_id);
    }

    Status flow_run() { return flow.run(props, deps); }
    float get_float(EntityId entity, uint32_t name_hash) const { return props.get_float(entity, name_hash); }

    Status add_dependency(FieldId src, FieldId dst) { return deps.add_dependency(src, dst); }
    bool validate_graph() const { return !deps.has_cycle(); }
    void register_handler(FieldId field, FieldHandler handler) { flow.register_handler(field, handler); }
};

} // namespace uc
