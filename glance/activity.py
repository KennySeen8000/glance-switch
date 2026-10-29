"""Watches mouse and keyboard activity without installing input hooks.

Hooks would run Python on every keystroke and risk lagging the whole system;
polling the cursor, the buttons and GetLastInputInfo at UI rate is enough.
"""
from __future__ import annotations

from . import win32


class Activity:
    def __init__(self):
        self.last_mouse = float("-inf")
        self.last_key = float("-inf")
        self.buttons_down = False
        self._pos = win32.cursor_pos()
        self._tick = win32.last_input_tick()
        self._buttons = win32.mouse_buttons()
        self._ignore_until = 0.0

    def ignore_injected(self, now: float, seconds: float = 0.15) -> None:
        """Our own synthetic input (see win32.activate) is not user activity."""
        self._ignore_until = now + seconds

    def poll(self, now: float) -> list[tuple[int, int]]:
        """Update activity timestamps; returns positions of new left clicks."""
        pos = win32.cursor_pos()
        tick = win32.last_input_tick()
        buttons = win32.mouse_buttons()
        clicks: list[tuple[int, int]] = []

        pressed = buttons & ~self._buttons
        if pos != self._pos or pressed:
            self.last_mouse = now
            if pressed & 1:
                clicks.append(pos)
        elif tick != self._tick and buttons == self._buttons and now >= self._ignore_until:
            # Input arrived but the mouse did not move: keyboard (or wheel).
            self.last_key = now

        self.buttons_down = buttons != 0
        self._pos, self._tick, self._buttons = pos, tick, buttons
        return clicks
