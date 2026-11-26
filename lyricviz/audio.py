"""Optional audio playback via pygame (``pip install pygame-ce``).

The visualizer always runs on its own clock; when audio is available it is
started/seeked/paused together with that clock. ``audio_offset`` in the song
config shifts the audio if your file has a different intro length.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


class AudioPlayer:
    def __init__(self, path: Optional[Path], offset: float = 0.0):
        self.ok = False
        self.error: Optional[str] = None
        self.offset = offset
        if path is None:
            return
        if not path.exists():
            self.error = f"audio file not found: {path}"
            return
        try:
            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            import pygame  # noqa: WPS433

            pygame.mixer.init()
            pygame.mixer.music.load(str(path))
            self._music = pygame.mixer.music
            self.ok = True
        except Exception as e:  # no pygame, no audio device, bad file ...
            self.error = f"audio disabled: {e}"

    def play(self, t: float) -> None:
        if not self.ok:
            return
        pos = t + self.offset
        try:
            self._music.play(start=max(0.0, pos))
        except Exception:
            self._music.play()

    def pause(self) -> None:
        if self.ok:
            self._music.pause()

    def resume(self) -> None:
        if self.ok:
            self._music.unpause()

    def stop(self) -> None:
        if self.ok:
            self._music.stop()
