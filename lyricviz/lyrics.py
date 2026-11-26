"""Lyric timing model.

Every line has its own start time and end time. Inside a line, each *word*
gets a start time (explicit from the config, or estimated from syllable
counts), and each *character* gets a reveal time inside its word. The
renderer only ever asks "how old is this character at time t?", so all the
typing / fading / dropping effects stay perfectly locked to the clock.
"""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

_VOWELS = re.compile(r"[aeiouy]+", re.I)


def syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 1
    n = len(_VOWELS.findall(w))
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1  # silent e: "line", "like"
    return max(1, n)


def parse_markup(text: str):
    """``*word*`` marks emphasis, ``\\*`` is a literal asterisk.

    Returns (plain_text, emphasis_mask).
    """
    out: List[str] = []
    mask: List[bool] = []
    emph = False
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text) and text[i + 1] == "*":
            out.append("*")
            mask.append(emph)
            i += 2
            continue
        if c == "*":
            emph = not emph
            i += 1
            continue
        out.append(c)
        mask.append(emph)
        i += 1
    return "".join(out), mask


@dataclass
class Word:
    text: str
    first: int  # index of first char in the line's plain text
    emph: bool
    start: float = 0.0
    end: float = 0.0


@dataclass
class LyricLine:
    t: float
    end: float
    text: str
    reveal: Optional[float] = None
    effect: Optional[str] = None
    word_times: Optional[Sequence[float]] = None
    big: bool = False
    style: Dict[str, Any] = field(default_factory=dict)
    index: int = 0

    plain: str = field(init=False, default="")
    emph: List[bool] = field(init=False, default_factory=list)
    words: List[Word] = field(init=False, default_factory=list)
    char_t: List[float] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        if self.end <= self.t:
            raise ValueError(f"lyric line {self.text!r}: end ({self.end}) must be after t ({self.t})")
        self.plain, self.emph = parse_markup(self.text)
        self._split_words()
        self._time_words()
        self._time_chars()

    # --------------------------------------------------------------- timing
    @property
    def duration(self) -> float:
        return self.end - self.t

    @property
    def reveal_end(self) -> float:
        dur = self.duration
        r = self.reveal if self.reveal is not None else dur * 0.85
        return self.t + max(0.05, min(r, dur))

    def _split_words(self) -> None:
        for m in re.finditer(r"\S+", self.plain):
            self.words.append(Word(m.group(), m.start(), any(self.emph[m.start():m.end()])))

    def _time_words(self) -> None:
        words = self.words
        if not words:
            return
        if self.word_times:
            times = [float(x) for x in self.word_times]
            if len(times) != len(words):
                raise ValueError(
                    f"lyric line {self.text!r}: {len(times)} word times for {len(words)} words")
            if any(b < a for a, b in zip(times, times[1:])):
                raise ValueError(f"lyric line {self.text!r}: word times must not decrease")
            for w, s in zip(words, times):
                w.start = s
        else:
            weights = [syllables(w.text) + 0.35 for w in words]
            span = self.reveal_end - self.t
            total = sum(weights)
            acc = self.t
            for w, k in zip(words, weights):
                w.start = acc
                acc += span * k / total
        for a, b in zip(words, words[1:]):
            a.end = b.start
        words[-1].end = max(words[-1].start + 0.05, self.reveal_end)

    def _time_chars(self) -> None:
        n = len(self.plain)
        self.char_t = [self.t] * n
        for w in self.words:
            L = len(w.text)
            # characters type out over the first 60% of the word, so the
            # word is fully visible while it is still being sung
            span = max(0.03, (w.end - w.start) * 0.6)
            for k in range(L):
                self.char_t[w.first + k] = w.start + span * (k / max(1, L))
        # spaces inherit the previous char's time
        last = self.t
        for i, c in enumerate(self.plain):
            if c == " ":
                self.char_t[i] = last
            else:
                last = self.char_t[i]

    def word_at(self, t: float) -> Optional[Word]:
        for w in self.words:
            if w.start <= t < w.end:
                return w
        return None

    def word_index_of_char(self, i: int) -> int:
        for k, w in enumerate(self.words):
            if w.first <= i < w.first + len(w.text):
                return k
        return -1


class LyricsManager:
    """Lookup structure over the sorted lyric lines."""

    def __init__(self, lines: Sequence[LyricLine]):
        self.lines = sorted(lines, key=lambda l: l.t)
        for i, l in enumerate(self.lines):
            l.index = i
        self._starts = [l.t for l in self.lines]

    def current(self, t: float) -> Optional[LyricLine]:
        i = bisect.bisect_right(self._starts, t) - 1
        if i >= 0 and self.lines[i].t <= t < self.lines[i].end:
            return self.lines[i]
        return None

    def between(self, start: float, end: float) -> List[LyricLine]:
        lo = bisect.bisect_left(self._starts, start)
        hi = bisect.bisect_left(self._starts, end)
        return self.lines[lo:hi]

    def validate(self) -> List[str]:
        warns: List[str] = []
        for a, b in zip(self.lines, self.lines[1:]):
            if b.t < a.end - 1e-6:
                warns.append(f"line {a.index + 1} {a.plain!r} overlaps line {b.index + 1} "
                             f"(ends {a.end:.2f}s, next starts {b.t:.2f}s)")
        for l in self.lines:
            if l.words and l.words[0].start < l.t - 1e-6:
                warns.append(f"line {l.index + 1}: first word starts before the line")
            if l.words and l.words[-1].start > l.end:
                warns.append(f"line {l.index + 1}: last word starts after the line ends")
        return warns
