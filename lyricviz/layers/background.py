"""Atmosphere layers: skies, stars, moon, clouds, fog, light and texture."""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from ..canvas import Canvas, Rect
from ..color import RGB, add, gradient, mix, scale
from ..fx import beat_env, fbm, hash01, noise2, window
from .base import Layer, register


class NoiseTexture:
    """Pre-baked tileable fbm texture; sampling it per frame is cheap."""

    def __init__(self, w: int, h: int, seed: int, sx: float, sy: float):
        self.w, self.h = w, h
        self.data = [[fbm(x * sx, y * sy, seed) for x in range(w)] for y in range(h)]

    def at(self, x: float, y: float) -> float:
        return self.data[int(y) % self.h][int(x) % self.w]


@register("gradient")
class Gradient(Layer):
    """Vertical sky gradient. ``to`` + ``shift: [t0, t1]`` morphs it over time."""

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.stops = self.colors("colors", "sky")
        self.to = self.colors("to", "sky") if "to" in spec else None
        sh = spec.get("shift", [0.0, max(1.0, ctx.scene_duration)])
        self.shift = (float(sh[0]), float(sh[1]))
        self.breathe = self.num("breathe", 0.0)

    def draw(self, cv, t, rect, alpha):
        stops = self.stops
        if self.to:
            k = window(t, *self.shift)
            n = max(len(stops), len(self.to))
            stops = [mix(gradient(self.stops, i / (n - 1)), gradient(self.to, i / (n - 1)), k)
                     for i in range(n)]
        if self.breathe:
            b = 1.0 + self.breathe * math.sin(t * 0.9)
            stops = [scale(c, b) for c in stops]
        if rect.x == 0 and rect.w >= cv.w and alpha >= 1.0:
            cv.fill_vertical(stops, rect.y, rect.y2)
            return
        span = max(1, rect.h - 1)
        for y in range(max(0, rect.y), min(cv.h, rect.y2)):
            c = gradient(stops, (y - rect.y) / span)
            for x in range(max(0, rect.x), min(cv.w, rect.x2)):
                cv.tint(x, y, c, alpha)


@register("stars")
class Stars(Layer):
    """Twinkling star field with depth (dim far stars, rare bright ones)
    and the occasional shooting star."""

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.density = self.num("density", 0.03)
        self.band = spec.get("band", [0.0, 1.0])
        self.speed = self.num("twinkle", 1.0)
        self.shooting = self.num("shooting", 7.0)  # seconds between, 0 = off
        self.tints = self.colors("colors", "lyric") + [(255, 255, 255)] * 3
        self._key = None
        self._stars: List[Tuple[int, int, float, float, float, RGB]] = []

    def _build(self, rect: Rect) -> None:
        self._stars = []
        y0 = rect.y + int(self.band[0] * rect.h)
        y1 = rect.y + int(self.band[1] * rect.h)
        for y in range(y0, y1):
            for x in range(rect.x, rect.x2):
                if hash01(x, y, self.seed) < self.density:
                    r = hash01(x, y, self.seed + 1)
                    tint = self.tints[int(hash01(x, y, 3) * len(self.tints))]
                    size = r ** 3  # most stars small, few big
                    self._stars.append((x, y, r * 6.283, 0.6 + r * 2.2, size, tint))
        self._key = rect

    def draw(self, cv, t, rect, alpha):
        if self._key != rect:
            self._build(rect)
        uni = self.ctx.unicode
        sp = self.speed
        for x, y, ph, spd, size, tint in self._stars:
            b = 0.5 + 0.5 * math.sin(t * spd * sp + ph)
            lvl = size * 0.7 + b * 0.5
            if lvl > 0.85:
                ch = "✦" if uni else "*"
            elif lvl > 0.62:
                ch = "+"
            elif lvl > 0.4:
                ch = "·" if uni else "."
            else:
                ch = "."
            col = scale(tint, 0.35 + 0.65 * b * (0.4 + size))
            cv.put(x, y, ch, col, alpha=alpha * (0.4 + 0.6 * b))
            if lvl > 0.85:
                cv.glow(x, y, 3, tint, 0.12 * b * alpha)
        if self.shooting > 0:
            self._shooting_star(cv, t, rect, alpha)

    def _shooting_star(self, cv, t, rect, alpha):
        period = self.shooting
        k = math.floor(t / period)
        local = t - k * period
        life = 1.1
        if local > life:
            return
        sx = rect.x + hash01(k, self.seed) * rect.w * 0.7
        sy = rect.y + hash01(k, self.seed + 9) * rect.h * 0.3
        p = local / life
        hx, hy = sx + p * rect.w * 0.35, sy + p * rect.h * 0.18
        for i in range(10):
            fade = (1 - i / 10.0) * (1 - p)
            x, y = hx - i * 1.6, hy - i * 0.45
            cv.put(x, y, "*" if i == 0 else ("-" if i > 3 else "~"),
                   scale((255, 245, 220), 0.4 + fade), bold=i == 0, alpha=alpha * fade)


@register("moon")
class Moon(Layer):
    """Procedural crescent moon with soft halo."""

    default_region = "full"

    def draw(self, cv, t, rect, alpha):
        fx, fy = self.spec.get("pos", [0.8, 0.2])
        cx, cy = rect.point(fx, fy)
        cy += math.sin(t * 0.3) * 0.3
        R = max(2.0, self.num("size", 0.12) * rect.h)  # vertical radius in rows
        phase = self.num("phase", 0.45)  # 0 full moon .. 1 thin crescent
        col = self.color("color", "#fff4d6")
        halo = self.color("halo", "@glow")
        cv.glow(cx, cy, R * 5.0, halo, 0.35 * alpha)
        cv.glow(cx, cy, R * 3.0, col, 0.22 * alpha)
        ox = phase * R * 2.0
        for y in range(int(cy - R) - 1, int(cy + R) + 2):
            for x in range(int(cx - R * 2) - 1, int(cx + R * 2) + 2):
                dx, dy = (x - cx) / 2.0, (y - cy)
                d = math.hypot(dx, dy)
                if d > R:
                    continue
                d2 = math.hypot(dx + ox / 2.0, dy + R * 0.25 * phase)
                if d2 < R * 0.98 and phase > 0:
                    continue
                edge = d / R
                crater = fbm(x * 0.4, y * 0.6, 5) if self.ctx.unicode else 0.5
                shade = 0.75 + 0.25 * (1 - edge) - 0.18 * (crater > 0.62)
                ch = "@" if edge < 0.55 else "%" if edge < 0.8 else "o" if edge < 0.93 else "."
                c = scale(col, shade)
                cv.put(x, y, ch, c, bg=mix(cv.get_bg(x, y), c, 0.55), alpha=alpha)


@register("clouds")
class Clouds(Layer):
    """Drifting noise clouds; two textures at different speeds = parallax."""

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.density = self.num("density", 0.5)
        self.speed = self.num("speed", 1.0)
        self.band = spec.get("band", [0.0, 0.45])
        self.col = self.color("color", "#c9b8d9")
        self.tex = None

    def draw(self, cv, t, rect, alpha):
        if self.tex is None:
            self.tex = (NoiseTexture(180, 30, self.seed, 0.045, 0.16),
                        NoiseTexture(160, 30, self.seed + 3, 0.08, 0.25))
        far, near = self.tex
        th = 1.0 - self.density * 0.55
        y0 = rect.y + int(self.band[0] * rect.h)
        y1 = rect.y + int(self.band[1] * rect.h)
        ramp = " .:-=+*"
        o1, o2 = t * 1.2 * self.speed, t * 2.6 * self.speed
        for y in range(max(0, y0), min(cv.h, y1)):
            vfade = 1.0 - abs((y - y0) / max(1, (y1 - y0)) - 0.4) * 1.2
            for x in range(max(0, rect.x), min(cv.w, rect.x2)):
                n = far.at(x + o1, y) * 0.6 + near.at(x + o2, y * 1.3) * 0.4
                d = (n - th) / (1 - th)
                if d <= 0:
                    continue
                d = min(1.0, d * 1.8) * max(0.0, vfade)
                c = scale(self.col, 0.55 + 0.45 * d)
                cv.tint(x, y, c, 0.55 * d * alpha)
                ch = ramp[min(len(ramp) - 1, int(d * len(ramp)))]
                if ch != " ":
                    cv.put(x, y, ch, mix(c, (255, 255, 255), 0.2 * d), alpha=alpha * d)


@register("fog")
class Fog(Layer):
    """Low drifting mist that tints the background."""

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.strength = self.num("strength", 0.35)
        self.col = self.color("color", "@accent")
        self.band = spec.get("band", [0.55, 1.0])
        self.tex = None

    def draw(self, cv, t, rect, alpha):
        if self.tex is None:
            self.tex = NoiseTexture(200, 24, self.seed, 0.035, 0.2)
        y0 = rect.y + int(self.band[0] * rect.h)
        y1 = rect.y + int(self.band[1] * rect.h)
        off = t * 2.0
        for y in range(max(0, y0), min(cv.h, y1)):
            depth = (y - y0) / max(1, y1 - y0)
            for x in range(max(0, rect.x), min(cv.w, rect.x2)):
                n = self.tex.at(x + off * (0.5 + depth), y * 1.7)
                k = max(0.0, n - 0.35) * 1.6 * depth * self.strength * alpha
                if k > 0.01:
                    cv.tint(x, y, self.col, min(0.85, k))
                    if k > 0.3 and hash01(x, y, int(t * 2)) < 0.04:
                        cv.put(x, y, "~", mix(self.col, (255, 255, 255), 0.4), alpha=k)


@register("bokeh")
class Bokeh(Layer):
    """Big out-of-focus light orbs drifting behind everything: instant dreaminess."""

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.count = int(self.num("count", 6))
        self.cols = self.colors("colors", "petals")
        self.strength = self.num("strength", 0.28)
        self.size = self.num("size", 1.0)

    def draw(self, cv, t, rect, alpha):
        for i in range(self.count):
            r1, r2, r3 = hash01(i, self.seed), hash01(i, self.seed + 1), hash01(i, self.seed + 2)
            x = rect.x + rect.w * (0.5 + 0.45 * math.sin(t * (0.05 + r1 * 0.08) + r2 * 6.28))
            y = rect.y + rect.h * (0.5 + 0.42 * math.cos(t * (0.04 + r2 * 0.07) + r3 * 6.28))
            rad = (6 + r3 * 12) * self.size * max(0.6, rect.h / 36)
            pulse = 0.65 + 0.35 * math.sin(t * (0.5 + r1) + i)
            cv.glow(x, y, rad, self.cols[i % len(self.cols)], self.strength * pulse * alpha)


@register("rays")
class Rays(Layer):
    """Shimmering god-rays fanning out from a light source."""

    def draw(self, cv, t, rect, alpha):
        sx, sy = rect.point(*self.spec.get("source", [0.15, -0.1]))
        col = self.color("color", "@glow")
        strength = self.num("strength", 0.22) * alpha
        n = self.num("count", 7)
        for y in range(max(0, rect.y), min(cv.h, rect.y2)):
            for x in range(max(0, rect.x), min(cv.w, rect.x2)):
                dx, dy = x - sx, (y - sy) * 2.0
                ang = math.atan2(dy, dx)
                v = 0.5 + 0.5 * math.sin(ang * n * 2 + t * 0.35 + math.sin(t * 0.2 + ang * 3))
                dist = math.hypot(dx, dy) / (rect.w + rect.h)
                k = (v ** 6) * max(0.0, 1.0 - dist * 1.1) * strength
                if k > 0.01:
                    cv.tint(x, y, col, k)


@register("hills")
class Hills(Layer):
    """Parallax hill silhouettes with swaying grass tips (far -> near)."""

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.cols = self.colors("colors", "leaf")
        if len(self.cols) == 1:
            base = self.cols[0]
            self.cols = [scale(base, 0.35), scale(base, 0.55), scale(base, 0.8)]
        self.grass = bool(spec.get("grass", True))
        self.height = self.num("height", 0.28)
        self.speed = self.num("speed", 0.4)

    def draw(self, cv, t, rect, alpha):
        n = len(self.cols)
        uni = self.ctx.unicode
        for i, col in enumerate(self.cols):
            depth = (i + 1) / n
            base = rect.y2 - rect.h * self.height * (1.15 - depth * 0.6)
            amp = rect.h * 0.08 * (1.2 - depth * 0.5)
            off = t * self.speed * depth * 2.0
            for x in range(max(0, rect.x), min(cv.w, rect.x2)):
                hx = noise2((x + off) * (0.03 + 0.02 * i), i * 7.3, self.seed + i)
                top = base - amp * hx * 2.0
                ytop = int(top)
                for y in range(max(ytop, rect.y), min(cv.h, rect.y2)):
                    shade = scale(col, 0.75 + 0.25 * (1 - (y - ytop) / max(1, rect.y2 - ytop)))
                    cv.put(x, y, " ", shade, bg=shade, alpha=alpha)
                if self.grass and 0 <= ytop - 1 < cv.h:
                    sway = math.sin(t * 2.2 + x * 0.35 + i)
                    ch = "/" if sway > 0.35 else "\\" if sway < -0.35 else "|"
                    if hash01(x, i, self.seed) < 0.18:
                        ch = "," if uni else ","
                    cv.put(x, ytop - 1, ch, mix(col, (255, 255, 255), 0.15 + 0.1 * depth),
                           alpha=alpha)


@register("vignette")
class Vignette(Layer):
    """Darkens the edges for a cinematic, lens-like frame."""

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self._mask = None
        self._key = None

    def draw(self, cv, t, rect, alpha):
        if self._key != (cv.w, cv.h):
            s = self.num("strength", 0.5)
            self._mask = []
            for y in range(cv.h):
                row = []
                for x in range(cv.w):
                    dx = (x - cv.w / 2) / (cv.w / 2)
                    dy = (y - cv.h / 2) / (cv.h / 2)
                    d = min(1.0, math.sqrt(dx * dx * 0.8 + dy * dy * 0.9))
                    row.append(1.0 - s * d ** 2.2)
                self._mask.append(row)
            self._key = (cv.w, cv.h)
        for y in range(cv.h):
            m = self._mask[y]
            bg, fg, ch = cv.bg[y], cv.fg[y], cv.ch[y]
            for x in range(cv.w):
                k = 1.0 - (1.0 - m[x]) * alpha
                if k < 0.98:
                    c = bg[x]
                    bg[x] = (int(c[0] * k), int(c[1] * k), int(c[2] * k))
                    if ch[x] != " ":  # a blank cell's fg is invisible
                        c, kf = fg[x], 0.4 + 0.6 * k
                        fg[x] = (int(c[0] * kf), int(c[1] * kf), int(c[2] * kf))


@register("pulse")
class Pulse(Layer):
    """Screen-wide light pulse, either on a tempo (``bpm``) or at ``hits`` times."""

    def draw(self, cv, t, rect, alpha):
        col = self.color("color", "@glow")
        strength = self.num("strength", 0.18)
        env = 0.0
        if "bpm" in self.spec:
            env = beat_env(t, self.num("bpm", 120), self.num("offset", 0.0), self.num("sharp", 5.0))
        for h in self.spec.get("hits", []):
            if 0 <= t - h < 1.5:
                env = max(env, math.exp(-(t - h) * self.num("decay", 3.0)))
        k = env * strength * alpha
        if k < 0.01:
            return
        r0, g0, b0 = col[0] * k, col[1] * k, col[2] * k
        for y in range(max(0, rect.y), min(cv.h, rect.y2)):
            bg = cv.bg[y]
            for x in range(max(0, rect.x), min(cv.w, rect.x2)):
                c = bg[x]
                bg[x] = (min(255, int(c[0] + r0)), min(255, int(c[1] + g0)), min(255, int(c[2] + b0)))


@register("wallpaper")
class Wallpaper(Layer):
    """Faint damask wall pattern with a slow travelling sheen (palace walls)."""

    TILE_U = [
        "  .-❦-.   ",
        " (  ✿  )  ",
        "  '-.-'   ",
        "    :     ",
        "  ~ ❀ ~   ",
        "    :     ",
    ]
    TILE_A = [
        "  .-&-.   ",
        " (  *  )  ",
        "  '-.-'   ",
        "    :     ",
        "  ~ * ~   ",
        "    :     ",
    ]

    def draw(self, cv, t, rect, alpha):
        tile = self.TILE_U if self.ctx.unicode else self.TILE_A
        col = self.color("color", "@gold" if "gold" in self.ctx.theme else "@accent")
        base = self.num("strength", 0.28)
        th, tw = len(tile), len(tile[0])
        for y in range(max(0, rect.y), min(cv.h, rect.y2)):
            row = tile[(y - rect.y) % th]
            shift = ((y - rect.y) // th) % 2 * (tw // 2)
            for x in range(max(0, rect.x), min(cv.w, rect.x2)):
                ch = row[(x - rect.x + shift) % tw]
                if ch == " ":
                    continue
                sheen = 0.5 + 0.5 * math.sin((x * 0.5 + y) * 0.12 - t * 1.2)
                k = base * (0.55 + 0.45 * sheen ** 4) * alpha
                cv.put(x, y, ch, mix(cv.get_bg(x, y), col, k))
