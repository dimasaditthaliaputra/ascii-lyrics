"""Album artwork -> terminal cells, and the ``artwork`` layer.

Conversion (Pillow): fit to the cell grid with the ~2:1 cell aspect, auto
contrast + unsharp mask to keep composition and edges readable, then map
luminance onto a glyph ramp and keep the pixel colour. Three styles:

``ascii``   classic density ramp (pure ASCII glyphs)
``blocks``  half-block ``▀`` with fg=top pixel, bg=bottom pixel (2x vertical detail)
``floral``  the artwork re-drawn with flower glyphs (used for the chorus)

Results are cached per size, so the per-frame cost is just copying cells.
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

from .art.rose import draw_rose
from .canvas import Canvas, Rect
from .color import RGB, mix, scale
from .fx import ease_out, hash01
from .layers.base import Layer, register

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
except ImportError:  # pragma: no cover - Pillow is optional
    Image = None

ASCII_RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
FLORAL_RAMP_U = " ·.:•*✿❀❁@"
FLORAL_RAMP_A = " ..:o*%&@@"

Cell = Tuple[str, RGB, RGB]


def make_sample_artwork(size: int = 512):
    """An original stand-in cover: a rose at dusk, petals in the air.

    Generated so the project ships with something to convert; point
    ``artwork.image`` in the song config at your own copy of the real cover.
    """
    if Image is None:
        return None
    W = H = size
    img = Image.new("RGB", (W, H))
    px = img.load()
    top, mid, bot = (24, 8, 30), (110, 32, 72), (238, 150, 160)
    for y in range(H):
        k = y / (H - 1)
        c = mix(top, mid, k / 0.6) if k < 0.6 else mix(mid, bot, (k - 0.6) / 0.4)
        for x in range(W):
            px[x, y] = c
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W * 0.18, H * 0.16, W * 0.82, H * 0.8], fill=(255, 120, 170))
    glow = glow.filter(ImageFilter.GaussianBlur(size // 8))
    img = Image.blend(img, glow, 0.35)
    d = ImageDraw.Draw(img)
    cx, cy, R = W * 0.5, H * 0.46, W * 0.24
    # stem + leaves
    d.line([(cx, cy + R * 0.8), (cx - W * 0.04, H * 0.98)], fill=(46, 110, 64), width=size // 48)
    d.ellipse([cx - W * 0.2, H * 0.72, cx - W * 0.03, H * 0.8], fill=(58, 138, 78))
    d.ellipse([cx + W * 0.0, H * 0.8, cx + W * 0.17, H * 0.87], fill=(50, 124, 70))
    # outer petals
    for i in range(7):
        a = i / 7 * math.tau
        ex, ey = cx + math.cos(a) * R * 0.55, cy + math.sin(a) * R * 0.5
        d.ellipse([ex - R * 0.62, ey - R * 0.52, ex + R * 0.62, ey + R * 0.52], fill=(205, 40, 85),
                  outline=(120, 10, 45), width=3)
    d.ellipse([cx - R * 0.95, cy - R * 0.85, cx + R * 0.95, cy + R * 0.85], fill=(225, 60, 105))
    # spiral heart of the rose
    for k in range(9, 0, -1):
        r = R * k / 10
        start = k * 47
        d.arc([cx - r, cy - r * 0.9, cx + r, cy + r * 0.9], start, start + 250,
              fill=(110 + k * 8, 8, 40), width=max(2, size // 90))
    # falling petals
    for i in range(26):
        x, y = hash01(i, 1) * W, hash01(i, 2) * H
        s = 6 + hash01(i, 3) * size * 0.03
        d.ellipse([x, y, x + s * 1.6, y + s], fill=(255, 170 + int(hash01(i, 4) * 60), 200))
    # vignette
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-W * 0.15, -H * 0.15, W * 1.15, H * 1.15], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(size // 6))
    img = Image.composite(img, Image.new("RGB", (W, H), (8, 2, 10)), vig)
    return img


class ArtworkSource:
    def __init__(self, path: Optional[Path], contrast: float = 1.35, saturation: float = 1.25):
        self.path = path
        self.contrast = contrast
        self.saturation = saturation
        self.image = None
        self.error: Optional[str] = None
        if Image is None:
            self.error = "Pillow not installed - using procedural artwork"
            return
        try:
            if path is not None and path.exists():
                self.image = Image.open(path).convert("RGB")
            else:
                if path is not None:
                    self.error = f"artwork {path} not found - using generated sample"
                self.image = make_sample_artwork(384)
        except Exception as e:  # unreadable file: fall back but tell the user
            self.error = f"could not read artwork ({e}) - using generated sample"
            self.image = make_sample_artwork(384)

    @property
    def available(self) -> bool:
        return self.image is not None

    def fit(self, max_cols: int, max_rows: int) -> Tuple[int, int]:
        """Largest cell size with the image's aspect (cells are ~2:1)."""
        w, h = self.image.size
        cols = max_cols
        rows = int(cols * h / w * 0.5)
        if rows > max_rows:
            rows = max_rows
            cols = int(rows * w / h * 2.0)
        return max(2, cols), max(2, rows)

    def cells(self, cols: int, rows: int, mode: str, unicode: bool) -> List[List[Cell]]:
        return _convert(id(self), self, cols, rows, mode, unicode)


@lru_cache(maxsize=48)
def _convert(_key, src: ArtworkSource, cols: int, rows: int, mode: str, unicode: bool):
    img = src.image
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Contrast(img).enhance(src.contrast)
    img = ImageEnhance.Color(img).enhance(src.saturation)
    if mode == "blocks" and unicode:
        small = img.resize((cols, rows * 2), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1, 60))
        px = small.load()
        return [[("▀", px[x, 2 * y], px[x, 2 * y + 1]) for x in range(cols)] for y in range(rows)]
    small = img.resize((cols, rows), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1, 80))
    gray = ImageOps.grayscale(small)
    px, gp = small.load(), gray.load()
    ramp = ASCII_RAMP if mode != "floral" else (FLORAL_RAMP_U if unicode else FLORAL_RAMP_A)
    n = len(ramp) - 1
    out = []
    for y in range(rows):
        row = []
        for x in range(cols):
            lum = gp[x, y] / 255.0
            ch = ramp[int(lum * n)]
            c = px[x, y]
            fg = mix(c, (255, 255, 255), 0.15 * lum)
            if mode == "floral":
                # keep darks empty so the illustration floats on the scene
                row.append((ch if lum > 0.5 else " ", fg, scale(c, 0.25 * lum)))
            else:
                row.append((ch if ch != " " else ".", fg, scale(c, 0.3)))
        out.append(row)
    return out


@register("artwork")
class ArtworkLayer(Layer):
    """Album artwork as ASCII.

    ``mode``: ``focus`` (big, dissolves in, floral border grows around it),
    ``decor`` (small polaroid hanging on a string), ``inspired`` (redrawn in
    flower glyphs with a shimmer wave), ``fade`` (dissolves away into petals).
    ``style``: ``ascii`` | ``blocks`` | ``floral`` conversion style.
    """

    default_region = "art"

    def draw(self, cv, t, rect, alpha):
        src = self.ctx.artwork
        mode = self.spec.get("mode", "focus")
        size = self.num("size", 0.8 if mode in ("focus", "fade", "inspired") else 0.32)
        cx, cy = rect.point(*self.spec.get("pos", [0.5, 0.5]))
        local = t - self.start
        if mode == "decor":
            cx += math.sin(t * 1.1) * 1.2  # gentle swing
        max_rows = max(3, int(rect.h * size))
        max_cols = max(6, int(rect.w * min(0.95, size * 1.4)))
        if src is None or not src.available:
            draw_rose(cv, cx, cy, max_rows / 2.2, ease_out(local / 3), t, alpha=alpha,
                      unicode=self.ctx.unicode)
            return
        cols, rows = src.fit(max_cols, max_rows)
        style = self.spec.get("style", "floral" if mode == "inspired" else "blocks")
        grid = src.cells(cols, rows, style, self.ctx.unicode)
        x0, y0 = int(cx - cols / 2), int(cy - rows / 2)
        box = Rect(x0, y0, cols, rows)
        if mode == "decor":
            self._polaroid(cv, box, t, alpha)
        elif mode in ("focus", "inspired"):
            cv.glow(cx, cy, cols * 0.9, self.color("glow", "@glow"), 0.3 * alpha)
        reveal = self.num("reveal", 2.5)
        for y, row in enumerate(grid):
            for x, (ch, fg, bg) in enumerate(row):
                h = hash01(x, y, self.seed)
                gx, gy = x0 + x, y0 + y
                if mode == "fade":
                    # cells crumble away (bottom first) and drift up as petals
                    p = local / max(0.1, self.num("duration", 4.0))
                    thresh = p * 1.4 - (1 - y / rows) * 0.4
                    if h < thresh:
                        drift = (thresh - h) * 18
                        if drift < 10:
                            cv.put(gx + drift * 1.5, gy - drift, "✿" if self.ctx.unicode else "*",
                                   fg, alpha=alpha * (1 - drift / 10))
                        continue
                    a = alpha
                else:
                    # dissolve in from the centre outward
                    d = math.hypot((x - cols / 2) / cols, (y - rows / 2) / rows)
                    a = alpha * max(0.0, min(1.0, (local / reveal) * 1.6 - d - h * 0.4))
                if a <= 0:
                    continue
                if mode == "inspired":
                    if ch == " ":
                        continue
                    wave = 0.5 + 0.5 * math.sin(x * 0.3 - y * 0.2 - t * 3)
                    fg = mix(fg, (255, 255, 255), wave ** 6 * 0.5)
                    cv.put(gx, gy, ch, fg, alpha=a)
                    cv.tint(gx, gy, bg, 0.5 * a)
                else:
                    cv.put(gx, gy, ch, fg, bg=bg, alpha=a)
        if mode == "focus" and self.spec.get("border", True):
            self._floral_border(cv, box, local, t, alpha)

    def _polaroid(self, cv: Canvas, box: Rect, t: float, alpha: float) -> None:
        paper = self.color("paper", "#f4ece6")
        for y in range(box.y - 1, box.y2 + 3):
            for x in range(box.x - 2, box.x2 + 2):
                cv.put(x, y, " ", paper, bg=paper, alpha=alpha)
        cap = str(self.spec.get("caption", ""))
        if cap:
            cv.text(box.cx - len(cap) / 2, box.y2 + 1, cap, (90, 60, 80), alpha=alpha)
        # string + pin
        for y in range(0, box.y - 1):
            cv.put(box.cx + (box.y - 1 - y) * 0.0, y, "│" if self.ctx.unicode else "|",
                   (200, 190, 200), alpha=alpha * 0.6)
        cv.put(box.cx, box.y - 1, "●" if self.ctx.unicode else "o", self.color("pin", "@accent"),
               bold=True, alpha=alpha)

    def _floral_border(self, cv: Canvas, box: Rect, local: float, t: float, alpha: float) -> None:
        """Vines with little blossoms creep around the cover clockwise."""
        cols = self.colors("colors", "petals")
        leaf = self.color("leaf", "@leaf")
        b = box.inset(-2, -1)
        path = [(x, b.y) for x in range(b.x, b.x2)] + [(b.x2, y) for y in range(b.y, b.y2)] + \
               [(x, b.y2) for x in range(b.x2, b.x, -1)] + [(b.x, y) for y in range(b.y2, b.y, -1)]
        grown = int(len(path) * ease_out(local / self.num("border_time", 4.0)))
        uni = self.ctx.unicode
        for i, (x, y) in enumerate(path[:grown]):
            horiz = y in (b.y, b.y2)
            wig = math.sin(i * 0.7 + t * 1.5)
            ch = ("~" if wig > 0 else "-") if horiz else ("(" if wig > 0 else ")")
            cv.put(x, y, ch, scale(leaf, 0.8 + 0.2 * wig), alpha=alpha)
            if i % 7 == 3:
                age = (grown - i) / 20.0
                c = cols[(i // 7) % len(cols)]
                g = "❀" if age > 1 else "✿" if age > 0.5 else "•"
                if not uni:
                    g = "@" if age > 1 else "*" if age > 0.5 else "o"
                cv.put(x, y, g, c, bold=True, alpha=alpha * min(1.0, age + 0.3))
