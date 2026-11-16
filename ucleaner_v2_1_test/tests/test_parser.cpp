#include "../ucleaner_types.h"
#include "../ulang_parser.h"
#include <cassert>
#include <cstdio>
using namespace uc;

void test_lang_parse_basic() {
    UlangParser parser; IR ir;
    const char* src = R"UC(
        entity @scene_1 {
            "start": 0.0
            "end": 30.0
            "position": [1.0, 2.0, 3.0]
            "mood": "dreamy"
        }
    )UC";
    assert(parser.compile(src, ir) == Status::Ok);
    assert(ir.entities.size() == 1);
    assert(ir.entities[0].name == "@scene_1");
    assert(ir.entities[0].fields.size() == 4);
    assert(ir.entities[0].fields[0].name == "start");
    assert(ir.entities[0].fields[0].type == PropType::Float);
    assert(ir.entities[0].fields[0].f_val == 0.0f);
    assert(ir.entities[0].fields[2].type == PropType::Vec3);
    assert(ir.entities[0].fields[2].v3_val[1] == 2.0f);
    assert(ir.entities[0].fields[3].type == PropType::Hash);
    printf("[PASS] T20: lang_parse_basic\n");
}
void test_lang_parse_error() {
    UlangParser parser; IR ir;
    const char* src = "entity @scene_1 { \"start\": 0.0\n";
    assert(parser.compile(src, ir) == Status::ParseError);
    assert(!parser.last_error().empty());
    printf("[PASS] T21: lang_parse_error\n");
}
void test_lang_ref_resolve() {
    UlangParser parser; IR ir;
    const char* src = R"UC(
        entity @cam_1 { "fov": 60.0 }
        entity @scene_1 { "camera": @cam_1 }
    )UC";
    assert(parser.compile(src, ir) == Status::Ok);
    assert(parser.resolve_refs(ir) == Status::Ok);
    assert(ir.entities[1].fields[0].type == PropType::Id);
    assert(ir.entities[1].fields[0].ref_hash == fnv1a("@cam_1"));
    IR ir_bad;
    parser.compile("entity @s { \"c\": @missing }", ir_bad);
    assert(parser.resolve_refs(ir_bad) == Status::NotFound);
    printf("[PASS] T22: lang_ref_resolve\n");
}
void test_lang_no_auto_field_deps() {
    UlangParser parser; IR ir;
    const char* src = R"UC(
        entity @cam_1 { "fov": 60.0 }
        entity @scene_1 { "camera": @cam_1 }
    )UC";
    parser.compile(src, ir);
    parser.resolve_refs(ir);
    assert(ir.entities.size() == 2);
    assert(ir.entities[1].fields[0].type == PropType::Id);
    printf("[PASS] T23: lang_no_auto_field_deps\n");
}

int main() {
    test_lang_parse_basic(); test_lang_parse_error();
    test_lang_ref_resolve(); test_lang_no_auto_field_deps();
    printf("\nAll parser tests passed.\n"); return 0;
}
