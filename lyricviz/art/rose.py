"""Spiral rose: concentric petal edges drawn with direction-aware line glyphs.

Every cell inside the rose computes its position on an Archimedean spiral.
Cells near a spiral turn become petal edges (glyph chosen from the spiral's
local tangent: ``- / | \\``), cells between turns are petal surfaces shaded
from bright (just past an edge, where the petal curls toward the light) to
deep (where it tucks under the next petal). Outer cupped petals wrap it.
"""
from __future__ import annotations

import math

from ..canvas import Canvas
from ..color import RGB, mix, scale
from ..fx import ease_out, slope_glyph


def draw_rose(cv: Canvas, cx: float, cy: float, R: float, bloom: float, t: float,
              deep: RGB = (150, 10, 50), light: RGB = (255, 120, 150),
              alpha: float = 1.0, spin: float = 0.25, unicode: bool = True) -> None:
    if R < 1 or alpha <= 0:
        return
    b = ease_out(bloom)
    Rr = R * (0.35 + 0.65 * b)
    turns = 2.2 + 2.0 * b
    outer = Rr * 1.32
    rot = t * spin
    fill = "·:;=+*%#" if unicode else ".:;=+*%#"
    for y in range(max(0, int(cy - outer) - 1), min(cv.h, int(cy + outer) + 2)):
        dy = (y - cy) * 1.22  # a rose head is a cup: wider than it is tall
        for x in range(max(0, int(cx - outer * 2) - 1), min(cv.w, int(cx + outer * 2) + 2)):
            dx = (x - cx) / 2.0
            r = math.hypot(dx, dy)
            ang = math.atan2(dy, dx)
            # wobbly outline so it reads as petals, not a disc
            rim = Rr * (1.0 + 0.09 * math.sin(5 * ang + rot * 0.6) + 0.04 * math.sin(9 * ang))
            if r <= rim:
                s = (r / Rr) * turns - (ang + rot) / (2 * math.pi)
                fr = s - math.floor(s)
                depth = r / Rr
                if fr < 0.16 + 0.06 * depth:
                    # petal edge: tangent of the spiral at this point
                    tx, ty = -math.sin(ang), math.cos(ang)
                    pitch = 1.0 / (turns * 2 * math.pi) * Rr
                    gx, gy = tx * r + math.cos(ang) * pitch, ty * r + math.sin(ang) * pitch
                    ch = slope_glyph(gx * 2, gy)
                    if ch == "-":
                        ch = "~" if depth > 0.4 else "-"
                    # bright curled lip of a petal over the shadow of the next
                    col = mix(light, (255, 235, 240), 0.35 * depth)
                    cv.put(x, y, ch, col, bg=scale(deep, 0.75 + 0.3 * depth), bold=True, alpha=alpha)
                else:
                    lit = (1.0 - fr) ** 1.5  # bright just after the edge
                    lit *= 0.45 + 0.55 * depth  # the heart of the rose is in shadow
                    lit += 0.15 * (-(dx * -0.55 + dy * -0.83) / (r + 0.5))
                    lit = max(0.05, min(1.0, lit))
                    body = mix(scale(deep, 0.6), light, lit * 0.75)
                    ch = fill[int(lit * 3)] if lit < 0.35 else " "
                    cv.put(x, y, ch, scale(deep, 0.5), bg=body, alpha=alpha)
            elif r <= outer * (0.86 + 0.14 * abs(math.cos(2.5 * (ang - rot * 0.3)))) and b > 0.2:
                # outer cupped petals, lighter and translucent
                u = (r - rim) / max(0.5, outer - rim)
                lit = 0.85 - 0.6 * u
                col = mix(light, (255, 220, 230), 0.25 * (1 - u))
                ch = ")" if dx > 0 else "("
                if abs(dy) > abs(dx) * 0.9:
                    ch = "_" if dy > 0 else "-"
                if u > 0.75:
                    ch = "'" if dy < 0 else "."
                cv.put(x, y, ch, scale(col, 0.6 + 0.5 * lit),
                       bg=mix(cv.get_bg(x, y), scale(mix(deep, light, 0.6), 0.45 + 0.35 * lit), 0.85 * b),
                       alpha=alpha * b)
