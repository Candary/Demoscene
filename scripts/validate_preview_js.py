#!/usr/bin/env python3
"""
validate_preview_js.py — проверка JavaScript секций в preview HTML файлах.

Ищет частые баги JS в preview шейдеров:
  1. Math functions без Math. prefix (cos, sin, floor, sqrt, etc.)
  2. Math constants без Math. prefix (PI, E)
  3. gl.* вызовы с null/undefined location (basic pattern check)
  4. Не balanced braces/parens в JS

Использование:
  python3 scripts/validate_preview_js.py
  python3 scripts/validate_preview_js.py download/shaders/sphere_scene_preview.html
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


# Math functions в JS — все требуют Math. prefix
MATH_FUNCTIONS = [
    'cos', 'sin', 'tan', 'asin', 'acos', 'atan', 'atan2',
    'floor', 'ceil', 'round',
    'sqrt', 'cbrt',
    'abs',
    'pow', 'exp', 'log', 'log2', 'log10',
    'min', 'max',
    'random',
    'sign',
    'hypot',
    'trunc',
    'fround',
]

# Math constants
MATH_CONSTANTS = ['PI', 'E', 'LN2', 'LN10', 'LOG2E', 'LOG10E', 'SQRT2', 'SQRT1_2']


def extract_js_sections(html: str) -> list[tuple[int, str]]:
    """Вернуть [(start_line, js_code), ...] для всех <script> БЕЗ id атрибута."""
    sections = []
    lines = html.split('\n')

    in_script = False
    script_start_line = 0
    script_lines: list[str] = []

    for i, line in enumerate(lines, 1):
        # Opening <script> WITHOUT id attribute
        if not in_script and re.search(r'<script(?![^>]*\sid=)[^>]*>', line):
            in_script = True
            script_start_line = i
            script_lines = []
            # Если на этой же строке есть код после >
            m = re.search(r'<script[^>]*>(.*)$', line)
            if m and m.group(1):
                script_lines.append(m.group(1))
            continue

        # Closing </script>
        if in_script and '</script>' in line:
            # Код до </script>
            before = line.split('</script>')[0]
            if before:
                script_lines.append(before)
            sections.append((script_start_line, '\n'.join(script_lines)))
            in_script = False
            continue

        if in_script:
            script_lines.append(line)

    return sections


def find_math_bugs(js: str, base_line: int) -> list[tuple[int, str, str]]:
    """Найти вызовы math functions без Math. prefix. Вернуть [(line, func, snippet), ...]."""
    bugs = []

    # Strip string literals and comments
    cleaned = re.sub(r"'(?:[^'\\]|\\.)*'", "''", js)
    cleaned = re.sub(r'"(?:[^"\\]|\\.)*"', '""', cleaned)
    cleaned = re.sub(r'`(?:[^`\\]|\\.)*`', '``', cleaned)
    cleaned = re.sub(r'//.*?$', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)

    lines = cleaned.split('\n')
    for func in MATH_FUNCTIONS:
        # Pattern: word boundary, func name, NOT preceded by '.', followed by '('
        # Negative lookbehind for '.' to skip Math.cos, gl.cos, etc.
        pattern = r'(?<![\w.])\b' + func + r'\s*\('
        for i, line in enumerate(lines):
            for m in re.finditer(pattern, line):
                # Skip if it's a property definition or method (e.g., obj.cos())
                # Check char before match — if '.', skip
                start = m.start()
                if start > 0 and line[start - 1] == '.':
                    continue
                actual_line = base_line + i
                snippet = line.strip()[:100]
                bugs.append((actual_line, func, snippet))

    # Check Math constants without prefix
    for const in MATH_CONSTANTS:
        # Pattern: word boundary, const name, NOT preceded by '.'
        # Must NOT be part of an identifier (e.g., MY_PI shouldn't match)
        pattern = r'(?<![\w.])\b' + const + r'\b(?!\w)'
        for i, line in enumerate(lines):
            for m in re.finditer(pattern, line):
                start = m.start()
                if start > 0 and line[start - 1] == '.':
                    continue
                # Skip if it's a property key (e.g., {PI: 3.14})
                if re.search(r'^\s*' + const + r'\s*:', line):
                    continue
                actual_line = base_line + i
                snippet = line.strip()[:100]
                bugs.append((actual_line, 'Math.' + const, snippet))

    return bugs


def find_gl_null_uniforms(js: str, base_line: int) -> list[tuple[int, str]]:
    """Найти gl.uniform* вызовы без проверки location на null."""
    bugs = []
    lines = js.split('\n')
    for i, line in enumerate(lines):
        # Pattern: gl.uniform[1234][fi][v]?(null,
        if re.search(r'gl\.uniform\w+\(\s*null\s*,', line):
            bugs.append((base_line + i, line.strip()[:100]))
    return bugs


def check_balanced(js: str) -> tuple[bool, bool]:
    """Вернуть (braces_balanced, parens_balanced)."""
    cleaned = re.sub(r"'(?:[^'\\]|\\.)*'", '', js)
    cleaned = re.sub(r'"(?:[^"\\]|\\.)*"', '', cleaned)
    cleaned = re.sub(r'`(?:[^`\\]|\\.)*`', '', cleaned)
    cleaned = re.sub(r'//.*?$', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)

    braces = cleaned.count('{') == cleaned.count('}')
    parens = cleaned.count('(') == cleaned.count(')')
    return braces, parens


def validate_file(path: Path) -> int:
    """Вернуть число найденных issues."""
    html = path.read_text(encoding='utf-8')
    sections = extract_js_sections(html)

    if not sections:
        print(f'  ⚠️  {path.name}: no <script> sections without id attribute found')
        return 0

    total_issues = 0
    for start_line, js in sections:
        math_bugs = find_math_bugs(js, start_line)
        null_bugs = find_gl_null_uniforms(js, start_line)
        braces_ok, parens_ok = check_balanced(js)

        if math_bugs or null_bugs or not braces_ok or not parens_ok:
            print(f'❌ {path.name} (script at line {start_line}):')
            for line, func, snippet in math_bugs:
                print(f'   line {line}: missing Math.{func}() — found "{func}(" without Math. prefix')
                print(f'      → {snippet}')
            for line, snippet in null_bugs:
                print(f'   line {line}: gl.uniform*(null, ...) — uniform location is null')
                print(f'      → {snippet}')
            if not braces_ok:
                print(f'   unbalanced braces {{}} in JS section')
            if not parens_ok:
                print(f'   unbalanced parens () in JS section')
            total_issues += len(math_bugs) + len(null_bugs) + (0 if braces_ok else 1) + (0 if parens_ok else 1)
        else:
            js_lines = js.count('\n') + 1
            print(f'✅ {path.name}: JS section OK ({js_lines} lines, starting at line {start_line})')

    return total_issues


def main():
    if len(sys.argv) > 1:
        files = [Path(arg) for arg in sys.argv[1:]]
    else:
        # Default: all preview HTMLs in download/shaders/
        shaders_dir = Path('/home/z/my-project/download/shaders')
        files = sorted(shaders_dir.glob('*_preview.html'))

    if not files:
        print('No preview HTML files found.')
        return 1

    print(f'Validating {len(files)} preview HTML files...\n')

    total_issues = 0
    for f in files:
        if not f.exists():
            print(f'❌ {f}: file not found')
            total_issues += 1
            continue
        total_issues += validate_file(f)

    print(f'\n{"=" * 60}')
    if total_issues == 0:
        print('✅ ALL JS SECTIONS OK')
    else:
        print(f'❌ {total_issues} issue(s) found')
    return 0 if total_issues == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
