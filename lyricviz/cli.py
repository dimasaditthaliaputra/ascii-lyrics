"""Command line entry point."""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

from . import layers  # noqa: F401  (registers layer types)
from .app import LiveRunner, Visualizer, fmt_time
from .audio import AudioPlayer
from .config import ConfigError, load_song, resolve_song_path, validate
from .terminal import FrameWriter, detect

ROOT = Path(__file__).resolve().parent.parent
SONGS = ROOT / "songs"


def parse_size(s: str):
    w, h = s.lower().split("x")
    return int(w), int(h)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lyricviz", description="ASCII lyrics visualizer")
    p.add_argument("song", nargs="?", default="drop_dead",
                   help="song folder name in songs/, a folder, or a song.yaml path")
    p.add_argument("--start", type=float, default=0.0, help="start at this second")
    p.add_argument("--until", type=float, help="stop at this second")
    p.add_argument("--fps", type=float, default=30.0)
    p.add_argument("--speed", type=float, default=1.0, help="playback speed (timing debug)")
    p.add_argument("--loop", action="store_true")
    p.add_argument("--color", choices=["truecolor", "256", "standard", "none"],
                   help="force a colour system (default: auto-detect)")
    p.add_argument("--no-color", action="store_true", help="same as --color none")
    p.add_argument("--ascii", action="store_true", help="plain ASCII glyphs only")
    p.add_argument("--no-audio", action="store_true")
    p.add_argument("--no-hud", action="store_true")
    p.add_argument("--list", action="store_true", help="list bundled songs")
    p.add_argument("--validate", action="store_true", help="check the song config and print the timeline")
    p.add_argument("--snapshot", type=float, metavar="T", help="print one frame at time T and exit")
    p.add_argument("--size", type=parse_size, help="frame size for --snapshot/--benchmark, e.g. 120x36")
    p.add_argument("--benchmark", action="store_true",
                   help="run the real-time loop headless and report fps + lyric sync accuracy")
    return p


def print_timeline(song, console: Console) -> None:
    table = Table(title=f"{song.title} — {song.artist}", show_lines=False)
    for col in ("scene", "time", "layout", "theme", "transition", "lines"):
        table.add_column(col)
    for s in song.scenes:
        lines = [l for l in song.lines if s.start <= l.t < s.end]
        table.add_row(s.name, f"{s.start:6.2f}–{s.end:6.2f}", s.layout, str(s.theme),
                      f"{s.transition.get('type')} {s.transition.get('duration', '')}",
                      "\n".join(f"{l.t:6.2f}  {l.plain}" for l in lines) or "-")
    console.print(table)


def benchmark(viz: Visualizer, args, console: Console) -> int:
    w, h = args.size or (120, 36)
    start = args.start
    until = args.until if args.until is not None else viz.song.duration
    fps = args.fps
    frame = 1.0 / fps
    origin = time.perf_counter()
    times, first_seen = [], {}
    writer = FrameWriter(viz.caps, stream=open("/dev/null", "w") if sys.platform != "win32" else None)
    while True:
        f0 = time.perf_counter()
        t = start + (f0 - origin) * args.speed
        if t >= until:
            break
        cv = viz.render(t, w, h)
        writer.draw(cv)  # include ANSI encoding cost
        for l in viz.lyrics.lines:
            if l.index not in first_seen and l.t <= t and l.t >= start:
                first_seen[l.index] = t - l.t
        spent = time.perf_counter() - f0
        times.append(spent)
        time.sleep(max(0.0, frame - spent))
    n = len(times)
    real = time.perf_counter() - origin
    console.print(f"[bold]frames[/]: {n} in {real:.1f}s -> {n / real:.1f} fps (target {fps:g})")
    if times:
        ms = sorted(x * 1000 for x in times)
        console.print(f"[bold]frame cost[/]: avg {statistics.mean(ms):.1f} ms, p95 {ms[int(n * 0.95) - 1]:.1f} ms, "
                      f"max {ms[-1]:.1f} ms (budget {frame * 1000:.1f} ms)")
    if first_seen:
        lat = [v * 1000 for v in first_seen.values()]
        console.print(f"[bold]lyric sync[/]: {len(lat)} lines, first visible avg {statistics.mean(lat):.1f} ms "
                      f"/ max {max(lat):.1f} ms after their timestamp")
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    console = Console(stderr=True)
    if args.list:
        for d in sorted(SONGS.iterdir()):
            if (d / "song.yaml").exists() or (d / "song.json").exists():
                console.print(f"  [bold]{d.name}[/]")
        return 0
    try:
        song = load_song(resolve_song_path(args.song, SONGS))
    except ConfigError as e:
        console.print(f"[red]config error:[/] {e}")
        return 2
    warns = validate(song)
    if args.validate:
        print_timeline(song, console)
        for w in warns:
            console.print(f"[yellow]warning:[/] {w}")
        if not warns:
            console.print("[green]timing OK[/] — no overlaps, no scene splits a line")
        return 1 if warns else 0

    force = "none" if args.no_color else args.color
    caps = detect(force, args.ascii)
    try:
        viz = Visualizer(song, caps)
    except KeyError as e:
        console.print(f"[red]config error:[/] {e.args[0]}")
        return 2
    viz.hud = not args.no_hud

    if args.snapshot is not None:
        w, h = args.size or (120, 36)
        viz.hud = False if args.no_hud else viz.hud
        # warm particles up so the still frame looks like the live one
        for k in range(30, 0, -1):
            viz.render(max(0.0, args.snapshot - k / 30.0), w, h)
        cv = viz.render(args.snapshot, w, h)
        sys.stdout.write(FrameWriter(caps).to_ansi(cv) + "\n")
        return 0
    if args.benchmark:
        return benchmark(viz, args, console)

    if not sys.stdout.isatty():
        console.print("[red]stdout is not a terminal[/]; use --snapshot or --benchmark for headless runs")
        return 2
    if viz.artwork is not None and viz.artwork.error and song.artwork is not None:
        console.print(f"[yellow]{viz.artwork.error}[/]")
    audio = None
    if not args.no_audio and song.audio:
        audio = AudioPlayer(song.audio, song.audio_offset)
        if audio.error:
            console.print(f"[yellow]{audio.error}[/]")
            time.sleep(1.0)
    runner = LiveRunner(viz, fps=args.fps, start=args.start, until=args.until, loop=args.loop,
                        speed=args.speed, audio=audio)
    runner.run()
    if runner.frame_times:
        avg = sum(runner.frame_times) / len(runner.frame_times)
        console.print(f"[dim]{song.title}: {len(runner.frame_times)} frames, "
                      f"avg render {avg * 1000:.1f} ms, ended at {fmt_time(runner.clock.now())}[/]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
