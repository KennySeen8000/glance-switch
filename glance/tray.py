"""System-tray icon and menu."""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

import pystray
from PIL import Image, ImageDraw

from . import DISPLAY_NAME, startup

if TYPE_CHECKING:
    from .app import App

log = logging.getLogger(__name__)

COLORS = {"ok": (79, 140, 255), "off": (130, 138, 152), "warn": (245, 165, 36)}
DWELL_CHOICES = (("Rápido (200 ms)", 200), ("Normal (350 ms)", 350), ("Lento (600 ms)", 600))


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

        return pystray.Menu(
            Item(f"Activado   ({s.hotkey_toggle.title()})", cmd("toggle"),
                 checked=lambda item: s.enabled, default=True),
            pystray.Menu.SEPARATOR,
            Item(f"Calibrar…   ({s.hotkey_calibrate.title()})", cmd("calibrate")),
            Item("Vista previa de cámara", cmd("preview"),
                 checked=lambda item: self.app.preview is not None),
            Item("Retardo antes de cambiar", pystray.Menu(*(dwell(l, ms) for l, ms in DWELL_CHOICES))),
            Item("Opciones", pystray.Menu(
                flag("Mostrar punto de mirada", "show_gaze_dot"),
                flag("Destello al cambiar de ventana", "flash_on_switch"),
                flag("Aprender de mis clics", "learn_from_clicks"),
                flag("Pausar con apps a pantalla completa", "pause_on_fullscreen"),
                Item("Iniciar con Windows", cmd("startup"),
                     checked=lambda item: startup.is_enabled()),
            )),
            Item("Abrir carpeta de datos", cmd("open_folder")),
            pystray.Menu.SEPARATOR,
            Item("Salir", cmd("quit")),
        )

    def start(self) -> None:
        threading.Thread(target=self.icon.run, name="tray", daemon=True).start()

    def set_state(self, state: str, tooltip: str) -> None:
        if state != self._state:
            self._state = state
            self.icon.icon = self._icons[state]
        if self.icon.title != tooltip:
            self.icon.title = tooltip

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
