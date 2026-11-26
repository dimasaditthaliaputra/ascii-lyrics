"""Procedural flowers drawn cell by cell.

Flower heads are evaluated in polar coordinates (aspect corrected because a
terminal cell is roughly twice as tall as it is wide). Petal shading uses a
fake surface normal - petals cup toward the viewer in the middle and fall
away at the tips - lit from the upper left, then mapped onto a character
density ramp. That is what gives the heads their pseudo-3D volume.
"""
from __future__ import annotations

import math
from typing import Sequence

from ..canvas import Canvas
from ..color import RGB, mix, scale
from ..fx import ease_out, hash01, slope_glyph

PETAL_RAMP = ".:-=+*#%@"
PETAL_RAMP_U = "·:-=+*#%@"
LIGHT = (-0.55, -0.83)  # from upper left, normalised


def draw_head(cv: Canvas, cx: float, cy: float, radius: float, bloom: float, t: float,
              petals: int = 6, rot: float = 0.0, base: RGB = (255, 120, 170),
              tip: RGB = (255, 210, 230), center: RGB = (255, 210, 110),
              alpha: float = 1.0, unicode: bool = True, sharp: float = 1.6,
              seed: int = 0) -> None:
    """One flower head. ``bloom`` 0 = tight bud, 1 = fully open."""
    if radius < 0.6 or alpha <= 0:
        return
    b = max(0.0, min(1.25, bloom))
    eb = ease_out(min(1.0, b))
    L = radius * (0.28 + 0.72 * min(1.15, b))  # petal reach
    if L < 2.6:
        # too small for per-cell shading: use a hand-placed glyph blossom
        _mini_head(cv, cx, cy, b, rot, base, tip, center, alpha, unicode)
        return
    ramp = PETAL_RAMP_U if unicode else PETAL_RAMP
    rc = L * (0.1 + 0.18 * eb)  # centre disc radius
    x0, x1 = int(cx - L * 2) - 1, int(cx + L * 2) + 2
    y0, y1 = int(cy - L) - 1, int(cy + L) + 2
    for y in range(max(0, y0), min(cv.h, y1)):
        dy = (y - cy)
        for x in range(max(0, x0), min(cv.w, x1)):
            dx = (x - cx) / 2.0
            r = math.sqrt(dx * dx + dy * dy)
            if r > L + 0.5:
                continue
            ang = math.atan2(dy, dx)
            # Petal profile: closed bud = round blob, open = distinct petals.
            f = abs(math.cos(petals * (ang - rot) / 2.0)) ** sharp
            f = (1 - eb) + eb * f
            edge = L * (0.3 + 0.7 * f)
            if r > edge:
                continue
            u = r / max(0.01, edge)  # 0 centre .. 1 tip
            if r < rc and b > 0.35:
                # seeded centre: alternating textured dots
                k = hash01(x, y, seed)
                ch = "@" if k > 0.55 else ("o" if k > 0.25 else ("°" if unicode else "*"))
                lit = 0.75 + 0.25 * (-(dx * LIGHT[0] + dy * LIGHT[1]) / (rc + 0.01))
                cv.put(x, y, ch, scale(center, lit), bg=scale(center, 0.35 * alpha + 0.05),
                       bold=True, alpha=alpha)
                continue
            # fake normal: cup in the middle, tilt outward toward the tip
            nx, ny = (dx / (r + 1e-6)) * u, (dy / (r + 1e-6)) * u
            lit = 0.55 - 0.45 * (nx * LIGHT[0] + ny * LIGHT[1])
            lit *= 0.65 + 0.35 * f  # crease between petals is darker
            lit *= 1.0 - 0.35 * max(0.0, u - 0.82) / 0.18  # rim falloff
            lit = max(0.05, min(1.0, lit))
            col = mix(base, tip, (u ** 2) * 0.55)
            if b < 0.35:
                col = mix((90, 160, 90), col, b / 0.35)  # green bud blushing pink
            # colour carries the form; glyphs only trace veins, shading and rims
            bgc = scale(col, 0.42 + 0.62 * lit)
            if u > 0.88:
                ch, fg = ("'" if dy < 0 else "."), scale(col, 1.25)
            elif f > 0.9 and u > 0.3:
                ch, fg = slope_glyph(dx * 2, dy), mix(bgc, (255, 255, 255), 0.35)  # mid vein
            elif lit < 0.4:
                ch, fg = ramp[1 + int(lit * 4)], scale(col, 0.3)  # shadowed crease
            else:
                ch, fg = " ", bgc
            cv.put(x, y, ch, fg, bg=mix(cv.get_bg(x, y), bgc, 0.95 * alpha), alpha=alpha)


def _mini_head(cv: Canvas, cx: float, cy: float, b: float, rot: float, base: RGB, tip: RGB,
               center: RGB, alpha: float, unicode: bool) -> None:
    """Glyph blossom for small flowers: bud -> half open -> five-petal star."""
    x, y = int(round(cx)), int(round(cy))
    bud = mix((90, 160, 90), base, min(1.0, b / 0.35))
    if b < 0.3:
        cv.put(x, y, "•" if unicode else "o", bud, bold=True, alpha=alpha)
        cv.put(x, y + 1, "v", (80, 150, 85), alpha=alpha)
        return
    if b < 0.65:
        cv.put(x - 1, y, "(", base, alpha=alpha)
        cv.put(x, y, "❀" if unicode else "@", tip, bold=True, alpha=alpha)
        cv.put(x + 1, y, ")", base, alpha=alpha)
        return
    petal = ("❀", "✿") if unicode else ("@", "*")
    k = int(rot * 0.6) % 2  # petals twinkle between two glyphs as the head turns
    for dx, dy, g in ((-2, 0, 0), (2, 0, 0), (-1, -1, 1), (1, -1, 1), (0, 1, 1)):
        cv.put(x + dx, y + dy, petal[(g + k) % 2], mix(base, tip, 0.3 + 0.3 * (dy < 0)),
               bold=True, alpha=alpha)
    for dx in (-1, 1):
        cv.put(x + dx, y, "-" if dx < 0 else "-", scale(base, 0.8), alpha=alpha)
    cv.put(x, y, "@" if b > 0.9 else "o", center, bg=scale(center, 0.4), bold=True, alpha=alpha)
    cv.glow(x, y, 4, base, 0.18 * alpha)


def stem_points(x0: float, y0: float, height: float, lean: float, sway: float,
                steps: int = 0):
    """Quadratic bezier from the ground up; returns list of (x, y)."""
    steps = steps or max(2, int(height * 1.5))
    tx, ty = x0 + lean + sway, y0 - height
    cxp, cyp = x0 + lean * 0.2 - sway * 0.4, y0 - height * 0.55
    pts = []
    for i in range(steps + 1):
        s = i / steps
        a, b_, c = (1 - s) ** 2, 2 * (1 - s) * s, s * s
        pts.append((a * x0 + b_ * cxp + c * tx, a * y0 + b_ * cyp + c * ty))
    return pts


def draw_stem(cv: Canvas, pts, col: RGB, alpha: float = 1.0) -> None:
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        ch = slope_glyph(xb - xa, yb - ya)
        if ch == "-":
            ch = "~"
        cv.put(round(xb), round(yb), ch, col, alpha=alpha)


def draw_leaf(cv: Canvas, x: float, y: float, side: int, size: float, col: RGB,
              t: float, alpha: float = 1.0, unicode: bool = True) -> None:
    """Lens-shaped shaded leaf with a midrib; ``side`` -1 left, +1 right."""
    length = max(2.0, size)
    flap = math.sin(t * 1.6 + x * 0.3) * 0.25
    # leaf axis in visual space (x cells, y rows*2), pointing outward and up
    ax, ay = side * 1.0, -(0.55 + flap)
    n = math.hypot(ax, ay)
    ax, ay = ax / n, ay / n
    width = length * 0.32
    x0, x1 = int(x - length * 2) - 1, int(x + length * 2) + 2
    y0, y1 = int(y - length) - 1, int(y + length) + 1
    for yy in range(max(0, y0), min(cv.h, y1)):
        for xx in range(max(0, x0), min(cv.w, x1)):
            vx, vy = (xx - x), (yy - y) * 2.0
            s = vx * ax + vy * ay  # along
            q = -vx * ay + vy * ax  # across
            if s <= 0.3 or s >= length * 2:
                continue
            half = width * 2 * math.sin(math.pi * s / (length * 2))
            if abs(q) > half:
                continue
            k = abs(q) / max(0.01, half)
            # solid colour body (lit upper half), midrib line, soft rim
            shade = 0.9 - 0.4 * k + (0.18 if q < 0 else -0.12)
            body = scale(col, shade * 0.75)
            if k < 0.25:
                ch = slope_glyph(ax, ay / 2.0)
            elif k > 0.8:
                ch = "'" if q < 0 else "."
            else:
                ch = " "
            cv.put(xx, yy, ch, scale(col, shade + 0.35), bg=mix(cv.get_bg(xx, yy), body, 0.9 * alpha),
                   alpha=alpha)


def draw_flower(cv: Canvas, gx: float, gy: float, height: float, head_r: float, bloom: float,
                grow: float, t: float, phase: float, colors: Sequence[RGB], stem: RGB, leaf: RGB,
                center: RGB, petals: int = 6, sway_amp: float = 1.0, alpha: float = 1.0,
                unicode: bool = True, seed: int = 0, spin: float = 0.15) -> None:
    """Full flower: swaying stem, two leaves, head. ``grow`` 0..1 stem height."""
    if grow <= 0.01:
        return
    h = height * ease_out(grow)
    sway = math.sin(t * 1.1 + phase) * sway_amp * (h / max(1.0, height)) * 1.6
    lean = math.sin(phase * 3.1) * height * 0.25
    pts = stem_points(gx, gy, h, lean, sway)
    draw_stem(cv, pts, stem, alpha)
    if h > 4:
        lx, ly = pts[len(pts) // 3]
        draw_leaf(cv, lx, ly, -1, min(4.0, 1.5 + h * 0.15), leaf, t + phase, alpha, unicode)
        lx, ly = pts[len(pts) // 2]
        draw_leaf(cv, lx, ly, 1, min(3.5, 1.2 + h * 0.12), leaf, t + phase + 1, alpha, unicode)
    hx, hy = pts[-1]
    base = colors[0]
    tip = colors[1] if len(colors) > 1 else mix(base, (255, 255, 255), 0.6)
    draw_head(cv, hx, hy, head_r * min(1.0, 0.4 + grow), bloom, t, petals,
              rot=t * spin + phase, base=base, tip=tip, center=center, alpha=alpha,
              unicode=unicode, seed=seed)
