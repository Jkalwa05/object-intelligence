"""Privacy veto: a crop that is really a person, or that holds a face, never goes to Claude (spec §2.1).

A label list can never be complete (the detector sometimes calls a person "flag" or "night sky"), so this also
looks at geometry: the focus box may not cover most of a person, sit in a person's head zone, or lie over a face.
"""

from __future__ import annotations

from oi.config import Settings
from oi.contracts import Track

PERSON_COVER = 0.40  # the focus box covers 40 % of a person box: it is the person, not something held
HEAD_ZONE = 1 / 3  # the top third of a person box
HEAD_SHARE = 0.50  # half of the focus box lies in a head zone
FACE_SHARE = 0.20  # the focus box covers 20 % of a face box
FACE_WIDEN = 0.25  # a face box widened by 25 % per side includes hair, ears and earrings
ON_FACE_SHARE = 0.50  # half of the focus box lies on the widened face: it is worn, not held up

Box = tuple[float, float, float, float]


def _area(box: Box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _overlap(a: Box, b: Box) -> float:
    return _area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))


def privacy_veto(focus: Track, tracks: list[Track], s: Settings) -> bool:
    """True if the focus crop could show a person or a face. `tracks` are all raw detections of the frame."""
    person_labels, face_labels = set(s.person_labels), set(s.face_labels)
    focus_area = _area(focus.box)
    for other in tracks:
        if other.id == focus.id:
            continue
        label = other.label.lower()
        if label in person_labels:
            x1, y1, x2, y2 = other.box
            head_zone = (x1, y1, x2, y1 + (y2 - y1) * HEAD_ZONE)
            if _overlap(focus.box, other.box) >= PERSON_COVER * _area(other.box):
                return True
            if focus_area and _overlap(focus.box, head_zone) >= HEAD_SHARE * focus_area:
                return True
        elif label in face_labels:
            if _overlap(focus.box, other.box) >= FACE_SHARE * _area(other.box):
                return True
            x1, y1, x2, y2 = other.box
            dx, dy = (x2 - x1) * FACE_WIDEN, (y2 - y1) * FACE_WIDEN
            widened = (x1 - dx, y1 - dy, x2 + dx, y2 + dy)
            if focus_area and _overlap(focus.box, widened) >= ON_FACE_SHARE * focus_area:
                return True
    return False
