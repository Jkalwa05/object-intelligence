"""Colour signature of an object, to recognise it when the tracker gives it a new number (spec §11).

Colours alone cannot tell objects apart: the same iPhone from front and back is barely similar, a lamp and an iPhone
can look alike. They are only the last check, after time (at most 3 s gone), place (the old one has vanished) and
size; a doubtful case is analysed anew rather than given someone else's name.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from oi.contracts import Track

BINS = [8, 4, 4]  # hue, saturation, brightness: coarse, so light and pose may change a little
MIN_SIMILARITY = 0.5  # correlation of two signatures


def signature(image: np.ndarray, track: Track) -> np.ndarray:
    """Colour histogram of the object's own pixels (inside its outline if there is one), summing to 1."""
    h, w = image.shape[:2]
    x1, y1 = max(0, math.floor(track.box[0])), max(0, math.floor(track.box[1]))
    x2, y2 = min(w, math.ceil(track.box[2])), min(h, math.ceil(track.box[3]))
    if x2 <= x1 or y2 <= y1:
        return np.zeros(int(np.prod(BINS)), np.float32)
    crop = image[y1:y2, x1:x2]
    mask = None
    if len(track.polygon) >= 3:
        mask = np.zeros(crop.shape[:2], np.uint8)
        cv2.fillPoly(mask, [np.array([[round(x - x1), round(y - y1)] for x, y in track.polygon], np.int32)], 255)
    hist = cv2.calcHist([cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)], [0, 1, 2], mask, BINS, [0, 180, 0, 256, 0, 256])
    total = float(hist.sum())
    return (hist / total).flatten() if total else np.zeros(int(np.prod(BINS)), np.float32)


def similar(a: np.ndarray, b: np.ndarray) -> bool:
    if not a.any() or not b.any():
        return False
    return float(cv2.compareHist(a, b, cv2.HISTCMP_CORREL)) >= MIN_SIMILARITY
