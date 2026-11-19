// json.h — минимальный JSON для конфигурации и заданий nxGen.
//
// Свой парсер, потому что зависимость от внешней библиотеки ради чтения
// конфигурации противоречит требованию «проект собирается без зависимостей».
// Поддерживается весь JSON, который нужен: объекты, массивы, строки с
// экранированием, числа, true/false/null. Комментарии не допускаются.
#pragma once

#include <array>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace nxgen {

class Json {
public:
    enum class Type { Null, Bool, Number, String, Array, Object };

    Json() = default;
    Json(bool v) : type_(Type::Bool), bool_(v) {}
    Json(double v) : type_(Type::Number), number_(v) {}
    Json(int v) : type_(Type::Number), number_(double(v)) {}
    Json(const char* v) : type_(Type::String), string_(v) {}
    Json(std::string v) : type_(Type::String), string_(std::move(v)) {}
    Json(std::vector<Json> v) : type_(Type::Array), array_(std::move(v)) {}
    Json(std::map<std::string, Json> v) : type_(Type::Object), object_(std::move(v)) {}

    static Json array() { return Json(std::vector<Json>{}); }
    static Json object() { return Json(std::map<std::string, Json>{}); }

    Type type() const { return type_; }
    bool is_null() const { return type_ == Type::Null; }
    bool is_object() const { return type_ == Type::Object; }
    bool is_array() const { return type_ == Type::Array; }
    bool is_string() const { return type_ == Type::String; }
    bool is_number() const { return type_ == Type::Number; }
    bool is_bool() const { return type_ == Type::Bool; }

    bool as_bool(bool def = false) const { return type_ == Type::Bool ? bool_ : def; }
    double as_double(double def = 0.0) const { return type_ == Type::Number ? number_ : def; }
    float as_float(float def = 0.0f) const { return float(as_double(def)); }
    int as_int(int def = 0) const { return type_ == Type::Number ? int(number_) : def; }
    const std::string& as_string() const {
        static const std::string empty;
        return type_ == Type::String ? string_ : empty;
    }
    std::string as_string(const std::string& fallback) const {
        return type_ == Type::String ? string_ : fallback;
    }

    bool has(const std::string& key) const {
        return type_ == Type::Object && object_.find(key) != object_.end();
    }

    const Json& at(const std::string& key) const {
        static const Json null_value;
        if (type_ != Type::Object) return null_value;
        auto it = object_.find(key);
        return it == object_.end() ? null_value : it->second;
    }

    const Json& at(size_t index) const {
        static const Json null_value;
        if (type_ != Type::Array || index >= array_.size()) return null_value;
        return array_[index];
    }

    size_t size() const {
        if (type_ == Type::Array) return array_.size();
        if (type_ == Type::Object) return object_.size();
        return 0;
    }

    const std::vector<Json>& items() const { return array_; }
    const std::map<std::string, Json>& fields() const { return object_; }

    void set(const std::string& key, Json value) {
        if (type_ != Type::Object) { type_ = Type::Object; object_.clear(); }
        object_[key] = std::move(value);
    }
    void push(Json value) {
        if (type_ != Type::Array) { type_ = Type::Array; array_.clear(); }
        array_.push_back(std::move(value));
    }

    // --- сериализация -----------------------------------------------------
    std::string dump(int indent = 0) const {
        std::string out;
        dump_into(out, indent, 0);
        return out;
    }

    // --- разбор -----------------------------------------------------------
    static Json parse(const std::string& text) {
        Parser parser(text);
        Json value = parser.parse_value();
        parser.skip_ws();
        if (!parser.eof()) throw std::runtime_error("json: trailing data");
        return value;
    }

private:
    Type type_ = Type::Null;
    bool bool_ = false;
    double number_ = 0.0;
    std::string string_;
    std::vector<Json> array_;
    std::map<std::string, Json> object_;

    static void escape(std::string& out, const std::string& s) {
        out += '"';
        for (char c : s) {
            switch (c) {
                case '"': out += "\\\""; break;
                case '\\': out += "\\\\"; break;
                case '\n': out += "\\n"; break;
                case '\t': out += "\\t"; break;
                case '\r': out += "\\r"; break;
                default:
                    if (static_cast<unsigned char>(c) < 0x20) {
                        char buf[8];
                        std::snprintf(buf, sizeof(buf), "\\u%04x", static_cast<unsigned char>(c));
                        out += buf;
                    } else {
                        out += c;
                    }
            }
        }
        out += '"';
    }

    void dump_into(std::string& out, int indent, int depth) const {
        auto newline = [&](int d) {
            if (indent <= 0) return;
            out += '\n';
            out.append(size_t(indent * d), ' ');
        };
        switch (type_) {
            case Type::Null: out += "null"; break;
            case Type::Bool: out += bool_ ? "true" : "false"; break;
            case Type::Number: {
                char buf[32];
                if (number_ == std::floor(number_) && std::fabs(number_) < 1e15) {
                    std::snprintf(buf, sizeof(buf), "%.0f", number_);
                } else {
                    std::snprintf(buf, sizeof(buf), "%.6g", number_);
                }
                out += buf;
                break;
            }
            case Type::String: escape(out, string_); break;
            case Type::Array: {
                out += '[';
                for (size_t i = 0; i < array_.size(); ++i) {
                    if (i) out += ',';
                    newline(depth + 1);
                    array_[i].dump_into(out, indent, depth + 1);
                }
                if (!array_.empty()) newline(depth);
                out += ']';
                break;
            }
            case Type::Object: {
                out += '{';
                size_t i = 0;
                for (const auto& kv : object_) {
                    if (i++) out += ',';
                    newline(depth + 1);
                    escape(out, kv.first);
                    out += indent > 0 ? ": " : ":";
                    kv.second.dump_into(out, indent, depth + 1);
                }
                if (!object_.empty()) newline(depth);
                out += '}';
                break;
            }
        }
    }

    struct Parser {
        explicit Parser(const std::string& text) : text(text) {}
        const std::string& text;
        size_t pos = 0;

        bool eof() const { return pos >= text.size(); }
        char peek() const { return pos < text.size() ? text[pos] : '\0'; }

        void skip_ws() {
            while (!eof()) {
                char c = text[pos];
                if (c == ' ' || c == '\t' || c == '\n' || c == '\r') { ++pos; continue; }
                break;
            }
        }

        [[noreturn]] void fail(const std::string& what) const {
            throw std::runtime_error("json: " + what + " at offset " + std::to_string(pos));
        }

        Json parse_value() {
            skip_ws();
            if (eof()) fail("unexpected end");
            char c = peek();
            if (c == '{') return parse_object();
            if (c == '[') return parse_array();
            if (c == '"') return Json(parse_string());
            if (c == 't' || c == 'f') return parse_bool();
            if (c == 'n') return parse_null();
            return parse_number();
        }

        Json parse_object() {
            ++pos;  // {
            Json obj = Json::object();
            skip_ws();
            if (peek() == '}') { ++pos; return obj; }
            while (true) {
                skip_ws();
                if (peek() != '"') fail("expected key");
                std::string key = parse_string();
                skip_ws();
                if (peek() != ':') fail("expected ':'");
                ++pos;
                obj.set(key, parse_value());
                skip_ws();
                if (peek() == ',') { ++pos; continue; }
                if (peek() == '}') { ++pos; return obj; }
                fail("expected ',' or '}'");
            }
        }

        Json parse_array() {
            ++pos;  // [
            Json arr = Json::array();
            skip_ws();
            if (peek() == ']') { ++pos; return arr; }
            while (true) {
                arr.push(parse_value());
                skip_ws();
                if (peek() == ',') { ++pos; continue; }
                if (peek() == ']') { ++pos; return arr; }
                fail("expected ',' or ']'");
            }
        }

        std::string parse_string() {
            ++pos;  // "
            std::string out;
            while (!eof()) {
                char c = text[pos++];
                if (c == '"') return out;
                if (c != '\\') { out += c; continue; }
                if (eof()) fail("bad escape");
                char e = text[pos++];
                switch (e) {
                    case '"': out += '"'; break;
                    case '\\': out += '\\'; break;
                    case '/': out += '/'; break;
                    case 'n': out += '\n'; break;
                    case 't': out += '\t'; break;
                    case 'r': out += '\r'; break;
                    case 'b': out += '\b'; break;
                    case 'f': out += '\f'; break;
                    case 'u': {
                        if (pos + 4 > text.size()) fail("bad \\u escape");
                        unsigned code = 0;
                        for (int i = 0; i < 4; ++i) {
                            char h = text[pos++];
                            code <<= 4;
                            if (h >= '0' && h <= '9') code |= unsigned(h - '0');
                            else if (h >= 'a' && h <= 'f') code |= unsigned(h - 'a' + 10);
                            else if (h >= 'A' && h <= 'F') code |= unsigned(h - 'A' + 10);
                            else fail("bad hex in \\u");
                        }
                        // UTF-8 (BMP): достаточно для конфигурации
                        if (code < 0x80) out += char(code);
                        else if (code < 0x800) {
                            out += char(0xC0 | (code >> 6));
                            out += char(0x80 | (code & 0x3F));
                        } else {
                            out += char(0xE0 | (code >> 12));
                            out += char(0x80 | ((code >> 6) & 0x3F));
                            out += char(0x80 | (code & 0x3F));
                        }
                        break;
                    }
                    default: fail("unknown escape");
                }
            }
            fail("unterminated string");
        }

        Json parse_bool() {
            if (text.compare(pos, 4, "true") == 0) { pos += 4; return Json(true); }
            if (text.compare(pos, 5, "false") == 0) { pos += 5; return Json(false); }
            fail("expected true/false");
        }

        Json parse_null() {
            if (text.compare(pos, 4, "null") == 0) { pos += 4; return Json(); }
            fail("expected null");
        }

        Json parse_number() {
            size_t start = pos;
            if (peek() == '-') ++pos;
            while (!eof() && (std::isdigit(static_cast<unsigned char>(peek())) || peek() == '.' ||
                              peek() == 'e' || peek() == 'E' || peek() == '+' || peek() == '-')) {
                ++pos;
            }
            if (start == pos) fail("expected value");
            return Json(std::strtod(text.substr(start, pos - start).c_str(), nullptr));
        }
    };
};

}  // namespace nxgen
