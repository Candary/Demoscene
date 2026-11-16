#include "../ucleaner_types.h"
#include "../entity_store.h"
#include "../prop_store.h"
#include "../dep_graph.h"
#include "../flow_scheduler.h"
#include <cassert>
#include <cstdio>
#include <vector>
#include <string>
using namespace uc;

static FieldId mkfield(EntityStore& e, PropStore& p, const char* en, const char* fn) {
    EntityId id = e.find_by_name(fnv1a(en)); if (id == ENTITY_NULL) e.create_entity(fnv1a(en), id);
    FieldId f; p.add_field(id, fnv1a(fn), PropType::Float, f);
    return f;
}

void test_flow_coalesce() {
    EntityStore e; PropStore p; p.set_entity_store(&e); DepGraph d; FlowScheduler fl;
    FieldId a = mkfield(e,p,"@e1","a");
    int calls=0;
    fl.register_handler(a, [&](FieldId, PropStore&) -> Status { calls++; return Status::Ok; });
    for (int i=0;i<100;i++) fl.enqueue(a);
    assert(fl.queue_size()==1);
    assert(fl.run(p,d) == Status::Ok);
    assert(calls==1);
    printf("[PASS] T13: flow_coalesce\n");
}
void test_flow_batch() {
    EntityStore e; PropStore p; p.set_entity_store(&e); DepGraph d; FlowScheduler fl;
    FieldId a=mkfield(e,p,"@e1","a"); FieldId b=mkfield(e,p,"@e2","b"); FieldId c=mkfield(e,p,"@e3","c");
    d.add_dependency(a,b); d.add_dependency(a,c);
    int ca=0,cb=0,cc=0;
    fl.register_handler(a,[&](FieldId,PropStore&)->Status{ca++;return Status::Ok;});
    fl.register_handler(b,[&](FieldId,PropStore&)->Status{cb++;return Status::Ok;});
    fl.register_handler(c,[&](FieldId,PropStore&)->Status{cc++;return Status::Ok;});
    fl.enqueue(a); fl.enqueue(a); fl.enqueue(a);
    assert(fl.run(p,d)==Status::Ok);
    assert(ca==1 && cb==1 && cc==1);
    printf("[PASS] T14: flow_batch\n");
}
void test_flow_handler_error() {
    EntityStore e; PropStore p; p.set_entity_store(&e); DepGraph d; FlowScheduler fl;
    FieldId a=mkfield(e,p,"@e1","a"); FieldId b=mkfield(e,p,"@e2","b");
    d.add_dependency(a,b);
    int cb=0;
    fl.register_handler(a,[&](FieldId,PropStore&)->Status{return Status::InvalidField;});
    fl.register_handler(b,[&](FieldId,PropStore&)->Status{cb++;return Status::Ok;});
    fl.enqueue(a);
    assert(fl.run(p,d) == Status::InvalidField);
    assert(cb==0);
    printf("[PASS] T15: flow_handler_error\n");
}
void test_flow_depth_exceeded() {
    EntityStore e; PropStore p; p.set_entity_store(&e); DepGraph d; FlowScheduler fl;
    const int N=100;
    std::vector<FieldId> f;
    for (int i=0;i<N;i++) { char nm[32]; snprintf(nm,32,"@e%d",i); f.push_back(mkfield(e,p,nm,"v")); }
    for (int i=0;i<N-1;i++) d.add_dependency(f[i],f[i+1]);
    fl.set_max_iterations(10);
    fl.enqueue(f[0]);
    assert(fl.run(p,d) == Status::DepthExceeded);
    printf("[PASS] T16: flow_depth_exceeded\n");
}
void test_lowlevel_no_notify() {
    EntityStore e; PropStore p; p.set_entity_store(&e); DepGraph d; FlowScheduler fl;
    FieldId a=mkfield(e,p,"@e1","a");
    int calls=0;
    fl.register_handler(a,[&](FieldId,PropStore&)->Status{calls++;return Status::Ok;});
    p.set_float(field_entity(a), fnv1a("a"), 42.0f);
    assert(calls==0);
    printf("[PASS] T18: lowlevel_no_notify\n");
}

int main() {
    test_flow_coalesce(); test_flow_batch(); test_flow_handler_error();
    test_flow_depth_exceeded(); test_lowlevel_no_notify();
    printf("\nAll flow tests passed.\n"); return 0;
}
