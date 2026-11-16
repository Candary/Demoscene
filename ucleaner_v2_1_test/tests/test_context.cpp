#include "../ucleaner.h"
#include <cassert>
#include <cstdio>
using namespace uc;

void test_set_float_returns_flow_status() {
    Context ctx;
    EntityId e1,e2;
    ctx.create_entity(fnv1a("@e1"),e1);
    ctx.create_entity(fnv1a("@e2"),e2);
    FieldId fa,fb;
    ctx.add_field(e1, fnv1a("a"), PropType::Float, fa);
    ctx.add_field(e2, fnv1a("b"), PropType::Float, fb);
    ctx.add_dependency(fa, fb);
    ctx.register_handler(fb, [](FieldId, PropStore&) -> Status { return Status::InvalidField; });
    assert(ctx.set_float(e1, fnv1a("a"), 42.0f) == Status::InvalidField);
    printf("[PASS] T17: set_float_returns_flow_status\n");
}
void test_highlevel_notifies() {
    Context ctx;
    EntityId e; ctx.create_entity(fnv1a("@e"),e);
    FieldId fx; ctx.add_field(e, fnv1a("x"), PropType::Float, fx);
    int calls=0;
    ctx.register_handler(fx, [&calls](FieldId, PropStore&) -> Status { calls++; return Status::Ok; });
    assert(ctx.set_float(e, fnv1a("x"), 10.0f) == Status::Ok);
    assert(calls==1);
    assert(ctx.get_float(e, fnv1a("x")) == 10.0f);
    printf("[PASS] T19: highlevel_notifies\n");
}
void test_batch_api() {
    Context ctx;
    EntityId e; ctx.create_entity(fnv1a("@e"),e);
    FieldId fa,fb;
    ctx.add_field(e, fnv1a("a"), PropType::Float, fa);
    ctx.add_field(e, fnv1a("b"), PropType::Float, fb);
    int calls=0;
    ctx.register_handler(fa, [&calls](FieldId, PropStore&) -> Status { calls++; return Status::Ok; });
    ctx.register_handler(fb, [&calls](FieldId, PropStore&) -> Status { calls++; return Status::Ok; });
    ctx.set_float_batch(e, fnv1a("a"), 1.0f);
    ctx.set_float_batch(e, fnv1a("b"), 2.0f);
    assert(calls==0);
    assert(ctx.flow_run() == Status::Ok);
    assert(calls==2);
    printf("[PASS] T14b: batch_api\n");
}

int main() {
    test_set_float_returns_flow_status();
    test_highlevel_notifies();
    test_batch_api();
    printf("\nAll context tests passed.\n"); return 0;
}
