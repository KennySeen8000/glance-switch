"""Decides *when* the gaze has rested on a window long enough to switch."""
from __future__ import annotations


class Decider:
    """Dwell timer with blip tolerance and a cooldown between switches.

    A different candidate seen for less than `gap_s` (a blink, a noisy frame)
    does not restart the dwell timer of the current candidate.
    """

    def __init__(self, dwell_s: float = 0.35, cooldown_s: float = 0.6,
                 min_confidence: float = 0.6, gap_s: float = 0.12):
        self.dwell_s = dwell_s
        self.cooldown_s = cooldown_s
        self.min_confidence = min_confidence
        self.gap_s = gap_s
        self._last_switch = float("-inf")
        self.reset()

    def reset(self) -> None:
        self._cand: int | None = None
        self._since = 0.0
        self._seen = float("-inf")

    @property
    def candidate(self) -> int | None:
        return self._cand

    def progress(self, now: float) -> float:
        if self._cand is None:
            return 0.0
        return min(1.0, (now - self._since) / self.dwell_s) if self.dwell_s else 1.0

    def update(self, now: float, candidate: int | None, confidence: float,
               foreground: int | None) -> int | None:
        """Feed one observation; returns a window handle when it is time to switch."""
        if candidate is not None and confidence < self.min_confidence:
            candidate = None
        if candidate is not None and candidate == foreground:
            candidate = None

        if candidate == self._cand and candidate is not None:
            self._seen = now
        elif self._cand is None or now - self._seen > self.gap_s:
            self._cand = candidate
            self._since = self._seen = now
        if self._cand is None or candidate != self._cand:
            return None

        if now - self._since >= self.dwell_s and now - self._last_switch >= self.cooldown_s:
            target = self._cand
            self._last_switch = now
            self.reset()
            return target
        return None
