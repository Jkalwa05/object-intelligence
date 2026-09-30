"""Loads the real YOLOE weights (downloaded on first run). Runs only with `uv run pytest -m model`."""

import cv2
import pytest
from ultralytics.utils import ASSETS

from oi.config import Settings
from oi.perception import YoloeDetector


@pytest.fixture(scope="module")
def detector() -> YoloeDetector:
    return YoloeDetector(Settings())


@pytest.mark.model
def test_yoloe_finds_objects_on_bus_image(detector):
    detector.reset()
    tracks = detector.detect(cv2.imread(str(ASSETS / "bus.jpg")), 0.0)
    print(f"\n{detector.model_name}: {[(t.id, t.label, round(t.score, 2)) for t in tracks]}")
    assert len(tracks) >= 1 and all(isinstance(t.label, str) for t in tracks)


@pytest.mark.model
def test_reset_restarts_track_ids(detector):
    image = cv2.imread(str(ASSETS / "bus.jpg"))
    detector.reset()
    detector.detect(image, 0.0)
    detector.detect(image, 0.1)
    detector.reset()
    tracks = detector.detect(image, 0.2)
    assert min(t.id for t in tracks) == 1
