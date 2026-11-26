"""Foreground illustrations: flowers, gardens, roses, 3D meshes, sprites and
little story props (phone, window, palace frame, crystal ball, heart monitor,
Christmas tree, title cards and captions)."""
from __future__ import annotations

import math
from typing import Dict

from .. import font
from ..art import mesh3d
from ..art.flower import draw_flower, draw_leaf
from ..art.rose import draw_rose
from ..art.sprites import BUTTERFLY, BUTTERFLY_CYCLE, LIBRARY, SMALL_BUTTERFLY
from ..canvas import Canvas, Rect
from ..color import RGB, gradient, mix, scale
from ..fx import beat_env, ease_out, ease_out_back, hash01, noise2, slope_glyph, window
from ..themes import resolve_color
from .base import Layer, register


def _pos(layer: Layer, rect: Rect, default=(0.5, 0.5)):
    fx, fy = layer.spec.get("pos", list(default))
    return rect.point(fx, fy)


# ------------------------------------------------------------------ flowers
@register("flower")
class Flower(Layer):
    """One procedural flower. ``bloom`` / ``grow`` accept keyframes."""

    default_region = "art"

    def draw(self, cv, t, rect, alpha):
        gx, gy = _pos(self, rect, (0.5, 0.95))
        th = self.ctx.theme
        cols = self.colors("colors", "petals")
        height = self.num("height", 0.55) * rect.h
        head = self.num("size", 0.16) * rect.h
        draw_flower(cv, gx, gy, height, head, self.kf("bloom", t, 1.0), self.kf("grow", t, 1.0),
                    t, self.num("phase", 0.7), cols, self.color("stem", "@stem"),
                    self.color("leaf", "@leaf"), self.color("center", "@center"),
                    petals=int(self.num("petals", 6)), sway_amp=self.num("sway", 1.0),
                    alpha=alpha, unicode=self.ctx.unicode, seed=self.seed,
                    spin=self.num("spin", 0.15))


@register("garden")
class Garden(Layer):
    """A meadow of flowers that grows in, blooms in a wave, or all at once.

    Keys: ``count``, ``height: [min, max]`` (fraction of region), ``size``,
    ``grow: [t0, t1]`` staggered sprouting window, ``bloom: [t0, t1]``
    staggered blooming window, ``bloom_at: t`` everything bursts open at
    once (buds wait, breathing, until then), ``ground`` fraction.
    """

    default_region = "full"

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.cols = self.colors("colors", "petals")

    def _bloom(self, i: int, n: int, t: float) -> float:
        order = hash01(i, self.seed + 4)
        if "bloom_at" in self.spec:
            at = self.num("bloom_at", 0.0) + order * self.num("bloom_spread", 0.35)
            if t < at:
                return 0.12 + 0.05 * math.sin(t * 3 + i)  # tense, breathing buds
            return 0.12 + 0.95 * ease_out_back((t - at) / 0.8, 2.2)
        b0, b1 = self.spec.get("bloom", [0.0, 0.0])
        start = b0 + (b1 - b0) * order
        return min(1.0, window(t, start, start + 1.6)) if b1 > 0 or b0 > 0 else 1.0

    def draw(self, cv, t, rect, alpha):
        n = int(self.num("count", max(4, rect.w // 9)))
        hmin, hmax = self.spec.get("height", [0.25, 0.55])
        g0, g1 = self.spec.get("grow", [0.0, 0.0])
        ground = rect.y + rect.h * self.num("ground", 0.98)
        head = self.num("size", 0.09) * rect.h
        stem, leaf, center = self.color("stem", "@stem"), self.color("leaf", "@leaf"), \
            self.color("center", "@center")
        items = []
        for i in range(n):
            back = hash01(i, self.seed + 9) < 0.45
            depth = 0.6 if back else 1.0
            fx = (i + 0.5 + (hash01(i, self.seed) - 0.5) * 0.8) / n
            h = (hmin + (hmax - hmin) * hash01(i, self.seed + 1)) * rect.h * depth
            items.append((depth, i, fx, h))
        for depth, i, fx, h in sorted(items):
            start = g0 + (g1 - g0) * hash01(i, self.seed + 2)
            grow = window(t, start, start + 2.0) if (g0 or g1) else 1.0
            c0 = self.cols[i % len(self.cols)]
            c1 = mix(self.cols[(i + 2) % len(self.cols)], (255, 255, 255), 0.45)
            dim = 0.55 + 0.45 * depth
            draw_flower(cv, rect.x + fx * rect.w, ground - (1 - depth) * rect.h * 0.08, h,
                        head * depth * (0.8 + 0.5 * hash01(i, 7)), self._bloom(i, n, t), grow, t,
                        hash01(i, self.seed + 3) * 6.28, [scale(c0, dim), scale(c1, dim)],
                        scale(stem, dim), scale(leaf, dim), center,
                        petals=5 + int(hash01(i, 11) * 4), alpha=alpha, unicode=self.ctx.unicode,
                        seed=self.seed + i, sway_amp=self.num("sway", 1.0))
        if self.spec.get("grass", True):
            y = int(ground)
            for x in range(rect.x, rect.x2):
                s = math.sin(t * 2 + x * 0.4)
                ch = "/" if s > 0.3 else "\\" if s < -0.3 else "|"
                if hash01(x, 3, self.seed) < 0.3:
                    ch = ","
                cv.put(x, y, ch, scale(leaf, 0.6 + 0.4 * hash01(x, 5)), alpha=alpha)
                if hash01(x, 6, self.seed) < 0.5:
                    cv.put(x, y - 1, "'" if s > 0 else ".", scale(leaf, 0.8), alpha=alpha * 0.8)


@register("rose")
class Rose(Layer):
    """Big spiral rose with stem and leaves (pseudo-3D shading)."""

    default_region = "art"

    def draw(self, cv, t, rect, alpha):
        cx, cy = _pos(self, rect, (0.5, 0.42))
        R = self.num("size", 0.22) * rect.h
        bloom = self.kf("bloom", t, 1.0)
        cy += math.sin(t * 0.8) * 0.4
        if self.spec.get("stem", True):
            col = self.color("stem", "@stem")
            leaf = self.color("leaf", "@leaf")
            sway = math.sin(t * 0.9) * 1.2
            bottom = rect.y2 - 1
            prev = None
            for y in range(int(cy + R * 0.9), bottom + 1):
                k = (y - cy) / max(1, bottom - cy)
                x = cx + sway * (1 - k) + math.sin(k * 3.0) * 1.5
                if prev is not None:
                    cv.put(x, y, slope_glyph(x - prev, 1), col, alpha=alpha)
                    if hash01(y, self.seed) < 0.15:
                        cv.put(x + 1, y, ">", scale(col, 1.2), alpha=alpha)  # thorn
                prev = x
            ly = cy + R + (bottom - cy - R) * 0.4
            draw_leaf(cv, cx + 1, ly, 1, R * 0.7, leaf, t, alpha, self.ctx.unicode)
            draw_leaf(cv, cx - 1, ly + R * 0.35, -1, R * 0.6, leaf, t + 1, alpha, self.ctx.unicode)
        draw_rose(cv, cx, cy, R, bloom, t, self.color("deep", "#8f0a35"),
                  self.color("light", "@accent"), alpha, self.num("spin", 0.25), self.ctx.unicode)
        cv.glow(cx, cy, R * 4, self.color("light", "@accent"), 0.12 * alpha)


@register("mesh")
class Mesh(Layer):
    """Spinning lit 3D point-cloud: ``shape: heart`` (beats on ``bpm``) or
    ``shape: flower`` (``bloom`` keyframes open the petals)."""

    default_region = "art"
    _cache: Dict[str, object] = {}

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.shape = spec.get("shape", "heart")
        if self.shape not in Mesh._cache:
            Mesh._cache[self.shape] = mesh3d.heart_mesh() if self.shape == "heart" else mesh3d.FlowerMesh()
        self.mesh = Mesh._cache[self.shape]

    def draw(self, cv, t, rect, alpha):
        cx, cy = _pos(self, rect, (0.5, 0.5))
        size = self.num("size", 0.3) * rect.h
        yaw = t * self.num("spin", 0.8) + self.num("yaw", 0.0)
        pitch = self.num("pitch", 0.35) + math.sin(t * 0.6) * self.num("wobble", 0.12)
        if self.shape == "heart":
            beat = beat_env(t, self.num("bpm", 0.0), self.num("offset", 0.0), 7.0) \
                if "bpm" in self.spec else 0.0
            cols = self.colors("colors", "petals")
            items = mesh3d.heart_items(self.mesh, yaw, pitch, beat)
            glow = cols[0]
            cv.glow(cx, cy, size * 3.2 * (1 + 0.15 * beat), glow, (0.25 + 0.3 * beat) * alpha)
            mesh3d.render_points(cv, items, cx, cy, size * (1 + 0.1 * beat), cols, alpha)
        else:
            cols = self.colors("colors", "petals")
            cols = [cols[0], cols[1 % len(cols)], self.color("center", "@center"),
                    mix(cols[0], (255, 255, 255), 0.6)]
            items = mesh3d.flower_items(self.mesh, self.kf("bloom", t, 1.0), yaw, pitch, t)
            cv.glow(cx, cy, size * 3, cols[0], 0.22 * alpha)
            mesh3d.render_points(cv, items, cx, cy, size, cols, alpha, two_sided=True)


# ------------------------------------------------------------------ sprites
@register("sprite")
class SpriteLayer(Layer):
    """A library sprite (``name``) with ``fps``, ``bob`` and a ``palette``
    mapping mask keys to colours."""

    default_region = "art"
    PALETTES = {
        "cherub": {"w": "#fff6e8", "f": "#ffd9a8", "h": "#ffc94a", "s": "#ffd7c2"},
        "couple": {"a": "#2a1238", "b": "#3a1440"},
        "snowman": {"h": "#2a2a35", "c": "#ff8c2b", "k": "#30303a", "a": "#8a5a3a", "s": "#f4fbff"},
        "butterfly": {"w": "#ffb3e6", "p": "#ffe9a8", "b": "#5a3550"},
    }

    def draw(self, cv, t, rect, alpha):
        name = self.spec.get("name", "butterfly")
        sp = LIBRARY[name]
        merged = dict(self.PALETTES.get(name, {}))
        merged.update(self.spec.get("palette") or {})
        pal = {k: resolve_color(v, self.ctx.theme) for k, v in merged.items()}
        cx, cy = _pos(self, rect)
        cy += math.sin(t * self.num("bob_speed", 1.6)) * self.num("bob", 0.6)
        frame = int(t * self.num("fps", 2.0)) % len(sp.frames)
        cv.blit(sp, cx - sp.w / 2, cy - sp.h / 2, pal, alpha=alpha, frame=frame,
                bold_keys=self.spec.get("bold", ""))


@register("butterflies")
class Butterflies(Layer):
    """Flock of butterflies on looping flight paths; ``big`` ones flap a
    3-frame wing animation, small ones are 3-character sprites."""

    default_region = "full"

    def draw(self, cv, t, rect, alpha):
        n = int(self.num("count", 4))
        big = int(self.num("big", 1))
        cols = self.colors("colors", "petals")
        accent = self.color("accent", "@center")
        for i in range(n):
            a, b, c = (hash01(i, self.seed + k) for k in range(3))
            sp = self.num("speed", 1.0)
            x = rect.x + rect.w * (0.5 + 0.42 * math.sin(t * (0.18 + a * 0.15) * sp + c * 6.28))
            y = rect.y + rect.h * (0.45 + 0.35 * math.sin(t * (0.31 + b * 0.2) * sp + a * 6.28))
            y += math.sin(t * 6 + i) * 0.4
            col = cols[i % len(cols)]
            flap = t * (5 + a * 3) + i
            if i < big:
                frame = BUTTERFLY_CYCLE[int(flap) % 4]
                pal = {"w": col, "p": accent, "b": scale(col, 0.4)}
                cv.blit(BUTTERFLY, x - BUTTERFLY.w / 2, y - BUTTERFLY.h / 2, pal, alpha=alpha,
                        frame=frame, bold_keys="p")
            else:
                g = SMALL_BUTTERFLY[int(flap) % 4] if self.ctx.unicode else "{|}"
                cv.text(x - 1, y, g, col, bold=True, alpha=alpha)


# -------------------------------------------------------------------- props
@register("phone")
class Phone(Layer):
    """Glowing phone: types a search, then doom-scrolls a feed while
    hearts float off the screen."""

    default_region = "art"
    QUERY = "you"

    def draw(self, cv, t, rect, alpha):
        uni = self.ctx.unicode
        w = int(max(18, min(26, rect.w * self.num("width", 0.42))))
        h = int(max(12, min(22, rect.h * self.num("height", 0.62))))
        cx, cy = _pos(self, rect, (0.5, 0.5))
        x0, y0 = int(cx - w / 2), int(cy - h / 2 + math.sin(t * 0.9) * 0.5)
        screen = self.color("screen", "#223a6b")
        glow = self.color("glow", "#6fa8ff")
        body = self.color("body", "#d8d0e8")
        txt = self.color("text", "#eaf2ff")
        acc = self.color("accent", "@accent")
        cv.glow(cx, cy, w * 1.6, glow, 0.35 * alpha)
        H, V = ("─", "│") if uni else ("-", "|")
        tl, tr, bl, br = ("╭", "╮", "╰", "╯") if uni else (".", ".", "'", "'")
        corners = {(x0, y0): tl, (x0 + w - 1, y0): tr, (x0, y0 + h - 1): bl, (x0 + w - 1, y0 + h - 1): br}
        for x in range(x0, x0 + w):
            for y in range(y0, y0 + h):
                edge_x, edge_y = x in (x0, x0 + w - 1), y in (y0, y0 + h - 1)
                if edge_x or edge_y:
                    ch = corners.get((x, y), V if edge_x else H)
                    cv.put(x, y, ch, body, bold=True, alpha=alpha)
                else:
                    shade = mix(screen, (255, 255, 255), 0.08 * (1 - (y - y0) / h))
                    cv.put(x, y, " ", shade, bg=shade, alpha=alpha)
        ix, iw = x0 + 2, w - 4
        top = y0 + 1
        cv.text(ix, top, "9:41", txt, alpha=alpha)
        cv.text(x0 + w - 6, top, "▂▄▆" if uni else "lll", txt, alpha=alpha)
        local = t - self.start
        # search bar, typed query
        typed = self.QUERY[:max(0, min(len(self.QUERY), int((local - 0.4) / 0.28)))]
        cursor = "▏" if uni else "|"
        bar = ("⌕ " if uni else "> ") + typed + (cursor if int(t * 2.5) % 2 else " ")
        cv.text(ix, top + 1, (H * iw), scale(txt, 0.5), alpha=alpha)
        cv.text(ix, top + 2, bar[:iw], txt, bold=True, alpha=alpha)
        cv.text(ix, top + 3, (H * iw), scale(txt, 0.5), alpha=alpha)
        # feed scrolls once the search is done
        feed_top, feed_bot = top + 4, y0 + h - 2
        scroll = max(0.0, local - 1.6) * self.num("scroll", 2.2)
        item_h = 6
        for row in range(feed_top, feed_bot + 1):
            k = row - feed_top + int(scroll)
            item, line = divmod(k, item_h)
            seed = item * 13 + self.seed
            if line == 0:
                cv.text(ix, row, ("● @you" if uni else "o @you") + "  · " + str(1 + item % 9) + "h",
                        txt, alpha=alpha)
            elif line in (1, 2, 3):
                for dx in range(iw):
                    v = noise2(dx * 0.25 + item * 5, line * 0.5, 3)
                    c = gradient([acc, glow, (255, 220, 160)], (v + hash01(item, 1)) % 1)
                    ch = ("░", "▒", "▓", "█")[int(v * 3.99)] if uni else ".:#@"[int(v * 3.99)]
                    cv.put(ix + dx, row, ch, scale(c, 0.85), bg=scale(c, 0.35), alpha=alpha)
            elif line == 4:
                liked = hash01(seed, 2) < 0.6
                heart = ("♥" if liked else "♡") if uni else "<3"
                cv.text(ix, row, heart, acc if liked else txt, bold=liked, alpha=alpha)
                cv.text(ix + 3, row, "%d,%03d" % (1 + int(hash01(seed, 3) * 9), int(hash01(seed, 4) * 999)),
                        scale(txt, 0.8), alpha=alpha)
        # hearts escaping the screen
        for i in range(6):
            period = 2.6
            ph = (t + i * period / 6) % period / period
            hx = x0 + w - 3 + math.sin(ph * 6 + i) * 2 + ph * 4
            hy = y0 + h * 0.75 - ph * (h + 4)
            cv.put(hx, hy, "♥" if uni else "<", acc, bold=True, alpha=alpha * math.sin(ph * math.pi))


@register("window")
class Window(Layer):
    """Bedroom window at night: moon and stars in the panes, swaying
    curtains, and a little pot of flowers on the sill that slowly blooms."""

    default_region = "art"

    def draw(self, cv, t, rect, alpha):
        uni = self.ctx.unicode
        bx = rect.sub(*self.spec.get("box", [0.12, 0.08, 0.76, 0.6]))
        wood = self.color("frame", "#8a6a8f")
        night = self.color("night", "#0b1236")
        moon = self.color("moon", "#fff1c9")
        curtain = self.color("curtain", "@accent")
        # panes
        for y in range(bx.y + 1, bx.y2 - 1):
            k = (y - bx.y) / max(1, bx.h)
            pane = mix(night, (40, 30, 90), k)
            for x in range(bx.x + 1, bx.x2 - 1):
                cv.put(x, y, " ", pane, bg=pane, alpha=alpha)
                if hash01(x, y, self.seed) < 0.04:
                    tw = 0.5 + 0.5 * math.sin(t * 2 + x * y)
                    cv.put(x, y, "·" if tw < 0.7 else "✦" if uni else "*", scale((255, 255, 240), 0.4 + 0.6 * tw),
                           alpha=alpha)
        mx, my = bx.x + bx.w * 0.68, bx.y + bx.h * 0.32
        R = max(1.5, bx.h * 0.16)
        cv.glow(mx, my, R * 6, (120, 130, 255), 0.3 * alpha)
        for y in range(int(my - R) - 1, int(my + R) + 2):
            for x in range(int(mx - 2 * R) - 1, int(mx + 2 * R) + 2):
                d = math.hypot((x - mx) / 2, y - my)
                d2 = math.hypot((x - mx - R * 0.9) / 2, y - my + R * 0.2)
                if d <= R + 0.3 and d2 > R * 0.85 and bx.contains(x, y):
                    # solid, softly shaded crescent; the bright limb faces away from the shadow
                    k = min(1.0, (d2 - R * 0.85) / (R * 0.6))
                    c = scale(moon, 0.55 + 0.45 * k)
                    edge = d > R - 0.4
                    cv.put(x, y, "." if edge else " ", moon, bg=mix(cv.get_bg(x, y), c, 0.6 if edge else 1.0),
                           alpha=alpha)
        # frame + cross bars
        H, V = ("═", "║") if uni else ("=", "|")
        for x in range(bx.x, bx.x2):
            for y in (bx.y, bx.y2 - 1, bx.y + bx.h // 2):
                cv.put(x, y, H, wood, bold=True, alpha=alpha)
        for y in range(bx.y, bx.y2):
            for x in (bx.x, bx.x2 - 1, bx.x + bx.w // 2):
                cv.put(x, y, V, wood, bold=True, alpha=alpha)
        corners = ("╔", "╗", "╚", "╝") if uni else ("+",) * 4
        for (x, y), ch in zip(((bx.x, bx.y), (bx.x2 - 1, bx.y), (bx.x, bx.y2 - 1), (bx.x2 - 1, bx.y2 - 1)), corners):
            cv.put(x, y, ch, wood, bold=True, alpha=alpha)
        # sill
        sill_y = bx.y2
        for x in range(bx.x - 2, bx.x2 + 2):
            cv.put(x, sill_y, "▀" if uni else "=", scale(wood, 1.15), alpha=alpha)
        # curtains: folds sway with a travelling sine
        cw = max(3, bx.w // 6)
        for side in (-1, 1):
            for y in range(bx.y - 1, bx.y2 + 1):
                k = (y - bx.y + 1) / (bx.h + 2)
                sway = math.sin(t * 1.3 + y * 0.35 + side) * (0.5 + k * 1.5)
                tie = 1.0 - 0.45 * math.exp(-((k - 0.62) ** 2) * 40)  # tied back
                width = int(cw * tie)
                base = bx.x - 1 if side < 0 else bx.x2 - width + 1
                for i in range(width):
                    # velvet folds: shading carries the shape, glyphs only on crests
                    fold = math.sin((i + sway) * 1.7)
                    c = scale(curtain, 0.22 + 0.3 * (fold + 1) / 2)
                    ch = "│" if fold > 0.85 and uni else ("|" if fold > 0.85 else " ")
                    cv.put(base + i, y, ch, scale(curtain, 0.75), bg=c, alpha=alpha)
                if y == bx.y - 1:
                    for i in range(width):
                        cv.put(base + i, y, "▄" if uni else "_", scale(curtain, 0.9), alpha=alpha)
        # potted flowers on the sill
        pots = int(self.num("pots", 2))
        for p in range(pots):
            px = bx.x + bx.w * (0.3 + 0.4 * p / max(1, pots - 1))
            cv.text(px - 2, sill_y - 1, "\\__/", (190, 110, 80), alpha=alpha)
            grow = window(t, 0.3 + p * 0.6, 2.5 + p * 0.6)
            bloom = window(t, 2.5 + p * 1.0, 5.5 + p * 1.0)
            cols = self.colors("flowers", "petals")
            draw_flower(cv, px, sill_y - 2, 4.5, 1.8, bloom, grow, t, p * 2.1,
                        [cols[p % len(cols)], (255, 240, 250)], self.color("stem", "@stem"),
                        self.color("leaf", "@leaf"), self.color("center", "@center"),
                        petals=5, sway_amp=0.6, alpha=alpha, unicode=uni, seed=p)


@register("frame")
class OrnateFrame(Layer):
    """Gilded baroque picture frame with a travelling shine."""

    default_region = "art"

    def draw(self, cv, t, rect, alpha):
        uni = self.ctx.unicode
        bx = rect.sub(*self.spec.get("box", [0.1, 0.05, 0.8, 0.55]))
        gold = self.color("color", "@gold" if "gold" in self.ctx.theme else "@accent")
        panel = self.color("panel", "#2a1410")
        for y in range(bx.y + 2, bx.y2 - 2):
            k = (y - bx.y) / bx.h
            c = mix(panel, scale(panel, 1.8), 1 - abs(k - 0.4) * 1.5)
            for x in range(bx.x + 2, bx.x2 - 2):
                cv.put(x, y, " ", c, bg=mix(cv.get_bg(x, y), c, 0.85), alpha=alpha)
        perim = 2 * (bx.w + bx.h)
        shine = (t * 18) % perim

        def gcol(i):
            d = min(abs(i - shine), perim - abs(i - shine))
            return mix(scale(gold, 0.75), (255, 250, 220), math.exp(-d * d / 30))

        H, V = ("═", "║") if uni else ("=", "|")
        h2, v2 = ("─", "│") if uni else ("-", "|")
        orn = "❦" if uni else "&"
        for i, x in enumerate(range(bx.x, bx.x2)):
            top_ch = orn if (i % 8 == 4) else H
            cv.put(x, bx.y, top_ch, gcol(i), bold=True, alpha=alpha)
            cv.put(x, bx.y2 - 1, top_ch, gcol(perim - i - bx.h), bold=True, alpha=alpha)
            if bx.x + 1 < x < bx.x2 - 2:
                cv.put(x, bx.y + 1, h2, scale(gold, 0.6), alpha=alpha)
                cv.put(x, bx.y2 - 2, h2, scale(gold, 0.6), alpha=alpha)
        for j, y in enumerate(range(bx.y, bx.y2)):
            cv.put(bx.x, y, V, gcol(perim - j), bold=True, alpha=alpha)
            cv.put(bx.x2 - 1, y, V, gcol(bx.w + j), bold=True, alpha=alpha)
            if bx.y + 1 < y < bx.y2 - 2:
                cv.put(bx.x + 1, y, v2, scale(gold, 0.6), alpha=alpha)
                cv.put(bx.x2 - 2, y, v2, scale(gold, 0.6), alpha=alpha)
        for x, y in ((bx.x, bx.y), (bx.x2 - 1, bx.y), (bx.x, bx.y2 - 1), (bx.x2 - 1, bx.y2 - 1)):
            cv.put(x, y, "@", (255, 240, 200), bold=True, alpha=alpha)
            cv.glow(x, y, 4, gold, 0.25 * alpha)
        # crest on top
        cv.text(bx.cx - 3, bx.y - 1, ".-" + orn + "-.", gold, bold=True, alpha=alpha)


@register("crystal_ball")
class CrystalBall(Layer):
    """Fortune-teller's ball: swirling mist that clears to reveal a sprite
    (``content: couple``) at ``reveal`` seconds."""

    default_region = "art"

    def draw(self, cv, t, rect, alpha):
        cx, cy = _pos(self, rect, (0.5, 0.45))
        R = max(4.0, self.num("size", 0.34) * rect.h)
        mist = self.colors("mist", "petals")
        glass = self.color("glass", "@glow")
        reveal = self.num("reveal", 2.0)
        clear = window(t, reveal, reveal + 1.8)
        cv.glow(cx, cy, R * 4.5, glass, 0.32 * alpha)
        for y in range(int(cy - R), int(cy + R) + 1):
            for x in range(int(cx - 2 * R), int(cx + 2 * R) + 1):
                dx, dy = (x - cx) / 2.0, y - cy
                r = math.hypot(dx, dy)
                if r > R:
                    continue
                u = r / R
                ang = math.atan2(dy, dx)
                swirl = 0.5 + 0.5 * math.sin(ang * 2 + u * 5 - t * 1.6)
                n = noise2(x * 0.18 + t * 0.4, y * 0.3 - t * 0.2, self.seed)
                m = swirl * 0.5 + n * 0.5
                inner = mix((20, 10, 45), gradient(mist, m), (0.55 + 0.45 * m) * (1 - 0.7 * clear))
                inner = mix(inner, scale(glass, 0.35), u ** 3)
                cv.put(x, y, " ", inner, bg=inner, alpha=alpha)
                if m > 0.62 and clear < 0.8:
                    cv.put(x, y, "~" if m > 0.8 else "·" if self.ctx.unicode else ".",
                           mix(inner, (255, 255, 255), 0.5), alpha=alpha * (1 - clear))
                if u > 0.9:
                    cv.put(x, y, "(" if dx < -abs(dy) else ")" if dx > abs(dy) else
                           ("‿" if self.ctx.unicode else "_") if dy > 0 else "-",
                           mix(glass, (255, 255, 255), 0.5), bold=True, alpha=alpha)
        name = self.spec.get("content")
        if name and clear > 0:
            sp = LIBRARY[name]
            pal = {"a": self.color("a", "#1c0b2e"), "b": self.color("b", "#2b0d33")}
            ox, oy = cx - sp.w / 2, cy - sp.h / 2 + 0.5
            for j, line in enumerate(sp.frames[0]):
                for i, ch in enumerate(line):
                    if ch == " ":
                        continue
                    x, y = ox + i, oy + j
                    if math.hypot((x - cx) / 2, y - cy) < R * 0.92:
                        k = sp.masks[0][j][i] if sp.masks else "a"
                        cv.put(x, y, ch, pal.get(k, pal["a"]), alpha=alpha * clear)
        # highlight + stand
        cv.put(cx - R * 0.9, cy - R * 0.55, "`", (255, 255, 255), bold=True, alpha=alpha)
        cv.put(cx - R * 0.75, cy - R * 0.68, "o" if R > 6 else ".", (255, 255, 255), alpha=alpha * 0.8)
        gold = self.color("stand", "#d9a441")
        w = int(R * 2.4)
        cv.text(cx - w / 2, cy + R, "\\" + "_" * (w - 2) + "/", gold, bold=True, alpha=alpha)
        cv.text(cx - w / 2 - 1, cy + R + 1, "/" + "_" * w + "\\", scale(gold, 0.8), alpha=alpha)


def _ecg(phase: float) -> float:
    def g(c, w, a):
        return a * math.exp(-((phase - c) ** 2) / (2 * w * w))
    return g(0.12, 0.025, 0.15) + g(0.23, 0.008, -0.15) + g(0.26, 0.012, 1.0) + \
        g(0.29, 0.01, -0.35) + g(0.48, 0.04, 0.28)


@register("heartbeat")
class Heartbeat(Layer):
    """Hospital-monitor sweep that spikes on the beat - 'the most alive'."""

    default_region = "art"

    def draw(self, cv, t, rect, alpha):
        uni = self.ctx.unicode
        bpm = self.num("bpm", 120)
        period = 60.0 / bpm
        base = rect.y + rect.h * self.num("y", 0.5)
        amp = rect.h * self.num("amp", 0.3)
        x0, x1 = rect.x + 1, rect.x2 - 2
        W = x1 - x0
        speed = self.num("speed", W / 2.2)
        col = self.color("color", "@accent")
        head = (t * speed) % W
        prev_y = None
        for i in range(W):
            age = ((head - i) % W) / speed
            if age > (W - 3) / speed:
                prev_y = None
                continue
            st = t - age
            v = _ecg((st % period) / period)
            y = base - v * amp
            fade = math.exp(-age * self.num("decay", 0.9))
            c = mix(scale(col, 0.25), mix(col, (255, 255, 255), 0.3), fade)
            yi = int(round(y))
            if prev_y is not None and abs(yi - prev_y) > 0:
                step = 1 if yi > prev_y else -1
                for yy in range(prev_y, yi, step):
                    cv.put(x0 + i, yy, "│" if uni else "|", c, alpha=alpha * fade)
            ch = "─" if uni else "-"
            if prev_y is not None and yi != prev_y:
                ch = ("╲" if yi > prev_y else "╱") if uni else ("\\" if yi > prev_y else "/")
            cv.put(x0 + i, yi, ch, c, bold=fade > 0.6, alpha=alpha * max(0.15, fade))
            prev_y = yi
        hx = x0 + int(head)
        hy = base - _ecg((t % period) / period) * amp
        cv.put(hx, hy, "●" if uni else "@", (255, 255, 255), bold=True, alpha=alpha)
        cv.glow(hx, hy, 6, col, 0.5 * alpha)
        beat = beat_env(t, bpm, period * 0.26, 6.0)
        hx2, hy2 = rect.x + rect.w * 0.85, rect.y + rect.h * self.num("heart_y", 0.18)
        cv.glow(hx2, hy2, 6 + 6 * beat, col, (0.25 + 0.4 * beat) * alpha)
        cv.text(hx2 - 3, hy2 + 1, "%d BPM" % int(bpm), scale(col, 0.9), alpha=alpha)
        cv.put(hx2, hy2, "♥" if uni else "<3", mix(col, (255, 255, 255), beat * 0.6), bold=True,
               alpha=alpha)


@register("tree")
class XmasTree(Layer):
    """Christmas tree with blinking lights, garland and a twinkling star."""

    default_region = "art"

    def draw(self, cv, t, rect, alpha):
        uni = self.ctx.unicode
        cx, by = _pos(self, rect, (0.5, 0.92))
        H = max(8, int(self.num("size", 0.7) * rect.h))
        green = self.color("color", "#2f8f4e")
        lights = [(255, 80, 80), (255, 215, 90), (110, 180, 255), (255, 140, 220)]
        top = by - H
        for i in range(H):
            y = int(top + i + 1)
            tier = (i % (H // 3 + 1)) / (H // 3 + 1)
            half = (i / H) * H * 0.9 * (0.55 + 0.45 * tier) + 1
            for x in range(int(cx - half), int(cx + half) + 1):
                rel = (x - cx) / half
                if x == int(cx - half):
                    ch = "/"
                elif x == int(cx + half):
                    ch = "\\"
                else:
                    ch = "^" if hash01(x, y, 2) < 0.5 else "*"
                shade = 0.55 + 0.45 * (1 - abs(rel)) - 0.2 * (rel > 0.3)
                cv.put(x, y, ch, scale(green, shade + 0.3), bg=scale(green, 0.3 * shade), alpha=alpha)
                if abs(math.sin((x - cx) * 0.35 + y * 0.9)) < 0.12:
                    cv.put(x, y, "~", (230, 190, 90), alpha=alpha)
                if hash01(x, y, self.seed) < 0.09 and abs(rel) < 0.95:
                    k = int(hash01(x, y, 5) * len(lights))
                    on = math.sin(t * 3 + hash01(x, y, 6) * 6.28) > -0.2
                    lc = lights[k] if on else scale(lights[k], 0.35)
                    cv.put(x, y, "o" if uni else "o", lc, bold=on, alpha=alpha)
                    if on:
                        cv.glow(x, y, 2.5, lc, 0.18 * alpha)
        tw = 0.5 + 0.5 * math.sin(t * 2.5)
        cv.glow(cx, top, 8 + 3 * tw, (255, 220, 120), (0.35 + 0.2 * tw) * alpha)
        cv.put(cx, top, "★" if uni else "*", (255, 230, 140), bold=True, alpha=alpha)
        cv.text(cx - 1, by + 1, "|_|", (130, 80, 50), alpha=alpha)


# --------------------------------------------------------------- typography
@register("title")
class Title(Layer):
    """Big block-font title with gradient, drop shadow and letter reveal."""

    default_region = "full"

    def draw(self, cv, t, rect, alpha):
        text = str(self.spec.get("text", "")).upper()
        sub = self.spec.get("subtitle")
        cols = self.colors("colors", "lyric")
        uni = self.ctx.unicode
        block = "█" if uni else "#"
        width = font.measure(text)
        cx, cy = _pos(self, rect, (0.5, 0.2))
        x0, y0 = int(cx - width / 2), int(cy - 2)
        local = t - self.start
        per = self.num("letter_delay", 0.12)
        fits = width <= rect.w - 2
        if not fits:
            cv.text(cx - len(text) / 2, cy, text, cols[0], bold=True, alpha=alpha)
        else:
            for i, dx, rows in font.layout(text):
                a = alpha * min(1.0, max(0.0, (local - i * per) / 0.5))
                if a <= 0:
                    continue
                for ry, row in enumerate(rows):
                    for rx, ch in enumerate(row):
                        if ch == " ":
                            continue
                        x, y = x0 + dx + rx, y0 + ry
                        cv.put(x + 1, y + 1, " ", (0, 0, 0), bg=scale(cv.get_bg(x + 1, y + 1), 0.4), alpha=a)
                        shimmer = 0.5 + 0.5 * math.sin(t * 2 - (dx + rx) * 0.15)
                        c = mix(gradient(cols, ry / 4), (255, 255, 255), shimmer ** 6 * 0.6)
                        cv.put(x, y, block, c, bold=True, alpha=a)
        if sub:
            a = alpha * min(1.0, max(0.0, (local - len(text) * per - 0.3) / 0.8))
            spaced = " ".join(str(sub))
            cv.text(cx - len(spaced) / 2, y0 + (6 if fits else 2), spaced, self.color("sub_color", "@past"),
                    alpha=a)


@register("caption")
class Caption(Layer):
    """Small typed caption, e.g. credits in the outro."""

    default_region = "full"

    def draw(self, cv, t, rect, alpha):
        text = str(self.spec.get("text", ""))
        cx, cy = _pos(self, rect, (0.5, 0.9))
        n = int(max(0.0, t - self.start) / self.num("char_delay", 0.05))
        shown = text[:n]
        col = self.color("color", "@past")
        cv.text(int(cx - len(text) / 2), int(cy), shown, col, bold=bool(self.spec.get("bold")),
                alpha=alpha)
