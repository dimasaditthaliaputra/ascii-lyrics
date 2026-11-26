#!/usr/bin/env python3
"""Render visualizer frames to PNG (for previews, READMEs and visual QA).

    python tools/frame_to_png.py drop_dead 12.5 30 44.9 --size 120x36 --out previews/

Draws each cell's background rectangle and glyph with a monospace font
(falls back to a symbol font for glyphs the monospace font lacks).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from lyricviz import layers  # noqa: E402,F401
from lyricviz.app import Visualizer  # noqa: E402
from lyricviz.cli import SONGS, parse_size  # noqa: E402
from lyricviz.config import load_song, resolve_song_path  # noqa: E402
from lyricviz.terminal import Capabilities  # noqa: E402

MONO = ["/System/Library/Fonts/Menlo.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "C:/Windows/Fonts/consola.ttf"]
SYMBOL = ["/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
          "/System/Library/Fonts/Apple Symbols.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def _font(paths, size):
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def render_png(cv, path: Path, cell_w=9, cell_h=18) -> None:
    mono = _font(MONO, 15)
    sym = _font(SYMBOL, 14)
    img = Image.new("RGB", (cv.w * cell_w, cv.h * cell_h))
    d = ImageDraw.Draw(img)
    for y in range(cv.h):
        for x in range(cv.w):
            x0, y0 = x * cell_w, y * cell_h
            d.rectangle([x0, y0, x0 + cell_w - 1, y0 + cell_h - 1], fill=cv.bg[y][x])
            ch = cv.ch[y][x]
            if ch == " ":
                continue
            if ch == "▀":  # draw half blocks exactly
                d.rectangle([x0, y0, x0 + cell_w - 1, y0 + cell_h // 2 - 1], fill=cv.fg[y][x])
                continue
            if ch == "█":
                d.rectangle([x0, y0, x0 + cell_w - 1, y0 + cell_h - 1], fill=cv.fg[y][x])
                continue
            f = mono if ord(ch) < 0x2500 or ch in "─│╭╮╰╯═║╔╗╚╝╱╲▂▄▆▌▏░▒▓" else sym
            d.text((x0, y0 + 1), ch, font=f, fill=cv.fg[y][x])
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("song")
    ap.add_argument("times", nargs="+", type=float)
    ap.add_argument("--size", type=parse_size, default=(120, 36))
    ap.add_argument("--out", default="previews")
    ap.add_argument("--hud", action="store_true")
    args = ap.parse_args()
    song = load_song(resolve_song_path(args.song, SONGS))
    viz = Visualizer(song, Capabilities("truecolor", True))
    viz.hud = args.hud
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    w, h = args.size
    for t in args.times:
        for k in range(45, 0, -1):  # warm up particles like a live run
            viz.render(max(0.0, t - k / 30.0), w, h)
        cv = viz.render(t, w, h)
        p = out / f"{Path(song.folder).name}_{t:05.1f}.png"
        render_png(cv, p)
        print(p)


if __name__ == "__main__":
    main()
