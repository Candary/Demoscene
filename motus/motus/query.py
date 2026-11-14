"""Текст -> единый IR. DSL и свободный язык дают одинаковые Cmd.

Переключение режима: строка `mode dsl` / `mode free` / `mode auto`.
Директива действует до конца запроса и запоминается в сессии Runtime.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .clock import Transport
from .core import MotusError, QueryError, Registry

DSL_VERBS = ("new", "set", "anim", "proc", "fx", "drop")
MODES = ("dsl", "free", "auto")


@dataclass
class Cmd:
    op: str
    at: float = 0.0
    name: str = ""
    parent: str = ""
    channel: str = ""
    values: Dict[str, Any] = field(default_factory=dict)
    keys: List[Tuple[float, Any]] = field(default_factory=list)
    ease: str = "linear"
    mode: str = "replace"
    weight: float = 1.0
    loop: str = "hold"
    duration: float = 0.0
    priority: int = 0
    proc: str = ""
    effect: str = ""
    count: int = 400
    seed: int = 1
    attach: str = ""


@dataclass
class ParseResult:
    commands: List[Cmd]
    issues: List[QueryError]
    mode: str

    @property
    def ok(self) -> bool:
        return not self.issues


# ------------------------------------------------------------------ лексер
def tokenize(line: str) -> List[str]:
    """Пробелы внутри (...) и "..." не разрывают токен. Комментарии: # и //."""
    out: List[str] = []
    cur: List[str] = []
    depth = 0
    quote = False
    i = 0
    while i < len(line):
        ch = line[i]
        if not quote and depth == 0:
            if ch == "#" or (ch == "/" and i + 1 < len(line) and line[i + 1] == "/"):
                break
        if ch == '"':
            quote = not quote
            cur.append(ch)
        elif ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            cur.append(ch)
        elif ch in " \t" and depth == 0 and not quote:
            if cur:
                out.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
        i += 1
    if cur:
        out.append("".join(cur))
    if depth or quote:
        raise QueryError("незакрытая скобка или кавычка", fragment=line)
    return out


def parse_value(tok: str) -> Any:
    tok = tok.strip()
    if tok.startswith('"') and tok.endswith('"') and len(tok) >= 2:
        return tok[1:-1]
    if tok.startswith("(") and tok.endswith(")"):
        body = tok[1:-1].strip()
        if not body:
            return ()
        return tuple(parse_value(p) for p in _split_commas(body))
    low = tok.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return float(tok)
    except ValueError:
        return tok


def _split_commas(body: str) -> List[str]:
    parts: List[str] = []
    depth = 0
    cur: List[str] = []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def parse_time(tok: Any, tr: Transport) -> float:
    """2 | 2s | 500ms | beat:8 | bar:2 — музыкальная сетка поддерживается нативно."""
    if isinstance(tok, (int, float)):
        return float(tok)
    s = str(tok).strip().lower()
    if s.startswith("beat:"):
        return tr.seconds(float(s[5:]))
    if s.startswith("bar:"):
        return tr.seconds(float(s[4:]) * tr.beats_per_bar)
    mult = 1.0
    if s.endswith("ms"):
        mult, s = 0.001, s[:-2]
    elif s.endswith("s"):
        s = s[:-1]
    v = float(s)
    if not math.isfinite(v):
        raise ValueError("время должно быть конечным")
    return v * mult


def _split_target(tok: str) -> Tuple[str, str]:
    if "." not in tok:
        raise QueryError("ожидается <объект>.<канал>", fragment=tok)
    name, channel = tok.split(".", 1)
    rest = ""
    # position.x / param.glow / scale.uniform — точка может быть частью канала
    if channel in ("position", "scale") or channel.startswith("param"):
        rest = ""
    return name, channel + rest


# ------------------------------------------------------------------ DSL
def parse_dsl_line(toks: List[str], tr: Transport, line: int) -> Cmd:
    verb = toks[0]
    args: Dict[str, Any] = {}
    keys: List[Tuple[float, Any]] = []
    pos: List[str] = []
    for tok in toks[1:]:
        if "=" in tok and not tok.startswith("("):
            k, v = tok.split("=", 1)
            if k == "k":
                if ":" not in v:
                    raise QueryError("ключ задаётся как k=<t>:<значение>", fragment=tok, line=line)
                ts, vs = v.split(":", 1)
                keys.append((parse_time(ts, tr), parse_value(vs)))
            else:
                args[k] = parse_value(v)
        else:
            pos.append(tok)

    def t_of(key: str, default: float = 0.0) -> float:
        return parse_time(args[key], tr) if key in args else default

    c = Cmd(op=verb)
    try:
        c.at = t_of("at")
        if verb == "new":
            if not pos:
                raise QueryError("new требует имени", line=line)
            c.name = pos[0]
            c.parent = str(args.get("parent", ""))
            c.values = {k: v for k, v in args.items() if k not in ("at", "parent")}
        elif verb == "set":
            if not pos:
                raise QueryError("set требует <объект>.<канал>", line=line)
            c.name, c.channel = _split_target(pos[0])
            if "v" in args:
                c.values["v"] = args["v"]
            elif len(pos) > 1:
                c.values["v"] = parse_value(pos[1])
            else:
                raise QueryError("set требует значения (v=... )", line=line)
        elif verb == "anim":
            if not pos:
                raise QueryError("anim требует <объект>.<канал>", line=line)
            c.name, c.channel = _split_target(pos[0])
            c.ease = str(args.get("ease", "linear"))
            c.mode = str(args.get("mode", "replace"))
            c.weight = float(args.get("weight", 1.0))
            c.loop = str(args.get("loop", "hold"))
            c.priority = int(args.get("prio", 0))
            c.duration = t_of("over")
            if keys:
                c.keys = keys
            elif "from" in args and "to" in args:
                span = c.duration if c.duration > 0 else 1.0
                c.duration = span
                c.keys = [(0.0, args["from"]), (span, args["to"])]
            else:
                raise QueryError("anim требует k=<t>:<v> ... либо from=/to=", line=line)
        elif verb == "proc":
            if len(pos) < 2:
                raise QueryError("proc требует <объект>.<канал> <процедура>", line=line)
            c.name, c.channel = _split_target(pos[0])
            c.proc = pos[1]
            c.mode = str(args.get("mode", "replace"))
            c.weight = float(args.get("weight", 1.0))
            c.loop = str(args.get("loop", "hold"))
            c.priority = int(args.get("prio", 0))
            c.duration = t_of("over")
            c.seed = int(args.get("seed", 1))
            c.values = {k: v for k, v in args.items()
                        if k not in ("at", "over", "mode", "weight", "loop", "prio", "seed")}
        elif verb == "fx":
            if not pos:
                raise QueryError("fx требует имени эффекта", line=line)
            c.effect = pos[0]
            c.attach = str(args.get("on", ""))
            c.duration = t_of("for", 2.0)
            c.count = int(args.get("count", 400))
            c.seed = int(args.get("seed", 1))
            c.values = {k: v for k, v in args.items()
                        if k not in ("at", "for", "count", "seed", "on", "origin")}
            if "origin" in args:
                c.values["origin"] = args["origin"]
        elif verb == "drop":
            if not pos:
                raise QueryError("drop требует имени", line=line)
            c.name = pos[0]
        else:
            raise QueryError(f"неизвестная команда '{verb}'", fragment=verb,
                             hints=list(DSL_VERBS), line=line)
    except (ValueError, TypeError) as exc:
        raise QueryError(f"{verb}: {exc}", line=line, fragment=" ".join(toks)) from exc
    return c


# ------------------------------------------------------------------ свободный язык
VERBS = Registry("verb")
NOUNS = Registry("noun")
COLORS = Registry("color")
NUMWORDS = Registry("number-word")
DIRS = Registry("direction")

for _w in ("создай", "создать", "добавь", "добавить", "new", "create", "spawn", "add"):
    VERBS.add(_w, "new")
for _w in ("анимируй", "анимировать", "двигай", "двинь", "перемести", "лети", "летит",
           "move", "animate", "fly"):
    VERBS.add(_w, "anim")
for _w in ("вращай", "вращать", "крути", "крутится", "spin", "rotate"):
    VERBS.add(_w, "spin")
for _w in ("пульсируй", "пульсирует", "дыши", "pulse"):
    VERBS.add(_w, "pulse")
for _w in ("взорви", "взрыв", "взорвется", "взорвётся", "искры", "фейерверк",
           "burst", "explode", "firework"):
    VERBS.add(_w, "burst")
for _w in ("фонтан", "струя", "fountain"):
    VERBS.add(_w, "fountain")
for _w in ("спираль", "вихрь", "spiral", "vortex"):
    VERBS.add(_w, "spiral")
for _w in ("ударная", "волна", "shockwave"):
    VERBS.add(_w, "shockwave")
for _w in ("удали", "убери", "исчезни", "исчезнет", "remove", "delete", "hide"):
    VERBS.add(_w, "drop")
for _w in ("покрась", "окрась", "цвет", "color", "paint"):
    VERBS.add(_w, "paint")
for _w in ("подожди", "жди", "wait"):
    VERBS.add(_w, "wait")

for _w, _n in (("шар", "ball"), ("сфера", "ball"), ("sphere", "ball"), ("ball", "ball"),
               ("куб", "box"), ("cube", "box"), ("box", "box"),
               ("тор", "torus"), ("torus", "torus"), ("точка", "dot"), ("dot", "dot")):
    NOUNS.add(_w, _n)

for _w, _c in (("оранжевый", (1.0, 0.6, 0.2)), ("orange", (1.0, 0.6, 0.2)),
               ("красный", (1.0, 0.15, 0.1)), ("red", (1.0, 0.15, 0.1)),
               ("синий", (0.2, 0.4, 1.0)), ("blue", (0.2, 0.4, 1.0)),
               ("голубой", (0.3, 0.8, 1.0)), ("cyan", (0.3, 0.8, 1.0)),
               ("зеленый", (0.3, 1.0, 0.4)), ("green", (0.3, 1.0, 0.4)),
               ("белый", (1.0, 1.0, 1.0)), ("white", (1.0, 1.0, 1.0))):
    COLORS.add(_w, _c)

for _w, _n in (("полсекунды", 0.5), ("секунду", 1.0), ("две", 2.0), ("два", 2.0),
               ("три", 3.0), ("четыре", 4.0), ("пять", 5.0), ("ten", 10.0)):
    NUMWORDS.add(_w, _n)

for _w, _d in (("вправо", (2.0, 0.0, 0.0)), ("right", (2.0, 0.0, 0.0)),
               ("влево", (-2.0, 0.0, 0.0)), ("left", (-2.0, 0.0, 0.0)),
               ("вверх", (0.0, 2.0, 0.0)), ("up", (0.0, 2.0, 0.0)),
               ("вниз", (0.0, -2.0, 0.0)), ("down", (0.0, -2.0, 0.0))):
    DIRS.add(_w, _d)

_SEQ = re.compile(r"\b(потом|затем|then|after that)\b")
_WORD = re.compile(r"[а-яА-Яa-zA-Z0-9_]+")


def _fuzzy(reg: Registry, word: str) -> Optional[str]:
    """Точное совпадение (case-insensitive), затем осторожный префикс (LCP>=4 и >=60%)."""
    wl = word.lower()
    for k in reg.names():
        if k.lower() == wl:
            return k
    best, score = None, 0.0
    for k in reg.names():
        kl = k.lower()
        n = min(len(kl), len(wl))
        lcp = 0
        while lcp < n and kl[lcp] == wl[lcp]:
            lcp += 1
        if lcp < 4:
            continue
        s = lcp / max(len(kl), len(wl))
        if s >= 0.6 and s > score:
            best, score = k, s
    return best


def _clauses(text: str) -> List[str]:
    out: List[str] = []
    for part in re.split(r"[.,;!?\n]+", text):
        for sub in _SEQ.split(part):
            s = sub.strip()
            if s and not _SEQ.fullmatch(s):
                out.append(s)
    return out


def parse_free(text: str, tr: Transport, state: Dict[str, Any]) -> Tuple[List[Cmd], List[QueryError]]:
    """Режем клаузу по найденным глаголам, а не по союзам — «взорвётся и исчезнет» = 2 команды."""
    cmds: List[Cmd] = []
    issues: List[QueryError] = []
    clock = state.setdefault("clock", 0.0)
    last = state.get("last", "")

    for ci, cl in enumerate(_clauses(text)):
        words = _WORD.findall(cl)
        hits: List[Tuple[int, str]] = []
        for idx, w in enumerate(words):
            key = _fuzzy(VERBS, w)
            if key:
                hits.append((idx, VERBS.get(key)))
        if not hits:
            color = next((COLORS.get(k) for k in words if k in COLORS), None)
            if color and last:
                cmds.append(Cmd(op="set", name=last, channel="param.color",
                                values={"v": color}, at=clock))
                continue
            issues.append(QueryError("не распознано действие", line=ci + 1, fragment=cl,
                                     hints=["создай", "двигай", "взорви", "удали"]))
            continue

        bounds = [h[0] for h in hits] + [len(words)]
        for n, (_, verb) in enumerate(hits):
            seg = words[bounds[n]:bounds[n + 1]]
            color = next((COLORS.get(k) for k in seg if k in COLORS), None)
            noun = next((NOUNS.get(k) for k in seg if k in NOUNS), None)
            direction = next((DIRS.get(k) for k in seg if k in DIRS), None)
            num = None
            for w in seg:
                if w in NUMWORDS:
                    num = NUMWORDS.get(w)
                    break
                try:
                    num = float(w)
                    break
                except ValueError:
                    continue
            secs = any(("секунд" in w) or ("second" in w) or w == "s" for w in seg)
            dur = num if (num is not None and secs) else None
            explicit = next((w for w in seg if w.startswith("@")), None)
            name = explicit[1:] if explicit else (noun or last)

            if verb == "new":
                name = explicit[1:] if explicit else (noun or f"obj{len(cmds)}")
                c = Cmd(op="new", name=name, at=clock)
                if color:
                    c.values["param.color"] = color
                cmds.append(c)
                last = name
            elif verb == "wait":
                clock += dur if dur is not None else (num if num is not None else 0.5)
            elif verb == "drop":
                if not last:
                    issues.append(QueryError("нечего удалять", line=ci + 1, fragment=cl))
                    continue
                cmds.append(Cmd(op="drop", name=last, at=clock))
            elif verb == "paint":
                if not last or color is None:
                    issues.append(QueryError("нужен объект и цвет", line=ci + 1, fragment=cl))
                    continue
                cmds.append(Cmd(op="set", name=last, channel="param.color",
                                values={"v": color}, at=clock))
            elif verb in ("anim", "spin", "pulse"):
                if not last:
                    issues.append(QueryError("сначала создайте объект", line=ci + 1, fragment=cl))
                    continue
                d = dur if dur is not None else 2.0
                if verb == "spin":
                    cmds.append(Cmd(op="proc", name=last, channel="rotation", proc="spin",
                                    at=clock, values={"rate": num or 90.0}))
                elif verb == "pulse":
                    cmds.append(Cmd(op="proc", name=last, channel="scale.uniform",
                                    proc="pulse", at=clock, mode="mul",
                                    values={"freq": (num or 1.0), "amp": 0.15}))
                else:
                    delta = direction or (2.0, 0.0, 0.0)
                    cmds.append(Cmd(op="anim", name=last, channel="position", at=clock,
                                    duration=d, ease="smooth",
                                    keys=[(0.0, (0.0, 0.0, 0.0)), (d, delta)]))
                    clock += d
            elif verb in ("burst", "fountain", "spiral"):
                cmds.append(Cmd(op="fx", effect=verb, attach=last, at=clock,
                                duration=dur or 1.5, count=int(num or 400) if not secs else 400,
                                values={}))
                clock += dur or 1.0
            elif verb == "shockwave":
                cmds.append(Cmd(op="fx", effect="shockwave", at=clock, duration=dur or 0.8))
                clock += dur or 0.8
            else:
                issues.append(QueryError(f"не поддержано: {verb}", line=ci + 1, fragment=cl))

    state["clock"] = clock
    state["last"] = last
    return cmds, issues


# ------------------------------------------------------------------ роутер
def _detect(line: str) -> str:
    toks = line.split()
    return "dsl" if toks and toks[0] in DSL_VERBS else "free"


def parse(text: str, *, mode: str = "auto", transport: Optional[Transport] = None,
          state: Optional[dict] = None) -> ParseResult:
    tr = transport or Transport()
    st = state if state is not None else {}
    if mode not in MODES:
        raise QueryError(f"режим '{mode}' неизвестен", hints=list(MODES))
    current = mode
    cmds: List[Cmd] = []
    issues: List[QueryError] = []
    free_buf: List[str] = []

    def flush() -> None:
        nonlocal free_buf
        if free_buf:
            c, i = parse_free("\n".join(free_buf), tr, st)
            cmds.extend(c)
            issues.extend(i)
            free_buf = []

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        low = line.lower()
        if low.startswith("mode "):
            flush()
            want = low[5:].strip()
            if want not in MODES:
                issues.append(QueryError(f"режим '{want}' неизвестен", line=lineno,
                                         hints=list(MODES)))
            else:
                current = want
            continue
        resolved = _detect(line) if current == "auto" else current
        if resolved == "dsl":
            flush()
            try:
                cmds.append(parse_dsl_line(tokenize(line), tr, lineno))
            except QueryError as exc:
                issues.append(exc)
            except (ValueError, TypeError) as exc:
                issues.append(QueryError(str(exc), line=lineno, fragment=line))
        else:
            free_buf.append(line)
    flush()
    return ParseResult(cmds, issues, current)