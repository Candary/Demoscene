# Диагностическая бисекция preview.html: создаёт варианты с поэтапным
# отключением новых блоков, чтобы найти причину падения FPS.
# Вариант A: MapScene без букв (сразу return MapSceneBase)
# Вариант B: A + стеклянная ветка шейдинга заменена на заливку magenta
# Вариант C: B + LetterBehind заменён на мгновенный фон
# Вариант D: C + stepLetters() как no-op (JS-физика выключена)
import re, pathlib

src = pathlib.Path('/home/z/my-project/download/demo_intro/preview.html').read_text(encoding='utf-8')
out_dir = pathlib.Path('/home/z/my-project/download/demo_intro')

# --- Вариант A: MapScene без букв ---
a = src
m = re.search(r'vec2 MapScene\(vec3 p\) \{.*?\n\}\n\n// CalcNormal', a, re.S)
assert m, 'MapScene block not found'
a = a[:m.start()] + (
    'vec2 MapScene(vec3 p) {\n'
    '    return MapSceneBase(p);  // DEBUG A: без букв\n'
    '}\n\n// CalcNormal'
) + a[m.end():]
(out_dir / 'preview_dbgA.html').write_text(a, encoding='utf-8')

# --- Вариант B: A + стеклянная ветка -> плоский magenta ---
b = a
m = re.search(r'        if \(hit\.y >= MAT_LETTER - 0\.05\) \{.*?\n        \} else if \(hit\.y >= MAT_PARTICLE\) \{', b, re.S)
assert m, 'glass branch not found'
b = b[:m.start()] + (
    '        if (hit.y >= MAT_LETTER - 0.05) {\n'
    '            col = vec3(1.0, 0.0, 1.0);  // DEBUG B\n'
    '        } else if (hit.y >= MAT_PARTICLE) {'
) + b[m.end():]
(out_dir / 'preview_dbgB.html').write_text(b, encoding='utf-8')

# --- Вариант C: B + LetterBehind -> мгновенный фон ---
c = b
m = re.search(r'vec3 LetterBehind\(vec3 ro, vec3 rd\) \{.*?\n\}\n\n// --- Основная функция', c, re.S)
assert m, 'LetterBehind not found'
c = c[:m.start()] + (
    'vec3 LetterBehind(vec3 ro, vec3 rd) {\n'
    '    return vec3(0.0);  // DEBUG C\n'
    '}\n\n// --- Основная функция'
) + c[m.end():]
(out_dir / 'preview_dbgC.html').write_text(c, encoding='utf-8')

# --- Вариант D: C + stepLetters no-op ---
d = c
m = re.search(r'function stepLetters\(dt\) \{.*?\n\}\n\nresetLetters\(\);', d, re.S)
assert m, 'stepLetters not found'
d = d[:m.start()] + (
    'function stepLetters(dt) {  // DEBUG D: no-op\n}\n\nresetLetters();'
) + d[m.end():]
(out_dir / 'preview_dbgD.html').write_text(d, encoding='utf-8')

print('Created: preview_dbgA/B/C/D.html')
