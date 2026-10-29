"""Global hotkeys via RegisterHotKey on a dedicated message-loop thread."""
from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import wintypes as W
from typing import Callable

from . import win32

log = logging.getLogger(__name__)

_MODIFIERS = {"ctrl": win32.MOD_CONTROL, "control": win32.MOD_CONTROL,
              "alt": win32.MOD_ALT, "shift": win32.MOD_SHIFT, "win": win32.MOD_WIN}


def parse(combo: str) -> tuple[int, int]:
    """'ctrl+alt+g' -> (modifiers, virtual key)."""
    mods, key = 0, None
    for part in combo.lower().replace(" ", "").split("+"):
        if part in _MODIFIERS:
            mods |= _MODIFIERS[part]
        elif len(part) == 1 and part.isalnum():
            key = ord(part.upper())
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            key = 0x70 + int(part[1:]) - 1
        else:
            raise ValueError(f"unknown key {part!r} in hotkey {combo!r}")
    if key is None:
        raise ValueError(f"hotkey {combo!r} has no key")
    return mods, key


class HotkeyThread(threading.Thread):
    def __init__(self, bindings: dict[str, str], on_hotkey: Callable[[str], None]):
        super().__init__(name="hotkeys", daemon=True)
        self._bindings = bindings  # combo -> command name
        self._on_hotkey = on_hotkey
        self._tid = 0
        self.failed: list[str] = []

    def run(self) -> None:
        self._tid = win32.GetCurrentThreadId()
        names: dict[int, str] = {}
        for i, (combo, name) in enumerate(self._bindings.items(), start=1):
            try:
                mods, vk = parse(combo)
            except ValueError:
                log.warning("Invalid hotkey %r", combo)
                continue
            if win32.RegisterHotKey(None, i, mods | win32.MOD_NOREPEAT, vk):
                names[i] = name
            else:
                log.warning("Hotkey %s is already taken by another app", combo)
                self.failed.append(combo)
        msg = W.MSG()
        try:
            while win32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == win32.WM_HOTKEY and msg.wParam in names:
                    self._on_hotkey(names[msg.wParam])
        finally:
            for i in names:
                win32.UnregisterHotKey(None, i)

    def stop(self) -> None:
        if self._tid:
            win32.PostThreadMessageW(self._tid, win32.WM_QUIT, 0, 0)
