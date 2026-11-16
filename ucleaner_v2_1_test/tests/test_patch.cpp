#include "../ucleaner_types.h"
#include "../entity_store.h"
#include "../prop_store.h"
#include "../patch_engine.h"
#include <cassert>
#include <cstdio>
using namespace uc;

static FieldId mkfield(EntityStore& e, PropStore& p, const char* en, const char* fn) {
    EntityId id = e.find_by_name(fnv1a(en)); if (id == ENTITY_NULL) e.create_entity(fnv1a(en), id);
    FieldId f; p.add_field(id, fnv1a(fn), PropType::Float, f);
    return f;
}

void test_patch_atomicity() {
    EntityStore e; PropStore p; p.set_entity_store(&e); PatchEngine pe;
    EntityId ent; e.create_entity(fnv1a("@test"), ent);
    FieldId fx = mkfield(e,p,"@test","x"); FieldId fy = mkfield(e,p,"@test","y");
    p.set_float(ent, fnv1a("x"), 1.0f); p.set_float(ent, fnv1a("y"), 2.0f);
    uint32_t vx = p.field_version(ent, fnv1a("x"));
    uint32_t vy = p.field_version(ent, fnv1a("y"));
    Patch pat = pe.create_patch();
    pe.patch_set_float(pat, fx, fnv1a("x"), 10.0f, vx);
    pe.patch_set_float(pat, fy, fnv1a("y"), 20.0f, vy+100);
    assert(pe.validate(pat, e, p) == Status::VersionMismatch);
    assert(p.get_float(ent, fnv1a("x")) == 1.0f);
    assert(p.get_float(ent, fnv1a("y")) == 2.0f);
    printf("[PASS] T7: patch_atomicity\n");
}
void test_patch_double_apply() {
    EntityStore e; PropStore p; p.set_entity_store(&e); PatchEngine pe;
    EntityId ent; e.create_entity(fnv1a("@test"), ent);
    FieldId fv = mkfield(e,p,"@test","v");
    Patch pat = pe.create_patch();
    pe.patch_set_float(pat, fv, fnv1a("v"), 5.0f);
    assert(pe.apply(pat, p) == Status::Ok);
    assert(p.get_float(ent, fnv1a("v")) == 5.0f);
    uint32_t v = p.field_version(ent, fnv1a("v"));
    assert(pe.apply(pat, p) == Status::Ok);
    assert(p.field_version(ent, fnv1a("v")) == v);
    printf("[PASS] T8: patch_double_apply\n");
}
void test_patch_type_mismatch() {
    EntityStore e; PropStore p; p.set_entity_store(&e); PatchEngine pe;
    EntityId ent; e.create_entity(fnv1a("@test"), ent);
    FieldId fp; p.add_field(ent, fnv1a("pos"), PropType::Vec3, fp);
    Patch pat = pe.create_patch();
    pe.patch_set_float(pat, fp, fnv1a("pos"), 42.0f);
    assert(pe.validate(pat, e, p) == Status::TypeMismatch);
    printf("[PASS] T5b: patch_type_mismatch\n");
}

int main() { test_patch_atomicity(); test_patch_double_apply(); test_patch_type_mismatch(); printf("\nAll patch tests passed.\n"); return 0; }
