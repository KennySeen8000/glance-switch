"""Windowless launcher (double-click, or used by "Iniciar con Windows")."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from glance.__main__ import run  # noqa: E402

run()
