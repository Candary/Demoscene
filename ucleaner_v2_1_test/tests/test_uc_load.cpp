#include "ucleaner.h"
#include "ulang_parser.h"
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>

int main() {
    // Read uLang file
    std::ifstream f("demo_v63.uc");
    if (!f) { printf("ERROR: cannot open demo_v63.uc\n"); return 1; }
    std::stringstream ss; ss << f.rdbuf();
    std::string text = ss.str();

    // Parse
    uc::UlangParser parser;
    uc::IR ir;
    uc::Status s = parser.compile(text.c_str(), ir);
    if (s != uc::Status::Ok) {
        printf("PARSE ERROR: %s\n", parser.last_error().c_str());
        return 1;
    }
    printf("[OK] Parsed %zu entities\n", ir.entities.size());

    // Resolve refs
    s = parser.resolve_refs(ir);
    if (s != uc::Status::Ok) {
        printf("RESOLVE ERROR: %s\n", parser.last_error().c_str());
        return 1;
    }
    printf("[OK] All references resolved\n");

    // Print entities
    for (const auto& ent : ir.entities) {
        printf("  %s (%zu fields):\n", ent.name.c_str(), ent.fields.size());
        for (const auto& fld : ent.fields) {
            printf("    %s: ", fld.name.c_str());
            switch (fld.type) {
                case uc::PropType::Float: printf("float=%.2f\n", fld.f_val); break;
                case uc::PropType::Vec3: printf("vec3=[%.1f,%.1f,%.1f]\n", fld.v3_val[0], fld.v3_val[1], fld.v3_val[2]); break;
                case uc::PropType::Hash: printf("hash=0x%08x\n", fld.hash_val); break;
                case uc::PropType::Id: printf("ref=%s\n", fld.ref_name.c_str()); break;
                default: printf("?\n"); break;
            }
        }
    }

    // Load into uCleaner Context
    uc::Context ctx;
    // Create entities from IR
    for (const auto& ent : ir.entities) {
        uc::EntityId eid;
        ctx.create_entity(ent.name_hash, eid);
        for (const auto& fld : ent.fields) {
            uc::FieldId fid;
            if (fld.type == uc::PropType::Float) {
                ctx.add_field(eid, fld.name_hash, uc::PropType::Float, fid);
                ctx.props.set_float(eid, fld.name_hash, fld.f_val);
            } else if (fld.type == uc::PropType::Vec3) {
                ctx.add_field(eid, fld.name_hash, uc::PropType::Vec3, fid);
                ctx.props.set_vec3(eid, fld.name_hash, fld.v3_val);
            } else if (fld.type == uc::PropType::Hash) {
                ctx.add_field(eid, fld.name_hash, uc::PropType::Hash, fid);
            } else if (fld.type == uc::PropType::Id) {
                ctx.add_field(eid, fld.name_hash, uc::PropType::Id, fid);
                // Resolve ref to entity ID
                uc::EntityId ref_id = ctx.entities.find_by_name(fld.ref_hash);
                if (ref_id != uc::ENTITY_NULL) {
                    ctx.props.set_id(eid, fld.name_hash, ref_id);
                }
            }
        }
    }

    // Verify: read back scene_dawn
    uc::EntityId dawn_id = ctx.entities.find_by_name(uc::fnv1a("@scene_dawn"));
    if (dawn_id != uc::ENTITY_NULL) {
        uc::EntityId pal_id = ctx.props.get_id(dawn_id, uc::fnv1a("palette"));
        float intensity = ctx.props.get_float(dawn_id, uc::fnv1a("intensity"));
        printf("\n[VERIFY] @scene_dawn: palette_id=%u, intensity=%.2f\n", pal_id, intensity);
        if (pal_id != uc::ENTITY_NULL) {
            float r = ctx.props.get_float(pal_id, uc::fnv1a("base_r"));
            printf("  palette base_r = %.2f\n", r);
        }
    }

    // Verify: timeline duration
    uc::EntityId tl_id = ctx.entities.find_by_name(uc::fnv1a("@timeline"));
    float dur = ctx.props.get_float(tl_id, uc::fnv1a("duration"));
    printf("[VERIFY] @timeline: duration=%.1f\n", dur);

    printf("\n[FLOW] All %zu entities loaded into uCleaner Context.\n", ir.entities.size());
    return 0;
}
