"""Deterministic randomness, noise and easing helpers shared by all layers."""
from __future__ import annotations

import math


def hash01(*args: float) -> float:
    """Stable pseudo-random value in [0, 1) from integer-ish inputs."""
    h = 2166136261
    for a in args:
        h ^= int(a * 1000003) & 0xFFFFFFFF
        h = (h * 16777619) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0x5BD1E995) & 0xFFFFFFFF
    h ^= h >> 15
    return (h & 0xFFFFFF) / float(0x1000000)


def _smooth(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def noise2(x: float, y: float, seed: int = 0) -> float:
    """Value noise in [0, 1)."""
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    a = hash01(xi, yi, seed)
    b = hash01(xi + 1, yi, seed)
    c = hash01(xi, yi + 1, seed)
    d = hash01(xi + 1, yi + 1, seed)
    u, v = _smooth(xf), _smooth(yf)
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v


def fbm(x: float, y: float, seed: int = 0, octaves: int = 3) -> float:
    total, amp, norm = 0.0, 1.0, 0.0
    for i in range(octaves):
        total += noise2(x, y, seed + i * 17) * amp
        norm += amp
        x *= 2.03
        y *= 2.03
        amp *= 0.5
    return total / norm


def ease_out(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_in_out(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def ease_out_back(t: float, s: float = 1.7) -> float:
    """Overshoots then settles; makes blooms feel springy."""
    t = min(1.0, max(0.0, t)) - 1.0
    return t * t * ((s + 1) * t + s) + 1.0


def bounce(t: float) -> float:
    t = min(1.0, max(0.0, t))
    if t < 1 / 2.75:
        return 7.5625 * t * t
    if t < 2 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    if t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    t -= 2.625 / 2.75
    return 7.5625 * t * t + 0.984375


def window(t: float, start: float, end: float) -> float:
    """0 before ``start``, ramps to 1 at ``end``."""
    if end <= start:
        return 1.0 if t >= start else 0.0
    return min(1.0, max(0.0, (t - start) / (end - start)))


def beat_env(t: float, bpm: float, offset: float = 0.0, sharp: float = 6.0) -> float:
    """1.0 on each beat decaying exponentially until the next."""
    if bpm <= 0:
        return 0.0
    period = 60.0 / bpm
    phase = ((t - offset) % period) / period
    return math.exp(-phase * sharp)


DIR_GLYPHS = ("-", "\\", "|", "/")


def slope_glyph(dx: float, dy: float) -> str:
    """Line glyph for a screen-space direction (y grows downward)."""
    ang = math.atan2(dy, dx * 0.5)  # undo cell aspect
    a = (ang % math.pi) / math.pi  # 0..1
    idx = int(a * 4 + 0.5) % 4
    return DIR_GLYPHS[idx]
