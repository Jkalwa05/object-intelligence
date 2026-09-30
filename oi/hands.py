"""A dedicated hand detector: Apple's Vision framework (VNDetectHumanHandPoseRequest), local, no download.

YOLOE's open vocabulary almost never says "hand", but "only what you hold gets focus" needs hands every frame.
Vision's model is trained on a great many example hands; on top of that a hand only counts when Vision is sure, enough
of its 21 joints are visible, and it is found at the same place in two frames in a row.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import Quartz
import Vision

from oi.contracts import Track

DETECT_WIDTH = 1280  # full camera width: 12 instead of 7 joints on a held phone, still about 5 ms
MIN_POINT_CONFIDENCE = 0.3
MAX_HANDS = 4
MIN_HAND_CONFIDENCE = 0.6  # Vision's own confidence that this is a hand
MIN_JOINTS = 6  # of 21 joints: a held object may hide the rest, but fewer points make no hand shape
OUTLINE_POINTS = 16
OUTLINE_PAD = 0.15  # the joints are the skeleton: the outline lies 15 % of the hand size further out, on the skin
CONFIRM_IOU = 0.2  # the same hand in the next frame overlaps its last box at least this much

Point = tuple[float, float]
Box = tuple[float, float, float, float]


def _cgimage(bgr: np.ndarray):
    h, w = bgr.shape[:2]
    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA).tobytes()
    provider = Quartz.CGDataProviderCreateWithData(None, rgba, len(rgba), None)
    return Quartz.CGImageCreate(w, h, 8, 32, w * 4, Quartz.CGColorSpaceCreateDeviceRGB(),
                                Quartz.kCGImageAlphaNoneSkipLast, provider, None, False,
                                Quartz.kCGRenderingIntentDefault)


def hand_outline(joints: list[Point], w: int, h: int) -> list[Point]:
    """A smooth outline around the joints: for 16 directions, the farthest joint in that direction plus padding."""
    cx = sum(x for x, _ in joints) / len(joints)
    cy = sum(y for _, y in joints) / len(joints)
    size = max(max(x for x, _ in joints) - min(x for x, _ in joints), max(y for _, y in joints) - min(y for _, y in joints))
    pad = OUTLINE_PAD * size
    outline = []
    for k in range(OUTLINE_POINTS):
        ux, uy = math.cos(2 * math.pi * k / OUTLINE_POINTS), math.sin(2 * math.pi * k / OUTLINE_POINTS)
        r = max((x - cx) * ux + (y - cy) * uy for x, y in joints) + pad
        outline.append((min(float(w), max(0.0, cx + r * ux)), min(float(h), max(0.0, cy + r * uy))))
    return outline


def hand_track(joints: list[Point], confidence: float, index: int, w: int, h: int) -> Track | None:
    """A hand from its visible joints (pixels), or None when it does not look like a real hand."""
    if confidence < MIN_HAND_CONFIDENCE or len(joints) < MIN_JOINTS:
        return None
    outline = hand_outline(joints, w, h)
    box = (min(x for x, _ in outline), min(y for _, y in outline), max(x for x, _ in outline), max(y for _, y in outline))
    return Track(id=-(101 + index), box=box, polygon=outline, label="hand", score=confidence, age_frames=1,
                 first_seen_ts=0.0, joints=list(joints))


def _iou(a: Box, b: Box) -> float:
    inter = max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


class HandConfirmer:
    """A hand counts once it is found at about the same place in two frames in a row: one-frame ghosts never do."""

    def __init__(self) -> None:
        self._previous: list[Track] = []

    def confirm(self, hands: list[Track]) -> list[Track]:
        confirmed = [h for h in hands if any(_iou(h.box, p.box) >= CONFIRM_IOU for p in self._previous)]
        self._previous = hands
        return confirmed


class HandFinder:
    """`find(image)` returns the plausible hands as tracks labelled "hand" with negative ids (they are not tracked)."""

    def find(self, image: np.ndarray) -> list[Track]:
        h, w = image.shape[:2]
        scale = min(1.0, DETECT_WIDTH / w)
        small = cv2.resize(image, (round(w * scale), round(h * scale))) if scale < 1.0 else image
        request = Vision.VNDetectHumanHandPoseRequest.alloc().init()
        request.setMaximumHandCount_(MAX_HANDS)
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(_cgimage(small), None)
        ok, _ = handler.performRequests_error_([request], None)
        if not ok:
            return []
        hands: list[Track] = []
        for observation in request.results() or []:
            points, _ = observation.recognizedPointsForGroupKey_error_(
                Vision.VNHumanHandPoseObservationJointsGroupNameAll, None)
            joints = [(p.location().x * w, (1.0 - p.location().y) * h)  # Vision's origin is bottom-left
                      for p in (points or {}).values() if p.confidence() > MIN_POINT_CONFIDENCE]
            hand = hand_track(joints, float(observation.confidence()), len(hands), w, h)
            if hand is not None:
                hands.append(hand)
        return hands
