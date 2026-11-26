"""Particle layers: petals, snow, rain, sparkles, fireflies, hearts, bursts.

Particles live in screen space and have a ``depth`` in (0, 1]: far particles
are smaller glyphs, dimmer and slower, near ones are big, bright and fast.
That one number is what sells the parallax / pseudo-3D feel.
"""
from __future__ import annotations

import math
import random
from typing import List, Sequence

from ..canvas import Canvas, Rect
from ..color import RGB, mix, scale
from ..fx import hash01
from .base import Layer, register


class P:
    __slots__ = ("x", "y", "vx", "vy", "age", "life", "depth", "phase", "col", "kind")

    def __init__(self, x, y, vx, vy, life, depth, phase, col, kind=0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.age, self.life = 0.0, life
        self.depth, self.phase, self.col, self.kind = depth, phase, col, kind


class ParticleLayer(Layer):
    """Shared spawn/update/prewarm machinery."""

    max_particles = 500

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.rng = random.Random(self.seed)
        self.parts: List[P] = []
        self._acc = 0.0
        self._warm = False

    def reset(self) -> None:
        self.parts = []
        self._acc = 0.0
        self._warm = False

    def spawn(self, rect: Rect, t: float, prewarm: bool = False) -> P:
        raise NotImplementedError

    def step(self, p: P, dt: float, t: float, rect: Rect) -> bool:
        """Advance one particle; return False to kill it."""
        raise NotImplementedError

    def rate(self, t: float) -> float:
        return self.kf("rate", t, 4.0)

    def update(self, dt, t, rect):
        if not self._warm:
            # Pre-populate so a scene never starts with an empty sky.
            n = int(self.rate(max(t, self.start)) * self.num("prewarm", 3.0))
            self.parts = [self.spawn(rect, t, prewarm=True) for _ in range(min(n, self.max_particles))]
            self._warm = True
        if t >= self.start and (self.until is None or t < self.until):
            self._acc += self.rate(t) * dt
            while self._acc >= 1.0 and len(self.parts) < self.max_particles:
                self.parts.append(self.spawn(rect, t))
                self._acc -= 1.0
            self._acc = min(self._acc, 3.0)
        alive = []
        for p in self.parts:
            p.age += dt
            if p.age < p.life and self.step(p, dt, t, rect):
                alive.append(p)
        self.parts = alive


@register("petals")
class Petals(ParticleLayer):
    """Falling, fluttering petals. Keys: rate, wind, fall, flutter, swirl, colors."""

    NEAR_U = ("❀", "✿", "❁", "✾")
    MID_U = ("✿", "*", "❀", "•")
    FAR_U = ("·", ".", "·", "'")
    NEAR_A = ("@", "*", "o", "*")
    MID_A = ("*", "o", "*", "+")
    FAR_A = (".", "'", ".", ",")

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.cols = self.colors("colors", "petals")

    def spawn(self, rect, t, prewarm=False):
        r = self.rng
        wind = self.kf("wind", t, 1.5)
        x = rect.x + r.uniform(-0.25, 1.05) * rect.w - wind * 4
        y = rect.y + (r.uniform(0, rect.h) if prewarm else r.uniform(-3, -1))
        depth = r.random() ** 0.8 * 0.85 + 0.15
        fall = self.num("fall", 3.0)
        col = self.cols[r.randrange(len(self.cols))]
        return P(x, y, 0.0, fall * (0.4 + depth), 60.0, depth, r.uniform(0, 6.28), col)

    def step(self, p, dt, t, rect):
        wind = self.kf("wind", t, 1.5)
        flutter = self.num("flutter", 2.5)
        swirl = self.kf("swirl", t, 0.0)
        sway = math.sin(p.age * (1.2 + p.depth) + p.phase) * flutter
        vx = (wind * 2.0 + sway) * (0.4 + p.depth)
        vy = p.vy + math.cos(p.age * 1.7 + p.phase) * 0.6
        if swirl:
            dx, dy = p.x - rect.cx, (p.y - rect.cy) * 2
            d = math.hypot(dx, dy) + 1.0
            vx += -dy / d * swirl * p.depth * 6
            vy += dx / d * swirl * p.depth * 3
        p.x += vx * dt
        p.y += vy * dt
        return p.y < rect.y2 + 1 and rect.x - rect.w * 0.4 < p.x < rect.x2 + rect.w * 0.4

    def draw(self, cv, t, rect, alpha):
        uni = self.ctx.unicode
        near, mid, far = (self.NEAR_U, self.MID_U, self.FAR_U) if uni else \
            (self.NEAR_A, self.MID_A, self.FAR_A)
        for p in sorted(self.parts, key=lambda q: q.depth):
            frame = int(p.age * (3 + p.depth * 4) + p.phase) % 4
            if p.depth > 0.72:
                ch, bold = near[frame], True
            elif p.depth > 0.42:
                ch, bold = mid[frame], False
            else:
                ch, bold = far[frame], False
            col = scale(p.col, 0.45 + 0.6 * p.depth)
            cv.put(p.x, p.y, ch, col, bold=bold, alpha=alpha * min(1.0, 0.35 + p.depth))


@register("snow")
class Snow(ParticleLayer):
    max_particles = 700

    def spawn(self, rect, t, prewarm=False):
        r = self.rng
        depth = r.random() * 0.85 + 0.15
        y = rect.y + (r.uniform(0, rect.h) if prewarm else -1)
        return P(rect.x + r.uniform(-0.1, 1.1) * rect.w, y, 0.0,
                 self.num("fall", 3.5) * (0.3 + depth), 80.0, depth, r.uniform(0, 6.28),
                 (255, 255, 255))

    def rate(self, t):
        return self.kf("rate", t, 12.0)

    def step(self, p, dt, t, rect):
        wind = self.kf("wind", t, 0.6)
        p.x += (wind + math.sin(p.age * 0.9 + p.phase) * 0.8) * dt * (0.4 + p.depth) * 2
        p.y += p.vy * dt
        return p.y < rect.y2

    def draw(self, cv, t, rect, alpha):
        uni = self.ctx.unicode
        col = self.color("color", "#ffffff")
        for p in self.parts:
            if p.depth > 0.8:
                ch = "✶" if uni else "*"
            elif p.depth > 0.55:
                ch = "*"
            elif p.depth > 0.35:
                ch = "•" if uni else "o"
            else:
                ch = "·" if uni else "."
            cv.put(p.x, p.y, ch, scale(col, 0.45 + 0.55 * p.depth), bold=p.depth > 0.8,
                   alpha=alpha * (0.4 + 0.6 * p.depth))


@register("rain")
class Rain(ParticleLayer):
    max_particles = 600

    def rate(self, t):
        return self.kf("rate", t, 50.0)

    def spawn(self, rect, t, prewarm=False):
        r = self.rng
        depth = r.random() * 0.8 + 0.2
        y = rect.y + (r.uniform(0, rect.h) if prewarm else -1)
        return P(rect.x + r.uniform(-0.1, 1.1) * rect.w, y, self.kf("wind", t, -3.0),
                 self.num("fall", 28.0) * (0.45 + depth), 10.0, depth, 0.0,
                 self.color("color", "#9fb6cf"))

    def step(self, p, dt, t, rect):
        if p.kind == 1:  # splash
            return p.age < 0.25
        p.x += p.vx * dt
        p.y += p.vy * dt
        ground = rect.y2 - 1 - int((1 - p.depth) * 3)
        if p.y >= ground:
            if p.depth > 0.5 and len(self.parts) < self.max_particles:
                s = P(p.x, ground, 0, 0, 0.25, p.depth, 0, p.col, kind=1)
                self.parts.append(s)
            return False
        return True

    def draw(self, cv, t, rect, alpha):
        for p in self.parts:
            col = scale(p.col, 0.4 + 0.6 * p.depth)
            if p.kind == 1:
                k = p.age / 0.25
                ch = "o" if k < 0.3 else "." if k < 0.6 else "`"
                cv.put(p.x, p.y, ch, col, alpha=alpha * (1 - k))
                if k > 0.3:
                    cv.put(p.x - 1, p.y, ".", col, alpha=alpha * (1 - k) * 0.7)
                    cv.put(p.x + 1, p.y, ".", col, alpha=alpha * (1 - k) * 0.7)
                continue
            ch = "/" if p.vx < -6 else "\\" if p.vx > 6 else "|"
            if p.depth < 0.45:
                ch = "'" if p.depth < 0.3 else ch
            cv.put(p.x, p.y, ch, col, alpha=alpha * (0.35 + 0.65 * p.depth))
            if p.depth > 0.7:
                cv.put(p.x - p.vx * 0.03, p.y - 1, ch, scale(col, 0.6), alpha=alpha * 0.5)


@register("sparkles")
class Sparkles(ParticleLayer):
    """Short-lived twinkles that pop in and out of existence."""

    def rate(self, t):
        return self.kf("rate", t, 8.0)

    def spawn(self, rect, t, prewarm=False):
        r = self.rng
        cols = self.colors("colors", "emph")
        return P(rect.x + r.random() * rect.w, rect.y + r.random() * rect.h, 0, 0,
                 r.uniform(0.6, 1.6), r.random(), r.uniform(0, 1), cols[r.randrange(len(cols))])

    def step(self, p, dt, t, rect):
        p.y -= dt * 0.3
        return True

    def draw(self, cv, t, rect, alpha):
        seq = ("·", "+", "✦", "✧", "+", "·") if self.ctx.unicode else (".", "+", "*", "*", "+", ".")
        for p in self.parts:
            k = p.age / p.life
            ch = seq[min(len(seq) - 1, int(k * len(seq)))]
            b = math.sin(k * math.pi)
            cv.put(p.x, p.y, ch, mix(p.col, (255, 255, 255), b * 0.5), bold=b > 0.7,
                   alpha=alpha * b)
            if b > 0.75 and p.depth > 0.6:
                cv.glow(p.x, p.y, 3, p.col, 0.15 * alpha)


@register("fireflies")
class Fireflies(Layer):
    """Lazy glowing motes on lissajous paths."""

    def draw(self, cv, t, rect, alpha):
        n = int(self.num("count", 10))
        col = self.color("color", "@emph")
        for i in range(n):
            a, b, c = hash01(i, self.seed), hash01(i, self.seed + 1), hash01(i, self.seed + 2)
            x = rect.x + rect.w * (0.5 + 0.45 * math.sin(t * (0.13 + a * 0.2) + c * 9))
            y = rect.y + rect.h * (0.5 + 0.42 * math.sin(t * (0.17 + b * 0.2) + a * 9))
            pulse = max(0.0, math.sin(t * (1.2 + b) + c * 6)) ** 2
            cv.glow(x, y, 4, col, 0.35 * pulse * alpha)
            cv.put(x, y, "•" if self.ctx.unicode else "o", mix(col, (255, 255, 255), pulse * 0.6),
                   bold=True, alpha=alpha * (0.3 + 0.7 * pulse))


@register("hearts")
class Hearts(ParticleLayer):
    """Hearts drifting upward with a wobble."""

    def rate(self, t):
        return self.kf("rate", t, 2.0)

    def spawn(self, rect, t, prewarm=False):
        r = self.rng
        cols = self.colors("colors", "petals")
        y = rect.y + (r.uniform(0, rect.h) if prewarm else rect.h + 1)
        depth = r.random() * 0.8 + 0.2
        return P(rect.x + r.random() * rect.w, y, 0, -self.num("rise", 4.0) * (0.4 + depth),
                 20.0, depth, r.uniform(0, 6.28), cols[r.randrange(len(cols))])

    def step(self, p, dt, t, rect):
        p.x += math.sin(p.age * 2 + p.phase) * dt * 2
        p.y += p.vy * dt
        return p.y > rect.y - 1

    def draw(self, cv, t, rect, alpha):
        uni = self.ctx.unicode
        for p in self.parts:
            h = (p.y - rect.y) / max(1, rect.h)
            fade = min(1.0, h * 2.5)
            ch = ("♥" if p.depth > 0.5 else "♡") if uni else "<"
            cv.put(p.x, p.y, ch, scale(p.col, 0.5 + 0.6 * p.depth), bold=p.depth > 0.6,
                   alpha=alpha * fade * (0.4 + 0.6 * p.depth))


@register("burst")
class Burst(ParticleLayer):
    """Explosions of petals at given scene times: ``at: [2.5, 4.0]``.

    ``origin: [fx, fy]`` (in the region), ``count``, ``power``.
    """

    max_particles = 900

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.cols = self.colors("colors", "petals")
        self._last_t = None

    def rate(self, t):
        return 0.0

    def reset(self):
        super().reset()
        self._last_t = None

    def spawn(self, rect, t, prewarm=False):
        return P(0, 0, 0, 0, 0, 0, 0, (0, 0, 0))  # never used for prewarm (rate 0)

    def update(self, dt, t, rect):
        last = self._last_t
        self._last_t = t
        if last is not None and 0 <= t - last < 0.5:
            for when in self.spec.get("at", []):
                if last < when <= t:
                    self._explode(rect)
        alive = []
        for p in self.parts:
            p.age += dt
            drag = math.exp(-dt * 1.8)
            p.vx *= drag
            p.vy = p.vy * drag + self.num("gravity", 9.0) * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            if p.age < p.life and p.y < rect.y2 + 2:
                alive.append(p)
        self.parts = alive

    def _explode(self, rect):
        r = self.rng
        ox, oy = rect.point(*self.spec.get("origin", [0.5, 0.5]))
        power = self.num("power", 30.0)
        for _ in range(int(self.num("count", 160))):
            ang = r.uniform(0, 6.283)
            sp = power * (0.25 + r.random() ** 0.6)
            depth = r.random() * 0.8 + 0.2
            self.parts.append(P(ox, oy, math.cos(ang) * sp * 2, math.sin(ang) * sp - power * 0.3,
                                r.uniform(1.8, 3.6), depth, r.uniform(0, 6.28),
                                self.cols[r.randrange(len(self.cols))]))

    def draw(self, cv, t, rect, alpha):
        uni = self.ctx.unicode
        glyphs = ("❀", "✿", "❁", "✦", "•", "·") if uni else ("@", "*", "o", "+", ".", ".")
        for p in self.parts:
            k = p.age / p.life
            idx = min(len(glyphs) - 1, int(k * 3 + (1 - p.depth) * 3))
            cv.put(p.x, p.y, glyphs[idx], mix(scale(p.col, 0.5 + 0.6 * p.depth), (255, 255, 255),
                                              max(0.0, 0.6 - k * 2)),
                   bold=k < 0.3, alpha=alpha * (1 - k ** 2))
