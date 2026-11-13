"""Граф рендера: из клипов, активных в данный момент, строится список проходов (passes) и выделяются текстуры (FBO).

Правила (один источник истины — этот планировщик; рантайм лишь исполняет готовый план):
  * дорожки идут снизу вверх (по order). Сцены/оверлеи композитятся в «накопитель» (acc);
  * первая сцена, если она непрозрачная (blend=normal, opacity=1), рисуется прямо в acc — без своего FBO;
  * эффект с direct_blend=true рисуется в acc с GL-смешиванием, без своего FBO (частицы, вспышки, титры);
  * иначе: свой FBO + COMPOSITE в acc;
  * переход читает A и B (каждый в своём FBO) и пишет результат (если он первый слой — сразу в acc);
  * post обрабатывает всё, что ниже его дорожки (пинг-понг: читает acc, пишет новый acc); то, что выше, рисуется после;
  * финальный acc = экран (SCREEN): без post вообще нет лишних текстур;
  * физические текстуры выделяются по времени жизни (greedy по интервалам): цепочка из любого числа post использует 2 текстуры.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .effects import EffectCatalog
from .timeline import EPS, ResolvedShow, RClip

DIRECT_BLENDS = ("normal", "add", "screen", "multiply")


@dataclass
class Op:
    op: str                    # CLEAR | RENDER | DRAW | COMPOSITE | TRANSITION | POST
    clip: str | None = None
    reads: list[str] = field(default_factory=list)
    write: str | None = None   # новая цель (RENDER/TRANSITION/POST) или цель очистки
    dest: str | None = None    # цель, в которую смешиваем «на месте» (DRAW/COMPOSITE)
    blend: str | None = None

    def refs(self) -> list[str]:
        return [x for x in [*self.reads, self.write, self.dest] if x]

    def to_dict(self) -> dict:
        return {k: v for k, v in {"op": self.op, "clip": self.clip, "reads": self.reads or None, "write": self.write,
                                  "dest": self.dest, "blend": self.blend}.items() if v is not None}


@dataclass
class Segment:
    start: float
    end: float
    ops: list[Op]
    targets: dict[str, str]    # виртуальная цель -> 'screen' | 'fbo<k>'
    n_physical: int
    cost: int
    active: list[str]

    def physical_ops(self) -> list[dict]:
        out = []
        for o in self.ops:
            d = o.to_dict()
            for k in ("reads", "write", "dest"):
                if k in d:
                    d[k] = [self.targets[x] for x in d[k]] if k == "reads" else self.targets[d[k]]
            out.append(d)
        return out


def _opaque(c: RClip) -> bool:
    """Полностью непрозрачный слой: blend=normal и opacity — константа 1."""
    op = c.opacity
    return (c.blend == "normal" and op is not None and len(op.rpn) == 1 and op.rpn[0][0] == "n" and abs(op.rpn[0][1] - 1.0) < 1e-12)


def plan_instant(res: ResolvedShow, cat: EffectCatalog, m: float) -> tuple[list[Op], list[RClip]]:
    active = [c for c in res.clips if c.eff_start - EPS <= m < c.eff_end - EPS and c.kind != "event"]
    byid = {c.id: c for c in active}
    consumed = {i for c in active if c.kind == "transition" for i in c.inputs}
    ops: list[Op] = []
    n = [0]

    def new() -> str:
        n[0] += 1
        return f"v{n[0]}"

    acc: str | None = None

    def layer(c: RClip, img: str | None, ef) -> None:
        """Добавить слой c: img — уже отрисованная картинка (или None, если рисуем сами)."""
        nonlocal acc
        if img is None:
            if acc is None and c.kind == "scene" and _opaque(c):
                acc = new(); ops.append(Op("RENDER", c.id, write=acc)); return
            if ef.direct_blend and c.blend in DIRECT_BLENDS:
                if acc is None:
                    acc = new(); ops.append(Op("CLEAR", write=acc))
                ops.append(Op("DRAW", c.id, dest=acc, blend=c.blend)); return
            img = new(); ops.append(Op("RENDER", c.id, write=img))
        if acc is None:
            if c.blend == "normal" and _opaque(c):
                acc = img; return
            acc = new(); ops.append(Op("CLEAR", write=acc))
        ops.append(Op("COMPOSITE", c.id, reads=[img], dest=acc, blend=c.blend))

    for order in sorted({c.track_order for c in active}):
        items = sorted([c for c in active if c.track_order == order and c.id not in consumed], key=lambda c: (c.eff_start, c.order_in_show))
        for c in items:
            ef = cat.get(c.effect)
            if c.kind in ("scene", "overlay"):
                layer(c, None, ef)
            elif c.kind == "transition":
                a, b = byid.get(c.inputs[0]), byid.get(c.inputs[1])
                if a is None or b is None:
                    continue
                ta, tb, out = new(), new(), new()
                ops.append(Op("RENDER", a.id, write=ta)); ops.append(Op("RENDER", b.id, write=tb))
                ops.append(Op("TRANSITION", c.id, reads=[ta, tb], write=out))
                layer(c, out, ef)
            elif c.kind == "post":
                if acc is None:
                    continue
                nxt = new(); ops.append(Op("POST", c.id, reads=[acc], write=nxt)); acc = nxt
    if acc is None:
        acc = new(); ops.append(Op("CLEAR", write=acc))
    ops.append(Op("PRESENT", reads=[acc]))
    return ops, active


def allocate(ops: list[Op]) -> tuple[dict[str, str], int]:
    """Виртуальные цели -> физические по времени жизни. Финальный acc (читается PRESENT) — это экран."""
    final = next(o for o in ops if o.op == "PRESENT").reads[0]
    first: dict[str, int] = {}
    last: dict[str, int] = {}
    for i, o in enumerate(ops):
        for r in o.refs():
            first.setdefault(r, i)
            last[r] = i
    targets = {final: "screen"}
    free: list[tuple[int, str]] = []   # (индекс последнего использования, имя)
    k = 0
    for v in sorted((v for v in first if v != final), key=lambda v: first[v]):
        pick = next((f for f in sorted(free) if f[0] < first[v]), None)
        if pick:
            free.remove(pick); name = pick[1]
        else:
            name = f"fbo{k}"; k += 1
        targets[v] = name
        free.append((last[v], name))
    return targets, k


def plan(res: ResolvedShow, cat: EffectCatalog) -> list[Segment]:
    D = res.duration
    pts = sorted({0.0, D, *[x for c in res.clips if c.kind != "event" for x in (c.eff_start, c.eff_end) if 0.0 <= x <= D]})
    segs: list[Segment] = []
    for a, b in zip(pts, pts[1:]):
        if b - a < 1e-6:
            continue
        ops, active = plan_instant(res, cat, (a + b) / 2)
        targets, k = allocate(ops)
        seg = Segment(a, b, ops, targets, k, sum(cat.get(c.effect).cost for c in active), [c.id for c in active])
        if segs and segs[-1].physical_ops() == seg.physical_ops() and segs[-1].active == seg.active:
            segs[-1].end = b          # те же проходы -> объединяем интервалы
        else:
            segs.append(seg)
    return segs


def memory_report(segs: list[Segment], width: int = 1920, height: int = 1080, bytes_per_pixel: int = 8) -> dict:
    peak = max((s.n_physical for s in segs), default=0)
    worst = max(segs, key=lambda s: s.n_physical, default=None)
    return {"segments": len(segs), "peak_fbos": peak, "peak_at": [worst.start, worst.end] if worst else None,
            "fbo_bytes_each": width * height * bytes_per_pixel, "peak_fbo_megabytes": round(peak * width * height * bytes_per_pixel / 1e6, 1),
            "assumption": f"{width}x{height}, {bytes_per_pixel} байт/пиксель (RGBA16F)", "max_cost": max((s.cost for s in segs), default=0)}
