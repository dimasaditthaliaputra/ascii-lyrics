"""Draws the lyric lines of the active scene on top of the illustration.

Lines of a scene are laid out together up front, so the block never jumps
when a new line appears; unsung lines are just invisible. When the scene
changes, the outgoing lines fade out *after* their last line has finished
(never cut mid-line) while the new scene's lines type in at their position.

Per-character effects (all functions of the character's age):
``typewriter`` flash + cursor, ``fade``, ``rise`` (hops up from the row below),
``wave`` (a light ripple runs along the letters), ``drop`` (falls
in from the top with a bounce), ``pop``. ``*emphasis*`` words pulse in the
theme's emphasis colours, glow, and throw a few sparkles when they land.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from . import font
from .canvas import Canvas, Rect
from .color import RGB, gradient, mix, scale
from .fx import bounce, hash01
from .lyrics import LyricLine, LyricsManager
from .scenes import Scene, SceneManager
from .themes import resolve_color, resolve_colors

EXIT_FADE = 0.7


class _Seg:
    __slots__ = ("line", "a", "b", "x", "y", "big")

    def __init__(self, line, a, b, x, y, big):
        self.line, self.a, self.b, self.x, self.y, self.big = line, a, b, x, y, big


def wrap(text: str, width: int) -> List[Tuple[int, int]]:
    """Word-wrap, returning (start, end) index pairs into ``text``."""
    out, start, n = [], 0, len(text)
    while start < n:
        if n - start <= width:
            out.append((start, n))
            break
        cut = text.rfind(" ", start, start + width + 1)
        if cut <= start:
            cut = start + width
        out.append((start, cut))
        start = cut + 1 if cut < n and text[cut] == " " else cut
    return out or [(0, 0)]


class LyricsView:
    def __init__(self, lyrics: LyricsManager, scenes: SceneManager, unicode: bool,
                 color: bool = True):
        self.lyrics = lyrics
        self.scenes = scenes
        self.unicode = unicode
        self.color = color

    # --------------------------------------------------------------- layout
    def layout(self, lines: List[LyricLine], rect: Rect, align: str, t: float) -> List[_Seg]:
        width = max(8, rect.w - 2)
        blocks = []
        for line in lines:
            if line.big and font.measure(line.plain) <= width:
                blocks.append((line, [(0, len(line.plain))], True))
            else:
                blocks.append((line, wrap(line.plain, width), False))

        def height(bs, gap):
            return sum((font.HEIGHT if big else len(segs)) for _, segs, big in bs) + gap * max(0, len(bs) - 1)

        gap = 1
        if height(blocks, gap) > rect.h:
            gap = 0
        while height(blocks, gap) > rect.h and len(blocks) > 1:
            # keep the newest lines: drop the oldest finished one
            blocks.pop(0)
        y = rect.y + max(0, (rect.h - height(blocks, gap)) // 2)
        segs: List[_Seg] = []
        for line, parts, big in blocks:
            for a, b in parts:
                w = font.measure(line.plain[a:b]) if big else (b - a)
                if align == "left":
                    x = rect.x + 1
                elif align == "right":
                    x = rect.x2 - 1 - w
                else:
                    x = rect.x + (rect.w - w) // 2
                segs.append(_Seg(line, a, b, x, y, big))
                y += font.HEIGHT if big else 1
            y += gap
        return segs

    # ----------------------------------------------------------------- draw
    def draw(self, cv: Canvas, t: float, reserve_bottom: int = 0) -> None:
        mgr = self.scenes
        i = mgr.index_at(t)
        # outgoing group (previous scene), faded only after its last line ends
        if i > 0:
            prev_spec = mgr.specs[i - 1]
            prev_lines = self.lyrics.between(prev_spec.start, prev_spec.end)
            if prev_lines:
                fade_from = max(mgr.specs[i].start, prev_lines[-1].end)
                a = 1.0 - (t - fade_from) / EXIT_FADE
                if a > 0:
                    self._draw_group(cv, t, mgr.scene(i - 1), prev_lines, min(1.0, a), reserve_bottom)
        spec = mgr.specs[i]
        lines = self.lyrics.between(spec.start, spec.end)
        if lines and t >= lines[0].t - 0.05:
            self._draw_group(cv, t, mgr.scene(i), lines, 1.0, reserve_bottom)

    def _draw_group(self, cv: Canvas, t: float, scene: Scene, lines: List[LyricLine],
                    group_alpha: float, reserve_bottom: int) -> None:
        style = scene.spec.lyrics
        theme = scene.theme
        rect = scene.regions(cv.w, cv.h, reserve_bottom)["lyrics"]
        align = style.get("align", "center")
        segs = self.layout(lines, rect, align, t)
        if not segs:
            return
        if style.get("glass", True):
            started = [s for s in segs if s.line.t <= t]
            if started:
                x0 = min(s.x for s in segs) - 2
                x1 = max(s.x + (font.measure(s.line.plain[s.a:s.b]) if s.big else s.b - s.a)
                         for s in segs) + 2
                y0, y1 = segs[0].y - 1, max(s.y + (font.HEIGHT if s.big else 1) for s in segs) + 1
                k = float(style.get("glass_strength", 0.38)) * group_alpha
                k *= min(1.0, (t - lines[0].t + 0.3) / 0.8)
                glass = Rect(x0, y0, x1 - x0, y1 - y0)
                cv.darken_rect(glass, k, feather=2)
                if not self.color:
                    # without colour, dimming does nothing: clear texture glyphs instead
                    for y in range(max(0, glass.y), min(cv.h, glass.y2)):
                        for x in range(max(0, glass.x), min(cv.w, glass.x2)):
                            cv.ch[y][x] = " "
        pal = {
            "lyric": resolve_colors(style.get("colors"), theme, "lyric"),
            "emph": resolve_colors(style.get("emph"), theme, "emph"),
            "past": resolve_color(style.get("past", "@past"), theme),
            "sing": resolve_color(style.get("sing", "@sing"), theme),
            "glow": resolve_color(style.get("glow", "@glow"), theme),
        }
        default_effect = style.get("effect", "typewriter")
        top = rect.y
        # glows + sparkles first, so they never cover a neighbouring line's text
        for s in segs:
            if t >= s.line.t:
                self._emphasis_fx(cv, t, s, pal, group_alpha)
        for s in segs:
            line = s.line
            if t < line.t:
                continue
            eff = line.effect or default_effect
            if s.big:
                self._draw_big(cv, t, s, pal, eff, group_alpha, top)
            else:
                self._draw_seg(cv, t, s, pal, eff, group_alpha, top)

    # ---------------------------------------------------------------- lines
    def _char_color(self, line: LyricLine, i: int, t: float, frac: float, pal) -> Tuple[RGB, bool]:
        sung = line.word_at(t)
        if line.emph[i]:
            c = gradient(pal["emph"], 0.5 + 0.5 * math.sin(t * 4.0 + i * 0.35))
            bold = True
        else:
            c = gradient(pal["lyric"], (frac + t * 0.05) % 1.0 if len(pal["lyric"]) > 1 else 0)
            bold = False
        if sung is not None and sung.first <= i < sung.first + len(sung.text):
            c = mix(c, pal["sing"], 0.45)
            bold = True
        if t > line.end:
            c = mix(c, pal["past"], min(1.0, (t - line.end) / 0.8) * (0.4 if line.emph[i] else 0.75))
            bold = bold and line.emph[i]
        return c, bold

    def _draw_seg(self, cv, t, s: _Seg, pal, eff, galpha, top) -> None:
        line = s.line
        n = max(1, s.b - s.a)
        last_revealed = None
        for k, i in enumerate(range(s.a, s.b)):
            ch = line.plain[i]
            age = t - line.char_t[i]
            if age < 0:
                continue
            last_revealed = k
            if ch == " ":
                continue
            x, y = s.x + k, s.y
            col, bold = self._char_color(line, i, t, k / n, pal)
            a = galpha
            if eff == "fade":
                a *= min(1.0, age / 0.45)
            elif eff == "rise" and age < 0.16:
                y += 1  # a quick hop up from the row below
                a *= 0.4 + age / 0.16 * 0.6
            elif eff == "wave":
                # a light ripple travels along the line, crest on the newest letters
                rip = math.exp(-age * 2.5) * (0.5 + 0.5 * math.sin(age * 14.0))
                col = mix(col, (255, 255, 255), 0.7 * rip)
            elif eff == "drop" and age < 0.75:
                y = int(top + (s.y - top) * bounce(age / 0.75))
            elif eff == "pop" and age < 0.12:
                ch = "*"
            if eff in ("typewriter", "pop") and age < 0.14:
                col, bold = mix(col, (255, 255, 255), 0.8), True
            cv.put(x, y, ch, col, bold=bold, alpha=a)
        # blinking cursor while the line is still being sung
        if eff == "typewriter" and line.t <= t < line.reveal_end and last_revealed is not None \
                and last_revealed < s.b - s.a - 1 and int(t * 4) % 2 == 0:
            cv.put(s.x + last_revealed + 1, s.y, "▌" if self.unicode else "_",
                   pal["sing"], alpha=galpha * 0.8)

    def _emphasis_fx(self, cv, t, s: _Seg, pal, galpha) -> None:
        line = s.line
        for w in line.words:
            if not w.emph or not (s.a <= w.first < s.b):
                continue
            age = t - w.start
            if age < 0:
                continue
            if s.big:
                wlen = font.measure(w.text)
                wx = s.x + font.measure(line.plain[s.a:w.first] + " ") - 1 + wlen / 2.0
                wy = s.y + 2
            else:
                wlen = len(w.text)
                wx = s.x + (w.first - s.a) + wlen / 2.0
                wy = s.y
            pulse = 0.5 + 0.5 * math.sin(t * 4)
            fade = 1.0 if t < line.end else max(0.3, 1 - (t - line.end) / 2)
            cv.glow(wx, wy, wlen * 1.2 + 3, pal["glow"], (0.18 + 0.1 * pulse) * galpha * fade)
            if age < 1.3:
                seq = ("✦", "✧", "+", "·") if self.unicode else ("*", "+", "+", ".")
                for j in range(5):
                    h1, h2 = hash01(line.index, w.first, j), hash01(j, w.first, line.index + 3)
                    px = wx + (h1 - 0.5) * (wlen + 6)
                    py = wy + (-1 if h2 < 0.5 else 1) * ((3 if s.big else 1) + age * 1.5 * h2)
                    gi = min(len(seq) - 1, int(age / 1.3 * len(seq)))
                    cv.put(px, py, seq[gi], gradient(pal["emph"], h1), bold=True,
                           alpha=galpha * (1 - age / 1.3))

    def _draw_big(self, cv, t, s: _Seg, pal, eff, galpha, top) -> None:
        line = s.line
        block = "█" if self.unicode else "#"
        text = line.plain[s.a:s.b]
        for idx, dx, rows in font.layout(text):
            i = s.a + idx
            age = t - line.char_t[i]
            if age < 0:
                continue
            yoff = 0
            a = galpha
            if eff == "drop" and age < 0.8:
                yoff = int((top - s.y - font.HEIGHT) * (1 - bounce(age / 0.8)))
            elif eff == "fade":
                a *= min(1.0, age / 0.5)
            col, _ = self._char_color(line, i, t, idx / max(1, len(text)), pal)
            flash = max(0.0, 1 - age / 0.35)
            for ry, row in enumerate(rows):
                for rx, ch in enumerate(row):
                    if ch == " ":
                        continue
                    x, y = s.x + dx + rx, s.y + ry + yoff
                    cv.put(x + 1, y + 1, " ", (0, 0, 0), bg=scale(cv.get_bg(x + 1, y + 1), 0.45), alpha=a)
                    c = mix(scale(col, 1.0 - ry * 0.08), (255, 255, 255), flash * 0.8)
                    cv.put(x, y, block, c, bold=True, alpha=a)
