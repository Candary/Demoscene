"""Математика без зависимостей. Матрицы — column-major (готовы к glUniformMatrix4fv).

Vec3 = (x, y, z); Quat = (x, y, z, w); Mat4 = 16 float, элемент m[col*4 + row].
"""
from __future__ import annotations

import math
from typing import Sequence, Tuple

Vec3 = Tuple[float, float, float]
Quat = Tuple[float, float, float, float]
Mat4 = Tuple[float, ...]

ZERO: Vec3 = (0.0, 0.0, 0.0)
ONE: Vec3 = (1.0, 1.0, 1.0)
QID: Quat = (0.0, 0.0, 0.0, 1.0)
IDENTITY: Mat4 = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0,
                  0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
TAU = math.tau


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def vec(seq: Sequence[float], n: int) -> Tuple[float, ...]:
    out = tuple(float(x) for x in seq)
    if len(out) != n or not all(math.isfinite(x) for x in out):
        raise ValueError(f"ожидался вектор из {n} конечных чисел, получено {seq!r}")
    return out


def vadd(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vsub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vscale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def qnorm(q: Quat) -> Quat:
    n = math.sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3])
    if n <= 0.0 or not math.isfinite(n):
        return QID
    return (q[0] / n, q[1] / n, q[2] / n, q[3] / n)


def qmul(a: Quat, b: Quat) -> Quat:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def qaxis(axis: Vec3, angle: float) -> Quat:
    x, y, z = axis
    n = math.sqrt(x * x + y * y + z * z)
    if n <= 0.0:
        return QID
    h = angle * 0.5
    s = math.sin(h) / n
    return (x * s, y * s, z * s, math.cos(h))


def qslerp(a: Quat, b: Quat, t: float) -> Quat:
    """Кратчайшая дуга + nlerp-fallback при почти совпадающих кватернионах."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    d = ax * bx + ay * by + az * bz + aw * bw
    if d < 0.0:
        bx, by, bz, bw = -bx, -by, -bz, -bw
        d = -d
    if d > 0.9995:
        return qnorm((ax + (bx - ax) * t, ay + (by - ay) * t,
                      az + (bz - az) * t, aw + (bw - aw) * t))
    d = min(1.0, max(-1.0, d))
    th = math.acos(d)
    s = math.sin(th)
    wa = math.sin((1.0 - t) * th) / s
    wb = math.sin(t * th) / s
    return (wa * ax + wb * bx, wa * ay + wb * by, wa * az + wb * bz, wa * aw + wb * bw)


def compose(pos: Vec3, rot: Quat, scale: Vec3) -> Mat4:
    """M = T * R * S. Кватернион считается нормализованным."""
    x, y, z, w = rot
    sx, sy, sz = scale
    x2, y2, z2 = x + x, y + y, z + z
    xx, yy, zz = x * x2, y * y2, z * z2
    xy, xz, yz = x * y2, x * z2, y * z2
    wx, wy, wz = w * x2, w * y2, w * z2
    return ((1.0 - (yy + zz)) * sx, (xy + wz) * sx, (xz - wy) * sx, 0.0,
            (xy - wz) * sy, (1.0 - (xx + zz)) * sy, (yz + wx) * sy, 0.0,
            (xz + wy) * sz, (yz - wx) * sz, (1.0 - (xx + yy)) * sz, 0.0,
            pos[0], pos[1], pos[2], 1.0)


def matmul(a: Mat4, b: Mat4) -> Mat4:
    out = [0.0] * 16
    for c in range(4):
        b0, b1, b2, b3 = b[c * 4:c * 4 + 4]
        for r in range(4):
            out[c * 4 + r] = a[r] * b0 + a[4 + r] * b1 + a[8 + r] * b2 + a[12 + r] * b3
    return tuple(out)


def translation(m: Mat4) -> Vec3:
    return (m[12], m[13], m[14])


_M32 = 0xFFFFFFFF


def _mix(x: int) -> int:
    x &= _M32
    x ^= x >> 16
    x = (x * 0x7FEB352D) & _M32
    x ^= x >> 15
    x = (x * 0x846CA68B) & _M32
    x ^= x >> 16
    return x


def hash01(seed: int, *index: int) -> float:
    """Детерминированный [0,1]. Замена глобальному random: зависит только от аргументов."""
    h = _mix(int(seed))
    for i in index:
        h = _mix(h ^ _mix(int(i) + 0x9E3779B9))
    return h / 4294967295.0


def hash_sym(seed: int, *index: int) -> float:
    return hash01(seed, *index) * 2.0 - 1.0