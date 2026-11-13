#!/usr/bin/env python3
"""Простой валидатор GLSL шейдеров — извлекает код из shaders.h
и проверяет базовый синтаксис через регулярные выражения и проверки
баланса скобок."""

import re
import sys

PATH = "/home/z/my-project/download/demo_intro/shaders.h"

def extract_shader(content, marker):
    """Извлечь содержимое шейдера из R\"GLSL(...)GLSL\" блока."""
    pat = rf'{marker}.*?R"GLSL\((.*?)\)GLSL"'
    m = re.search(pat, content, re.DOTALL)
    if not m:
        return None
    return m.group(1)

def check_balance(code):
    """Проверить баланс { } ( ) [ ] в шейдере."""
    pairs = {')': '(', '}': '{', ']': '['}
    stack = []
    in_string = False
    in_line_comment = False
    in_block_comment = False
    i = 0
    line = 1
    col = 1
    while i < len(code):
        c = code[i]
        if c == '\n':
            line += 1
            col = 1
            in_line_comment = False
        else:
            col += 1

        # Пропуск комментариев
        if not (in_line_comment or in_block_comment or in_string):
            if i + 1 < len(code) and code[i:i+2] == '//':
                in_line_comment = True
                i += 2
                continue
            if i + 1 < len(code) and code[i:i+2] == '/*':
                in_block_comment = True
                i += 2
                continue
        if in_line_comment:
            i += 1
            continue
        if in_block_comment:
            if i + 1 < len(code) and code[i:i+2] == '*/':
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        # Пропуск строковых литералов (хотя GLSL их нечасто использует)
        if c == '"':
            in_string = not in_string
            i += 1
            continue
        if in_string:
            i += 1
            continue

        if c in '({[':
            stack.append((c, line, col))
        elif c in ')}]':
            if not stack:
                return f"Unbalanced '{c}' at line {line}, col {col}"
            top, top_line, top_col = stack.pop()
            if pairs[c] != top:
                return f"Mismatched '{c}' (expected closing for '{top}' at line {top_line}, col {top_col}) but got '{c}' at line {line}, col {col}"
        i += 1
    if stack:
        top, top_line, top_col = stack[-1]
        return f"Unclosed '{top}' opened at line {top_line}, col {top_col}"
    return None

def main():
    with open(PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    vs = extract_shader(content, 'kVertexShaderSrc')
    fs = extract_shader(content, 'kFragmentShaderSrc')

    if not vs:
        print("FAIL: vertex shader not found")
        return 1
    if not fs:
        print("FAIL: fragment shader not found")
        return 1

    print(f"Vertex shader: {len(vs)} chars, {vs.count(chr(10))+1} lines")
    err = check_balance(vs)
    if err:
        print(f"  FAIL: {err}")
    else:
        print("  OK: brackets balanced")

    print(f"Fragment shader: {len(fs)} chars, {fs.count(chr(10))+1} lines")
    err = check_balance(fs)
    if err:
        print(f"  FAIL: {err}")
    else:
        print("  OK: brackets balanced")

    # Проверка на основные проблемы
    for sh_name, sh in [("vertex", vs), ("fragment", fs)]:
        # Проверка точки входа
        if "void main()" not in sh and "void main(" not in sh:
            print(f"  WARN: {sh_name} shader has no main()")
        # Проверка на устаревшие вызовы, которые не работают в 3.3 core
        if "glBegin" in sh or "glEnd" in sh or "ftransform" in sh:
            print(f"  FAIL: {sh_name} uses deprecated GLSL")
        # Проверка #version
        if '#version' not in sh:
            print(f"  WARN: {sh_name} has no #version directive")

    print("\nDone.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
