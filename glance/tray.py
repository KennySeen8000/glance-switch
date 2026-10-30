"""System-tray icon and menu."""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

import pystray
from PIL import Image, ImageDraw

from . import DISPLAY_NAME, i18n, startup
from .i18n import t

if TYPE_CHECKING:
    from .app import App

log = logging.getLogger(__name__)

COLORS = {"ok": (79, 140, 255), "off": (130, 138, 152), "warn": (245, 165, 36)}
DWELL_CHOICES = (("dwell_fast", 200), ("dwell_normal", 350), ("dwell_slow", 600))


def make_icon(state: str) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = COLORS[state]
    # Almond-shaped eye outline made of two arcs, iris in the state colour.
    d.chord((4, 14, 60, 74), 200, 340, fill=(240, 243, 250, 255))
    d.chord((4, -10, 60, 50), 20, 160, fill=(240, 243, 250, 255))
    d.ellipse((20, 18, 44, 42), fill=color + (255,))
    d.ellipse((28, 26, 36, 34), fill=(16, 18, 24, 255))
    if state == "off":
        d.line((10, 54, 54, 10), fill=(16, 18, 24, 255), width=9)
        d.line((10, 54, 54, 10), fill=color + (255,), width=5)
    return img


class Tray:
    def __init__(self, app: "App"):
        self.app = app
        self._icons = {state: make_icon(state) for state in COLORS}
        self._state = "warn"
        self.icon = pystray.Icon("GlanceSwitch", self._icons[self._state], DISPLAY_NAME,
                                 menu=self._menu())

    def _menu(self) -> pystray.Menu:
        s = self.app.settings
        Item = pystray.MenuItem

        def cmd(name: str):
            return lambda icon, item: self.app.post(name)

        def flag(label: str, attr: str):
            return Item(label, cmd(f"toggle:{attr}"), checked=lambda item: getattr(s, attr))

        def dwell(label: str, ms: int):
            return Item(label, cmd(f"dwell:{ms}"), checked=lambda item: s.dwell_ms == ms, radio=True)

        def lang(code: str, label: str):
            return Item(label, cmd(f"lang:{code}"), checked=lambda item: i18n.language() == code,
                        radio=True)

        return pystray.Menu(
            Item(t("menu_enabled", hotkey=s.hotkey_toggle.title()), cmd("toggle"),
                 checked=lambda item: s.enabled, default=True),
            pystray.Menu.SEPARATOR,
            Item(t("menu_calibrate", hotkey=s.hotkey_calibrate.title()), cmd("calibrate")),
            Item(t("menu_preview"), cmd("preview"),
                 checked=lambda item: self.app.preview is not None),
            Item(t("menu_delay"), pystray.Menu(*(dwell(t(key), ms) for key, ms in DWELL_CHOICES))),
            # Shown in both languages so it can be found whichever one is active.
            Item("Idioma / Language", pystray.Menu(
                *(lang(code, label) for code, label in i18n.LANGUAGES.items()))),
            Item(t("menu_options"), pystray.Menu(
                flag(t("opt_gaze_dot"), "show_gaze_dot"),
                flag(t("opt_flash"), "flash_on_switch"),
                flag(t("opt_learn"), "learn_from_clicks"),
                flag(t("opt_fullscreen"), "pause_on_fullscreen"),
                Item(t("opt_startup"), cmd("startup"),
                     checked=lambda item: startup.is_enabled()),
            )),
            Item(t("menu_open_folder"), cmd("open_folder")),
            pystray.Menu.SEPARATOR,
            Item(t("menu_quit"), cmd("quit")),
        )

    def start(self) -> None:
        threading.Thread(target=self.icon.run, name="tray", daemon=True).start()

    def set_state(self, state: str, tooltip: str) -> None:
        if state != self._state:
            self._state = state
            self.icon.icon = self._icons[state]
        if self.icon.title != tooltip:
            self.icon.title = tooltip

    def rebuild_menu(self) -> None:
        """Recreate the menu so its labels follow a language change."""
        self.icon.menu = self._menu()

    def refresh_menu(self) -> None:
        try:
            self.icon.update_menu()
        except Exception:
            log.debug("Tray menu refresh failed", exc_info=True)

    def notify(self, message: str) -> None:
        try:
            self.icon.notify(message, DISPLAY_NAME)
        except Exception:
            log.debug("Tray notification failed", exc_info=True)

    def stop(self) -> None:
        self.icon.stop()
