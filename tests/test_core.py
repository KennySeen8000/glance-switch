import numpy as np
import pytest

from glance import features
from glance.app import vote
from glance.calibration import grid_points
from glance.decider import Decider
from glance.filters import OneEuro
from glance.hotkeys import parse
from glance.model import CLICK_GROUP_BASE, MAX_CLICK_SAMPLES, CalibrationData, fit
from glance.win32 import Rect, Window


def synthetic(n_targets=12, per=12, noise=0.004, seed=0):
    """Targets on a 1920x1080 screen produced by a smooth head/eye model."""
    rng = np.random.default_rng(seed)
    pts = grid_points([Rect(0, 0, 1920, 1080)], 4, 3)[:n_targets]
    F, Y, G = [], [], []
    for g, (x, y) in enumerate(pts):
        u, v = (x - 960) / 960, (y - 540) / 540
        for _ in range(per):
            yaw = 0.25 * u + rng.normal(0, noise)
            pitch = -0.15 * v + rng.normal(0, noise)
            ex = 0.5 + 0.06 * u + rng.normal(0, noise / 2)
            ey = 0.04 * v + rng.normal(0, noise / 2)
            F.append([yaw, pitch, ex, ey, 0.5, -1.0, -45.0])
            Y.append([x, y])
            G.append(g)
    return np.array(F), np.array(Y), np.array(G)


def test_model_fits_and_reports_cv_error():
    F, Y, G = synthetic()
    m = fit(F, Y, G)
    assert m.cv_error < 60
    pred = m.predict(F[0])
    assert pred.shape == (2,)
    assert np.hypot(*(pred - Y[0])) < 60


def test_calibration_data_roundtrip_and_click_cap(tmp_path):
    F, Y, G = synthetic()
    data = CalibrationData.empty("0,0,1920x1080")
    for g in np.unique(G):
        data.add(F[G == g], Y[G == g][0], int(g))
    for i in range(MAX_CLICK_SAMPLES + 10):
        data.add_click(F[i % len(F)], Y[i % len(F)])
    assert data.click_count == MAX_CLICK_SAMPLES
    path = tmp_path / "c.json"
    data.save(path)
    loaded = CalibrationData.load(path)
    assert loaded is not None and loaded.click_count == MAX_CLICK_SAMPLES
    assert (loaded.groups >= CLICK_GROUP_BASE).sum() == MAX_CLICK_SAMPLES
    assert loaded.fit().cv_error < 80


def test_decider_dwell_blip_and_cooldown():
    d = Decider(dwell_s=0.3, cooldown_s=0.5, min_confidence=0.6, gap_s=0.12)
    fg = 1
    assert d.update(0.0, 2, 1.0, fg) is None
    assert d.update(0.1, 2, 1.0, fg) is None
    assert d.update(0.15, 3, 1.0, fg) is None   # blip, timer keeps running
    assert d.update(0.31, 2, 1.0, fg) == 2
    # Cooldown: next window must wait even after dwelling.
    assert d.update(0.40, 3, 1.0, 2) is None
    assert d.update(0.75, 3, 1.0, 2) is None
    assert d.update(0.82, 3, 1.0, 2) == 3


def test_decider_ignores_low_confidence_and_foreground():
    d = Decider(dwell_s=0.1, cooldown_s=0.0)
    assert d.update(0.0, 5, 0.3, 1) is None
    assert d.update(0.5, 5, 0.3, 1) is None
    assert d.update(1.0, 1, 1.0, 1) is None
    assert d.update(2.0, 1, 1.0, 1) is None


def test_vote_prefers_dominant_window_and_respects_occlusion():
    taskbar = Window(1, Rect(0, 1040, 1920, 1080), "", "Shell_TrayWnd", 9, False)
    editor = Window(2, Rect(0, 0, 960, 1040), "editor", "X", 10, True)
    browser = Window(3, Rect(960, 0, 1920, 1040), "browser", "X", 11, True)
    wins = [taskbar, editor, browser]
    win, conf = vote(wins, 400, 500, 60)
    assert win is editor and conf == 1.0
    win, conf = vote(wins, 1500, 1060, 60)
    assert win is None
    win, conf = vote(wins, 965, 500, 60)  # on the border: uncertain
    assert conf < 0.8


def test_one_euro_smooths_noise_and_holds_same_timestamp():
    f = OneEuro()
    rng = np.random.default_rng(1)
    out = [f(i / 15, np.array([500.0, 500.0]) + rng.normal(0, 30, 2)) for i in range(60)]
    assert np.std(np.array(out[20:]), axis=0).max() < 20
    assert np.array_equal(f(59 / 15, [0, 0]), out[-1])


def test_eye_metrics_centre_and_blink():
    pts = np.zeros((478, 2))
    for left, right, top, bottom, iris in (features.RIGHT_EYE, features.LEFT_EYE):
        pts[left], pts[right] = (0, 0), (30, 0)
        pts[top], pts[bottom] = (15, -5), (15, 5)
        pts[iris] = (15, 0)
    m = features.measure(pts, np.eye(4))
    assert m.eye_x == pytest.approx(0.5)
    assert m.eye_y == pytest.approx(0.0)
    assert not m.blinking
    for _, _, top, bottom, _ in (features.RIGHT_EYE, features.LEFT_EYE):
        pts[top], pts[bottom] = (15, -1), (15, 1)
    assert features.measure(pts, np.eye(4)).blinking


def test_hotkey_parse():
    assert parse("ctrl+alt+g") == (0x2 | 0x1, ord("G"))
    assert parse("shift+F5") == (0x4, 0x74)
    with pytest.raises(ValueError):
        parse("ctrl+alt")
