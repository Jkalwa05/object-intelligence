"""A dedicated hand detector: Apple's Vision framework (VNDetectHumanHandPoseRequest), local, no download.

YOLOE's open vocabulary almost never says "hand", but "only what you hold gets focus" needs hands every frame.
"""

from __future__ import annotations

import cv2
import numpy as np
import Quartz
import Vision

from oi.contracts import Track

DETECT_WIDTH = 640
MIN_POINT_CONFIDENCE = 0.3
MAX_HANDS = 4
WIDEN = 0.20  # the joints sit inside the hand; widen their box by 20 % per side to cover palm and fingertips


def _cgimage(bgr: np.ndarray):
    h, w = bgr.shape[:2]
    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA).tobytes()
    provider = Quartz.CGDataProviderCreateWithData(None, rgba, len(rgba), None)
    return Quartz.CGImageCreate(w, h, 8, 32, w * 4, Quartz.CGColorSpaceCreateDeviceRGB(),
                                Quartz.kCGImageAlphaNoneSkipLast, provider, None, False,
                                Quartz.kCGRenderingIntentDefault)


class HandFinder:
    """`find(image)` returns hand boxes as tracks labelled "hand" with negative ids (they are not tracked)."""

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
        hands = []
        for observation in request.results() or []:
            points, _ = observation.recognizedPointsForGroupKey_error_(
                Vision.VNHumanHandPoseObservationJointsGroupNameAll, None)
            joints = [p.location() for p in (points or {}).values() if p.confidence() > MIN_POINT_CONFIDENCE]
            if len(joints) < 3:
                continue
            xs = [p.x * w for p in joints]
            ys = [(1.0 - p.y) * h for p in joints]  # Vision's origin is bottom-left
            x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
            dx, dy = (x2 - x1) * WIDEN, (y2 - y1) * WIDEN
            hands.append(Track(id=-(101 + len(hands)), box=(max(0.0, x1 - dx), max(0.0, y1 - dy), min(float(w), x2 + dx),
                                                             min(float(h), y2 + dy)),
                               polygon=[], label="hand", score=float(observation.confidence()), age_frames=1,
                               first_seen_ts=0.0))
        return hands
