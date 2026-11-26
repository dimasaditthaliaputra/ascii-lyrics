# AGENTS.md

Terminal lyric visualizer. A song is `songs/<name>/song.yaml`; a scene is a stack of
**layers** painted back to front into a cell `Canvas`. Read `README.md` §4-§6 for the
config format; this file is the checklist for adding new ASCII components.

## Map

| Path | Role |
|---|---|
| `lyricviz/layers/base.py` | `Layer`, `@register`, `REGISTRY`, shared keys (`region/start/until/fade_in/fade_out/opacity/seed`) |
| `lyricviz/layers/{background,particles,illustrations}.py` | built-in layers |
| `lyricviz/layers/__init__.py` | imports every layer module; a new module must be imported here |
| `lyricviz/art/*.py` | hand-drawn art (`sprites.py`: `LIBRARY`, `auto_masks`) and procedural shapes |
| `lyricviz/canvas.py` | `Canvas` (`put/text/glow/tint/blit/darken_rect`), `Rect`, `Sprite` |
| `lyricviz/themes.py` | theme palettes (`@key` colour references) and atmospheres |
| `lyricviz/terminal.py` | `ASCII_FALLBACK` glyph table for non-UTF-8 terminals |
| `tests/` | `unittest` (run `.venv/bin/python -m unittest discover`) |

## Adding a new layer

1. Subclass `Layer`, decorate with `@register("name")`, implement `draw(self, cv, t, rect, alpha)`.
   Put it in an existing module if it fits, otherwise a new `lyricviz/layers/<name>.py`
   and add it to the import line in `lyricviz/layers/__init__.py`.
2. Read parameters with `self.num / self.kf / self.color / self.colors / self.spec.get`.
   Use `self.kf` for anything that should accept keyframes (`[[t, v], ...]`).
3. Add a row to the table in `README.md` §6.1 (name + every parameter you read).
4. Use it in a scene and look at it (see Verification).

## Adding a new sprite (most common "new ASCII component")

1. In `lyricviz/art/sprites.py` write `NAME_FRAMES` (list of raw strings, one per animation
   frame, all frames the same size) and a rule `def _name_rule(c, x, y, w) -> str` that
   returns a colour **key** for each character. Build it with
   `Sprite(FRAMES, auto_masks(FRAMES, rule))`.
2. Register it in `LIBRARY` at the bottom of the file.
3. Add default colours for its keys to `SpriteLayer.PALETTES` in
   `lyricviz/layers/illustrations.py`. Keys not in the palette render white.
4. Document the keys in `README.md` below §6.1 (the paragraph about `palette`).

Example:

```python
LANTERN_FRAMES = [r"""
  _|_
 /___\
 |(@)|
 \___/
"""]
def _lantern_rule(c, x, y, w):
    return "f" if c == "@" else "b"      # f = flame, b = body
LANTERN = Sprite(LANTERN_FRAMES, auto_masks(LANTERN_FRAMES, _lantern_rule))
# LIBRARY["lantern"] = LANTERN ; PALETTES["lantern"] = {"f": "#ffc36b", "b": "#d8d8d8"}
```

Sprite conventions: backtick `` ` `` is the transparent glyph (skipped); `Sprite.solid`
(`"\0"`) paints a background block so a silhouette occludes what is behind it. A leading
and trailing blank line in the raw string are stripped.

## Rules that are not obvious from the code

- **Cells are ~2:1 (tall:wide).** A circle needs `dx` and `dy * 2` (see `Canvas.glow`).
  Spread things horizontally about twice as far as vertically.
- **Deterministic randomness.** Use `random.Random(self.seed)`; never the global `random`
  and never `hash(str)`. `self.seed` already differs per layer and per scene.
- **Seeking.** The player can jump in time. Stateless layers should derive everything from
  `t`. Stateful layers (particles) update in `update(dt, t, rect)` and must rebuild
  their state in `reset()`; `update` starts running 0.5 s before `start`.
- **Draw inside `rect`.** `rect` is the region the layer was given (`full`, `art`,
  `lyrics`). Use `rect.point(fx, fy)` / `rect.sub(...)`; do not assume the screen size.
  The terminal may be as small as 60x18 or as big as 220x60.
- **Multiply by `alpha`.** Pass the `alpha` argument through to `cv.put/text/glow/blit`
  so `start/fade_in/until/fade_out/opacity` work.
- **Unicode fallback.** Pick glyphs with `self.g("♥", "<")` or make sure every non-ASCII
  glyph you use is in `ASCII_FALLBACK` (`lyricviz/terminal.py`). Use single-width glyphs only
  (no emoji, no CJK); a double-width glyph shifts the whole row and `test_render` rejects
  multi-character cells.
- **Colours.** Take them from the theme: `self.color("color", "@glow")`,
  `self.colors("colors", "petals")`. Theme keys: `sky`(list), `lyric`(list), `emph`(list),
  `past`, `sing`, `glow`, `accent`, `petals`(list), `leaf`, `stem`, `center`
  (`versailles_gold` also has `gold`); the authoritative list is `THEMES` in
  `lyricviz/themes.py`. Hard-coded hex is fine as a fallback default, not as the only option.
- **Performance.** Render cost scales with cells touched. Frame budget is ~35 ms at
  120x36 (`python main.py <song> --benchmark`). Avoid per-cell Python loops over the full
  canvas each frame; `Canvas.glow` and `darken_rect` are already the heavy ones.
- **Do not touch the terminal.** Layers only paint into the `Canvas`; the renderer writes
  the ANSI.

## Verification (do all of these before saying a component works)

```bash
.venv/bin/python -m unittest discover          # includes every bundled song at 3 sizes
python main.py <song> --validate               # timing / missing file warnings
python main.py <song> --snapshot 30 --size 120x36
python tools/frame_to_png.py <song> 6 14 30 --out previews/   # look at the picture
python main.py <song> --ascii                  # glyph fallback still reads well
```

Render at a small size (`--size 60x18`) and a large one (`--size 200x56`), at the time the
layer is visible, and check that it stays inside its region and nothing is clipped or
double-width. When adding a layer, add a short test to `tests/` that builds it via
`build_layer` and draws a frame without error, in both unicode and ASCII mode.

## Known state

- `songs/shape_of_my_heart/song.yaml` is a scaffold: lyrics, audio and real timings are not
  filled in yet.
- Two tests fail on a clean checkout: `tests.test_lyrics.MarkupTest.test_syllables` and
  `tests.test_render.RenderTest.test_lyrics_appear_on_time` (the latter on `drop_dead`).
  Do not assume a new failure is yours without comparing against this list.
- Lyrics and cover art belong to their rights holders; do not commit full copyrighted
  lyrics, audio files or real album covers.
