from types import SimpleNamespace

import numpy as np

from oi.perception import FakeDetector, TrackAges, simplify_polygon, tracks_from_result
from tests.helpers import trk


def fake_result(ids, boxes, cls, conf, masks=None, names=None):
    as_array = lambda values: np.array(values, dtype=float)  # noqa: E731
    return SimpleNamespace(
        boxes=SimpleNamespace(id=None if ids is None else as_array(ids), xyxy=as_array(boxes), cls=as_array(cls),
                              conf=as_array(conf)),
        masks=None if masks is None else SimpleNamespace(xy=[as_array(m) for m in masks]),
        names=names or {0: "cup", 1: "person"})


def test_untracked_detections_are_skipped():
    assert tracks_from_result(fake_result(None, [[0, 0, 10, 10]], [0], [0.9]), 1.0, TrackAges()) == []


def test_conversion_maps_fields_and_ages():
    ages = TrackAges()
    result = fake_result([3], [[10, 20, 110, 220]], [0], [0.8], masks=[[[10, 20], [110, 20], [110, 220]]])
    (first,) = tracks_from_result(result, 1.0, ages)
    (second,) = tracks_from_result(result, 1.1, ages)
    assert (first.id, first.label, first.box, first.polygon) == (3, "cup", (10, 20, 110, 220),
                                                                  [(10, 20), (110, 20), (110, 220)])
    assert first.score == 0.8
    assert (first.age_frames, second.age_frames, second.first_seen_ts) == (1, 2, 1.0)


def test_masks_missing_gives_empty_polygon():
    (track,) = tracks_from_result(fake_result([1], [[0, 0, 10, 10]], [1], [0.5]), 0.0, TrackAges())
    assert track.polygon == [] and track.label == "person"


def test_simplify_polygon_limits_points():
    assert len(simplify_polygon(np.random.rand(200, 2))) == 48
    assert len(simplify_polygon(np.random.rand(10, 2))) == 10


def test_fake_detector_repeats_last():
    a, b = trk(1, (0, 0, 10, 10)), trk(2, (0, 0, 10, 10))
    detector = FakeDetector([[a], [b]])
    frame = np.zeros((10, 10, 3), np.uint8)
    assert [detector.detect(frame, t) for t in (0.0, 0.1, 0.2)] == [[a], [b], [b]]
    detector.reset()
    assert detector.reset_calls == 1
