"""Small RGB colour toolkit. Colours are plain ``(r, g, b)`` int tuples."""
from __future__ import annotations

import colorsys
from typing import Iterable, List, Sequence, Tuple, Union

RGB = Tuple[int, int, int]
ColorLike = Union[str, Sequence[int], None]

BLACK: RGB = (0, 0, 0)
WHITE: RGB = (255, 255, 255)


def hex2rgb(value: str) -> RGB:
    s = value.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError(f"bad colour {value!r}")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def to_rgb(value: ColorLike, default: RGB = WHITE) -> RGB:
    if value is None:
        return default
    if isinstance(value, str):
        return hex2rgb(value)
    r, g, b = value  # type: ignore[misc]
    return (int(r), int(g), int(b))


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def mix(a: RGB, b: RGB, t: float) -> RGB:
    """Linear blend from ``a`` (t=0) to ``b`` (t=1)."""
    if t <= 0:
        return a
    if t >= 1:
        return b
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def scale(c: RGB, k: float) -> RGB:
    if 0.0 <= k <= 1.0:  # hot path: dimming never overflows, skip the clamps
        return (int(c[0] * k), int(c[1] * k), int(c[2] * k))
    return (
        min(255, max(0, int(c[0] * k))),
        min(255, max(0, int(c[1] * k))),
        min(255, max(0, int(c[2] * k))),
    )


def add(c: RGB, d: RGB, k: float = 1.0) -> RGB:
    """Additive light: ``c + d * k`` clamped."""
    return (
        min(255, int(c[0] + d[0] * k)),
        min(255, int(c[1] + d[1] * k)),
        min(255, int(c[2] + d[2] * k)),
    )


def gradient(stops: Sequence[RGB], t: float) -> RGB:
    """Evenly spaced multi-stop gradient."""
    n = len(stops)
    if n == 1:
        return stops[0]
    t = clamp(t) * (n - 1)
    i = int(t)
    if i >= n - 1:
        return stops[-1]
    return mix(stops[i], stops[i + 1], t - i)


def hsv(h: float, s: float, v: float) -> RGB:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))


def luminance(c: RGB) -> float:
    return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255.0


def parse_list(values: Iterable[ColorLike]) -> List[RGB]:
    return [to_rgb(v) for v in values]
