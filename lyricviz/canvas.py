"""Cell buffer that every layer paints into (painter's algorithm, back to front).

Each cell stores a glyph, a foreground colour, a background colour and a bold
flag. Layers never touch the terminal: the renderer turns a finished canvas
into ANSI in one write, which is what keeps the animation flicker free.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from .color import BLACK, RGB, WHITE, gradient, mix, scale


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2.0

    @property
    def cy(self) -> float:
        return self.y + self.h / 2.0

    def point(self, fx: float, fy: float) -> tuple:
        return (self.x + fx * self.w, self.y + fy * self.h)

    def sub(self, fx: float, fy: float, fw: float, fh: float) -> "Rect":
        return Rect(
            int(round(self.x + fx * self.w)),
            int(round(self.y + fy * self.h)),
            max(1, int(round(fw * self.w))),
            max(1, int(round(fh * self.h))),
        )

    def inset(self, dx: int, dy: int) -> "Rect":
        return Rect(self.x + dx, self.y + dy, max(1, self.w - 2 * dx), max(1, self.h - 2 * dy))

    def contains(self, x: float, y: float) -> bool:
        return self.x <= x < self.x2 and self.y <= y < self.y2


class Canvas:
    __slots__ = ("w", "h", "ch", "fg", "bg", "bold")

    def __init__(self, w: int, h: int, bg: RGB = BLACK):
        self.w = w
        self.h = h
        self.ch: List[List[str]] = [[" "] * w for _ in range(h)]
        self.fg: List[List[RGB]] = [[WHITE] * w for _ in range(h)]
        self.bg: List[List[RGB]] = [[bg] * w for _ in range(h)]
        self.bold: List[List[bool]] = [[False] * w for _ in range(h)]

    @property
    def rect(self) -> Rect:
        return Rect(0, 0, self.w, self.h)

    # ------------------------------------------------------------------ fills
    def clear(self, bg: RGB = BLACK) -> None:
        w = self.w
        for y in range(self.h):
            self.ch[y] = [" "] * w
            self.fg[y] = [WHITE] * w
            self.bg[y] = [bg] * w
            self.bold[y] = [False] * w

    def fill_vertical(self, stops: Sequence[RGB], y0: int = 0, y1: Optional[int] = None) -> None:
        """Vertical sky gradient; also wipes glyphs (it is a background)."""
        y1 = self.h if y1 is None else y1
        span = max(1, y1 - y0 - 1)
        w = self.w
        for y in range(max(0, y0), min(self.h, y1)):
            c = gradient(stops, (y - y0) / span)
            self.ch[y] = [" "] * w
            self.fg[y] = [WHITE] * w
            self.bg[y] = [c] * w
            self.bold[y] = [False] * w

    def copy_from(self, other: "Canvas") -> None:
        for y in range(self.h):
            self.ch[y] = other.ch[y][:]
            self.fg[y] = other.fg[y][:]
            self.bg[y] = other.bg[y][:]
            self.bold[y] = other.bold[y][:]

    # ---------------------------------------------------------------- drawing
    def put(self, x, y, ch: str, fg: RGB = WHITE, bg: Optional[RGB] = None,
            bold: bool = False, alpha: float = 1.0) -> None:
        """Draw one glyph. ``bg=None`` keeps whatever is behind (transparent).

        ``alpha`` < 1 blends the foreground into the existing background, so a
        glyph can fade in/out without a separate compositing pass.
        """
        xi = int(x)
        yi = int(y)
        if xi < 0 or yi < 0 or xi >= self.w or yi >= self.h or alpha <= 0.02:
            return
        row_bg = self.bg[yi]
        if bg is not None:
            if alpha < 1.0:
                bg = mix(row_bg[xi], bg, alpha)
            row_bg[xi] = bg
        if alpha < 1.0:
            fg = mix(row_bg[xi], fg, alpha)
        self.ch[yi][xi] = ch
        self.fg[yi][xi] = fg
        self.bold[yi][xi] = bold

    def text(self, x, y, s: str, fg: RGB = WHITE, bg: Optional[RGB] = None,
             bold: bool = False, alpha: float = 1.0) -> None:
        xi = int(x)
        for i, c in enumerate(s):
            if c != " ":
                self.put(xi + i, y, c, fg, bg, bold, alpha)

    def get_bg(self, x: int, y: int) -> RGB:
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.bg[y][x]
        return BLACK

    def set_bg(self, x: int, y: int, c: RGB) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.bg[y][x] = c

    def tint(self, x: int, y: int, c: RGB, amount: float) -> None:
        """Blend background (and glyph colour) toward ``c``."""
        if 0 <= x < self.w and 0 <= y < self.h and amount > 0.004:
            self.bg[y][x] = mix(self.bg[y][x], c, amount)
            self.fg[y][x] = mix(self.fg[y][x], c, amount * 0.5)

    def glow(self, cx: float, cy: float, radius: float, c: RGB, strength: float) -> None:
        """Soft radial light in the background (aspect corrected: cells are ~2:1)."""
        if strength <= 0 or radius <= 0:
            return
        ry = radius / 2.0
        x0, x1 = int(cx - radius) - 1, int(cx + radius) + 2
        y0, y1 = int(cy - ry) - 1, int(cy + ry) + 2
        inv = 1.0 / radius
        for y in range(max(0, y0), min(self.h, y1)):
            dy = (y - cy) * 2.0
            rowb = self.bg[y]
            for x in range(max(0, x0), min(self.w, x1)):
                dx = x - cx
                d = math.sqrt(dx * dx + dy * dy) * inv
                if d < 1.0:
                    k = (1.0 - d) * (1.0 - d) * strength
                    rowb[x] = mix(rowb[x], c, k)

    def darken_rect(self, r: Rect, k: float, feather: int = 2) -> None:
        """Frosted-glass panel: dims the backdrop, softly feathered at edges."""
        for y in range(max(0, r.y - feather), min(self.h, r.y2 + feather)):
            dy = max(r.y - y, y - (r.y2 - 1), 0)
            for x in range(max(0, r.x - feather * 2), min(self.w, r.x2 + feather * 2)):
                dx = max(r.x - x, x - (r.x2 - 1), 0) / 2.0
                d = max(dx, dy)
                f = 1.0 if d <= 0 else max(0.0, 1.0 - d / (feather + 1))
                if f > 0:
                    m = 1.0 - k * f
                    c = self.bg[y][x]
                    self.bg[y][x] = (int(c[0] * m), int(c[1] * m), int(c[2] * m))
                    m = 1.0 - k * f * 0.6
                    c = self.fg[y][x]
                    self.fg[y][x] = (int(c[0] * m), int(c[1] * m), int(c[2] * m))

    def blit(self, sprite: "Sprite", x, y, palette: Dict[str, RGB], alpha: float = 1.0,
             bold_keys: str = "", default: RGB = WHITE, frame: int = 0,
             recolor: Optional[Callable[[int, int, RGB], RGB]] = None) -> None:
        rows = sprite.frames[frame % len(sprite.frames)]
        mask = sprite.masks[frame % len(sprite.masks)] if sprite.masks else None
        xi, yi = int(round(x)), int(round(y))
        for j, line in enumerate(rows):
            mrow = mask[j] if mask is not None and j < len(mask) else ""
            for i, c in enumerate(line):
                if c == " " or c == sprite.transparent:
                    continue
                k = mrow[i] if i < len(mrow) else " "
                col = palette.get(k, default)
                if recolor is not None:
                    col = recolor(i, j, col)
                if c == sprite.solid:
                    self.put(xi + i, yi + j, " ", col, bg=col, alpha=alpha)
                else:
                    self.put(xi + i, yi + j, c, col, bold=k in bold_keys, alpha=alpha)


class Sprite:
    """Multi-frame ASCII art with an optional parallel colour-key mask.

    ``transparent`` glyphs are skipped; ``solid`` glyphs paint a background
    block (handy for silhouettes that should occlude what is behind them).
    """

    def __init__(self, frames: Sequence[str], masks: Optional[Sequence[str]] = None,
                 transparent: str = "`", solid: str = "\0"):
        self.frames = [self._lines(f) for f in frames]
        self.masks = [self._lines(m) for m in masks] if masks else []
        self.transparent = transparent
        self.solid = solid
        self.w = max(len(l) for f in self.frames for l in f)
        self.h = max(len(f) for f in self.frames)

    @staticmethod
    def _lines(s: str) -> List[str]:
        lines = s.split("\n")
        if lines and lines[0].strip() == "":
            lines = lines[1:]
        if lines and lines[-1].strip() == "":
            lines = lines[:-1]
        return lines
