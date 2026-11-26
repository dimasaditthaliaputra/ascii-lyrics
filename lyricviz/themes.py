"""Mood palettes and atmosphere presets.

A *theme* is a palette (sky, lyric colours, particle colours ...). An
*atmosphere* is a ready-made stack of background layers for a mood, so a song
config can say ``atmosphere: christmas`` instead of listing snow, stars, etc.
Any colour value in a song config may reference a theme key with ``@key``.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

from .color import RGB, to_rgb

THEMES: Dict[str, Dict[str, Any]] = {
    "dusk_rose": {
        "sky": ["#12061a", "#2c0f2e", "#5a1d45", "#8c3658"],
        "lyric": ["#ffe3f0", "#f9b4d6", "#e7b8ff"],
        "emph": ["#ffe7a3", "#ff7fb6"],
        "past": "#a77d98", "sing": "#ffffff", "glow": "#ff6fae", "accent": "#ff9cc8",
        "petals": ["#ffb7d5", "#ff8fbf", "#f9d0e3", "#ffffff", "#e889b5"],
        "leaf": "#4e9a63", "stem": "#3f7d4f", "center": "#ffd36e",
    },
    "midnight": {
        "sky": ["#03040f", "#0a1030", "#1b1747", "#33205a"],
        "lyric": ["#dfe6ff", "#b7c6ff", "#e2c7ff"],
        "emph": ["#9fe8ff", "#ff9ad5"],
        "past": "#7b7fa6", "sing": "#ffffff", "glow": "#6f8cff", "accent": "#a3b5ff",
        "petals": ["#f3c4ff", "#c8b6ff", "#ffd1ea"],
        "leaf": "#3d7f66", "stem": "#2f6650", "center": "#fff1a8",
    },
    "lavender_dream": {
        "sky": ["#140a26", "#2b1650", "#53307d", "#8a5aa8"],
        "lyric": ["#f5ecff", "#d9c2ff", "#ffc9ec"],
        "emph": ["#fff2a8", "#c99cff"],
        "past": "#9a86b8", "sing": "#ffffff", "glow": "#b58cff", "accent": "#e1c8ff",
        "petals": ["#e7d3ff", "#ffc9ec", "#c3a6ff", "#ffffff"],
        "leaf": "#5aa37a", "stem": "#3f7d5f", "center": "#ffe28a",
    },
    "versailles_gold": {
        "sky": ["#1a0d07", "#3b1f10", "#6b3a1f", "#a8643a"],
        "lyric": ["#fff4d6", "#ffd99a", "#ffc2c2"],
        "emph": ["#fff7c2", "#ffb347"],
        "past": "#b8977a", "sing": "#ffffff", "glow": "#ffc36b", "accent": "#ffd27a",
        "petals": ["#ffd0d8", "#ffb6c1", "#fff0c9", "#ffcf8a"],
        "leaf": "#6a9a4a", "stem": "#4c7a37", "center": "#ffe08a", "gold": "#e6b64c",
    },
    "passion": {
        "sky": ["#14020a", "#3a0619", "#6e0f2d", "#b0234a"],
        "lyric": ["#ffe0e8", "#ff9fb8", "#ffc7a8"],
        "emph": ["#ffffff", "#ff3d6e"],
        "past": "#b57586", "sing": "#ffffff", "glow": "#ff2e63", "accent": "#ff6b8f",
        "petals": ["#ff5c85", "#ff8fab", "#ffc2d1", "#ffffff", "#e0245e"],
        "leaf": "#3f8f55", "stem": "#2e6e40", "center": "#ffd36e",
    },
    "bloom": {
        "sky": ["#1b0516", "#4a0f36", "#8f2a5a", "#e0707d"],
        "lyric": ["#fff0f6", "#ffc0db", "#ffe3a8"],
        "emph": ["#ffffff", "#ffd36e"],
        "past": "#c497ad", "sing": "#ffffff", "glow": "#ff8fb8", "accent": "#ffd1e6",
        "petals": ["#ffb7d5", "#ff8fbf", "#ffe0ec", "#ffffff", "#ffd36e", "#d9a6ff"],
        "leaf": "#4fa868", "stem": "#3b8150", "center": "#ffd36e",
    },
    "christmas": {
        "sky": ["#020611", "#071a33", "#0e2c4f", "#1d4a6b"],
        "lyric": ["#f4fbff", "#cfe9ff", "#ffd7d7"],
        "emph": ["#ffdf6e", "#ff5a5a"],
        "past": "#8aa2b8", "sing": "#ffffff", "glow": "#ffcf6e", "accent": "#ff6b6b",
        "petals": ["#ffffff", "#e6f4ff", "#cde6ff"],
        "leaf": "#2f8f4e", "stem": "#5b3a24", "center": "#ffdf6e",
    },
    "rain": {
        "sky": ["#05070b", "#11171f", "#1c2632", "#2c3a48"],
        "lyric": ["#dbe7f2", "#a9bccf", "#c7d3e0"],
        "emph": ["#ffffff", "#8fb8de"],
        "past": "#6c7d8e", "sing": "#ffffff", "glow": "#5f87ad", "accent": "#9fc1e0",
        "petals": ["#7f9bb8", "#a9c2da"],
        "leaf": "#3b5f4f", "stem": "#2b4a3c", "center": "#c7d3e0",
    },
    "shadow": {
        "sky": ["#000000", "#07050a", "#120d18", "#1d1526"],
        "lyric": ["#cfc6d9", "#9d8fb0", "#d4b3c9"],
        "emph": ["#ffffff", "#b066ff"],
        "past": "#5e536b", "sing": "#ffffff", "glow": "#5b2a86", "accent": "#8a63b0",
        "petals": ["#6b4a85", "#3b2a4f"],
        "leaf": "#2b3d33", "stem": "#1f2d26", "center": "#9d8fb0",
    },
}

ATMOSPHERES: Dict[str, List[Dict[str, Any]]] = {
    "romantic": [
        {"type": "gradient"},
        {"type": "bokeh", "count": 7},
        {"type": "petals", "rate": 3},
    ],
    "dreamy": [
        {"type": "gradient"},
        {"type": "stars", "density": 0.025},
        {"type": "bokeh", "count": 6},
        {"type": "sparkles", "rate": 6},
    ],
    "night": [
        {"type": "gradient"},
        {"type": "stars", "density": 0.035},
        {"type": "moon", "pos": [0.82, 0.18]},
    ],
    "christmas": [
        {"type": "gradient"},
        {"type": "stars", "density": 0.02},
        {"type": "snow", "rate": 14},
        {"type": "hills", "colors": ["#cfe3f2", "#e9f4fb", "#ffffff"], "grass": False},
    ],
    "sad": [
        {"type": "gradient"},
        {"type": "clouds", "density": 0.7, "speed": 0.6, "color": "#56677c"},
        {"type": "rain", "rate": 60},
        {"type": "fog", "strength": 0.25},
    ],
    "dark": [
        {"type": "gradient"},
        {"type": "fog", "strength": 0.45, "color": "#2a1f3a"},
        {"type": "fireflies", "count": 8, "color": "#b066ff"},
        {"type": "vignette", "strength": 0.6},
    ],
}


def get_theme(name_or_dict: Any) -> Dict[str, Any]:
    """Resolve a theme name, or a dict ``{base: name, ...overrides}``."""
    if isinstance(name_or_dict, dict):
        base = copy.deepcopy(THEMES.get(name_or_dict.get("base", "dusk_rose"), THEMES["dusk_rose"]))
        base.update({k: v for k, v in name_or_dict.items() if k != "base"})
        return base
    name = name_or_dict or "dusk_rose"
    if name not in THEMES:
        raise KeyError(f"unknown theme {name!r}; available: {', '.join(sorted(THEMES))}")
    return copy.deepcopy(THEMES[name])


def resolve_color(value: Any, theme: Dict[str, Any], default: str = "#ffffff") -> RGB:
    """``"#ff00aa"`` -> rgb, ``"@accent"`` -> theme colour, lists take first item."""
    if value is None:
        value = default
    if isinstance(value, str) and value.startswith("@"):
        value = theme.get(value[1:], default)
    if isinstance(value, list) and value and isinstance(value[0], str):
        value = value[0]
    return to_rgb(value)


def resolve_colors(value: Any, theme: Dict[str, Any], default_key: str) -> List[RGB]:
    if value is None:
        value = "@" + default_key
    if isinstance(value, str) and value.startswith("@"):
        value = theme.get(value[1:], "#ffffff")
    if isinstance(value, str):
        value = [value]
    return [resolve_color(v, theme) for v in value]
