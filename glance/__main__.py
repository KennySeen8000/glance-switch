"""Entry point: `python -m glance`."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from . import APP_NAME, DISPLAY_NAME, __version__, i18n, win32
from .config import Settings, data_dir


def setup_logging(verbose: bool) -> None:
    handlers: list[logging.Handler] = [
        RotatingFileHandler(data_dir() / "glance.log", maxBytes=1_000_000, backupCount=2,
                            encoding="utf-8"),
    ]
    if sys.stderr is not None:  # pythonw has no console
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=handlers,
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="glance", description=DISPLAY_NAME)
    parser.add_argument("--verbose", "-v", action="store_true", help="debug logging")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()

    setup_logging(args.verbose)
    i18n.set_language(Settings.load().language)
    if not win32.acquire_single_instance(APP_NAME):
        win32.message_box(i18n.t("already_running", name=DISPLAY_NAME), DISPLAY_NAME)
        return 1
    win32.set_dpi_awareness()

    from .app import App

    try:
        App().run()
    except Exception:
        logging.getLogger(__name__).exception("Fatal error")
        win32.message_box(i18n.t("crashed", name=DISPLAY_NAME, path=data_dir() / "glance.log"),
                          DISPLAY_NAME)
        return 1
    return 0


def run() -> None:
    code = main()
    logging.shutdown()
    # MediaPipe/OpenCV native threads can keep the interpreter alive at exit.
    os._exit(code)


if __name__ == "__main__":
    run()
