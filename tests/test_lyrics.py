"""Lyric timing: per-line timestamps, word timing, per-character reveal."""
import unittest

from lyricviz.lyrics import LyricLine, LyricsManager, parse_markup, syllables
from lyricviz.lyrics_view import wrap


class MarkupTest(unittest.TestCase):
    def test_emphasis_mask(self):
        plain, mask = parse_markup("a *bold* word")
        self.assertEqual(plain, "a bold word")
        self.assertEqual([i for i, m in enumerate(mask) if m], [2, 3, 4, 5])

    def test_escaped_asterisk(self):
        plain, mask = parse_markup(r"5 \* 5")
        self.assertEqual(plain, "5 * 5")
        self.assertFalse(any(mask))

    def test_syllables(self):
        self.assertEqual(syllables("intuition"), 4)
        self.assertEqual(syllables("line"), 1)
        self.assertEqual(syllables("Ohh"), 1)


class TimingTest(unittest.TestCase):
    def test_chars_revealed_within_line_and_monotonic(self):
        line = LyricLine(t=10.0, end=14.0, text="One two *three* four five")
        times = [t for c, t in zip(line.plain, line.char_t) if c != " "]
        self.assertEqual(times, sorted(times))
        self.assertGreaterEqual(times[0], 10.0)
        self.assertLessEqual(times[-1], line.reveal_end)
        self.assertLess(line.reveal_end, line.end + 1e-9)

    def test_explicit_word_times_are_respected(self):
        line = LyricLine(t=42.0, end=44.0, text="kiss me and I might",
                         word_times=[42.0, 42.35, 42.9, 43.2, 43.6])
        self.assertEqual([w.start for w in line.words], [42.0, 42.35, 42.9, 43.2, 43.6])
        self.assertAlmostEqual(line.char_t[line.words[3].first], 43.2)
        self.assertEqual(line.word_at(42.5).text, "me")

    def test_word_time_count_mismatch_is_an_error(self):
        with self.assertRaises(ValueError):
            LyricLine(t=0, end=2, text="two words", word_times=[0.0])

    def test_reveal_override(self):
        line = LyricLine(t=0.0, end=10.0, text="slow line", reveal=2.0)
        self.assertAlmostEqual(line.reveal_end, 2.0)
        self.assertLessEqual(max(line.char_t), 2.0)

    def test_individual_timing_not_static(self):
        a = LyricLine(t=0.0, end=2.0, text="same text here")
        b = LyricLine(t=5.0, end=11.0, text="same text here")
        span_a = a.char_t[-1] - a.char_t[0]
        span_b = b.char_t[-1] - b.char_t[0]
        self.assertGreater(span_b, span_a * 2)  # longer line -> slower typing

    def test_manager_lookup_and_overlap_warning(self):
        lines = [LyricLine(0, 2, "a"), LyricLine(1.5, 3, "b"), LyricLine(4, 5, "c")]
        m = LyricsManager(lines)
        self.assertEqual(m.current(0.5).plain, "a")
        self.assertIsNone(m.current(3.5))
        self.assertEqual([l.plain for l in m.between(1, 5)], ["b", "c"])
        self.assertEqual(len(m.validate()), 1)


class WrapTest(unittest.TestCase):
    def test_wrap_keeps_every_char_index(self):
        text = "You're looking like someone on the walls of a palace"
        parts = wrap(text, 16)
        self.assertTrue(all(b - a <= 16 for a, b in parts))
        rebuilt = " ".join(text[a:b] for a, b in parts)
        self.assertEqual(rebuilt, text)


if __name__ == "__main__":
    unittest.main()
