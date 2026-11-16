// tests/test_entity.cpp — T1, T2, T3
// FIX: entity_generation(id1) == 1 (not 0) after gen=1 fix
#include "../ucleaner_types.h"
#include "../entity_store.h"
#include <cassert>
#include <cstdio>

using namespace uc;

void test_entity_stable_id() {
    EntityStore store;
    EntityId id1;
    assert(store.create_entity(fnv1a("@scene_1"), id1) == Status::Ok);
    assert(store.is_alive(id1));
    assert(entity_index(id1) == 0);
    assert(entity_generation(id1) == 1);  // FIX: was 0

    EntityId id1_copy = id1;
    assert(store.destroy_entity(id1_copy) == Status::Ok);
    assert(!store.is_alive(id1));
    assert(!store.is_alive(id1_copy));

    EntityId id2;
    assert(store.create_entity(fnv1a("@scene_2"), id2) == Status::Ok);
    assert(store.is_alive(id2));
    assert(entity_index(id2) == entity_index(id1));
    assert(entity_generation(id2) == entity_generation(id1) + 1);
    printf("[PASS] T1: entity_stable_id\n");
}

void test_entity_name_collision() {
    EntityStore store;
    EntityId id1;
    assert(store.create_entity(fnv1a("@unique"), id1) == Status::Ok);
    EntityId id2;
    assert(store.create_entity(fnv1a("@unique"), id2) == Status::AlreadyExists);
    store.destroy_entity(id1);
    EntityId id3;
    assert(store.create_entity(fnv1a("@unique"), id3) == Status::Ok);
    assert(store.is_alive(id3));
    printf("[PASS] T2: entity_name_collision\n");
}

void test_field_id_layout() {
    for (uint16_t gen = 0; gen < 4; gen++) {
        for (uint16_t idx = 0; idx < 256; idx += 17) {
            EntityId e = make_entity_id(gen, idx);
            for (uint16_t slot = 0; slot < MAX_FIELDS_PER_ENTITY; slot++) {
                FieldId f = make_field_id(e, slot);
                assert(field_entity(f) == e);
                assert(field_slot(f) == slot);
            }
        }
    }
    printf("[PASS] T3: field_id_layout\n");
}

int main() {
    test_entity_stable_id();
    test_entity_name_collision();
    test_field_id_layout();
    printf("\nAll entity tests passed.\n");
    return 0;
}
