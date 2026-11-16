#include "../ucleaner_types.h"
#include "../entity_store.h"
#include "../prop_store.h"
#include "../dep_graph.h"
#include <cassert>
#include <cstdio>
using namespace uc;

static FieldId mkfield(EntityStore& e, PropStore& p, const char* en, const char* fn) {
    EntityId id = e.find_by_name(fnv1a(en)); if (id == ENTITY_NULL) e.create_entity(fnv1a(en), id);
    FieldId f; p.add_field(id, fnv1a(fn), PropType::Float, f);
    return f;
}

void test_dep_self_reference() {
    EntityStore e; PropStore p; p.set_entity_store(&e); DepGraph d;
    FieldId a = mkfield(e,p,"@e1","a");
    assert(d.add_dependency(a,a) == Status::SelfReference);
    printf("[PASS] T9: dep_self_reference\n");
}
void test_dep_duplicate() {
    EntityStore e; PropStore p; p.set_entity_store(&e); DepGraph d;
    FieldId a = mkfield(e,p,"@e1","a"); FieldId b = mkfield(e,p,"@e2","b");
    assert(d.add_dependency(a,b) == Status::Ok); assert(d.edge_count()==1);
    assert(d.add_dependency(a,b) == Status::Ok); assert(d.edge_count()==1);
    printf("[PASS] T10: dep_duplicate\n");
}
void test_cycle_a_b_a() {
    EntityStore e; PropStore p; p.set_entity_store(&e); DepGraph d;
    FieldId a = mkfield(e,p,"@e1","a"); FieldId b = mkfield(e,p,"@e2","b");
    d.add_dependency(a,b); d.add_dependency(b,a);
    assert(d.has_cycle());
    printf("[PASS] T11: cycle_a_b_a\n");
}
void test_cycle_a_b_c_a() {
    EntityStore e; PropStore p; p.set_entity_store(&e); DepGraph d;
    FieldId a = mkfield(e,p,"@e1","a"); FieldId b = mkfield(e,p,"@e2","b"); FieldId c = mkfield(e,p,"@e3","c");
    d.add_dependency(a,b); d.add_dependency(b,c); d.add_dependency(c,a);
    assert(d.has_cycle());
    printf("[PASS] T12: cycle_a_b_c_a\n");
}
void test_no_cycle_dag() {
    EntityStore e; PropStore p; p.set_entity_store(&e); DepGraph d;
    FieldId a = mkfield(e,p,"@e1","a"); FieldId b = mkfield(e,p,"@e2","b"); FieldId c = mkfield(e,p,"@e3","c");
    d.add_dependency(a,b); d.add_dependency(b,c);
    assert(!d.has_cycle());
    printf("[PASS] T13: no_cycle_dag\n");
}
void test_remove_entity_deps() {
    EntityStore e; PropStore p; p.set_entity_store(&e); DepGraph d;
    FieldId a = mkfield(e,p,"@e1","a"); FieldId b = mkfield(e,p,"@e2","b"); FieldId c = mkfield(e,p,"@e3","c");
    d.add_dependency(a,b); d.add_dependency(b,c);
    assert(d.edge_count()==2);
    d.remove_entity_dependencies(field_entity(b));
    assert(d.edge_count()==0);
    printf("[PASS] T14: remove_entity_deps\n");
}

int main() {
    test_dep_self_reference(); test_dep_duplicate(); test_cycle_a_b_a();
    test_cycle_a_b_c_a(); test_no_cycle_dag(); test_remove_entity_deps();
    printf("\nAll dep tests passed.\n"); return 0;
}
