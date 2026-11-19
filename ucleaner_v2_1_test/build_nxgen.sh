#!/bin/bash
# build_nxgen.sh — build nxGen standalone CLI tool
# Requires: C++17 compiler (g++ or cl)
set -e

cd "$(dirname "$0")"
mkdir -p build

g++ -std=c++17 -O2 -Wall -I. \
    nxgen/main.cpp \
    -o build/nxgen

echo "[ok] nxgen built: build/nxgen"
echo "run: ./build/nxgen run --preset text_to_scene --text 'epic cold city' --out out/demo"
