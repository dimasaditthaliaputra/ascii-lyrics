"""Rendering: every frame of every song, multiple sizes, colour/Unicode fallbacks,
plus a frame-time budget check."""
import io
import time
import unittest
from pathlib import Path

from lyricviz import layers  # noqa: F401
from lyricviz.app import MIN_H, MIN_W, Visualizer
from lyricviz.config import load_song
from lyricviz.terminal import Capabilities, FrameWriter

ROOT = Path(__file__).resolve().parent.parent
SONGS = sorted((ROOT / "songs").glob("*/song.yaml"))


def sweep(viz, w, h, step=0.25):
    t = 0.0
    while t < viz.song.duration:
        cv = viz.render(t, w, h)
        yield t, cv
        t += step


class RenderTest(unittest.TestCase):
    def test_all_songs_all_sizes_render(self):
        for path in SONGS:
            song = load_song(path)
            for w, h in ((MIN_W, MIN_H), (100, 30), (160, 48)):
                viz = Visualizer(song, Capabilities("truecolor", True))
                for t, cv in sweep(viz, w, h, 0.5):
                    self.assertEqual((cv.w, cv.h), (w, h))
                    for row in cv.ch:
                        self.assertEqual(len(row), w)
                        for c in row:
                            self.assertEqual(len(c), 1, f"{path.parent.name} t={t} {w}x{h}: {c!r}")

    def test_too_small_terminal_shows_message(self):
        viz = Visualizer(load_song(SONGS[0]), Capabilities("truecolor", True))
        cv = viz.render(5.0, 40, 10)
        self.assertIn("enlarge", "".join("".join(r) for r in cv.ch))

    def test_ascii_and_no_color_fallbacks(self):
        song = load_song(ROOT / "songs" / "drop_dead" / "song.yaml")
        for caps in (Capabilities(None, False), Capabilities("256", False), Capabilities("standard", True)):
            viz = Visualizer(song, caps)
            buf = io.StringIO()
            fw = FrameWriter(caps, stream=buf)
            for t in (3.0, 14.0, 21.0, 30.0, 40.0, 45.0, 55.0):
                fw.draw(viz.render(t, 100, 30))
            out = buf.getvalue()
            if not caps.unicode:
                out.encode("ascii")  # raises if any non-ASCII glyph slipped through
            if caps.color_system is None:
                self.assertNotIn("38;2;", out)
            if caps.color_system == "256":
                self.assertNotIn("38;2;", out)
                self.assertIn("38;5;", out)

    def test_lyrics_appear_on_time(self):
        song = load_song(ROOT / "songs" / "drop_dead" / "song.yaml")
        viz = Visualizer(song, Capabilities(None, True))
        viz.hud = False
        for line in song.lines:
            if line.big:
                continue
            first_word = line.plain.split()[0]
            before = "\n".join("".join(r) for r in viz.render(line.t - 0.2, 120, 36).ch)
            after = "\n".join("".join(r) for r in viz.render(line.reveal_end + 0.3, 120, 36).ch)
            self.assertIn(line.plain, after, f"line not fully shown after reveal: {line.plain}")
            self.assertNotIn(line.plain, before, f"line shown too early: {line.plain}")
            self.assertTrue(first_word)

    def test_frame_budget(self):
        song = load_song(ROOT / "songs" / "drop_dead" / "song.yaml")
        viz = Visualizer(song, Capabilities("truecolor", True))
        fw = FrameWriter(viz.caps, stream=io.StringIO())
        costs = []
        for t, _ in zip([i / 30 for i in range(0, int(song.duration * 30), 3)], range(10 ** 9)):
            t0 = time.perf_counter()
            fw.draw(viz.render(t, 120, 36))
            costs.append(time.perf_counter() - t0)
        costs.sort()
        median = costs[len(costs) // 2]
        self.assertLess(median, 1 / 30, f"median frame {median * 1000:.1f} ms exceeds 30 fps budget")


if __name__ == "__main__":
    unittest.main()
