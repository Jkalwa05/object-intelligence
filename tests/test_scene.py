import pytest

from oi.scene import SceneMap
from tests.helpers import trk

LAMP = (500, 20, 700, 180)


def calibrate(scene, tracks_for, start=0.0):
    """11 frames 0.5 s apart (5 s); returns the freeze flags."""
    return [scene.observe(tracks_for(i), start + i * 0.5) for i in range(11)]


def test_stable_objects_become_frozen_markers():
    scene = SceneMap()
    flags = calibrate(scene, lambda i: [trk(1, (500 + i % 2, 20, 700, 180), label="lamp")])
    assert flags.count(True) == 1 and flags[-1] is True and not scene.calibrating
    (item,) = scene.items
    assert item.label == "lamp" and item.box == pytest.approx(LAMP, abs=1)


def test_flicker_is_dropped():
    scene = SceneMap()
    calibrate(scene, lambda i: [trk(1, LAMP, label="lamp")]
              + ([trk(2, (100, 100, 200, 200), label="ghost")] if i in (3, 4) else []))
    assert [i.label for i in scene.items] == ["lamp"]


def test_marker_uses_the_most_common_label():
    scene = SceneMap()
    calibrate(scene, lambda i: [trk(1, LAMP, label="ceiling light" if i % 3 == 0 else "lamp")])
    assert scene.items[0].label == "lamp"


def test_nothing_changes_after_freezing():
    scene = SceneMap()
    calibrate(scene, lambda i: [trk(1, LAMP, label="lamp")])
    assert scene.observe([trk(2, (0, 0, 50, 50), label="new")], 6.0) is False
    assert [i.label for i in scene.items] == ["lamp"]


def test_reset_starts_a_new_calibration():
    scene = SceneMap()
    calibrate(scene, lambda i: [trk(1, LAMP, label="lamp")])
    scene.reset()
    assert scene.calibrating and scene.items == []
    flags = calibrate(scene, lambda i: [trk(3, (10, 10, 110, 110), label="door")], start=10.0)
    assert flags[-1] and [i.label for i in scene.items] == ["door"]
