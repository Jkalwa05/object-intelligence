"""Privacy veto: a crop that is really a person, or that holds a face, never goes to Claude (spec §2.1).

A label list can never be complete (the detector sometimes calls a person "flag" or "night sky"), so this also
looks at geometry: the focus box may not cover most of a person, sit in a person's head zone, or lie over a face.
"""

from __future__ import annotations

import math

import numpy as np

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


BODY_WIDEN = 1.0  # shoulders: the body zone is the face box widened by one face width per side
ON_BODY_SHARE = 0.50  # half of a box lies on the body: worn (shirt, necklace), not something in the background


GREY = 128


def person_zones(people: list[Track], frame_h: float) -> list[Box]:
    """Where people are: every person box, and for every face the body zone below it (the face box widened to the
    shoulders, from the hairline down to the bottom of the frame)."""
    zones = []
    for other in people:
        x1, y1, x2, y2 = other.box
        if other.label.lower() == "face":
            w, h = x2 - x1, y2 - y1
            zones.append((x1 - BODY_WIDEN * w, y1 - FACE_WIDEN * h, x2 + BODY_WIDEN * w, frame_h))
        else:
            zones.append(other.box)
    return zones


def on_person(track: Track, people: list[Track], frame_h: float) -> bool:
    """True if the track lies mostly on a person (see `person_zones`)."""
    area = _area(track.box)
    return bool(area) and any(_overlap(track.box, zone) >= ON_BODY_SHARE * area
                              for zone in person_zones(people, frame_h))


WORN_SHARE = 0.25  # a quarter of a box lies in a body zone ...
BOTTOM_EDGE = 0.02  # ... and it reaches the bottom edge of the frame (within 2 % of its height)


def worn(track: Track, people: list[Track], frame_h: float) -> bool:
    """Shirt, shoulders and arms of the person in front of the camera: partly in a body zone and cut off by the bottom
    edge, like every torso in a webcam picture. Something held in front of the chest ends above that edge."""
    area = _area(track.box)
    if not area or track.box[3] < frame_h * (1 - BOTTOM_EDGE):
        return False
    return any(_overlap(track.box, zone) >= WORN_SHARE * area for zone in person_zones(people, frame_h))


def mask_people(image: np.ndarray, people: list[Track]) -> np.ndarray:
    """A copy of the frame in which every person zone is flat grey: the only way a whole frame may leave the Mac."""
    out = image.copy()
    h, w = out.shape[:2]
    for x1, y1, x2, y2 in person_zones(people, h):
        out[max(0, math.floor(y1)):min(h, math.ceil(y2)), max(0, math.floor(x1)):min(w, math.ceil(x2))] = GREY
    return out


def privacy_veto(focus: Track, tracks: list[Track], s: Settings, head_zone: bool = True) -> bool:
    """True if the focus crop could show a person or a face. `tracks` are all raw detections of the frame.

    `head_zone=False` when a dedicated face detector supplies face boxes: faces are then covered directly, and the
    coarse "top third of a person" rule would only block objects held beside the head."""
    person_labels, face_labels = set(s.person_labels), set(s.face_labels)
    focus_area = _area(focus.box)
    for other in tracks:
        if other.id == focus.id:
            continue
        label = other.label.lower()
        if label in person_labels:
            x1, y1, x2, y2 = other.box
            zone = (x1, y1, x2, y1 + (y2 - y1) * HEAD_ZONE)
            if _overlap(focus.box, other.box) >= PERSON_COVER * _area(other.box):
                return True
            if head_zone and focus_area and _overlap(focus.box, zone) >= HEAD_SHARE * focus_area:
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
