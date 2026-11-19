// loader.h — загрузка uLang в Context одним вызовом.
//
// Двухпроходная схема: сначала все сущности и поля, затем значения-ссылки.
// Иначе ссылка вперёд (@scene_1 → @cam_2, объявленный ниже) не разрешается.
#pragma once

#include <fstream>
#include <sstream>
#include <string>

#include "ucleaner.h"
#include "ulang_parser.h"

namespace uc {

inline Status load_ir(Context& ctx, const IR& ir) {
    // Проход 1: сущности и поля (значения ссылок пока не пишем).
    for (const auto& entity : ir.entities) {
        EntityId id;
        Status s = ctx.create_entity(entity.name_hash, id);
        if (s != Status::Ok) return s;
        for (const auto& field : entity.fields) {
            FieldId fid;
            s = ctx.add_field(id, field.name_hash, field.type, fid);
            if (s != Status::Ok) return s;
            switch (field.type) {
                case PropType::Float:
                    ctx.props.set_float(id, field.name_hash, field.f_val);
                    break;
                case PropType::Vec3:
                    ctx.props.set_vec3(id, field.name_hash, field.v3_val);
                    break;
                case PropType::Hash: {
                    Field* f = ctx.props.get_field(id, field.name_hash);
                    if (f) {
                        f->val.hash = field.hash_val;
                        f->version = 2;   // 1 — создание, 2 — запись значения
                    }
                    break;
                }
                default:
                    break;   // Id и IdList — во втором проходе
            }
        }
    }

    // Проход 2: ссылки.
    for (const auto& entity : ir.entities) {
        EntityId id = ctx.entities.find_by_name(entity.name_hash);
        if (id == ENTITY_NULL) continue;
        for (const auto& field : entity.fields) {
            if (field.type == PropType::Id) {
                EntityId ref = ctx.entities.find_by_name(field.ref_hash);
                if (ref == ENTITY_NULL) return Status::InvalidReference;
                Status s = ctx.props.set_id(id, field.name_hash, ref);
                if (s != Status::Ok) return s;
            } else if (field.type == PropType::IdList) {
                EntityId ids[MAX_IDLIST_LEN];
                size_t count = 0;
                for (uint32_t hash : field.idlist_hashes) {
                    if (count >= MAX_IDLIST_LEN) return Status::OutOfMemory;
                    EntityId ref = ctx.entities.find_by_name(hash);
                    if (ref == ENTITY_NULL) return Status::InvalidReference;
                    ids[count++] = ref;
                }
                Status s = ctx.props.set_idlist(id, field.name_hash, ids, uint8_t(count));
                if (s != Status::Ok) return s;
            }
        }
    }
    return Status::Ok;
}

class Loader {
public:
    static Status load_text(Context& ctx, const char* text, std::string* error = nullptr) {
        UlangParser parser;
        IR ir;
        Status s = parser.compile(text, ir);
        if (s != Status::Ok) {
            if (error) *error = parser.last_error();
            return s;
        }
        s = parser.resolve_refs(ir);
        if (s != Status::Ok) {
            if (error) *error = parser.last_error();
            return s;
        }
        s = load_ir(ctx, ir);
        if (s != Status::Ok && error) *error = uc::status_name(s);
        return s;
    }

    static Status load_file(Context& ctx, const std::string& path, std::string* error = nullptr) {
        std::ifstream in(path, std::ios::binary);
        if (!in) {
            if (error) *error = "cannot open " + path;
            return Status::NotFound;
        }
        std::ostringstream ss;
        ss << in.rdbuf();
        const std::string text = ss.str();
        return load_text(ctx, text.c_str(), error);
    }
};

}  // namespace uc
