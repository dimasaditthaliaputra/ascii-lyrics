"""Song config loading (YAML or JSON) and validation."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .lyrics import LyricLine, LyricsManager
from .scenes import LAYOUTS, SceneSpec

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


class ConfigError(Exception):
    pass


@dataclass
class SongConfig:
    path: Path
    title: str
    artist: str
    duration: float
    lines: List[LyricLine]
    scenes: List[SceneSpec]
    audio: Optional[Path] = None
    audio_offset: float = 0.0
    artwork: Optional[Path] = None
    artwork_opts: Dict[str, Any] = field(default_factory=dict)
    bpm: float = 0.0

    @property
    def folder(self) -> Path:
        return self.path.parent


def _read(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if yaml is None:
        raise ConfigError("PyYAML is not installed (pip install PyYAML), or use a .json song file")
    return yaml.safe_load(text) or {}


def resolve_song_path(arg: str, songs_dir: Path) -> Path:
    p = Path(arg)
    candidates = [p, p / "song.yaml", p / "song.yml", p / "song.json",
                  songs_dir / arg / "song.yaml", songs_dir / arg / "song.json"]
    for c in candidates:
        if c.is_file():
            return c.resolve()
    raise ConfigError(f"song {arg!r} not found (looked for a song.yaml in {p} and {songs_dir / arg})")


def load_song(path: Path) -> SongConfig:
    data = _read(path)
    base = path.parent
    meta = data.get("song", {})
    defaults = data.get("defaults", {})
    raw_lines = data.get("lyrics", [])
    if not raw_lines:
        raise ConfigError(f"{path}: no 'lyrics' entries")

    lines: List[LyricLine] = []
    raw_sorted = sorted(enumerate(raw_lines), key=lambda kv: float(kv[1].get("t", 0)))
    for n, (orig_idx, item) in enumerate(raw_sorted):
        where = f"{path.name}: lyrics[{orig_idx}]"
        if "t" not in item or "text" not in item:
            raise ConfigError(f"{where}: every line needs 't' (start seconds) and 'text'")
        t = float(item["t"])
        if "end" in item:
            end = float(item["end"])
        elif "dur" in item:
            end = t + float(item["dur"])
        else:
            nxt = raw_sorted[n + 1][1] if n + 1 < len(raw_sorted) else None
            gap = float(defaults.get("gap", 0.15))
            end = float(nxt["t"]) - gap if nxt else t + 3.0
        try:
            lines.append(LyricLine(
                t=t, end=end, text=str(item["text"]),
                reveal=float(item["reveal"]) if "reveal" in item else defaults.get("reveal"),
                effect=item.get("effect"),
                word_times=item.get("words"),
                big=bool(item.get("big", False)),
                style=item.get("style", {}),
            ))
        except ValueError as e:
            raise ConfigError(f"{where}: {e}") from None

    duration = float(meta.get("duration", max(l.end for l in lines) + 4.0))
    raw_scenes = data.get("scenes") or [{"name": "main", "start": 0, "atmosphere": "romantic"}]
    raw_scenes = sorted(raw_scenes, key=lambda s: float(s.get("start", 0)))
    scenes: List[SceneSpec] = []
    for i, s in enumerate(raw_scenes):
        name = s.get("name", f"scene{i + 1}")
        start = float(s.get("start", 0))
        end = float(raw_scenes[i + 1].get("start", duration)) if i + 1 < len(raw_scenes) else duration
        layout = s.get("layout", "left" if i % 2 == 0 else "right")
        if layout not in LAYOUTS:
            raise ConfigError(f"scene {name!r}: layout must be one of {', '.join(LAYOUTS)}")
        lyr = dict(defaults.get("lyrics", {}))
        lyr.update(s.get("lyrics", {}))
        spec = SceneSpec(
            name=name, start=start, end=end, layout=layout,
            theme=s.get("theme", defaults.get("theme", "dusk_rose")),
            atmosphere=s.get("atmosphere"),
            layers=list(s.get("layers", [])),
            transition=dict(s.get("transition", defaults.get("transition",
                                                             {"type": "dissolve", "duration": 1.2}))),
            lyrics=lyr,
            split=float(s.get("split", defaults.get("split", 0.42))),
        )
        scenes.append(spec)
    if scenes[0].start > 0:
        scenes[0].start = 0.0

    art = data.get("artwork") or {}
    if isinstance(art, str):
        art = {"image": art}
    audio = meta.get("audio")
    return SongConfig(
        path=path, title=str(meta.get("title", path.parent.name)),
        artist=str(meta.get("artist", "")), duration=duration, lines=lines, scenes=scenes,
        audio=(base / audio) if audio else None,
        audio_offset=float(meta.get("audio_offset", 0.0)),
        artwork=(base / art["image"]) if art.get("image") else None,
        artwork_opts=art, bpm=float(meta.get("bpm", 0.0)),
    )


def validate(song: SongConfig) -> List[str]:
    """Human-readable warnings about timing problems."""
    warns = LyricsManager(song.lines).validate()
    for a in song.scenes:
        for l in song.lines:
            if l.t < a.start < l.end - 0.05:
                warns.append(f"scene {a.name!r} starts at {a.start:.2f}s in the middle of line "
                             f"{l.plain!r} ({l.t:.2f}-{l.end:.2f}s); it would be split across scenes")
        dur = float(a.transition.get("duration", 0))
        if dur > a.duration:
            warns.append(f"scene {a.name!r}: transition ({dur}s) longer than the scene ({a.duration:.1f}s)")
    if song.lines[-1].end > song.duration:
        warns.append(f"last line ends after song duration ({song.duration}s)")
    if song.audio and not song.audio.exists():
        warns.append(f"audio file {song.audio} not found (visuals will run on the internal clock)")
    if song.artwork and not song.artwork.exists():
        warns.append(f"artwork {song.artwork} not found (a generated sample cover is used)")
    return warns
