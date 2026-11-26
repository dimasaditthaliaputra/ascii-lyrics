"""Scene switching, layouts, transitions and config validation."""
import unittest
from pathlib import Path

from lyricviz import layers  # noqa: F401
from lyricviz.canvas import Canvas
from lyricviz.config import load_song, validate
from lyricviz.scenes import SceneManager, SceneSpec, compute_layout
from lyricviz.transitions import MASKS, blend

ROOT = Path(__file__).resolve().parent.parent
SONGS = sorted((ROOT / "songs").glob("*/song.yaml"))


class LayoutTest(unittest.TestCase):
    def test_sides_alternate_and_stay_inside(self):
        for w, h in ((60, 18), (120, 36), (220, 60)):
            left = compute_layout(w, h, "left")
            right = compute_layout(w, h, "right")
            self.assertLess(left["lyrics"].x, left["art"].x)
            self.assertGreater(right["lyrics"].x, right["art"].x)
            for regions in (left, right, compute_layout(w, h, "center"), compute_layout(w, h, "top")):
                for r in regions.values():
                    self.assertGreaterEqual(r.x, 0)
                    self.assertLessEqual(r.x2, w)
                    self.assertLessEqual(r.y2, h)


class SceneManagerTest(unittest.TestCase):
    def setUp(self):
        specs = [SceneSpec("a", 0, 10), SceneSpec("b", 10, 20, transition={"type": "wipe", "duration": 2}),
                 SceneSpec("c", 20, 30, transition={"type": "cut"})]
        self.mgr = SceneManager(specs, unicode=True)

    def test_scene_at_boundaries(self):
        self.assertEqual(self.mgr.index_at(0), 0)
        self.assertEqual(self.mgr.index_at(9.999), 0)
        self.assertEqual(self.mgr.index_at(10.0), 1)
        self.assertEqual(self.mgr.index_at(99), 2)

    def test_transition_progress(self):
        self.assertEqual(self.mgr.transition_state(11.0), (1, 0, 0.5))
        self.assertEqual(self.mgr.transition_state(12.5), (1, None, 1.0))
        self.assertEqual(self.mgr.transition_state(20.1), (2, None, 1.0))  # cut

    def test_render_through_transition(self):
        cv = Canvas(80, 24)
        for t in (9.9, 10.0, 10.5, 11.9, 12.1):
            cur, prev, p = self.mgr.render(cv, t)
            self.assertEqual(cur.spec.name, "b" if t >= 10 else "a")

    def test_blend_endpoints(self):
        a, b, out = Canvas(20, 6), Canvas(20, 6), Canvas(20, 6)
        a.text(0, 0, "A" * 20)
        b.text(0, 0, "B" * 20)
        for kind in list(MASKS) + ["fade", "flash"]:
            blend(a, b, out, kind, 0.0, (255, 0, 0), True)
            self.assertEqual(out.ch[0][5], "A", kind)
            blend(a, b, out, kind, 1.0, (255, 0, 0), True)
            self.assertEqual(out.ch[0][5], "B", kind)


class BundledSongsTest(unittest.TestCase):
    def test_bundled_songs_validate_cleanly(self):
        self.assertTrue(SONGS)
        for path in SONGS:
            song = load_song(path)
            self.assertEqual(validate(song), [], path)
            # every lyric line belongs to exactly one scene and is not cut by a boundary
            for line in song.lines:
                owners = [s for s in song.scenes if s.start <= line.t < s.end]
                self.assertEqual(len(owners), 1)
                self.assertLessEqual(line.end, owners[0].end + 1e-6, f"{path.parent.name}: {line.plain}")


if __name__ == "__main__":
    unittest.main()
