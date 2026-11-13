# dbgE: полный эквивалент "до букв" (шейдер без каких-либо буквенных
# функций) — контрольный замер, чтобы отделить регрессию окружения
# (SwiftShader chrome-156) от стоимости кода букв.
import re, pathlib

src = pathlib.Path('/home/z/my-project/download/demo_intro/preview.html').read_text(encoding='utf-8')

# 1. MapScene -> return MapSceneBase
m = re.search(r'vec2 MapScene\(vec3 p\) \{.*?\n\}\n\n// CalcNormal', src, re.S)
assert m, 'MapScene not found'
src = src[:m.start()] + (
    'vec2 MapScene(vec3 p) {\n'
    '    return MapSceneBase(p);  // DBG E\n'
    '}\n\n// CalcNormal'
) + src[m.end():]

# 2. Удалить LetterBehind целиком
m = re.search(r'// --- «Просвет» сквозь стеклянную букву.*?vec3 LetterBehind\(vec3 ro, vec3 rd\) \{.*?\n\}\n\n(?=// --- Основная функция)', src, re.S)
assert m, 'LetterBehind not found'
src = src[:m.start()] + src[m.end():]

# 3. Удалить стеклянную ветку шейдинга
m = re.search(r'        if \(hit\.y >= MAT_LETTER - 0\.05\) \{.*?\n        \} else if \(hit\.y >= MAT_PARTICLE\) \{', src, re.S)
assert m, 'glass branch not found'
src = src[:m.start()] + '        if (hit.y >= MAT_PARTICLE) {' + src[m.end():]

out = pathlib.Path('/home/z/my-project/download/demo_intro/preview_dbgE.html')
out.write_text(src, encoding='utf-8')
print('Created: preview_dbgE.html')
