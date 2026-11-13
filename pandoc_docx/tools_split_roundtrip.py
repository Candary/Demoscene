import re
from pathlib import Path
T = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
 "a b v g d e e zh z i y k l m n o p r s t u f h c ch sh sch _ y _ e yu ya".split()))
def slug(s):
    s = re.sub(r"^\d+\.\s*", "", s.lower())
    s = "".join(T.get(c, c) for c in s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return "_".join(s.split("_")[:3]) or "section"
lines = Path("/tmp/real/all.md").read_text("utf-8").split("\n")
# 0..11: титульный блок, 12..139: «Оглавление» (поле TOC) — не переносим
start = next(i for i, l in enumerate(lines) if l.startswith("# 1. "))
parts, cur = [], None
for l in lines[start:]:
    if l.startswith("# "):
        cur = [l]; parts.append(cur)
    else:
        cur.append(l)
for n, p in enumerate(parts, 1):
    name = f"content/{n:02d}_{slug(p[0][2:])}.md"
    Path(name).write_text("\n".join(p).rstrip() + "\n", "utf-8")
    print(name, len(p), "строк")
