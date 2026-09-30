"""Scene calibration: the background is measured once and then frozen, so its markers never flicker.

During the first seconds after a connection (or after "R") every background detection is collected. Objects that
were there in at least half of the frames become markers with their most common label and median box; after that
the scene does not change until the next calibration.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from statistics import median

from oi.contracts import Track

CALIBRATION_S = 5.0
MIN_PRESENCE = 0.5  # seen in at least half of the calibration frames
MATCH_IOU = 0.5
EPS = 1e-6

Box = tuple[float, float, float, float]


def _iou(a: Box, b: Box) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    inter = max(0.0, w) * max(0.0, h)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


@dataclass(frozen=True)
class SceneItem:
    label: str
    box: Box  # pixels of the full frame


@dataclass
class _Cluster:
    boxes: list[Box] = field(default_factory=list)
    labels: Counter[str] = field(default_factory=Counter)
    frames: set[int] = field(default_factory=set)


class SceneMap:
    def __init__(self, calibration_s: float = CALIBRATION_S) -> None:
        self._calibration_s = calibration_s
        self.reset()

    def reset(self) -> None:
        """Start a new calibration (key R in the browser)."""
        self._start: float | None = None
        self._frame = 0
        self._clusters: list[_Cluster] = []
        self._frozen: list[SceneItem] | None = None

    @property
    def calibrating(self) -> bool:
        return self._frozen is None

    @property
    def items(self) -> list[SceneItem]:
        return list(self._frozen or [])

    def observe(self, tracks: list[Track], now: float) -> bool:
        """Feed the background candidates of one frame. Returns True exactly once: when the scene freezes."""
        if self._frozen is not None:
            return False
        if self._start is None:
            self._start = now
        self._frame += 1
        for t in tracks:
            cluster = max(self._clusters, key=lambda c: _iou(c.boxes[-1], t.box), default=None)
            if cluster is None or _iou(cluster.boxes[-1], t.box) < MATCH_IOU:
                cluster = _Cluster()
                self._clusters.append(cluster)
            cluster.boxes.append(t.box)
            cluster.labels[t.label] += 1
            cluster.frames.add(self._frame)
        if now - self._start < self._calibration_s - EPS:
            return False
        self._frozen = [SceneItem(label=c.labels.most_common(1)[0][0],
                                  box=tuple(median(b[i] for b in c.boxes) for i in range(4)))  # type: ignore[arg-type]
                        for c in self._clusters if len(c.frames) >= MIN_PRESENCE * self._frame]
        return True
