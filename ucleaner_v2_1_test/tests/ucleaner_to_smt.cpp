// ucleaner_to_smt.cpp — Phase 1 integration: uCleaner → .smt bridge
// Reads uLang file, loads into uCleaner Context, generates valid demo.smt
// This replaces hardcoded scene data with declarative uLang entities.
//
// Build: g++ -std=c++17 -O2 -Wall -Wextra -I. tests/ucleaner_to_smt.cpp -o build/ucleaner_to_smt
// Run:   ./build/ucleaner_to_smt demo_v63.uc > generated_demo.smt

#include "ucleaner.h"
#include "ulang_parser.h"
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

using namespace uc;

struct SceneDecl {
    std::string name;
    EntityId id;
    EntityId palette_id;
    EntityId camera_id;
    float start, end;
    float intensity, motion_speed, pulse;
    uint32_t shader_hash;
    uint32_t trans_in_hash, trans_out_hash;
};

static std::string hash_to_string(uint32_t h) {
    // Reverse-lookup: we can't get strings from hash, so we use a known mapping.
    // In production, uCleaner would store strings. For now, we map known values.
    static const struct { uint32_t h; const char* s; } map[] = {
        {fnv1a("dawn"), "dawn"},
        {fnv1a("spire"), "spire"},
        {fnv1a("fall"), "fall"},
        {fnv1a("crossfade"), "crossfade"},
        {fnv1a("fade"), "fade"},
        {fnv1a("bloom"), "bloom"},
        {fnv1a("flash"), "flash"},
    };
    for (auto& m : map) if (m.h == h) return m.s;
    return "unknown";
}

int main(int argc, char** argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <input.uc> [output.smt]\n", argv[0]);
        return 1;
    }

    // Read uLang file
    std::ifstream f(argv[1]);
    if (!f) { fprintf(stderr, "ERROR: cannot open %s\n", argv[1]); return 1; }
    std::stringstream ss; ss << f.rdbuf();
    std::string text = ss.str();

    // Parse uLang → IR
    UlangParser parser;
    IR ir;
    Status s = parser.compile(text.c_str(), ir);
    if (s != Status::Ok) {
        fprintf(stderr, "PARSE ERROR: %s\n", parser.last_error().c_str());
        return 1;
    }
    printf("[uCleaner→.smt] Parsed %zu entities from uLang\n", ir.entities.size());

    // Resolve references
    s = parser.resolve_refs(ir);
    if (s != Status::Ok) {
        fprintf(stderr, "RESOLVE ERROR: %s\n", parser.last_error().c_str());
        return 1;
    }
    printf("[uCleaner→.smt] All references resolved\n");

    // Load into uCleaner Context
    Context ctx;
    for (const auto& ent : ir.entities) {
        EntityId eid;
        ctx.create_entity(ent.name_hash, eid);
        for (const auto& fld : ent.fields) {
            FieldId fid;
            if (fld.type == PropType::Float) {
                ctx.add_field(eid, fld.name_hash, PropType::Float, fid);
                ctx.props.set_float(eid, fld.name_hash, fld.f_val);
            } else if (fld.type == PropType::Vec3) {
                ctx.add_field(eid, fld.name_hash, PropType::Vec3, fid);
                ctx.props.set_vec3(eid, fld.name_hash, fld.v3_val);
            } else if (fld.type == PropType::Hash) {
                ctx.add_field(eid, fld.name_hash, PropType::Hash, fid);
                // Directly set hash value (PropStore has no set_hash method)
                Field* hf = ctx.props.get_field(eid, fld.name_hash);
                if (hf) { hf->val.hash = fld.hash_val; hf->version = 1; }
            } else if (fld.type == PropType::Id) {
                ctx.add_field(eid, fld.name_hash, PropType::Id, fid);
                EntityId ref_id = ctx.entities.find_by_name(fld.ref_hash);
                if (ref_id != ENTITY_NULL) {
                    ctx.props.set_id(eid, fld.name_hash, ref_id);
                }
            }
        }
    }
    printf("[uCleaner→.smt] Loaded %zu entities into Context\n", ir.entities.size());

    // --- Phase 1: Uroboros adapter — read timeline from uCleaner ---
    EntityId tl_id = ctx.entities.find_by_name(fnv1a("@timeline"));
    float duration = 0;
    if (tl_id != ENTITY_NULL) {
        duration = ctx.props.get_float(tl_id, fnv1a("duration"));
    }
    printf("[Phase 1: Uroboros] duration = %.1f (from uCleaner, not hardcoded)\n", duration);

    // --- Phase 2: Scene Manager adapter — read scenes from uCleaner ---
    std::vector<SceneDecl> scenes;
    for (size_t i = 0; i < ir.entities.size(); i++) {
        EntityId eid = ctx.entities.find_by_name(ir.entities[i].name_hash);
        if (eid == ENTITY_NULL) continue;

        // Check if type == "scene" (hash)
        const Field* type_f = ctx.props.get_field_const(eid, fnv1a("type"));
        if (!type_f || type_f->type != PropType::Hash) continue;
        if (type_f->val.hash != fnv1a("scene")) continue;

        SceneDecl sc;
        sc.name = ir.entities[i].name;
        sc.id = eid;
        sc.start = ctx.props.get_float(eid, fnv1a("start"));
        sc.end = ctx.props.get_float(eid, fnv1a("end"));
        sc.intensity = ctx.props.get_float(eid, fnv1a("intensity"));
        sc.motion_speed = ctx.props.get_float(eid, fnv1a("motion_speed"));
        sc.pulse = ctx.props.get_float(eid, fnv1a("pulse"));
        sc.palette_id = ctx.props.get_id(eid, fnv1a("palette"));
        sc.camera_id = ctx.props.get_id(eid, fnv1a("camera"));

        const Field* sh_f = ctx.props.get_field_const(eid, fnv1a("shader"));
        sc.shader_hash = sh_f ? sh_f->val.hash : 0;

        const Field* ti_f = ctx.props.get_field_const(eid, fnv1a("transition_in"));
        sc.trans_in_hash = ti_f ? ti_f->val.hash : 0;
        const Field* to_f = ctx.props.get_field_const(eid, fnv1a("transition_out"));
        sc.trans_out_hash = to_f ? to_f->val.hash : 0;

        scenes.push_back(sc);
    }
    printf("[Phase 2: Scene Manager] %zu scenes loaded from uCleaner\n", scenes.size());

    // --- Phase 3: Motus adapter — read camera from uCleaner ---
    // (Camera is static in v63, so just verify it exists)
    EntityId cam_id = ctx.entities.find_by_name(fnv1a("@cam_static"));
    if (cam_id != ENTITY_NULL) {
        float fov = ctx.props.get_float(cam_id, fnv1a("fov"));
        printf("[Phase 3: Motus] camera fov = %.1f (from uCleaner)\n", fov);
    }

    // --- Phase 4: Color Matrix adapter — read palettes from uCleaner ---
    int pal_count = 0;
    for (size_t i = 0; i < ir.entities.size(); i++) {
        EntityId eid = ctx.entities.find_by_name(ir.entities[i].name_hash);
        if (eid == ENTITY_NULL) continue;
        const Field* type_f = ctx.props.get_field_const(eid, fnv1a("type"));
        // Palettes don't have "type" field in demo_v63.uc, they have base_r etc.
        const Field* br = ctx.props.get_field_const(eid, fnv1a("base_r"));
        if (br && br->type == PropType::Float) {
            pal_count++;
            float r = ctx.props.get_float(eid, fnv1a("base_r"));
            float g = ctx.props.get_float(eid, fnv1a("base_g"));
            float b = ctx.props.get_float(eid, fnv1a("base_b"));
            printf("[Phase 4: Color Matrix] %s base = (%.2f, %.2f, %.2f)\n",
                   ir.entities[i].name.c_str(), r, g, b);
        }
    }

    // --- Generate .smt output ---
    std::string out_path = (argc >= 3) ? argv[2] : "generated_demo.smt";
    FILE* out = fopen(out_path.c_str(), "w");
    if (!out) { fprintf(stderr, "ERROR: cannot write %s\n", out_path.c_str()); return 1; }

    // Header
    fprintf(out, "SMT 1\n");
    fprintf(out, "meta %.1f 60 1280 720 2026\n", duration);
    fprintf(out, "audio 128.0 0.0 4 0.25 15");
    for (int i = 0; i < 15; i++) fprintf(out, " %.2f", 0.1f + 0.05f * i);
    fprintf(out, "\n");
    fprintf(out, "sections %zu", scenes.size());
    for (auto& sc : scenes) fprintf(out, " %.1f", sc.start);
    fprintf(out, "\n\n");

    // Scene clips
    for (size_t i = 0; i < scenes.size(); i++) {
        auto& sc = scenes[i];
        float next_start = (i + 1 < scenes.size()) ? scenes[i+1].start : sc.end;
        float eff_start = sc.start;
        float eff_end = next_start;

        fprintf(out, "clip s%zu 10 scene %s %.1f %.1f %.1f %.1f normal %zu - - 0.0\n",
                i+1, hash_to_string(sc.shader_hash).c_str(),
                eff_start, eff_end, sc.start, sc.end - sc.start,
                11111 + i * 11111);
        fprintf(out, "prog opacity 1 n:1.0\n");
        fprintf(out, "prog progress 4 v:p n:0.0 n:1.0 f:clamp\n");

        // Palette uniforms from uCleaner
        if (sc.palette_id != ENTITY_NULL) {
            float br = ctx.props.get_float(sc.palette_id, fnv1a("base_r"));
            float bg = ctx.props.get_float(sc.palette_id, fnv1a("base_g"));
            float bb = ctx.props.get_float(sc.palette_id, fnv1a("base_b"));
            fprintf(out, "uni uPrimaryColor vec3 3\nprog 1 n:%.4f\nprog 1 n:%.4f\nprog 1 n:%.4f\n", br, bg, bb);

            float ar = ctx.props.get_float(sc.palette_id, fnv1a("accent1_r"));
            float ag = ctx.props.get_float(sc.palette_id, fnv1a("accent1_g"));
            float ab = ctx.props.get_float(sc.palette_id, fnv1a("accent1_b"));
            fprintf(out, "uni uAccentColor vec3 3\nprog 1 n:%.4f\nprog 1 n:%.4f\nprog 1 n:%.4f\n", ar, ag, ab);

            fprintf(out, "uni uIntensity float 1\nprog 1 n:%.4f\n", sc.intensity);
            fprintf(out, "uni uMotionSpeed float 1\nprog 1 n:%.4f\n", sc.motion_speed);
            fprintf(out, "uni uPulse float 1\nprog 1 n:%.4f\n", sc.pulse);
        }
        fprintf(out, "endclip\n\n");
    }

    // Post-processing clips (reuse from v63)
    const char* post_clips[] = {
        "clip blm_bright 24 post bloom_bright 0.0 %.1f 0.0 %.1f normal 77007 - - 0.0\nprog opacity 1 n:1.0\nprog progress 4 v:p n:0.0 n:1.0 f:clamp\nuni uThreshold float 1\nprog 1 n:0.6\nuni uIntensity float 1\nprog 1 n:1.0\nendclip\n",
        "clip blm_blurh 24 post bloom_blur 0.0 %.1f 0.0 %.1f normal 77008 - - 0.0\nprog opacity 1 n:1.0\nprog progress 4 v:p n:0.0 n:1.0 f:clamp\nuni uDirection vec2 2\nprog 1 n:1.0\nprog 1 n:0.0\nendclip\n",
        "clip blm_blurv 24 post bloom_blur 0.0 %.1f 0.0 %.1f normal 77009 - - 0.0\nprog opacity 1 n:1.0\nprog progress 4 v:p n:0.0 n:1.0 f:clamp\nuni uDirection vec2 2\nprog 1 n:0.0\nprog 1 n:1.0\nendclip\n",
        "clip blm_add 24 post passthrough 0.0 %.1f 0.0 %.1f normal 77010 - - 0.0\nprog opacity 1 n:1.0\nprog progress 4 v:p n:0.0 n:1.0 f:clamp\nendclip\n",
        "clip vig 25 post vignette 0.0 %.1f 0.0 %.1f normal 99001 - - 0.0\nprog opacity 1 n:1.0\nprog progress 4 v:p n:0.0 n:1.0 f:clamp\nuni uStrength float 1\nprog 1 n:0.35\nuni uSoftness float 1\nprog 1 n:0.5\nendclip\n",
        "clip grn 25 post grain 0.0 %.1f 0.0 %.1f normal 88008 - - 0.0\nprog opacity 1 n:1.0\nprog progress 4 v:p n:0.0 n:1.0 f:clamp\nuni uAmount float 1\nprog 1 n:0.03\nuni uExposure float 1\nprog 1 n:0.55\nendclip\n",
        "clip fin 30 event finish %.1f %.1f %.1f 0.0 0.0 normal 77777 - - 0.0\nprog opacity 1 n:1.0\nprog progress 4 v:p n:0.0 n:1.0 f:clamp\nendclip\n",
    };
    for (auto& pc : post_clips) {
        fprintf(out, pc, duration, duration, duration, duration, duration, duration);
    }
    fprintf(out, "\n");

    // Segments — one per scene
    for (size_t i = 0; i < scenes.size(); i++) {
        auto& sc = scenes[i];
        float next_start = (i + 1 < scenes.size()) ? scenes[i+1].start : duration;
        fprintf(out, "seg %.1f %.1f 8 2 5\n", sc.start, next_start);
        fprintf(out, "op RENDER s%zu - fbo0 - -\n", i+1);
        fprintf(out, "op POST blm_bright fbo0 fbo1 - -\n");
        fprintf(out, "op POST blm_blurh fbo1 fbo2 - -\n");
        fprintf(out, "op POST blm_blurv fbo2 fbo1 - -\n");
        fprintf(out, "op COMPOSITE blm_add fbo1 - fbo0 add\n");
        fprintf(out, "op POST vig fbo0 fbo1 - -\n");
        fprintf(out, "op POST grn fbo1 screen - -\n");
        fprintf(out, "op PRESENT - screen - - -\n");
        fprintf(out, "endseg\n");
    }
    fprintf(out, "end\n");
    fclose(out);

    printf("[uCleaner→.smt] Generated %s (%zu scenes, %.1fs)\n",
           out_path.c_str(), scenes.size(), duration);
    return 0;
}
