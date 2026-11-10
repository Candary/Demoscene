"""Язык выражений для связи «атом -> uniform»: безопасный, тотальный, детерминированный.

Почему не eval и не «просто строка»: выражение должно (1) проверяться до запуска, (2) считаться одинаково в Python и в C++,
(3) никогда не падать и не давать NaN в рантайме. Поэтому:
  * грамматика маленькая: числа, имена (с точками: audio.energy), + - * / %, сравнения, && || !, вызов функций из белого списка;
  * нет циклов, присваиваний, строк, индексации; все функции тотальны (деление на ноль = 0, sqrt(<0) = 0, pow(<0, дробь) = 0);
  * результат всегда конечное число (NaN/inf -> 0);
  * выражение компилируется в обратную польскую запись (RPN) — её исполняет стековая машина в ~60 строк на любом языке.
Булевы значения — 1.0 / 0.0. Все аргументы функций вычисляются (без «ленивости»), поэтому if(c, a, b) безопасен.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

MAX_TOKENS = 200
MAX_DEPTH = 32

FUNCS: dict[str, int] = {  # имя -> арность
    "abs": 1, "sign": 1, "floor": 1, "ceil": 1, "fract": 1, "sqrt": 1, "sin": 1, "cos": 1, "exp": 1,
    "min": 2, "max": 2, "pow": 2, "mod": 2, "step": 2, "clamp": 3, "mix": 3, "smoothstep": 3, "if": 3,
}
BINARY = {"||": 1, "&&": 2, "==": 3, "!=": 3, "<": 4, ">": 4, "<=": 4, ">=": 4, "+": 5, "-": 5, "*": 6, "/": 6, "%": 6}
UNARY = ("neg", "not")

_TOKEN = re.compile(r"\s*(?:(?P<num>(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)|(?P<id>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
                    r"|(?P<op>\|\||&&|==|!=|<=|>=|[-+*/%<>!(),]))")


class ExprError(ValueError):
    pass


@dataclass(frozen=True)
class Compiled:
    source: str
    rpn: tuple            # кортеж элементов ("n", x) | ("v", name) | ("o", op) | ("f", name)
    names: frozenset      # использованные переменные

    @property
    def is_constant(self) -> bool:
        return not self.names


def _tokenize(src: str, max_tokens: int = MAX_TOKENS):
    pos, out = 0, []
    src = src.strip()
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        if not m or m.end() == pos:
            raise ExprError(f"недопустимый символ {src[pos:pos + 1]!r} в позиции {pos}: {src!r}")
        pos = m.end()
        if m.group("num") is not None:
            out.append(("n", float(m.group("num"))))
        elif m.group("id") is not None:
            out.append(("id", m.group("id")))
        else:
            out.append(("p", m.group("op")))
        if len(out) > max_tokens:
            raise ExprError(f"выражение длиннее {max_tokens} токенов")
    if not out:
        raise ExprError("пустое выражение")
    return out


class _Parser:
    def __init__(self, toks, allowed):
        self.t, self.i, self.allowed, self.rpn, self.names = toks, 0, allowed, [], set()

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, val):
        k, v = self.take()
        if (k, v) != ("p", val):
            raise ExprError(f"ожидалось {val!r}, найдено {v!r}")

    def parse(self):
        self.expr(0, 0)
        if self.i != len(self.t):
            raise ExprError(f"лишние токены после выражения: {self.t[self.i][1]!r}")

    def expr(self, min_prec, depth):
        if depth > MAX_DEPTH:
            raise ExprError("слишком глубокая вложенность")
        self.unary(depth)
        while True:
            k, v = self.peek()
            if k != "p" or v not in BINARY or BINARY[v] < min_prec or BINARY[v] == 0:
                return
            self.take()
            self.expr(BINARY[v] + 1, depth + 1)
            self.rpn.append(("o", v))

    def unary(self, depth):
        k, v = self.peek()
        if (k, v) == ("p", "-"):
            self.take(); self.unary(depth + 1); self.rpn.append(("o", "neg"))
        elif (k, v) == ("p", "!"):
            self.take(); self.unary(depth + 1); self.rpn.append(("o", "not"))
        else:
            self.primary(depth)

    def primary(self, depth):
        k, v = self.take()
        if k == "n":
            self.rpn.append(("n", v))
        elif k == "id":
            if self.peek() == ("p", "("):
                if v not in FUNCS:
                    raise ExprError(f"неизвестная функция {v!r}; допустимо: {sorted(FUNCS)}")
                self.take()
                n = 0
                if self.peek() != ("p", ")"):
                    while True:
                        self.expr(1, depth + 1); n += 1
                        if self.peek() == ("p", ","):
                            self.take(); continue
                        break
                self.expect(")")
                if n != FUNCS[v]:
                    raise ExprError(f"{v}() принимает {FUNCS[v]} арг., передано {n}")
                self.rpn.append(("f", v))
            else:
                if self.allowed is not None and v not in self.allowed:
                    raise ExprError(f"неизвестная переменная {v!r}; доступно: {sorted(self.allowed)}")
                self.names.add(v)
                self.rpn.append(("v", v))
        elif (k, v) == ("p", "("):
            self.expr(1, depth + 1)
            self.expect(")")
        else:
            raise ExprError(f"неожиданный токен {v!r}")


def compile_expr(src: str, allowed_names=None, max_tokens: int = MAX_TOKENS) -> Compiled:
    """allowed_names: набор допустимых переменных (None — не проверять). max_tokens: лимит длины (для авторских выражений 200;
    для выражений, сгенерированных из кривых, больше). Бросает ExprError."""
    if not isinstance(src, str):
        raise ExprError(f"выражение должно быть строкой, получено {type(src).__name__}")
    p = _Parser(_tokenize(src, max_tokens), set(allowed_names) if allowed_names is not None else None)
    p.parse()
    return Compiled(src.strip(), tuple(p.rpn), frozenset(p.names))


def _fin(x: float) -> float:
    return x if math.isfinite(x) else 0.0


def _apply_fn(name, a):
    if name == "abs": return abs(a[0])
    if name == "sign": return (a[0] > 0) - (a[0] < 0)
    if name == "floor": return math.floor(a[0])
    if name == "ceil": return math.ceil(a[0])
    if name == "fract": return a[0] - math.floor(a[0])
    if name == "sqrt": return math.sqrt(a[0]) if a[0] > 0 else 0.0
    if name == "sin": return math.sin(a[0])
    if name == "cos": return math.cos(a[0])
    if name == "exp": return math.exp(min(a[0], 700.0))
    if name == "min": return min(a)
    if name == "max": return max(a)
    if name == "pow":
        x, y = a
        if x < 0 and y != math.floor(y):
            return 0.0
        try:
            return math.pow(x, y)
        except (OverflowError, ValueError, ZeroDivisionError):
            return 0.0
    if name == "mod": return a[0] - a[1] * math.floor(a[0] / a[1]) if a[1] != 0 else 0.0
    if name == "step": return 1.0 if a[1] >= a[0] else 0.0
    if name == "clamp": return min(max(a[0], a[1]), a[2])
    if name == "mix": return a[0] + (a[1] - a[0]) * a[2]
    if name == "smoothstep":
        e0, e1, x = a
        if e0 == e1:
            return 1.0 if x >= e1 else 0.0
        t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
        return t * t * (3.0 - 2.0 * t)
    if name == "if": return a[1] if a[0] != 0.0 else a[2]
    raise ExprError(f"неизвестная функция {name}")


def _apply_op(op, a, b=None):
    if op == "neg": return -a
    if op == "not": return 0.0 if a != 0.0 else 1.0
    if op == "+": return a + b
    if op == "-": return a - b
    if op == "*": return a * b
    if op == "/": return a / b if b != 0.0 else 0.0
    if op == "%": return a - b * math.floor(a / b) if b != 0.0 else 0.0
    if op == "<": return 1.0 if a < b else 0.0
    if op == ">": return 1.0 if a > b else 0.0
    if op == "<=": return 1.0 if a <= b else 0.0
    if op == ">=": return 1.0 if a >= b else 0.0
    if op == "==": return 1.0 if a == b else 0.0
    if op == "!=": return 1.0 if a != b else 0.0
    if op == "&&": return 1.0 if (a != 0.0 and b != 0.0) else 0.0
    if op == "||": return 1.0 if (a != 0.0 or b != 0.0) else 0.0
    raise ExprError(f"неизвестный оператор {op}")


def eval_rpn(rpn, env: dict) -> float:
    """Стековая машина. Эталон семантики: C++ реализация (runtime_ref/vm.hpp) обязана давать те же значения."""
    st: list[float] = []
    for kind, val in rpn:
        if kind == "n":
            st.append(float(val))
        elif kind == "v":
            st.append(float(env[val]))
        elif kind == "o":
            if val in UNARY:
                st.append(_fin(_apply_op(val, st.pop())))
            else:
                b = st.pop(); a = st.pop()
                st.append(_fin(_apply_op(val, a, b)))
        else:
            n = FUNCS[val]
            args = st[-n:]
            del st[-n:]
            st.append(_fin(float(_apply_fn(val, args))))
    if len(st) != 1:
        raise ExprError("повреждённая RPN: на стеке осталось не одно значение")
    return _fin(st[0])


def evaluate(src_or_compiled, env: dict) -> float:
    c = src_or_compiled if isinstance(src_or_compiled, Compiled) else compile_expr(src_or_compiled)
    return eval_rpn(c.rpn, env)


def fold_constant(c: Compiled) -> Compiled:
    """Выражение без переменных заменяется одним числом."""
    if c.is_constant and not (len(c.rpn) == 1 and c.rpn[0][0] == "n"):
        return Compiled(c.source, (("n", eval_rpn(c.rpn, {})),), frozenset())
    return c


def rpn_to_tokens(rpn) -> list[str]:
    """Текстовая форма для baked-файла: n:1.5  v:audio.energy  o:+  f:smoothstep."""
    out = []
    for kind, val in rpn:
        out.append(f"n:{val!r}" if kind == "n" else f"{kind}:{val}")
    return out
