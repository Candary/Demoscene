// Использование: conformance <demo.smt> <times.txt>   (times.txt — по одному T на строку)
// Печатает то же, что scene_manager.bake.golden_lines(); совпадение проверяет tests/test_scene_manager.py.
#include "sm_runtime.hpp"
int main(int argc, char** argv) {
    if (argc != 3) { std::fprintf(stderr, "usage: conformance demo.smt times.txt\n"); return 2; }
    try {
        sm::Show s = sm::load(argv[1]);
        std::ifstream f(argv[2]); std::string line;
        while (std::getline(f, line)) {
            if (line.empty()) continue;
            std::printf("T %s\n", line.c_str());
            std::fputs(sm::dump_frame(s, std::stod(line)).c_str(), stdout);
        }
    } catch (const std::exception& e) { std::fprintf(stderr, "error: %s\n", e.what()); return 1; }
    return 0;
}
