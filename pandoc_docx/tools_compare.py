import re, subprocess, sys, zipfile, difflib
def plain(p): return subprocess.run(["pandoc", p, "-t", "plain", "--wrap=none"], capture_output=True, text=True).stdout
def norm(t):
    t = re.sub(r"[ \t]+", " ", t)
    return [l.strip() for l in t.split("\n") if l.strip() and not re.fullmatch(r"[-\s]+", l.strip())]
def drop_toc_and_cover(lines, new=False):
    # убираем всё до первой H1-секции «1. Введение», кроме самого текста секций
    i = next(i for i, l in enumerate(lines) if re.match(r"^1\. Введение", l) and (not new or True) and i > 5)
    return lines[i:]
def stats(p):
    z = zipfile.ZipFile(p); x = z.read("word/document.xml").decode()
    return dict(H1=len(re.findall(r'pStyle w:val="Heading1"', x)), H2=len(re.findall(r'pStyle w:val="Heading2"', x)),
                tables=x.count("<w:tbl>"), images=len([n for n in z.namelist() if n.startswith("word/media/")]),
                drawings=x.count("<w:drawing>"), size_kb=round(__import__("os").path.getsize(p)/1024,1))
g, n = sys.argv[1], sys.argv[2]
print("golden", stats(g)); print("new   ", stats(n))
gl = norm(plain(g)); nl = norm(plain(n))
# позиция первой настоящей секции (после TOC) — вторая встреча «1. Введение»
def body(lines):
    idx = [i for i, l in enumerate(lines) if l.startswith("1. Введение")]
    return lines[idx[-1]:]
gb, nb = body(gl), body(nl)
print("строк в теле: golden", len(gb), "new", len(nb))
sm = difflib.SequenceMatcher(None, gb, nb, autojunk=False)
print("сходство строк: %.4f" % sm.ratio())
ops = [o for o in sm.get_opcodes() if o[0] != "equal"]
print("расхождений-блоков:", len(ops))
for tag, i1, i2, j1, j2 in ops[:12]:
    print(f"--- {tag}  golden[{i1}:{i2}] new[{j1}:{j2}]")
    for l in gb[i1:i2][:3]: print("  G:", l[:140])
    for l in nb[j1:j2][:3]: print("  N:", l[:140])
