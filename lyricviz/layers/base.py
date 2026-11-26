"""Layer base class and registry.

A scene is a stack of layers drawn back to front. Each layer is configured
by a dict from the song file, e.g.::

    {type: petals, rate: 6, start: 2.0, fade_in: 1.0, region: full}

Common keys understood by every layer:

``region``   ``full`` | ``art`` | ``lyrics`` - which part of the layout to use
``start``    scene-local second when the layer appears
``until``    scene-local second when it disappears (optional)
``fade_in`` / ``fade_out``  envelope durations
``opacity``  0..1 multiplier

To add a new layer type, subclass :class:`Layer` and decorate it with
``@register("my_type")``. It is then usable from any song config.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Type

from ..canvas import Canvas, Rect
from ..color import RGB
from ..themes import resolve_color, resolve_colors

REGISTRY: Dict[str, Type["Layer"]] = {}


def register(name: str) -> Callable[[Type["Layer"]], Type["Layer"]]:
    def deco(cls: Type["Layer"]) -> Type["Layer"]:
        cls.type_name = name
        REGISTRY[name] = cls
        return cls
    return deco


class SceneContext:
    """What a layer can know about its surroundings."""

    def __init__(self, theme: Dict[str, Any], unicode: bool, seed: int, artwork=None,
                 scene_name: str = "", scene_duration: float = 0.0, song=None):
        self.theme = theme
        self.unicode = unicode
        self.seed = seed
        self.artwork = artwork
        self.scene_name = scene_name
        self.scene_duration = scene_duration
        self.song = song


class Layer:
    type_name = "base"
    default_region = "full"

    def __init__(self, spec: Dict[str, Any], ctx: SceneContext):
        self.spec = spec
        self.ctx = ctx
        self.region = spec.get("region", self.default_region)
        self.start = float(spec.get("start", 0.0))
        until = spec.get("until")
        self.until: Optional[float] = float(until) if until is not None else None
        self.fade_in = float(spec.get("fade_in", 0.8 if self.start > 0 else 0.0))
        self.fade_out = float(spec.get("fade_out", 0.8))
        self.opacity = float(spec.get("opacity", 1.0))
        # deterministic per layer (str hash() is randomised per process)
        self.seed = int(spec.get("seed", ctx.seed * 31 + sum(map(ord, self.type_name))
                                 + 7 * int(spec.get("_index", 0))))

    # -------------------------------------------------------------- helpers
    def color(self, key: str, default: Any) -> RGB:
        return resolve_color(self.spec.get(key, default), self.ctx.theme)

    def colors(self, key: str, default_theme_key: str) -> List[RGB]:
        return resolve_colors(self.spec.get(key), self.ctx.theme, default_theme_key)

    def num(self, key: str, default: float) -> float:
        return float(self.spec.get(key, default))

    def kf(self, key: str, t: float, default: float) -> float:
        """Keyframed number: ``5`` or ``[[0, 2], [4, 12], [9, 0]]`` (time, value)."""
        v = self.spec.get(key, default)
        if not isinstance(v, list):
            return float(v)
        pts = sorted((float(a), float(b)) for a, b in v)
        if t <= pts[0][0]:
            return pts[0][1]
        for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
            if t <= t1:
                k = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
                return v0 + (v1 - v0) * k
        return pts[-1][1]

    def g(self, uni: str, ascii_: str) -> str:
        """Pick a glyph depending on Unicode support."""
        return uni if self.ctx.unicode else ascii_

    def alpha(self, t: float) -> float:
        if t < self.start:
            return 0.0
        a = 1.0
        if self.fade_in > 0:
            a = min(a, (t - self.start) / self.fade_in)
        if self.until is not None:
            if t >= self.until:
                return 0.0
            if self.fade_out > 0:
                a = min(a, (self.until - t) / self.fade_out)
        return max(0.0, min(1.0, a)) * self.opacity

    # ------------------------------------------------------------ lifecycle
    def reset(self) -> None:
        """Called after a seek; stateful layers re-initialise here."""

    def update(self, dt: float, t: float, rect: Rect) -> None:
        """Advance simulation state (particles etc.)."""

    def draw(self, cv: Canvas, t: float, rect: Rect, alpha: float) -> None:
        raise NotImplementedError

    def render(self, cv: Canvas, t: float, dt: float, regions: Dict[str, Rect]) -> None:
        rect = regions.get(self.region, regions["full"])
        if t >= self.start - 0.5:
            self.update(dt, t, rect)
        a = self.alpha(t)
        if a > 0.0:
            self.draw(cv, t, rect, a)


def build_layer(spec: Dict[str, Any], ctx: SceneContext) -> Layer:
    kind = spec.get("type")
    if kind not in REGISTRY:
        raise KeyError(f"unknown layer type {kind!r}; available: {', '.join(sorted(REGISTRY))}")
    return REGISTRY[kind](spec, ctx)
