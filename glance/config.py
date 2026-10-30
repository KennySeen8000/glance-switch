"""User settings and on-disk locations."""
from __future__ import annotations

import json
import logging
import os
import sys
import urllib.request
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from . import APP_NAME

log = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
SETTINGS_VERSION = 2


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(relative: str) -> Path:
    """Locate a bundled file both from source and from a PyInstaller build."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


def face_model_bytes() -> bytes:
    """Load the MediaPipe face model, downloading it on first run if needed.

    Loading from bytes (instead of a path) avoids MediaPipe failing on
    non-ASCII user folders.
    """
    for candidate in (resource_path("models/face_landmarker.task"),
                      data_dir() / "face_landmarker.task"):
        if candidate.is_file():
            return candidate.read_bytes()
    target = data_dir() / "face_landmarker.task"
    log.info("Downloading face model to %s", target)
    with urllib.request.urlopen(MODEL_URL, timeout=60) as resp:
        payload = resp.read()
    target.write_bytes(payload)
    return payload


@dataclass
class Settings:
    enabled: bool = True
    camera_index: int = 0
    camera_width: int = 1280
    camera_height: int = 720
    camera_fps: int = 15
    # How long the gaze must rest on a window before it gets focus.
    dwell_ms: int = 350
    # Minimum time between two focus switches.
    cooldown_ms: int = 600
    # Gaze switching pauses while the mouse is in use...
    mouse_grace_ms: int = 900
    # ...and while typing, so glancing at a reference doc does not steal keys.
    typing_grace_ms: int = 700
    # Share of the gaze "votes" a window needs to be considered.
    min_confidence: float = 0.6
    show_gaze_dot: bool = False
    flash_on_switch: bool = True
    learn_from_clicks: bool = True
    pause_on_fullscreen: bool = True
    calibration_cols: int = 5
    calibration_rows: int = 4
    # Fresh targets shown after calibration to measure the real accuracy.
    validation_points: int = 5
    hotkey_toggle: str = "ctrl+alt+g"
    hotkey_calibrate: str = "ctrl+alt+k"
    # Interface language: a key of i18n.LANGUAGES.
    language: str = "es"
    settings_version: int = SETTINGS_VERSION

    @classmethod
    def path(cls) -> Path:
        return data_dir() / "settings.json"

    @classmethod
    def load(cls) -> "Settings":
        settings = cls()
        try:
            raw = json.loads(cls.path().read_text(encoding="utf-8"))
        except FileNotFoundError:
            return settings
        except (OSError, ValueError):
            log.warning("Ignoring unreadable settings file", exc_info=True)
            return settings
        known = {f.name for f in fields(cls)}
        for key, value in raw.items():
            if key in known and isinstance(value, type(getattr(settings, key))):
                setattr(settings, key, value)
        if raw.get("settings_version", 1) < SETTINGS_VERSION:
            settings._migrate(raw.get("settings_version", 1))
        return settings

    def _migrate(self, from_version: int) -> None:
        defaults = Settings()
        if from_version < 2:
            # v2 calibrates on a denser grid; files saved by v1 hold the old 4x3.
            self.calibration_cols = defaults.calibration_cols
            self.calibration_rows = defaults.calibration_rows
        self.settings_version = SETTINGS_VERSION
        try:
            self.save()
        except OSError:
            log.warning("Could not save migrated settings", exc_info=True)

    def save(self) -> None:
        tmp = self.path().with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        tmp.replace(self.path())
