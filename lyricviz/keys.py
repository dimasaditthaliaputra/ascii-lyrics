"""Non-blocking keyboard input (POSIX cbreak mode, Windows msvcrt)."""
from __future__ import annotations

import os
import sys
from typing import List

if os.name == "nt":  # pragma: no cover
    import msvcrt
else:
    import select
    import termios
    import tty

_SEQ = {"\x1b[A": "up", "\x1b[B": "down", "\x1b[C": "right", "\x1b[D": "left"}


class KeyReader:
    def __init__(self):
        self.enabled = sys.stdin.isatty()
        self._old = None

    def __enter__(self):
        if self.enabled and os.name != "nt":
            fd = sys.stdin.fileno()
            self._old = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        return self

    def __exit__(self, *exc):
        if self._old is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old)

    def read(self) -> List[str]:
        if not self.enabled:
            return []
        if os.name == "nt":  # pragma: no cover
            keys = []
            while msvcrt.kbhit():
                c = msvcrt.getwch()
                if c in ("\x00", "\xe0"):
                    c2 = msvcrt.getwch()
                    keys.append({"H": "up", "P": "down", "M": "right", "K": "left"}.get(c2, ""))
                else:
                    keys.append(c)
            return keys
        data = ""
        while select.select([sys.stdin], [], [], 0)[0]:
            chunk = os.read(sys.stdin.fileno(), 64).decode("utf-8", "ignore")
            if not chunk:
                break
            data += chunk
        keys, i = [], 0
        while i < len(data):
            if data[i] == "\x1b" and data[i:i + 3] in _SEQ:
                keys.append(_SEQ[data[i:i + 3]])
                i += 3
            else:
                keys.append("esc" if data[i] == "\x1b" else data[i])
                i += 1
        return keys
