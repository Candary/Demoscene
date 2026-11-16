// ulang_parser.h — transcribed from Final Qwen.md Step 8
#pragma once
#include "ucleaner_types.h"
#include <string>
#include <vector>
#include <unordered_map>
#include <cctype>

namespace uc {

struct IRField {
    std::string name;
    uint32_t name_hash = 0;
    PropType type = PropType::None;
    float f_val = 0.0f;
    int32_t i_val = 0;
    float v3_val[3] = {0,0,0};
    uint32_t hash_val = 0;
    std::string ref_name;
    uint32_t ref_hash = 0;
};

struct IREntity {
    std::string name;
    uint32_t name_hash = 0;
    std::vector<IRField> fields;
};

struct IR { std::vector<IREntity> entities; };

enum class TokenType { Entity, AtName, LBrace, RBrace, Colon, Comma, LBracket, RBracket, String, Number, Eof, Error };

struct Token { TokenType type; std::string text; uint32_t line; uint32_t col; };

class Tokenizer {
public:
    Tokenizer(const char* src) : src_(src), pos_(0), line_(1), col_(1) {}
    Token next() {
        skip_ws();
        if (src_[pos_] == '\0') return {TokenType::Eof, "", line_, col_};
        uint32_t sl=line_, sc=col_; char c=src_[pos_];
        if (c=='{'){adv();return{TokenType::LBrace,"{",sl,sc};}
        if (c=='}'){adv();return{TokenType::RBrace,"}",sl,sc};}
        if (c==':'){adv();return{TokenType::Colon,":",sl,sc};}
        if (c==','){adv();return{TokenType::Comma,",",sl,sc};}
        if (c=='['){adv();return{TokenType::LBracket,"[",sl,sc};}
        if (c==']'){adv();return{TokenType::RBracket,"]",sl,sc};}
        if (c=='"')return read_string(sl,sc);
        if (c=='@')return read_at_name(sl,sc);
        if (std::isdigit((unsigned char)c)||c=='-'||c=='+')return read_number(sl,sc);
        if (std::isalpha((unsigned char)c)||c=='_')return read_ident(sl,sc);
        adv();
        return {TokenType::Error,std::string(1,c),sl,sc};
    }
private:
    void adv(){if(src_[pos_]=='\n'){line_++;col_=1;}else{col_++;}pos_++;}
    void skip_ws(){
        while(src_[pos_]){
            if(std::isspace((unsigned char)src_[pos_])){adv();continue;}
            if(src_[pos_]=='/'&&src_[pos_+1]=='/'){while(src_[pos_]&&src_[pos_]!='\n')adv();continue;}
            break;
        }
    }
    Token read_string(uint32_t l,uint32_t c){
        adv();std::string v;
        while(src_[pos_]&&src_[pos_]!='"'){v+=src_[pos_];adv();}
        if(src_[pos_]=='"')adv();
        return{TokenType::String,v,l,c};
    }
    Token read_at_name(uint32_t l,uint32_t c){
        adv();std::string v;
        while(src_[pos_]&&(std::isalnum((unsigned char)src_[pos_])||src_[pos_]=='_')){v+=src_[pos_];adv();}
        return{TokenType::AtName,"@"+v,l,c};
    }
    Token read_number(uint32_t l,uint32_t c){
        std::string v;
        while(src_[pos_]&&(std::isdigit((unsigned char)src_[pos_])||src_[pos_]=='.'||src_[pos_]=='-'||src_[pos_]=='+'||src_[pos_]=='e'||src_[pos_]=='E')){v+=src_[pos_];adv();}
        return{TokenType::Number,v,l,c};
    }
    Token read_ident(uint32_t l,uint32_t c){
        std::string v;
        while(src_[pos_]&&(std::isalnum((unsigned char)src_[pos_])||src_[pos_]=='_')){v+=src_[pos_];adv();}
        if(v=="entity")return{TokenType::Entity,v,l,c};
        return{TokenType::Error,v,l,c};
    }
    const char* src_; size_t pos_; uint32_t line_, col_;
};

class UlangParser {
public:
    Status compile(const char* text, IR& out_ir) {
        Tokenizer lex(text);
        Token tok = lex.next();
        while (tok.type != TokenType::Eof) {
            if (tok.type != TokenType::Entity) {
                last_error_ = "Expected 'entity' at line " + std::to_string(tok.line);
                return Status::ParseError;
            }
            Token name_tok = lex.next();
            if (name_tok.type != TokenType::AtName) {
                last_error_ = "Expected '@name' at line " + std::to_string(name_tok.line);
                return Status::ParseError;
            }
            Token brace_tok = lex.next();
            if (brace_tok.type != TokenType::LBrace) {
                last_error_ = "Expected '{' at line " + std::to_string(brace_tok.line);
                return Status::ParseError;
            }
            IREntity ent;
            ent.name = name_tok.text;
            ent.name_hash = fnv1a(ent.name.c_str());
            Token key_tok = lex.next();
            while (key_tok.type != TokenType::RBrace && key_tok.type != TokenType::Eof) {
                if (key_tok.type == TokenType::Comma) { key_tok = lex.next(); continue; }
                if (key_tok.type != TokenType::String) {
                    last_error_ = "Expected key string at line " + std::to_string(key_tok.line);
                    return Status::ParseError;
                }
                std::string key_name = key_tok.text;
                Token colon = lex.next();
                if (colon.type != TokenType::Colon) {
                    last_error_ = "Expected ':' at line " + std::to_string(colon.line);
                    return Status::ParseError;
                }
                IRField field;
                field.name = key_name;
                field.name_hash = fnv1a(key_name.c_str());
                Token val_tok = lex.next();
                Status s = parse_value(val_tok, lex, field);
                if (s != Status::Ok) return s;
                ent.fields.push_back(field);
                key_tok = lex.next();
            }
            if (key_tok.type == TokenType::Eof) {
                last_error_ = "Unexpected EOF, expected '}'";
                return Status::ParseError;
            }
            out_ir.entities.push_back(ent);
            tok = lex.next();
        }
        return Status::Ok;
    }

    Status resolve_refs(IR& ir) {
        std::unordered_map<uint32_t, size_t> name_to_idx;
        for (size_t i = 0; i < ir.entities.size(); i++)
            name_to_idx[ir.entities[i].name_hash] = i;
        for (auto& ent : ir.entities) {
            for (auto& f : ent.fields) {
                if (f.type == PropType::Id && !f.ref_name.empty()) {
                    f.ref_hash = fnv1a(f.ref_name.c_str());
                    if (name_to_idx.find(f.ref_hash) == name_to_idx.end()) {
                        last_error_ = "Reference not found: " + f.ref_name;
                        return Status::NotFound;
                    }
                }
            }
        }
        return Status::Ok;
    }
    const std::string& last_error() const { return last_error_; }

private:
    Status parse_value(const Token& tok, Tokenizer& lex, IRField& field) {
        if (tok.type == TokenType::Number) {
            field.type = PropType::Float;
            field.f_val = std::stof(tok.text);
            return Status::Ok;
        }
        if (tok.type == TokenType::String) {
            field.type = PropType::Hash;
            field.hash_val = fnv1a(tok.text.c_str());
            return Status::Ok;
        }
        if (tok.type == TokenType::AtName) {
            field.type = PropType::Id;
            field.ref_name = tok.text;
            return Status::Ok;
        }
        if (tok.type == TokenType::LBracket) {
            field.type = PropType::Vec3;
            Token v1=lex.next(); if(v1.type!=TokenType::Number)return err("Vec3: expected number");
            field.v3_val[0]=std::stof(v1.text);
            Token c1=lex.next(); if(c1.type!=TokenType::Comma)return err("Vec3: expected ','");
            Token v2=lex.next(); if(v2.type!=TokenType::Number)return err("Vec3: expected number");
            field.v3_val[1]=std::stof(v2.text);
            Token c2=lex.next(); if(c2.type!=TokenType::Comma)return err("Vec3: expected ','");
            Token v3=lex.next(); if(v3.type!=TokenType::Number)return err("Vec3: expected number");
            field.v3_val[2]=std::stof(v3.text);
            Token rb=lex.next(); if(rb.type!=TokenType::RBracket)return err("Vec3: expected ']'");
            return Status::Ok;
        }
        return err("Unexpected token in value");
    }
    Status err(const std::string& m){last_error_=m;return Status::ParseError;}
    std::string last_error_;
};

} // namespace uc
