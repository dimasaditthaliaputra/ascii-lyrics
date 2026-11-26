"""Real 3D point-cloud meshes rendered donut.c style.

Geometry (points + normals) is sampled once; each frame only applies a
rotation matrix, projects with a z-buffer and maps the lit normal onto a
luminance ramp. Used for the spinning 3D heart and the opening 3D flower.
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

from ..canvas import Canvas
from ..color import RGB, mix, scale

Vec = Tuple[float, float, float]
LUMA = ".,:-~=+*o#%@"


def _norm(v: Vec) -> Vec:
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def sample_surface(fn, us: int, vs: int, u_range, v_range, tag: int = 0, per_point: bool = True):
    """Sample a parametric surface; normals from finite differences.

    ``per_point`` orients each normal away from the centroid (right for thin,
    convex-ish pieces like petals). Closed surfaces with concave parts (the
    heart's cleft) instead keep the parametrisation's own consistent
    orientation, flipped as a whole if most normals point inward.
    """
    pts: List[Tuple[Vec, Vec, int, float]] = []
    u0, u1 = u_range
    v0, v1 = v_range
    eps = 1e-3
    raw = []
    for i in range(us):
        u = u0 + (u1 - u0) * (i + 0.5) / us
        for j in range(vs):
            v = v0 + (v1 - v0) * (j + 0.5) / vs
            p = fn(u, v)
            pu = fn(u + eps, v)
            pv = fn(u, v + eps)
            du = (pu[0] - p[0], pu[1] - p[1], pu[2] - p[2])
            dv = (pv[0] - p[0], pv[1] - p[1], pv[2] - p[2])
            e = abs((j + 0.5) / vs * 2 - 1)  # 0 on the centre line .. 1 at the side edge
            raw.append((p, _norm(_cross(du, dv)), i / max(1, us - 1), e))
    cx = sum(r[0][0] for r in raw) / len(raw)
    cy = sum(r[0][1] for r in raw) / len(raw)
    cz = sum(r[0][2] for r in raw) / len(raw)
    def outward(p, n):
        return n[0] * (p[0] - cx) + n[1] * (p[1] - cy) + n[2] * (p[2] - cz) >= 0

    flip_all = sum(1 for p, n, _, _ in raw if outward(p, n)) < len(raw) / 2
    for p, n, s, e in raw:
        if (per_point and not outward(p, n)) or (not per_point and flip_all):
            n = (-n[0], -n[1], -n[2])
        pts.append((p, n, tag, s, e))
    return pts


def heart_mesh():
    """Classic parametric 3D heart, normalised to roughly unit size."""
    def f(u, v):
        x = math.sin(u) * (15 * math.sin(v) - 4 * math.sin(3 * v))
        z = 8 * math.cos(u)
        y = math.sin(u) * (15 * math.cos(v) - 5 * math.cos(2 * v) - 2 * math.cos(3 * v) - math.cos(4 * v))
        return (x / 16.0, y / 16.0, z / 16.0)
    return sample_surface(f, 50, 100, (0.0, math.pi), (0.0, 2 * math.pi), per_point=False)


def petal_local(L: float, W: float, curl: float):
    """One petal in its local frame: length along +x, width along y, curl in z."""
    def f(s, w):
        x = s * L
        y = w * W * math.sin(math.pi * min(1.0, s ** 0.75))
        # cupped across the width; tips curl back once the petal is long enough
        z = curl * s * s - 0.5 * curl * max(0.0, s - 0.6) ** 2 * 4 + 0.45 * W * w * w
        return (x, y, z)
    return f


class FlowerMesh:
    """Petal geometry stays in petal-local space; each frame we rebuild only
    the per-petal matrices (petal angle x opening tilt x global spin)."""

    def __init__(self, outer: int = 8, inner: int = 5):
        self.rings = []
        outer_geo = sample_surface(petal_local(1.0, 0.27, 0.3), 26, 12, (0.0, 1.0), (-1.0, 1.0), tag=0)
        inner_geo = sample_surface(petal_local(0.6, 0.24, 0.35), 18, 10, (0.0, 1.0), (-1.0, 1.0), tag=1)
        self.rings.append((outer, outer_geo, 0.0, 1.0))
        self.rings.append((inner, inner_geo, math.pi / inner, 0.55))
        # centre dome
        def dome(u, v):
            r = 0.2
            return (r * math.sin(u) * math.cos(v), r * math.sin(u) * math.sin(v), 0.12 + r * 0.6 * math.cos(u))
        self.center = sample_surface(dome, 10, 24, (0.0, math.pi / 2), (0.0, 2 * math.pi), tag=2)


def rot_matrix(yaw: float, pitch: float, roll: float = 0.0):
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    # R = Rx(pitch) * Ry(yaw) * Rz(roll)
    ry = ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))
    rx = ((1, 0, 0), (0, cp, -sp), (0, sp, cp))
    rz = ((cr, -sr, 0), (sr, cr, 0), (0, 0, 1))
    return _mm(rx, _mm(ry, rz))


def _mm(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _mv(m, v):
    return (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2])


def render_points(cv: Canvas, items, cx: float, cy: float, size: float,
                  colors: Sequence[RGB], alpha: float = 1.0, light: Vec = (-0.4, 0.6, -0.7),
                  stride: int = 1, two_sided: bool = False) -> None:
    """``items``: iterable of (rotated_point, rotated_normal, tag, s, edge).

    ``tag`` selects the colour (0 outer petals, 1 inner petals, 2 centre),
    ``s`` runs base->tip, ``edge`` centre-line->side (used to ink petal rims).

    ``size`` is the radius in rows; x is doubled for cell aspect.
    The camera sits at -z (smaller z = closer); ``light`` points *toward* the
    light (upper-left-front). ``two_sided`` lights thin surfaces like petals
    from whichever side faces the light.
    """
    L = _norm(light)
    zbuf = {}
    ramp_n = len(LUMA) - 1
    for idx, (p, n, tag, s, e) in enumerate(items):
        if stride > 1 and idx % stride:
            continue
        persp = 1.0 / (1.0 + p[2] * 0.35)
        sx = int(round(cx + p[0] * size * 2.0 * persp))
        sy = int(round(cy - p[1] * size * persp))
        lum = n[0] * L[0] + n[1] * L[1] + n[2] * L[2]
        if two_sided and tag != 2:
            lum = abs(lum) * 0.92
        rec = (p[2], lum, tag, s, e)
        # splat each point over two cells: cells are tall, so sparse sampling
        # leaves horizontal gaps that would let back faces show through
        for kx, bias in ((sx, 0.0), (sx + 1, 0.04)):
            prev = zbuf.get((kx, sy))
            if prev is None or prev[0] > p[2] + bias:
                zbuf[(kx, sy)] = rec if bias == 0.0 else (p[2] + bias,) + rec[1:]
    for (sx, sy), (z, lum, tag, s, e) in zbuf.items():
        k = max(0.0, min(1.0, (lum + 1.0) * 0.5))
        k = k ** 1.4
        alt = tag >= 3
        tag = tag - 3 if alt else tag
        base = colors[min(tag, len(colors) - 1)]
        if alt:
            base = scale(base, 0.82)
        if tag < 2:
            k *= 1.0 - 0.45 * max(0.0, e - 0.7) / 0.3  # inked petal rims
            k *= 0.55 + 0.45 * min(1.0, s * 3)  # petals darken into the throat
        col = mix(scale(base, 0.3 + 0.9 * k), (255, 255, 255), max(0.0, k - 0.85) * 2)
        if tag == 0 and len(colors) > 3:
            col = mix(col, scale(colors[3], 0.3 + k), s * 0.5)  # petal tips lighter
        ch = LUMA[int(k * ramp_n)]
        cv.put(sx, sy, ch, col, bg=scale(base, 0.12 + 0.45 * k), bold=k > 0.7, alpha=alpha)


def heart_items(mesh, yaw: float, pitch: float, beat: float):
    (a, b, c), (d, e_, f), (g, h, i) = rot_matrix(yaw, pitch)
    sc = 1.0 + 0.12 * beat
    for p, n, tag, s, e in mesh:  # matrix product inlined: this is the hot loop
        x, y, z = p[0] * sc, p[1] * sc, p[2] * sc
        yield ((a * x + b * y + c * z, d * x + e_ * y + f * z, g * x + h * y + i * z),
               (a * n[0] + b * n[1] + c * n[2], d * n[0] + e_ * n[1] + f * n[2],
                g * n[0] + h * n[1] + i * n[2]), tag, s, e)


def flower_items(fm: FlowerMesh, bloom: float, yaw: float, pitch: float, t: float):
    g = rot_matrix(yaw, pitch, 0.0)
    for count, geo, offset, lift in fm.rings:
        # closed bud: petals stand up (tilt ~ 80 deg); open: lie back (~12 deg)
        tilt = math.radians(80 - 68 * bloom * (1.0 if lift > 0.9 else 0.75))
        for i in range(count):
            ang = offset + 2 * math.pi * i / count + math.sin(t * 0.8 + i) * 0.03
            ca, sa = math.cos(ang), math.sin(ang)
            ct, st = math.cos(tilt), math.sin(tilt)
            # local (x along petal) -> tilt up around local y -> spin around flower axis (z)
            tl = ((ct, 0, -st), (0, 1, 0), (st, 0, ct))
            rz = ((ca, -sa, 0), (sa, ca, 0), (0, 0, 1))
            m = _mm(g, _mm(_flip, _mm(rz, tl)))
            for p, n, tag, s, e in geo:
                # odd petals carry tag+3 so the renderer can tint alternate petals
                yield (_mv(m, p), _mv(m, n), tag + 3 * (i % 2), s, e)
    mc = _mm(g, _flip)
    for p, n, tag, s, e in fm.center:
        yield (_mv(mc, p), _mv(mc, n), tag, s, e)


# flower axis is local +z; flip so it points at the camera (-z) and petals open toward us
_flip = ((1, 0, 0), (0, 1, 0), (0, 0, -1))
