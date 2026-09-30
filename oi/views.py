"""View collector: quality gate, view fingerprints and the best crop of each view (spec §2.4).

Pure logic on image arrays. For the focus object it decides when a crop is good enough for Claude, releases the
sharpest crop of a short window, and tells whether that crop shows a view that has not been sent yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

from oi.config import Settings
from oi.contracts import Track

GateFailure = Literal["cut", "small", "blurry", "unsteady", "person", "lower"]


def sharpness(gray: np.ndarray) -> float:
    """Variance of the Laplacian after scaling to 256 px width; higher means sharper."""
    h, w = gray.shape[:2]
    small = cv2.resize(gray, (256, max(1, round(h * 256 / w))), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(small, cv2.CV_64F).var())


def dhash(gray: np.ndarray) -> int:
    """64-bit difference hash: scale to 9x8 and compare horizontal neighbours."""
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA).astype(np.int16)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    return sum(1 << i for i, bit in enumerate(bits) if bit)


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def _crop_bounds(shape: tuple[int, ...], box: tuple[float, float, float, float], margin: float
                 ) -> tuple[int, int, int, int]:
    h, w = shape[:2]
    x1, y1, x2, y2 = box
    mx, my = (x2 - x1) * margin, (y2 - y1) * margin
    return max(0, round(x1 - mx)), max(0, round(y1 - my)), min(w, round(x2 + mx)), min(h, round(y2 + my))


def crop_box(image: np.ndarray, box: tuple[float, float, float, float], margin: float) -> np.ndarray:
    """The box plus `margin` of its size on every side, clamped to the image."""
    left, top, right, bottom = _crop_bounds(image.shape, box, margin)
    return image[top:bottom, left:right]


def keep_only_object(crop: np.ndarray, polygon: list[tuple[float, float]], origin: tuple[int, int],
                     widen_px: int) -> np.ndarray:
    """Grey out everything outside the object's (slightly widened) outline, so only the object leaves the Mac."""
    if len(polygon) < 3:
        return crop
    mask = np.zeros(crop.shape[:2], np.uint8)
    points = np.array([[round(x - origin[0]), round(y - origin[1])] for x, y in polygon], np.int32)
    cv2.fillPoly(mask, [points], 255)
    if widen_px > 0:
        mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * widen_px + 1, 2 * widen_px + 1)))
    out = np.full_like(crop, 128)
    out[mask > 0] = crop[mask > 0]
    return out


def encode_for_claude(crop: np.ndarray, long_edge: int, quality: int) -> bytes:
    """JPEG with the long edge shrunk to at most `long_edge` pixels (never enlarged)."""
    h, w = crop.shape[:2]
    scale = long_edge / max(h, w)
    if scale < 1.0:
        crop = cv2.resize(crop, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buffer = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("JPEG encoding failed")
    return buffer.tobytes()


def quality_q(s: float, min_sharpness: float) -> float:
    """Sharpness mapped to an evidence weight: the threshold gives 0.5, five times the threshold gives 1.0."""
    return min(1.0, max(0.5, 0.5 + 0.5 * (s - min_sharpness) / (4 * min_sharpness)))


@dataclass(frozen=True)
class ReadyCrop:
    jpeg: bytes
    sharpness: float
    q: float
    dhash: int
    aspect: float
    view_id: int
    is_new_view: bool


@dataclass(frozen=True)
class ViewResult:
    ready: ReadyCrop | None
    failing: GateFailure | None
    hint: GateFailure | None
    sharpness: float | None


@dataclass(frozen=True)
class _SentView:
    dhash: int
    aspect: float
    view_id: int


class ViewCollector:
    """One per focus track. Call `offer` on every frame; call `mark_sent` when a released crop went to Claude."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._steady_since: float | None = None
        self._fail_since: float | None = None
        self._armed = True
        self._forced = False
        self._window_start: float | None = None
        self._best: tuple[float, np.ndarray, int, float] | None = None  # sharpness, sendable crop, dhash, aspect
        self._last_released: int | None = None
        self._sent: list[_SentView] = []
        self._next_view_id = 1

    def offer(self, track: Track, image: np.ndarray, steady: float, now: float,
              blocked: GateFailure | None = None) -> ViewResult:
        """`blocked`: the privacy veto's reason ("person", or "lower" for a held object in front of the face)."""
        s = self._s
        if steady >= s.steady_min:
            if self._steady_since is None:
                self._steady_since = now
        else:
            self._steady_since = None

        failing, sharp, crop, gray = (blocked, None, None, None) if blocked else self._gate(track, image, now)
        if failing is not None:
            if self._fail_since is None:
                self._fail_since = now
            hint = failing if now - self._fail_since >= s.hint_after_s else None
            self._window_start, self._best, self._armed = None, None, True
            return ViewResult(ready=None, failing=failing, hint=hint, sharpness=sharp)
        self._fail_since = None

        x1, y1, x2, y2 = track.box
        fingerprint, aspect = dhash(gray), (x2 - x1) / (y2 - y1)
        if not self._armed and (self._forced or (self._last_released is not None and hamming(
                fingerprint, self._last_released) >= s.dhash_min_distance)):
            self._armed = True
        if not self._armed:
            return ViewResult(ready=None, failing=None, hint=None, sharpness=sharp)

        if self._window_start is None:
            self._window_start, self._best = now, None
        if self._best is None or sharp > self._best[0]:
            left, top, _, _ = _crop_bounds(image.shape, track.box, s.crop_margin)
            widen = round(s.mask_dilate * max(x2 - x1, y2 - y1))
            self._best = (sharp, keep_only_object(crop, track.polygon, (left, top), widen), fingerprint, aspect)
        if now - self._window_start < s.best_of_window_s:
            return ViewResult(ready=None, failing=None, hint=None, sharpness=sharp)

        ready = self._release(*self._best)
        self._armed, self._forced, self._window_start, self._best = False, False, None, None
        self._last_released = ready.dhash
        return ViewResult(ready=ready, failing=None, hint=None, sharpness=sharp)

    def mark_sent(self, crop: ReadyCrop) -> None:
        if crop.is_new_view:
            self._sent.append(_SentView(crop.dhash, crop.aspect, crop.view_id))
            self._next_view_id = crop.view_id + 1

    def rearm(self) -> None:
        """The released crop could not be sent (a call was running): release again with the next good window."""
        self._armed = True

    def force_next(self) -> None:
        """Release the next good crop even if it shows a view that was already sent (\"Neu prüfen\")."""
        self._forced = True

    def _gate(self, track: Track, image: np.ndarray, now: float
              ) -> tuple[GateFailure | None, float | None, np.ndarray | None, np.ndarray | None]:
        s = self._s
        h, w = image.shape[:2]
        x1, y1, x2, y2 = track.box
        edge = s.edge_margin * w
        if x1 < edge or y1 < edge or w - x2 < edge or h - y2 < edge:
            return "cut", None, None, None
        if min(x2 - x1, y2 - y1) < s.min_box_side_px:
            return "small", None, None, None
        crop = crop_box(image, track.box, s.crop_margin)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        sharp = sharpness(gray)
        if sharp < s.min_sharpness:
            return "blurry", sharp, crop, gray
        if self._steady_since is None or now - self._steady_since < s.steady_hold_s:
            return "unsteady", sharp, crop, gray
        return None, sharp, crop, gray

    def _release(self, sharp: float, crop: np.ndarray, fingerprint: int, aspect: float) -> ReadyCrop:
        s = self._s
        is_new = all(hamming(fingerprint, v.dhash) >= s.dhash_min_distance
                     or abs(aspect - v.aspect) / v.aspect >= s.aspect_change for v in self._sent)
        if is_new:
            view_id = self._next_view_id
        else:
            view_id = min(self._sent, key=lambda v: hamming(fingerprint, v.dhash)).view_id
        return ReadyCrop(jpeg=encode_for_claude(crop, s.crop_long_edge, s.crop_jpeg_quality), sharpness=sharp,
                         q=quality_q(sharp, s.min_sharpness), dhash=fingerprint, aspect=aspect, view_id=view_id,
                         is_new_view=is_new)
