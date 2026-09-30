"""Builders for synthetic frames and pipeline data used across the tests."""

from __future__ import annotations

import cv2
import numpy as np

from oi.contracts import Track

Box = tuple[int, int, int, int]


def textured_patch(h: int, w: int, mirrored: bool = False, cell: int = 8) -> np.ndarray:
    """A sharp checkerboard on top of a left-to-right brightness ramp; mirroring flips the ramp."""
    ramp = np.linspace(40, 215, w)[None, :].repeat(h, axis=0)
    yy, xx = np.mgrid[0:h, 0:w]
    checker = np.where(((xx // cell) + (yy // cell)) % 2 == 0, 40.0, -40.0)
    patch = np.clip(ramp + checker, 0, 255).astype(np.uint8)
    return np.fliplr(patch) if mirrored else patch


def sharp_image(size: tuple[int, int] = (720, 1280), boxes: tuple[Box, ...] = (), mirrored: bool = False,
                cell: int = 8) -> np.ndarray:
    """Mid-grey BGR frame with a textured patch inside every box."""
    h, w = size
    image = np.full((h, w, 3), 128, np.uint8)
    for x1, y1, x2, y2 in boxes:
        image[y1:y2, x1:x2] = textured_patch(y2 - y1, x2 - x1, mirrored, cell)[..., None]
    return image


def blurry_image(size: tuple[int, int] = (720, 1280), boxes: tuple[Box, ...] = ()) -> np.ndarray:
    """The same frame, blurred everywhere (sigma 6)."""
    return cv2.GaussianBlur(sharp_image(size, boxes), (0, 0), 6)


def gradient_image() -> np.ndarray:
    """256x256 greyscale, brightness rising from left to right."""
    return np.tile(np.arange(256, dtype=np.uint8), (256, 1))


def trk(id: int, box: tuple[float, float, float, float], label: str = "cup", score: float = 0.9, age: int = 10,
        first_seen: float = 0.0) -> Track:
    return Track(id=id, box=box, polygon=[], label=label, score=score, age_frames=age, first_seen_ts=first_seen)
