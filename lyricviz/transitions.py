"""Scene transitions: blend the outgoing frame ``a`` into the incoming ``b``.

Each transition is a per-cell mask ``m(x, y)`` in [0, 1]; a cell shows ``b``
once progress passes its mask value. Cells right at the boundary get a
glowing edge glyph so the change reads as an effect, not a cut.
"""
from __future__ import annotations

import math
from typing import Callable, Dict

from .canvas import Canvas
from .color import RGB, mix, scale
from .fx import ease_in_out, hash01

MaskFn = Callable[[int, int, int, int], float]


def _dissolve(x, y, w, h):
    return hash01(x, y, 77)


def _wipe(x, y, w, h):
    return (x / max(1, w)) * 0.85 + (y / max(1, h)) * 0.15


def _wipe_left(x, y, w, h):
    return 1.0 - _wipe(x, y, w, h)


def _bloom(x, y, w, h):
    dx, dy = (x - w / 2) / (w / 2), (y - h / 2) / (h / 2) * 1.1
    r = math.sqrt(dx * dx + dy * dy) / 1.5
    ang = math.atan2(dy, dx)
    return min(1.0, r * (0.88 + 0.12 * math.cos(ang * 5)))  # petal-shaped iris


def _petal_rain(x, y, w, h):
    return min(1.0, (y / max(1, h)) * 0.75 + hash01(x, 3, 11) * 0.25)


MASKS: Dict[str, MaskFn] = {
    "dissolve": _dissolve,
    "wipe": _wipe,
    "wipe_left": _wipe_left,
    "bloom": _bloom,
    "petal_rain": _petal_rain,
}

_MASK_CACHE: Dict[tuple, list] = {}


def _mask_grid(kind: str, w: int, h: int) -> list:
    """Masks only depend on the screen size: compute once per resize."""
    key = (kind, w, h)
    grid = _MASK_CACHE.get(key)
    if grid is None:
        fn = MASKS.get(kind, _dissolve)
        grid = [[fn(x, y, w, h) for x in range(w)] for y in range(h)]
        if len(_MASK_CACHE) > 16:
            _MASK_CACHE.clear()
        _MASK_CACHE[key] = grid
    return grid


EDGE_U = ("✿", "❀", "·", "✦")
EDGE_A = ("*", "@", ".", "+")


def blend(a: Canvas, b: Canvas, out: Canvas, kind: str, p: float, edge: RGB, unicode: bool) -> None:
    p = ease_in_out(p)
    if kind == "fade":  # through black
        src, k = (a, 1 - p * 2) if p < 0.5 else (b, p * 2 - 1)
        for y in range(out.h):
            out.ch[y] = src.ch[y][:]
            out.bold[y] = src.bold[y][:]
            out.fg[y] = [scale(c, k) for c in src.fg[y]]
            out.bg[y] = [scale(c, k) for c in src.bg[y]]
        return
    if kind == "flash":  # through white light
        src = a if p < 0.5 else b
        k = 1 - abs(p - 0.5) * 2
        white = (255, 245, 250)
        for y in range(out.h):
            out.ch[y] = src.ch[y][:]
            out.bold[y] = src.bold[y][:]
            out.fg[y] = [mix(c, white, k) for c in src.fg[y]]
            out.bg[y] = [mix(c, white, k * 0.85) for c in src.bg[y]]
        return
    grid = _mask_grid(kind, out.w, out.h)
    band = 0.06
    glyphs = EDGE_U if unicode else EDGE_A
    # stretch so p=0 shows all of a and p=1 all of b despite the edge band
    q = p * (1 + 2 * band) - band
    w, h = out.w, out.h
    for y in range(h):
        ach, afg, abg, abo = a.ch[y], a.fg[y], a.bg[y], a.bold[y]
        bch, bfg, bbg, bbo = b.ch[y], b.fg[y], b.bg[y], b.bold[y]
        och, ofg, obg, obo = out.ch[y], out.fg[y], out.bg[y], out.bold[y]
        mrow = grid[y]
        for x in range(w):
            d = q - mrow[x]
            if d >= band:
                och[x], ofg[x], obg[x], obo[x] = bch[x], bfg[x], bbg[x], bbo[x]
            elif d <= -band:
                och[x], ofg[x], obg[x], obo[x] = ach[x], afg[x], abg[x], abo[x]
            else:
                k = (d + band) / (2 * band)
                och[x] = glyphs[int(hash01(x, y) * len(glyphs))]
                ofg[x] = mix(edge, (255, 255, 255), 1 - abs(k - 0.5) * 2)
                obg[x] = mix(abg[x], bbg[x], k)
                obo[x] = True
