#include "../ucleaner_types.h"
#include "../entity_store.h"
#include "../prop_store.h"
#include <cassert>
#include <cstdio>
using namespace uc;

void test_field_version_increment() {
    EntityStore entities; PropStore props; props.set_entity_store(&entities);
    EntityId id; entities.create_entity(fnv1a("@test"), id);
    FieldId f; assert(props.add_field(id, fnv1a("fov"), PropType::Float, f) == Status::Ok);
    assert(props.field_version(id, fnv1a("fov")) == 1);
    assert(props.set_float(id, fnv1a("fov"), 60.0f) == Status::Ok);
    assert(props.field_version(id, fnv1a("fov")) == 2);
    props.set_float(id, fnv1a("fov"), 75.0f);
    assert(props.field_version(id, fnv1a("fov")) == 3);
    printf("[PASS] T4: field_version_increment\n");
}

void test_field_type_mismatch() {
    EntityStore entities; PropStore props; props.set_entity_store(&entities);
    EntityId id; entities.create_entity(fnv1a("@test"), id);
    FieldId f; props.add_field(id, fnv1a("position"), PropType::Vec3, f);
    assert(props.set_float(id, fnv1a("position"), 42.0f) == Status::TypeMismatch);
    float pos[3]; props.get_vec3(id, fnv1a("position"), pos);
    assert(pos[0]==0.0f && pos[1]==0.0f && pos[2]==0.0f);
    printf("[PASS] T5: field_type_mismatch\n");
}

void test_version_conflict() {
    EntityStore entities; PropStore props; props.set_entity_store(&entities);
    EntityId id; entities.create_entity(fnv1a("@test"), id);
    FieldId f; props.add_field(id, fnv1a("x"), PropType::Float, f);
    props.set_float(id, fnv1a("x"), 1.0f);
    uint32_t v = props.field_version(id, fnv1a("x"));
    assert(v == 2);
    assert(props.set_float(id, fnv1a("x"), 2.0f, v+100) == Status::VersionMismatch);
    assert(props.get_float(id, fnv1a("x")) == 1.0f);
    assert(props.set_float(id, fnv1a("x"), 2.0f, v) == Status::Ok);
    assert(props.get_float(id, fnv1a("x")) == 2.0f);
    printf("[PASS] T6: version_conflict\n");
}

int main() { test_field_version_increment(); test_field_type_mismatch(); test_version_conflict(); printf("\nAll prop tests passed.\n"); return 0; }
