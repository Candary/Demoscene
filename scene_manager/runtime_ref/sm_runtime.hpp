// Scene Manager: эталон рантайма (C++17, без GL и внешних библиотек).
// Читает demo.smt (см. scene_manager/bake.py), считает программы uniform'ов и находит план проходов для любого времени T.
// Рендер (GL) сюда не входит: он исполняет готовые проходы. Семантика выражений обязана совпадать с scene_manager/expr.py.
#pragma once
#include <cmath>
#include <cstdio>
#include <fstream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace sm {

enum Var { V_t, V_p, V_dur, V_time, V_beat, V_beat_phase, V_bar, V_bar_phase, V_energy, V_section, V_COUNT };
enum TokKind { K_NUM, K_VAR, K_OP, K_FUNC };
struct Tok { TokKind k; double num; int id; };
using Program = std::vector<Tok>;

inline double fin(double x) { return std::isfinite(x) ? x : 0.0; }

inline int var_id(const std::string& s) {
    static const std::map<std::string, int> m = {{"t", V_t}, {"p", V_p}, {"dur", V_dur}, {"time", V_time}, {"audio.beat", V_beat},
        {"audio.beat_phase", V_beat_phase}, {"audio.bar", V_bar}, {"audio.bar_phase", V_bar_phase},
        {"audio.energy", V_energy}, {"audio.section", V_section}};
    auto it = m.find(s);
    if (it == m.end()) throw std::runtime_error("unknown variable " + s);
    return it->second;
}

// операторы: 0 +, 1 -, 2 *, 3 /, 4 %, 5 <, 6 >, 7 <=, 8 >=, 9 ==, 10 !=, 11 &&, 12 ||, 13 neg, 14 not
inline int op_id(const std::string& s) {
    static const std::map<std::string, int> m = {{"+", 0}, {"-", 1}, {"*", 2}, {"/", 3}, {"%", 4}, {"<", 5}, {">", 6}, {"<=", 7},
        {">=", 8}, {"==", 9}, {"!=", 10}, {"&&", 11}, {"||", 12}, {"neg", 13}, {"not", 14}};
    auto it = m.find(s);
    if (it == m.end()) throw std::runtime_error("unknown operator " + s);
    return it->second;
}

// функции: арность задана таблицей
struct FuncInfo { const char* name; int arity; };
inline const std::vector<FuncInfo>& funcs() {
    static const std::vector<FuncInfo> f = {{"abs", 1}, {"sign", 1}, {"floor", 1}, {"ceil", 1}, {"fract", 1}, {"sqrt", 1}, {"sin", 1},
        {"cos", 1}, {"exp", 1}, {"min", 2}, {"max", 2}, {"pow", 2}, {"mod", 2}, {"step", 2}, {"clamp", 3}, {"mix", 3},
        {"smoothstep", 3}, {"if", 3}};
    return f;
}
inline int func_id(const std::string& s) {
    const auto& f = funcs();
    for (size_t i = 0; i < f.size(); ++i) if (s == f[i].name) return (int)i;
    throw std::runtime_error("unknown function " + s);
}

inline Tok parse_tok(const std::string& s) {
    auto c = s.find(':');
    if (c == std::string::npos) throw std::runtime_error("bad token " + s);
    std::string k = s.substr(0, c), v = s.substr(c + 1);
    if (k == "n") return {K_NUM, std::stod(v), 0};
    if (k == "v") return {K_VAR, 0, var_id(v)};
    if (k == "o") return {K_OP, 0, op_id(v)};
    if (k == "f") return {K_FUNC, 0, func_id(v)};
    throw std::runtime_error("bad token kind " + s);
}

inline double apply_op(int op, double a, double b) {
    switch (op) {
        case 0: return a + b;
        case 1: return a - b;
        case 2: return a * b;
        case 3: return b != 0.0 ? a / b : 0.0;
        case 4: return b != 0.0 ? a - b * std::floor(a / b) : 0.0;
        case 5: return a < b; case 6: return a > b; case 7: return a <= b; case 8: return a >= b;
        case 9: return a == b; case 10: return a != b;
        case 11: return (a != 0.0 && b != 0.0); case 12: return (a != 0.0 || b != 0.0);
        case 13: return -a;
        case 14: return a != 0.0 ? 0.0 : 1.0;
    }
    throw std::runtime_error("bad op");
}

inline double apply_fn(int f, const double* a) {
    switch (f) {
        case 0: return std::fabs(a[0]);
        case 1: return (a[0] > 0) - (a[0] < 0);
        case 2: return std::floor(a[0]);
        case 3: return std::ceil(a[0]);
        case 4: return a[0] - std::floor(a[0]);
        case 5: return a[0] > 0 ? std::sqrt(a[0]) : 0.0;
        case 6: return std::sin(a[0]);
        case 7: return std::cos(a[0]);
        case 8: return std::exp(std::fmin(a[0], 700.0));
        case 9: return a[0] < a[1] ? a[0] : a[1];           // как Python min(a, b)
        case 10: return a[0] > a[1] ? a[0] : a[1];          // как Python max(a, b)
        case 11: { double x = a[0], y = a[1]; if (x < 0 && y != std::floor(y)) return 0.0; return std::pow(x, y); }
        case 12: return a[1] != 0.0 ? a[0] - a[1] * std::floor(a[0] / a[1]) : 0.0;
        case 13: return a[1] >= a[0] ? 1.0 : 0.0;
        case 14: { double m = a[0] > a[1] ? a[0] : a[1]; return m < a[2] ? m : a[2]; }   // min(max(x, lo), hi)
        case 15: return a[0] + (a[1] - a[0]) * a[2];
        case 16: {
            double e0 = a[0], e1 = a[1], x = a[2];
            if (e0 == e1) return x >= e1 ? 1.0 : 0.0;
            double t = (x - e0) / (e1 - e0); t = t < 0 ? 0 : (t > 1 ? 1 : t);
            return t * t * (3.0 - 2.0 * t);
        }
        case 17: return a[0] != 0.0 ? a[1] : a[2];
    }
    throw std::runtime_error("bad func");
}

inline double run(const Program& p, const double* vars) {
    double st[256]; int sp = 0;
    for (const Tok& t : p) {
        switch (t.k) {
            case K_NUM: st[sp++] = t.num; break;
            case K_VAR: st[sp++] = vars[t.id]; break;
            case K_OP:
                if (t.id >= 13) { st[sp - 1] = fin(apply_op(t.id, st[sp - 1], 0)); }
                else { double b = st[--sp], a = st[--sp]; st[sp++] = fin(apply_op(t.id, a, b)); }
                break;
            case K_FUNC: {
                int n = funcs()[t.id].arity; sp -= n; double r = fin(apply_fn(t.id, st + sp)); st[sp++] = r; break;
            }
        }
        if (sp >= 250) throw std::runtime_error("stack overflow");
    }
    if (sp != 1) throw std::runtime_error("corrupt program");
    return fin(st[0]);
}

struct Uniform { std::string name, type; std::vector<Program> comps; };
struct Clip {
    std::string id, kind, effect, blend, in_a, in_b;
    int track_order = 0; long seed = 0;
    double eff_start = 0, eff_end = 0, nom_start = 0, nom_dur = 0, prewarm = 0;
    Program opacity, progress;
    std::vector<Uniform> uniforms;
    std::map<std::string, std::vector<double>> arrays;   // константные массивы (farray)
};
struct Op { std::string op, clip, reads, write, dest, blend; };
struct Segment { double start = 0, end = 0; int cost = 0, fbos = 0; std::vector<Op> ops; };

struct Show {
    double duration = 0, bpm = 120, offset = 0, energy_rate = 20; int beats_per_bar = 4, fps = 60, w = 1920, h = 1080;
    std::vector<double> energy, sections;
    std::vector<Clip> clips;
    std::vector<Segment> segs;

    static constexpr double EPS = 1e-9;

    void audio_vars(double T, double* v) const {
        double spb = 60.0 / bpm;
        double b = (T - offset) / spb;
        v[V_beat] = b; v[V_beat_phase] = b - std::floor(b);
        double bar = b / beats_per_bar;
        v[V_bar] = bar; v[V_bar_phase] = bar - std::floor(bar);
        double e = 0.0;
        if (!energy.empty()) {
            double x = T * energy_rate;
            if (x <= 0) e = energy[0];
            else { int i = (int)x; if (i >= (int)energy.size() - 1) e = energy.back(); else { double f = x - i; e = energy[i] * (1 - f) + energy[i + 1] * f; } }
        }
        v[V_energy] = e;
        int idx = -1; for (size_t i = 0; i < sections.size(); ++i) if (T >= sections[i]) idx = (int)i;
        v[V_section] = idx;
    }
    bool is_active(const Clip& c, double T) const {
        return (c.eff_start - EPS <= T && T < c.eff_end - EPS) || (c.kind == "event" && T >= c.eff_start);
    }
    const Segment* segment_at(double T) const {
        for (const auto& s : segs) if (s.start - EPS <= T && T < s.end - EPS) return &s;
        if (!segs.empty() && std::fabs(T - segs.back().end) < EPS) return &segs.back();
        return nullptr;
    }
};

inline Program read_prog(std::istringstream& in) {
    size_t n; in >> n; Program p; p.reserve(n);
    for (size_t i = 0; i < n; ++i) { std::string s; in >> s; p.push_back(parse_tok(s)); }
    return p;
}

inline Show load(const std::string& path) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("cannot open " + path);
    Show s; std::string line;
    std::getline(f, line);
    if (line != "SMT 1") throw std::runtime_error("bad header");
    Clip* cur = nullptr; Segment* seg = nullptr; Uniform* uni = nullptr; size_t want = 0;
    while (std::getline(f, line)) {
        std::istringstream in(line); std::string k; in >> k;
        if (k == "meta") { in >> s.duration >> s.fps >> s.w >> s.h; long seed; in >> seed; }
        else if (k == "audio") {
            size_t n; in >> s.bpm >> s.offset >> s.beats_per_bar >> s.energy_rate >> n;
            s.energy.resize(n); for (auto& e : s.energy) in >> e;
        } else if (k == "sections") { size_t n; in >> n; s.sections.resize(n); for (auto& e : s.sections) in >> e; }
        else if (k == "clip") {
            s.clips.emplace_back(); cur = &s.clips.back();
            in >> cur->id >> cur->track_order >> cur->kind >> cur->effect >> cur->eff_start >> cur->eff_end >> cur->nom_start >> cur->nom_dur
               >> cur->blend >> cur->seed >> cur->in_a >> cur->in_b >> cur->prewarm;
        } else if (k == "prog") {
            std::string w; std::streampos pos = in.tellg(); in >> w;
            if (w == "opacity") cur->opacity = read_prog(in);
            else if (w == "progress") cur->progress = read_prog(in);
            else { in.seekg(pos); uni->comps.push_back(read_prog(in)); }
        } else if (k == "uni") {
            cur->uniforms.emplace_back(); uni = &cur->uniforms.back(); in >> uni->name >> uni->type >> want;
        } else if (k == "arr") {
            std::string name; size_t n; in >> name >> n; auto& v = cur->arrays[name]; v.resize(n); for (auto& x : v) in >> x;
        } else if (k == "endclip") { cur = nullptr; uni = nullptr; }
        else if (k == "seg") { s.segs.emplace_back(); seg = &s.segs.back(); in >> seg->start >> seg->end >> seg->cost >> seg->fbos; }
        else if (k == "op") { Op o; in >> o.op >> o.clip >> o.reads >> o.write >> o.dest >> o.blend; seg->ops.push_back(o); }
        else if (k == "endseg") seg = nullptr;
        else if (k == "end") break;
    }
    return s;
}

inline std::string g9(double v) { char b[64]; std::snprintf(b, sizeof b, "%.9g", v); return b; }

// Печать кадра в формате scene_manager.bake.golden_lines (для побайтной/численной сверки с Python).
inline std::string dump_frame(const Show& s, double T) {
    std::string out; char b[64];
    std::snprintf(b, sizeof b, "%.17g", T);
    // Python печатает repr(float); для сверки времён используем строку, переданную вызывающим кодом
    double vars[V_COUNT]; s.audio_vars(T, vars);
    std::map<std::string, const Clip*> act;
    for (const auto& c : s.clips) if (s.is_active(c, T)) act[c.id] = &c;
    for (const auto& kv : act) {
        const Clip& c = *kv.second;
        vars[V_t] = T - c.nom_start; vars[V_dur] = c.nom_dur; vars[V_p] = c.nom_dur > 0 ? vars[V_t] / c.nom_dur : 0.0; vars[V_time] = T;
        std::string line = "clip " + c.id + " uTime=" + g9(T - c.eff_start) + " uProgress=" + g9(run(c.progress, vars)) +
                           " opacity=" + g9(run(c.opacity, vars));
        std::map<std::string, std::string> us;
        for (const auto& u : c.uniforms) {
            std::string v; for (size_t i = 0; i < u.comps.size(); ++i) { if (i) v += ","; v += g9(run(u.comps[i], vars)); }
            us[u.name] = v;
        }
        for (const auto& kv2 : us) line += " " + kv2.first + "=" + kv2.second;
        out += line + "\n";
        for (const auto& ar : c.arrays) {
            double sum = 0; for (double x : ar.second) sum += x;
            out += "arr " + c.id + " " + ar.first + " n=" + std::to_string(ar.second.size()) + " sum=" + g9(sum) + "\n";
        }
    }
    if (const Segment* g = s.segment_at(T)) {
        out += "plan fbos=" + std::to_string(g->fbos) + "\n";
        for (const auto& o : g->ops) out += "  op " + o.op + " " + o.clip + " " + o.reads + " " + o.write + " " + o.dest + " " + o.blend + "\n";
    }
    return out;
}

}  // namespace sm
