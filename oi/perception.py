"""Perception: YOLOE-26 prompt-free detection with BoT-SORT tracking on the Mac GPU (spec §2.2)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from oi.config import Settings
from oi.contracts import Track

log = logging.getLogger(__name__)

TRACKER_CONFIG = Path(__file__).parent / "trackers" / "botsort.yaml"
MAX_POLYGON_POINTS = 48


class Detector(Protocol):
    model_name: str

    def detect(self, image: np.ndarray, t: float) -> list[Track]: ...

    def reset(self) -> None: ...


class TrackAges:
    """Remembers when each track ID was first seen and how many frames it has lived."""

    def __init__(self) -> None:
        self._first_seen: dict[int, float] = {}
        self._frames: dict[int, int] = {}

    def see(self, track_id: int, t: float) -> tuple[float, int]:
        first = self._first_seen.setdefault(track_id, t)
        self._frames[track_id] = self._frames.get(track_id, 0) + 1
        return first, self._frames[track_id]


def _as_numpy(values: Any) -> np.ndarray:
    return values.cpu().numpy() if hasattr(values, "cpu") else np.asarray(values)


def simplify_polygon(points: np.ndarray, max_points: int = MAX_POLYGON_POINTS) -> list[tuple[float, float]]:
    points = np.asarray(points, dtype=float).reshape(-1, 2)
    if len(points) > max_points:
        points = points[np.linspace(0, len(points) - 1, max_points).astype(int)]
    return [(float(x), float(y)) for x, y in points]


def tracks_from_result(result: Any, t: float, ages: TrackAges) -> list[Track]:
    """Ultralytics result -> tracks. Detections without a track ID are dropped."""
    boxes = result.boxes
    if boxes is None or boxes.id is None:
        return []
    ids = _as_numpy(boxes.id).astype(int)
    xyxy, classes, scores = _as_numpy(boxes.xyxy), _as_numpy(boxes.cls).astype(int), _as_numpy(boxes.conf)
    polygons = result.masks.xy if result.masks is not None else [None] * len(ids)
    tracks = []
    for track_id, box, cls, score, polygon in zip(ids, xyxy, classes, scores, polygons):
        first_seen, frames = ages.see(int(track_id), t)
        tracks.append(Track(id=int(track_id), box=tuple(float(v) for v in box),
                            polygon=[] if polygon is None else simplify_polygon(polygon),
                            label=str(result.names[int(cls)]), score=float(score), age_frames=frames,
                            first_seen_ts=first_seen))
    return tracks


class YoloeDetector:
    def __init__(self, settings: Settings) -> None:
        from ultralytics import YOLOE  # heavy import, only when the real detector is needed

        self._s = settings
        try:
            self._model = YOLOE(settings.detector)
            self.model_name = settings.detector
        except Exception:  # noqa: BLE001 - any failure to fetch or load falls back to the older weights
            log.warning("could not load %s, falling back to %s", settings.detector, settings.detector_fallback,
                        exc_info=True)
            self._model = YOLOE(settings.detector_fallback)
            self.model_name = settings.detector_fallback
        self._ages = TrackAges()

    def detect(self, image: np.ndarray, t: float) -> list[Track]:
        result = self._model.track(image, persist=True, tracker=str(TRACKER_CONFIG), imgsz=self._s.imgsz,
                                   device=self._s.device, conf=self._s.conf, verbose=False)[0]
        return tracks_from_result(result, t, self._ages)

    def reset(self) -> None:
        """Forget all tracks: the next call builds a fresh predictor and tracker, so IDs start again at 1."""
        self._model.predictor = None
        self._ages = TrackAges()


class FakeDetector:
    """Returns scripted track lists in order and then keeps repeating the last one."""

    model_name = "fake"

    def __init__(self, script: list[list[Track]]) -> None:
        self._script = script
        self._index = 0
        self.reset_calls = 0

    def detect(self, image: np.ndarray, t: float) -> list[Track]:
        tracks = self._script[min(self._index, len(self._script) - 1)]
        self._index += 1
        return tracks

    def reset(self) -> None:
        self.reset_calls += 1
