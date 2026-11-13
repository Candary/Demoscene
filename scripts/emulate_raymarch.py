# Полная эмуляция raymarch сцены при t=20 (фаза "чистого конуса")
# и t=16 (призма), чтобы найти, где луч теряется / появляется NaN.
import math

TAU = 2 * math.pi

def rot2d_apply(p, angle, plane):
    # GLSL: mat2(c, -s, s, c) -> M = [[c, s], [-s, c]] (column-major a,b,c,d)
    # p' = (c*x + s*y, -s*x + c*y) — поворот точки на -angle (CW)
    c, s = math.cos(angle), math.sin(angle)
    if plane == 'xz':
        x, z = p[0], p[2]
        return (c * x + s * z, p[1], -s * x + c * z)
    if plane == 'yz':
        y, z = p[1], p[2]
        return (p[0], c * y + s * z, -s * y + c * z)
    if plane == 'xy':
        x, y = p[0], p[1]
        return (c * x + s * y, -s * x + c * y, p[2])
    raise ValueError

def sdSphere(p, r):
    return math.sqrt(p[0]**2 + p[1]**2 + p[2]**2) - r

def sdTriPrism(p, hx, hy):
    qx, qy, qz = abs(p[0]), abs(p[1]), abs(p[2])
    d1 = qz - hy
    d2 = max(qx * 0.866025 + p[1] * 0.5, -p[1]) - hx * 0.5
    dx, dy = max(d1, 0.0), max(d2, 0.0)
    return math.hypot(dx, dy) + min(max(d1, d2), 0.0)

def sdCone(p, h, r):
    qx = math.sqrt(p[0]**2 + p[2]**2)
    qy = p[1]
    q = (qx, qy)
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

def sdCapsule(p, a, b, r):
    pa = (p[0]-a[0], p[1]-a[1], p[2]-a[2])
    ba = (b[0]-a[0], b[1]-a[1], b[2]-a[2])
    dotpab = pa[0]*ba[0] + pa[1]*ba[1] + pa[2]*ba[2]
    dotbaba = ba[0]**2 + ba[1]**2 + ba[2]**2
    h = max(0.0, min(1.0, dotpab / dotbaba))
    dx = pa[0] - ba[0]*h; dy = pa[1] - ba[1]*h; dz = pa[2] - ba[2]*h
    return math.sqrt(dx*dx + dy*dy + dz*dz) - r

def mix(a, b, f):
    return a * (1.0 - f) + b * f

def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)

def map_scene_d_main(p, t):
    # повороты: мышь (0), затем gRotXZ(t*0.5), gRotYZ(t*0.3), gRotXY(t*0.2)
    q = rot2d_apply(p, t * 0.5, 'xz')
    q = rot2d_apply(q, t * 0.3, 'yz')
    q = rot2d_apply(q, t * 0.2, 'xy')
    phase = (t * 0.25) % 9.0
    idx = math.floor(phase)
    frac_ = smoothstep(0.0, 1.0, phase - idx)
    d1 = sdSphere(q, 1.0)
    d2 = None  # box не нужен для этих тестов
    d4 = (abs(q[0]) + abs(q[1]) + abs(q[2]) - 1.0) * 0.57735027
    d5 = sdTriPrism(q, 1.0, 0.5)
    d6 = sdCone(q, 1.0, 0.9)
    d7 = sdCapsule(q, (-0.8, -0.6, 0.0), (0.8, 0.6, 0.0), 0.35)
    if idx < 3.5:   return mix(d4, d5, frac_), q
    elif idx < 4.5: return mix(d5, d6, frac_), q
    elif idx < 5.5: return mix(d6, d7, frac_), q
    elif idx < 6.5: return (mix(d7, d7, frac_), q)  # заглушка, не используется
    return (d1, q)

def raymarch(ro, rd, t, steps=60, max_dist=20.0, eps=0.001):
    tt = 0.0
    traj = []
    for i in range(steps):
        p = (ro[0] + rd[0]*tt, ro[1] + rd[1]*tt, ro[2] + rd[2]*tt)
        d, q = map_scene_d_main(p, t)
        traj.append((i, tt, d, q))
        if not math.isfinite(d):
            return ('NaN/inf at step', traj[-4:])
        if d < eps:
            return ('HIT', traj[-4:])
        tt += d * 0.9
        if tt > max_dist:
            return ('MISS maxdist', traj[-4:])
    return ('MISS steps', traj[-4:])

def cam_at(t):
    cam_t = t * 0.3
    dist = 3.5
    return (math.sin(cam_t)*dist, math.sin(cam_t*0.7)*(dist*0.35), math.cos(cam_t)*dist)

def norm(v):
    l = math.sqrt(sum(c*c for c in v))
    return (v[0]/l, v[1]/l, v[2]/l)

for T in (16.0, 18.5, 20.0, 21.0, 24.0):
    ro = cam_at(T)
    # луч в центр экрана: к origin
    rd = norm((-ro[0], -ro[1], -ro[2]))
    res, traj = raymarch(ro, rd, T)
    last = traj[-1]
    print(f"t={T:5.1f} центр экрана: {res}, последний шаг: i={last[0]} t={last[1]:.3f} d={last[2]:.5f}")
    # пара офцентровых лучей
    for name, uv in [("верх", 0.3), ("право", 0.3)]:
        if name == "верх":
            rd2 = norm((-ro[0], -ro[1]+0.35*3.5, -ro[2]))
        else:
            rd2 = norm((-ro[0]+0.35*3.5, -ro[1], -ro[2]))
        r2, _ = raymarch(ro, rd2, T)
        print(f"        луч {name}: {r2}")

# и точечная проверка sdCone вдоль луча t=20: на каких точках huge/NaN
print("\nПрофиль d_main вдоль центрального луча t=20 (первые 30 шагов):")
ro = cam_at(20.0)
rd = norm((-ro[0], -ro[1], -ro[2]))
tt = 0.0
for i in range(30):
    p = (ro[0]+rd[0]*tt, ro[1]+rd[1]*tt, ro[2]+rd[2]*tt)
    d, q = map_scene_d_main(p, 20.0)
    print(f"  step {i:2d} t={tt:6.3f} p=({p[0]:+.3f},{p[1]:+.3f},{p[2]:+.3f}) q=({q[0]:+.3f},{q[1]:+.3f},{q[2]:+.3f}) d={d:.5f}")
    tt += d * 0.9
    if tt > 20: break
