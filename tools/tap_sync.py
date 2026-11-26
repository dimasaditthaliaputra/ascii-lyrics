#!/usr/bin/env python3
"""Record lyric timestamps by tapping along to the song.

    python tools/tap_sync.py drop_dead            # tap, then review the result
    python tools/tap_sync.py drop_dead --write    # ... and update song.yaml
    python tools/tap_sync.py drop_dead --from 5   # re-tap from line 5 onward

Press SPACE the moment each line starts being sung. With an ``audio:`` file in
the song config (and pygame-ce installed) the song plays after a countdown.
Without audio, play the song anywhere else and press SPACE exactly when it
starts: that tap marks 0.00s.

Keys:  SPACE tap   u undo last tap   s skip line (keep its time)   q finish

What gets rewritten (only with --write; a .bak copy is kept):
  * ``t:`` of every tapped line,
  * ``end:`` of a tapped line -> next line's start minus ``defaults.gap``
    (``dur:`` lines keep their duration),
  * ``words: [...]`` explicit word times shift along with their line,
  * each scene's ``start:`` moves with the first line of that scene, so a
    scene boundary never ends up in the middle of a line.
Comments and formatting of the file are left untouched.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from lyricviz.audio import AudioPlayer  # noqa: E402
from lyricviz.cli import SONGS  # noqa: E402
from lyricviz.config import ConfigError, load_song, resolve_song_path, validate  # noqa: E402
from lyricviz.keys import KeyReader  # noqa: E402

NUM = r"-?\d+(?:\.\d+)?"


# ----------------------------------------------------------------- yaml text
def section_entries(text: str, key: str) -> List[Tuple[int, int]]:
    """(start, end) character spans of the top-level list items under ``key:``."""
    m = re.search(rf"^{key}:\s*$", text, re.M)
    if not m:
        return []
    nxt = re.search(r"^\S", text[m.end():], re.M)
    sec_end = m.end() + nxt.start() if nxt else len(text)
    body_start = m.end()
    items = [im for im in re.finditer(r"^( *)- ", text[body_start:sec_end], re.M)]
    if not items:
        return []
    indent = min(len(im.group(1)) for im in items)
    starts = [body_start + im.start() for im in items if len(im.group(1)) == indent]
    return [(s, e) for s, e in zip(starts, starts[1:] + [sec_end])]


def fmt(v: float) -> str:
    return f"{v:.2f}"


def rewrite(text: str, line_updates: Dict[int, dict], scene_starts: Dict[int, float]) -> str:
    """Apply new timings to the YAML text, preserving everything else.

    ``line_updates``: raw lyric index -> {"t", "end"?, "delta"}.
    ``scene_starts``: raw scene index -> new start.
    """
    edits: List[Tuple[int, int, str]] = []
    for i, (s, e) in enumerate(section_entries(text, "lyrics")):
        up = line_updates.get(i)
        if not up:
            continue
        chunk = text[s:e]
        chunk = re.sub(rf"(\bt:\s*){NUM}", lambda m: m.group(1) + fmt(up["t"]), chunk, count=1)
        if "end" in up:
            chunk = re.sub(rf"(\bend:\s*){NUM}", lambda m: m.group(1) + fmt(up["end"]), chunk, count=1)

        def shift_words(m):
            vals = [float(v) + up["delta"] for v in re.findall(NUM, m.group(2))]
            return m.group(1) + ", ".join(fmt(v) for v in vals) + m.group(3)
        chunk = re.sub(r"(\bwords:\s*\[)([^\]]*)(\])", shift_words, chunk, count=1)
        edits.append((s, e, chunk))
    for i, (s, e) in enumerate(section_entries(text, "scenes")):
        if i not in scene_starts:
            continue
        chunk = re.sub(rf"(\bstart:\s*){NUM}", lambda m: m.group(1) + fmt(scene_starts[i]),
                       text[s:e], count=1)
        edits.append((s, e, chunk))
    for s, e, chunk in sorted(edits, reverse=True):
        text = text[:s] + chunk + text[e:]
    return text


# ------------------------------------------------------------------- timing
def plan(raw_lines: List[dict], raw_scenes: List[dict], taps: Dict[int, float], gap: float):
    """Turn taps into new line times and scene starts."""
    old_t = [float(l["t"]) for l in raw_lines]
    new_t = [taps.get(i, old_t[i]) for i in range(len(raw_lines))]

    # scenes first: each follows the first line it contains
    starts: Dict[int, float] = {}
    scenes = sorted(range(len(raw_scenes)), key=lambda k: float(raw_scenes[k].get("start", 0)))
    old_starts = [float(raw_scenes[k].get("start", 0)) for k in scenes]
    new_starts = list(old_starts)
    for n in range(1, len(scenes)):
        s0 = old_starts[n]
        s1 = old_starts[n + 1] if n + 1 < len(scenes) else float("inf")
        firsts = [i for i in range(len(raw_lines)) if s0 <= old_t[i] < s1]
        if not firsts:
            # a scene without lyrics keeps its distance to the previous scene
            new_starts[n] = max(new_starts[n - 1] + 0.5, s0 + (new_starts[n - 1] - old_starts[n - 1]))
        else:
            first = min(firsts, key=lambda i: old_t[i])
            lead = old_t[first] - s0  # keep the same run-up before the first line
            new_starts[n] = min(max(new_starts[n - 1] + 0.5, new_t[first] - lead), new_t[first])
        if abs(new_starts[n] - s0) > 1e-9:
            starts[scenes[n]] = new_starts[n]

    def scene_of(i: int) -> int:
        n = 0
        while n + 1 < len(old_starts) and old_t[i] >= old_starts[n + 1]:
            n += 1
        return n

    order = sorted(range(len(raw_lines)), key=lambda i: new_t[i])
    updates: Dict[int, dict] = {}
    for pos, i in enumerate(order):
        if i not in taps:
            continue
        up = {"t": new_t[i], "delta": new_t[i] - old_t[i]}
        if "end" in raw_lines[i]:
            old_dur = float(raw_lines[i]["end"]) - old_t[i]
            end = new_t[order[pos + 1]] - gap if pos + 1 < len(order) else new_t[i] + old_dur
            n = scene_of(i)
            if n + 1 < len(new_starts):  # never run into the next scene
                end = min(end, new_starts[n + 1] - 0.05)
            up["end"] = max(new_t[i] + 0.3, end)
        updates[i] = up
    return updates, starts


# -------------------------------------------------------------------- tapping
def tap_session(song, raw_lines, start_index: int, use_audio: bool) -> Dict[int, float]:
    order = sorted(range(len(raw_lines)), key=lambda i: float(raw_lines[i]["t"]))
    order = order[start_index:]
    if not order:
        return {}
    plain = {i: str(raw_lines[i]["text"]).replace("*", "") for i in order}
    out = sys.stdout
    audio = None
    if use_audio and song.audio:
        audio = AudioPlayer(song.audio, song.audio_offset)
        if audio.error:
            print(f"  ! {audio.error} - continuing without audio")
            audio = None
    # start a few seconds before the first line we re-tap
    t_begin = max(0.0, float(raw_lines[order[0]]["t"]) - 4.0) if start_index else 0.0
    taps: Dict[int, float] = {}
    with KeyReader() as keys:
        if audio:
            for n in (3, 2, 1):
                out.write(f"\r  starting in {n} ... ")
                out.flush()
                time.sleep(1.0)
            audio.play(t_begin)
            origin = time.perf_counter() - t_begin
        else:
            out.write(f"\r  play the song (from {t_begin:.1f}s) and press SPACE the moment it starts ")
            out.flush()
            while " " not in keys.read():
                time.sleep(0.01)
            origin = time.perf_counter() - t_begin
        out.write("\n\n")
        k = 0
        while k < len(order):
            now = time.perf_counter() - origin
            for key in keys.read():
                if key == " ":
                    taps[order[k]] = round(now, 2)
                    out.write(f"\r  {now:7.2f}s  [{k + start_index + 1:>2}] {plain[order[k]]}\x1b[K\n")
                    k += 1
                elif key == "u" and k > 0:
                    k -= 1
                    taps.pop(order[k], None)
                    out.write(f"\r  undo  -> line {k + start_index + 1} again\x1b[K\n")
                elif key == "s":
                    out.write(f"\r  skip  [{k + start_index + 1:>2}] keeps {float(raw_lines[order[k]]['t']):.2f}s\x1b[K\n")
                    k += 1
                elif key in ("q", "esc"):
                    k = len(order)
                if k >= len(order):
                    break
            if k < len(order):
                out.write(f"\r  {now:7.2f}s  next > [{k + start_index + 1:>2}] {plain[order[k]]}\x1b[K")
                out.flush()
            time.sleep(0.01)
    if audio:
        audio.stop()
    print()
    return taps


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("song", help="song folder name in songs/, a folder, or a song.yaml path")
    ap.add_argument("--write", action="store_true", help="update song.yaml (keeps song.yaml.bak)")
    ap.add_argument("--from", dest="start", type=int, default=1, help="first line number to tap (1-based)")
    ap.add_argument("--no-audio", action="store_true")
    args = ap.parse_args()
    try:
        path = resolve_song_path(args.song, SONGS)
        song = load_song(path)
    except ConfigError as e:
        print(f"config error: {e}")
        return 2
    if path.suffix.lower() != ".yaml" and path.suffix.lower() != ".yml":
        print("tap_sync rewrites YAML song files only")
        return 2
    if not sys.stdin.isatty():
        print("tap_sync needs an interactive terminal")
        return 2
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    raw_lines, raw_scenes = data["lyrics"], data.get("scenes") or []
    gap = float((data.get("defaults") or {}).get("gap", 0.15))

    print(f"\n  {song.title} - {song.artist}: {len(raw_lines)} lines")
    print("  SPACE = line starts   u = undo   s = skip   q = finish\n")
    taps = tap_session(song, raw_lines, max(0, args.start - 1), not args.no_audio)
    if not taps:
        print("  no taps recorded")
        return 1

    updates, starts = plan(raw_lines, raw_scenes, taps, gap)
    print("  line                                         old t    new t    end")
    for i, up in sorted(updates.items(), key=lambda kv: kv[1]["t"]):
        name = str(raw_lines[i]["text"]).replace("*", "")[:42]
        end = fmt(up["end"]) if "end" in up else "(dur)"
        print(f"  {name:<44} {float(raw_lines[i]['t']):6.2f}  {up['t']:7.2f}  {end:>6}")
    for k, s in sorted(starts.items()):
        print(f"  scene {raw_scenes[k].get('name', k)!r}: start {float(raw_scenes[k]['start']):.2f} -> {s:.2f}")

    new_text = rewrite(text, updates, starts)
    if not args.write:
        print("\n  dry run - re-run with --write to save these timings")
        return 0
    shutil.copyfile(path, path.with_suffix(path.suffix + ".bak"))
    path.write_text(new_text, encoding="utf-8")
    print(f"\n  saved {path} (backup: {path.name}.bak)")
    warns = validate(load_song(path))
    for w in warns:
        print(f"  warning: {w}")
    if not warns:
        print("  timing OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
