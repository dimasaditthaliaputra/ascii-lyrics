"""Scene model, layout and the scene manager (incl. cross-scene transitions)."""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .canvas import Canvas, Rect
from .layers.base import Layer, SceneContext, build_layer
from .themes import ATMOSPHERES, get_theme, resolve_color
from .transitions import blend

LAYOUTS = ("left", "right", "center", "top", "bottom")


@dataclass
class SceneSpec:
    name: str
    start: float
    end: float = 0.0
    layout: str = "left"  # where the lyrics sit
    theme: Any = "dusk_rose"
    atmosphere: Optional[str] = None
    layers: List[Dict[str, Any]] = field(default_factory=list)
    transition: Dict[str, Any] = field(default_factory=lambda: {"type": "dissolve", "duration": 1.2})
    lyrics: Dict[str, Any] = field(default_factory=dict)  # lyric style overrides
    split: float = 0.42  # fraction of width used by the lyric column

    @property
    def duration(self) -> float:
        return self.end - self.start


def compute_layout(w: int, h: int, layout: str, split: float = 0.42,
                   reserve_bottom: int = 0) -> Dict[str, Rect]:
    """Regions: ``full`` screen, ``art`` side, ``lyrics`` side.

    Side layouts alternate the lyric column left/right; ``center`` puts the
    lyrics in a lower band over a full-screen illustration.
    """
    H = max(1, h - reserve_bottom)
    full = Rect(0, 0, w, H)
    if layout in ("left", "right"):
        lw = max(20, int(w * split))
        lw = min(lw, w - 10)
        if layout == "left":
            lyr, art = Rect(1, 0, lw - 2, H), Rect(lw, 0, w - lw, H)
        else:
            lyr, art = Rect(w - lw + 1, 0, lw - 2, H), Rect(0, 0, w - lw, H)
        return {"full": full, "art": art, "lyrics": lyr}
    if layout == "top":
        lh = max(5, int(H * 0.38))
        return {"full": full, "art": Rect(0, lh, w, H - lh), "lyrics": Rect(2, 1, w - 4, lh - 1)}
    # center / bottom: lyrics in the lower band, art everywhere
    lh = max(6, int(H * (0.4 if layout == "center" else 0.32)))
    lw = int(w * 0.84)
    return {"full": full, "art": Rect(0, 0, w, H - lh + 2),
            "lyrics": Rect((w - lw) // 2, H - lh, lw, lh - 1)}


class Scene:
    def __init__(self, spec: SceneSpec, unicode: bool, artwork=None, song=None, index: int = 0):
        self.spec = spec
        self.theme = get_theme(spec.theme)
        self.ctx = SceneContext(self.theme, unicode, seed=1000 + index * 97, artwork=artwork,
                                scene_name=spec.name, scene_duration=spec.duration, song=song)
        specs: List[Dict[str, Any]] = []
        if spec.atmosphere:
            if spec.atmosphere not in ATMOSPHERES:
                raise KeyError(f"scene {spec.name!r}: unknown atmosphere {spec.atmosphere!r}; "
                               f"available: {', '.join(sorted(ATMOSPHERES))}")
            specs.extend(dict(s) for s in ATMOSPHERES[spec.atmosphere])
        specs.extend(dict(s) for s in spec.layers)
        if not specs or specs[0].get("type") not in ("gradient",):
            specs.insert(0, {"type": "gradient"})
        self.layers: List[Layer] = []
        for i, s in enumerate(specs):
            s.setdefault("_index", i)
            try:
                self.layers.append(build_layer(s, self.ctx))
            except KeyError as e:
                raise KeyError(f"scene {spec.name!r} layer #{i + 1}: {e.args[0]}") from None
        self.last_t: Optional[float] = None

    def regions(self, w: int, h: int, reserve_bottom: int = 0) -> Dict[str, Rect]:
        return compute_layout(w, h, self.spec.layout, self.spec.split, reserve_bottom)

    def reset(self) -> None:
        for l in self.layers:
            l.reset()
        self.last_t = None

    def render(self, cv: Canvas, local_t: float, regions: Dict[str, Rect]) -> None:
        dt = 0.0 if self.last_t is None else local_t - self.last_t
        if dt < 0 or dt > 0.5:  # seek: restart simulations
            self.reset()
            dt = 0.0
        self.last_t = local_t
        cv.clear()
        for layer in self.layers:
            layer.render(cv, local_t, dt, regions)


class SceneManager:
    def __init__(self, specs: List[SceneSpec], unicode: bool, artwork=None, song=None):
        self.specs = sorted(specs, key=lambda s: s.start)
        self._starts = [s.start for s in self.specs]
        self.unicode = unicode
        self.artwork = artwork
        self.song = song
        self._scenes: Dict[int, Scene] = {}
        self._buf_a: Optional[Canvas] = None
        self._buf_b: Optional[Canvas] = None

    def index_at(self, t: float) -> int:
        return max(0, bisect.bisect_right(self._starts, t) - 1)

    def scene(self, i: int) -> Scene:
        if i not in self._scenes:
            self._scenes[i] = Scene(self.specs[i], self.unicode, self.artwork, self.song, i)
            # Drop far-away scenes to bound memory on long songs.
            for k in [k for k in self._scenes if abs(k - i) > 2]:
                del self._scenes[k]
        return self._scenes[i]

    def transition_state(self, t: float) -> Tuple[int, Optional[int], float]:
        """(current index, previous index or None, progress 0..1)."""
        i = self.index_at(t)
        spec = self.specs[i]
        dur = float(spec.transition.get("duration", 1.2))
        kind = spec.transition.get("type", "dissolve")
        if i > 0 and kind != "cut" and dur > 0 and t - spec.start < dur:
            return i, i - 1, (t - spec.start) / dur
        return i, None, 1.0

    def render(self, out: Canvas, t: float, reserve_bottom: int = 0) -> Tuple[Scene, Optional[Scene], float]:
        i, prev, p = self.transition_state(t)
        cur = self.scene(i)
        if prev is None:
            cur.render(out, t - cur.spec.start, cur.regions(out.w, out.h, reserve_bottom))
            return cur, None, 1.0
        if self._buf_a is None or (self._buf_a.w, self._buf_a.h) != (out.w, out.h):
            self._buf_a = Canvas(out.w, out.h)
            self._buf_b = Canvas(out.w, out.h)
        old = self.scene(prev)
        old.render(self._buf_a, t - old.spec.start, old.regions(out.w, out.h, reserve_bottom))
        cur.render(self._buf_b, t - cur.spec.start, cur.regions(out.w, out.h, reserve_bottom))
        edge = resolve_color(cur.spec.transition.get("color", "@accent"), cur.theme)
        blend(self._buf_a, self._buf_b, out, cur.spec.transition.get("type", "dissolve"), p, edge,
              self.unicode)
        return cur, old, p

    def reset(self) -> None:
        for s in self._scenes.values():
            s.reset()
