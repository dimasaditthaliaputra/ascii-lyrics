"""Terminal capability detection and the flicker-free frame writer.

`rich` is used for what it is great at: detecting the colour system and
down-converting truecolor to 256/16 colours. The per-frame write path is a
hand-rolled diff renderer, because redrawing a full rich ``Live`` layout 30
times a second is far too slow for cell-level animation:

* only rows that changed since the previous frame are re-emitted,
* consecutive cells with the same style share one escape sequence,
* the whole frame is wrapped in "synchronized output" (DEC mode 2026) so
  terminals that support it swap the frame atomically (no tearing).
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from rich.color import Color, ColorSystem
from rich.console import Console

from .canvas import Canvas
from .color import RGB

# Single-width Unicode glyphs we use -> ASCII stand-ins.
ASCII_FALLBACK = {
    "❀": "*", "✿": "*", "❁": "*", "✾": "*", "❃": "*", "❦": "&", "✽": "*",
    "✦": "+", "✧": "+", "⋆": "*", "✶": "*", "★": "*", "☆": "*", "✺": "*",
    "·": ".", "•": "o", "∙": ".", "°": "o", "˚": "o", "◦": "o", "○": "o", "●": "@",
    "♥": "<", "♡": "<",
    "─": "-", "━": "=", "│": "|", "┃": "|", "╭": ".", "╮": ".", "╰": "'", "╯": "'",
    "┌": "+", "┐": "+", "└": "+", "┘": "+", "═": "=", "║": "|", "╔": "+", "╗": "+",
    "╚": "+", "╝": "+", "╱": "/", "╲": "\\", "┼": "+", "├": "+", "┤": "+",
    "█": "#", "▓": "#", "▒": "%", "░": ":", "▀": '"', "▄": "_", "▌": "|", "▐": "|",
    "▏": "|", "▂": "_", "▃": "_", "▅": "=", "▆": "=", "▇": "#",
    "‿": "_", "⁀": "^", "ʚ": "{", "ɞ": "}", "~": "~", "≈": "~", "∿": "~",
    "◠": "^", "◡": "u", "⌒": "^", "♪": "d", "♫": "d", "❚": "|", "▲": "^", "▼": "v",
    "…": ".", "’": "'", "‘": "'", "“": '"', "”": '"', "—": "-", "–": "-",
}
_FALLBACK_TABLE = str.maketrans(ASCII_FALLBACK)


@dataclass
class Capabilities:
    color_system: Optional[str]  # "truecolor" | "256" | "standard" | None
    unicode: bool

    @property
    def color(self) -> bool:
        return self.color_system is not None


def detect(force_color: Optional[str] = None, force_ascii: bool = False) -> Capabilities:
    console = Console(force_terminal=True if force_color else None)
    system = console.color_system  # honours NO_COLOR / TERM / COLORTERM
    if force_color == "none" or os.environ.get("NO_COLOR"):
        system = None
    elif force_color:
        system = force_color
    if system == "windows":
        system = "standard"
    enc = (getattr(sys.stdout, "encoding", None) or "").lower()
    unicode_ok = not force_ascii and ("utf" in enc or os.environ.get("LYRICVIZ_UNICODE") == "1")
    return Capabilities(system, unicode_ok)


def terminal_size(default: Tuple[int, int] = (120, 36)) -> Tuple[int, int]:
    sz = shutil.get_terminal_size(default)
    return sz.columns, sz.lines


class FrameWriter:
    def __init__(self, caps: Capabilities, stream=None):
        self.caps = caps
        self.out = stream or sys.stdout
        self._prev: List[str] = []
        self._style_cache: Dict[Tuple[RGB, RGB, bool], str] = {}
        system = caps.color_system
        self._downgrade = {
            "256": ColorSystem.EIGHT_BIT,
            "standard": ColorSystem.STANDARD,
        }.get(system or "")

    # ------------------------------------------------------------ lifecycle
    def enter(self) -> None:
        self.out.write("\x1b[?1049h\x1b[?25l\x1b[2J")
        self.out.flush()
        self._prev = []

    def exit(self) -> None:
        self.out.write("\x1b[0m\x1b[2J\x1b[?25h\x1b[?1049l")
        self.out.flush()

    def invalidate(self) -> None:
        self._prev = []

    # -------------------------------------------------------------- styling
    def _sgr(self, fg: RGB, bg: RGB, bold: bool) -> str:
        key = (fg, bg, bold)
        s = self._style_cache.get(key)
        if s is not None:
            return s
        if self.caps.color_system is None:
            s = "\x1b[0;1m" if bold else "\x1b[0m"
        elif self._downgrade is None:
            s = "\x1b[0;%s38;2;%d;%d;%d;48;2;%d;%d;%dm" % (
                "1;" if bold else "", fg[0], fg[1], fg[2], bg[0], bg[1], bg[2])
        else:
            f = Color.from_rgb(*fg).downgrade(self._downgrade).get_ansi_codes(True)
            b = Color.from_rgb(*bg).downgrade(self._downgrade).get_ansi_codes(False)
            s = "\x1b[0;%s%sm" % ("1;" if bold else "", ";".join(f + b))
        if len(self._style_cache) > 60000:
            self._style_cache.clear()
        self._style_cache[key] = s
        return s

    def _quant(self, c: RGB) -> RGB:
        # Quantise slightly so near-identical gradient colours share styles.
        return (c[0] & 0xFC, c[1] & 0xFC, c[2] & 0xFC)

    def render_rows(self, cv: Canvas) -> List[str]:
        rows: List[str] = []
        q = self._quant
        sgr = self._sgr
        for y in range(cv.h):
            chs, fgs, bgs, bolds = cv.ch[y], cv.fg[y], cv.bg[y], cv.bold[y]
            parts: List[str] = []
            last = None
            for x in range(cv.w):
                key = (q(fgs[x]), q(bgs[x]), bolds[x])
                if key != last:
                    parts.append(sgr(*key))
                    last = key
                parts.append(chs[x])
            row = "".join(parts)
            if not self.caps.unicode:
                row = row.translate(_FALLBACK_TABLE).encode("ascii", "replace").decode("ascii")
            rows.append(row)
        return rows

    def draw(self, cv: Canvas) -> None:
        rows = self.render_rows(cv)
        prev = self._prev
        buf = ["\x1b[?2026h"]
        for y, row in enumerate(rows):
            if y < len(prev) and prev[y] == row:
                continue
            buf.append("\x1b[%d;1H" % (y + 1))
            buf.append(row)
        buf.append("\x1b[0m\x1b[?2026l")
        if len(buf) > 2:
            self.out.write("".join(buf))
            self.out.flush()
        self._prev = rows

    def to_ansi(self, cv: Canvas) -> str:
        """Whole frame as a printable ANSI string (used by --snapshot)."""
        return "\n".join(r + "\x1b[0m" for r in self.render_rows(cv))
