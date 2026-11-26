"""Visualizer core + the real-time loop.

``Visualizer.render(t, w, h)`` is a pure "what does the screen look like at
song time t" call. The live loop, ``--snapshot`` and the tests all use it,
so what you test is exactly what you see.

The live loop is an asyncio task: every frame reads the clock, renders, and
awaits only the *remaining* frame budget. Nothing ever blocks for a whole
lyric line, so all animations keep moving together.
"""
from __future__ import annotations

import asyncio
import signal
import sys
import time
from typing import List, Optional

from .artwork import ArtworkSource
from .audio import AudioPlayer
from .canvas import Canvas
from .clock import Clock
from .color import mix, scale
from .config import SongConfig
from .keys import KeyReader
from .lyrics import LyricsManager
from .lyrics_view import LyricsView
from .scenes import SceneManager
from .terminal import Capabilities, FrameWriter, terminal_size
from .themes import resolve_color

MIN_W, MIN_H = 60, 18


def fmt_time(t: float) -> str:
    t = max(0, int(t))
    return f"{t // 60}:{t % 60:02d}"


class Visualizer:
    def __init__(self, song: SongConfig, caps: Capabilities):
        self.song = song
        self.caps = caps
        art_path = song.artwork
        self.artwork = ArtworkSource(art_path, float(song.artwork_opts.get("contrast", 1.35)),
                                     float(song.artwork_opts.get("saturation", 1.25))) \
            if song.artwork_opts.get("enabled", True) else None
        self.lyrics = LyricsManager(song.lines)
        self.scenes = SceneManager(song.scenes, caps.unicode, self.artwork, song)
        self.view = LyricsView(self.lyrics, self.scenes, caps.unicode, caps.color)
        self.canvas: Optional[Canvas] = None
        self.hud = True
        self.paused = False
        self.toast: Optional[tuple] = None  # (text, until)

    def _canvas(self, w: int, h: int) -> Canvas:
        if self.canvas is None or (self.canvas.w, self.canvas.h) != (w, h):
            self.canvas = Canvas(w, h)
        return self.canvas

    def render(self, t: float, w: int, h: int) -> Canvas:
        cv = self._canvas(w, h)
        if w < MIN_W or h < MIN_H:
            cv.clear()
            msg = f"enlarge terminal to {MIN_W}x{MIN_H} (now {w}x{h})"
            cv.text(max(0, (w - len(msg)) // 2), h // 2, msg[:w], (255, 180, 210), bold=True)
            return cv
        reserve = 1 if self.hud else 0
        cur, _, _ = self.scenes.render(cv, t, reserve)
        self.view.draw(cv, t, reserve)
        if self.hud:
            self._draw_hud(cv, t, cur)
        if self.paused:
            label = " ❚❚ paused " if self.caps.unicode else " || paused "
            cv.text((w - len(label)) // 2, 1, label, (255, 255, 255), bg=(60, 30, 60), bold=True)
        if self.toast and time.perf_counter() < self.toast[1]:
            txt = f" {self.toast[0]} "
            cv.text((w - len(txt)) // 2, 2, txt, (255, 240, 250), bg=(40, 20, 50))
        return cv

    def _draw_hud(self, cv: Canvas, t: float, scene) -> None:
        y = cv.h - 1
        accent = resolve_color("@accent", scene.theme)
        dim = (110, 100, 120)
        for x in range(cv.w):
            cv.put(x, y, " ", dim, bg=scale(cv.get_bg(x, y), 0.35))
        uni = self.caps.unicode
        left = f" {'♪' if uni else '>'} {self.song.title} — {self.song.artist}  "
        right = f"  {fmt_time(t)} / {fmt_time(self.song.duration)}  [{scene.spec.name}]  " \
                f"space pause  {'←→' if uni else '<>'} seek  h hud  q quit "
        cv.text(0, y, left, mix(accent, (255, 255, 255), 0.3), bold=True)
        bar_x0 = len(left)
        bar_w = max(4, cv.w - len(left) - len(right))
        filled = int(bar_w * min(1.0, t / max(0.1, self.song.duration)))
        for i in range(bar_w):
            ch = ("━" if i < filled else "─") if uni else ("=" if i < filled else "-")
            cv.put(bar_x0 + i, y, ch, accent if i < filled else dim, bold=i < filled)
        if len(right) < cv.w - len(left):
            cv.text(cv.w - len(right), y, right, dim)


class LiveRunner:
    def __init__(self, viz: Visualizer, fps: float = 30.0, start: float = 0.0,
                 until: Optional[float] = None, loop: bool = False, speed: float = 1.0,
                 audio: Optional[AudioPlayer] = None):
        self.viz = viz
        self.fps = fps
        self.until = until if until is not None else viz.song.duration
        self.loop = loop
        self.clock = Clock(start, speed)
        self.audio = audio
        self.writer = FrameWriter(viz.caps)
        self.running = True
        self.frame_times: List[float] = []

    def toast(self, text: str) -> None:
        self.viz.toast = (text, time.perf_counter() + 1.5)

    def seek(self, t: float) -> None:
        t = min(max(0.0, t), self.viz.song.duration - 0.05)
        self.clock.seek(t)
        self.viz.scenes.reset()
        if self.audio and not self.clock.paused:
            self.audio.play(t)
        self.toast(f"{fmt_time(t)}")

    def handle(self, key: str) -> None:
        t = self.clock.now()
        if key in ("q", "Q", "esc"):
            self.running = False
        elif key == " ":
            self.clock.toggle()
            self.viz.paused = self.clock.paused
            if self.audio:
                self.audio.pause() if self.clock.paused else self.audio.resume()
        elif key == "right":
            self.seek(t + 5)
        elif key == "left":
            self.seek(t - 5)
        elif key in ("n", "p"):
            i = self.viz.scenes.index_at(t) + (1 if key == "n" else -1)
            i = max(0, min(len(self.viz.scenes.specs) - 1, i))
            self.seek(self.viz.scenes.specs[i].start)
            self.toast(self.viz.scenes.specs[i].name)
        elif key == "h":
            self.viz.hud = not self.viz.hud
        elif key == "r":
            self.seek(0.0)

    async def _loop(self, keys: KeyReader) -> None:
        frame = 1.0 / self.fps
        last_size = None
        if self.audio:
            self.audio.play(self.clock.now())
        while self.running:
            t0 = time.perf_counter()
            for k in keys.read():
                self.handle(k)
            w, h = terminal_size()
            if (w, h) != last_size:
                self.writer.invalidate()  # resize: full repaint
                sys.stdout.write("\x1b[2J")
                last_size = (w, h)
            t = self.clock.now()
            if t >= self.until:
                if self.loop:
                    self.seek(0.0)
                    continue
                break
            cv = self.viz.render(t, w, h)
            self.writer.draw(cv)
            spent = time.perf_counter() - t0
            self.frame_times.append(spent)
            await asyncio.sleep(max(0.001, frame - spent))

    def run(self) -> None:
        def _stop(*_):
            self.running = False
        try:
            signal.signal(signal.SIGTERM, _stop)
        except (ValueError, AttributeError):
            pass
        with KeyReader() as keys:
            self.writer.enter()
            try:
                asyncio.run(self._loop(keys))
            except KeyboardInterrupt:
                pass
            finally:
                if self.audio:
                    self.audio.stop()
                self.writer.exit()
