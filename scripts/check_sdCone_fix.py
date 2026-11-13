# Проверка НОВОЙ sdCone: конус, основание y=0 радиуса r, вершина (0,h).
# d = max(-y, (rho*h + y*r - h*r)/sqrt(h*h+r*r))
import math

def sdCone_new(p, h, r):
    rho = math.sqrt(p[0]**2 + p[2]**2)
    d_side = (rho * h + p[1] * r - h * r) / math.sqrt(h*h + r*r)
    d_base = -p[1]
    return max(d_base, d_side)

def sdCone_old(p, h, r):
    rho = math.sqrt(p[0]**2 + p[2]**2)
    q = (rho, p[1])
    k1 = (r, h)
    k2 = (r - h, 2.0 * h)
    s = -1.0 + 2.0 * (1.0 if k1[0] <= q[0] else 0.0)
    ca = (q[0] - k1[0]) * -1.0 + (q[1] - k1[1]) * 1.0
    cb = ((q[0] - k1[0]) * k2[0] + (q[1] - k1[1]) * k2[1]) * 0.5
    cond = ca * s - cb * max(0.0, 1.0 - s)
    if cond < 0.0:
        l1 = math.sqrt((q[0]-k1[0])**2 + (q[1]-k1[1])**2)
        return -min(l1, abs(cb))
    return math.sqrt((q[0] - k1[0]*s)**2 + (q[1] - k1[1]*1.0)**2)

H, R = 1.0, 0.9
cases = [
    ((0.0, 0.0, 0.0), 0, "центр основания"),
    ((0.0, 1.0, 0.0), 0, "вершина (апекс)"),
    ((0.9, 0.0, 0.0), 0, "край основания"),
    ((0.0, 0.5, 0.0), -1, "внутри по оси"),
    ((0.4, 0.3, 0.0), -1, "внутри сбоку"),
    ((0.726, -0.705, -3.517), +1, "точка у камеры при t=20 (был баг!)"),
    ((3.0, 0.5, 0.0), +1, "далеко сбоку"),
    ((0.0, 2.0, 0.0), +1, "над вершиной"),
    ((0.0, -1.0, 0.0), +1, "под основанием"),
    ((1.5, 0.9, 0.0), +1, "сбоку на уровне апекса"),
]
print(f"{'точка':42s} {'новая':>9s} {'старая':>9s}  вердикт")
fails = 0
for p, expect, desc in cases:
    dn = sdCone_new(p, H, R)
    do = sdCone_old(p, H, R)
    ok = (dn < 0 and expect == -1) or (abs(dn) < 1e-9 and expect == 0) or (dn > 0 and expect == 1)
    bad_old = (do < 0 and expect == 1)
    if not ok: fails += 1
    mark = "OK  " if ok else "FAIL"
    old_mark = " <- старая ВРЁТ (минус снаружи)" if bad_old else ""
    print(f"{desc:42s} {dn:+9.5f} {do:+9.5f}  {mark}{old_mark}")
print(f"\nОшибок новой формулы: {fails}")
