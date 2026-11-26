"""High-resolution song clock with pause, seek and speed."""
from __future__ import annotations

import time


class Clock:
    def __init__(self, start: float = 0.0, speed: float = 1.0):
        self.speed = speed
        self._origin = time.perf_counter()
        self._base = start
        self._paused_at = None

    def now(self) -> float:
        if self._paused_at is not None:
            return self._paused_at
        return self._base + (time.perf_counter() - self._origin) * self.speed

    @property
    def paused(self) -> bool:
        return self._paused_at is not None

    def pause(self) -> None:
        if self._paused_at is None:
            self._paused_at = self.now()

    def resume(self) -> None:
        if self._paused_at is not None:
            self.seek(self._paused_at)
            self._paused_at = None

    def toggle(self) -> None:
        self.resume() if self.paused else self.pause()

    def seek(self, t: float) -> None:
        t = max(0.0, t)
        self._origin = time.perf_counter()
        self._base = t
        if self._paused_at is not None:
            self._paused_at = t
