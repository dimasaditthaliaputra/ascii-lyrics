#!/usr/bin/env python3
"""Write the generated stand-in cover to songs/<song>/artwork.png.

    python tools/make_sample_artwork.py drop_dead
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lyricviz.artwork import make_sample_artwork  # noqa: E402

song = sys.argv[1] if len(sys.argv) > 1 else "drop_dead"
out = Path(__file__).resolve().parent.parent / "songs" / song / "artwork.png"
img = make_sample_artwork(512)
if img is None:
    sys.exit("Pillow is required")
img.save(out)
print(f"wrote {out}")
