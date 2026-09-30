"""A dedicated face detector for the privacy veto (OpenCV YuNet, MIT licence).

YOLOE's open vocabulary often names parts of a face "glasses" or "short hair" and no "face" at all, so the promise
"your face never leaves the Mac" rests on this small, reliable face model instead.
"""

from __future__ import annotations

import hashlib
import threading
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from oi.contracts import Track

FACE_MODEL_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
                  "face_detection_yunet_2023mar.onnx")
FACE_MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
FACE_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "face_detection_yunet_2023mar.onnx"
DETECT_WIDTH = 640  # faces are found on a downscaled copy; boxes are scaled back to the full frame
MIN_SCORE = 0.6


def ensure_model(path: Path = FACE_MODEL_PATH, url: str = FACE_MODEL_URL, sha256: str = FACE_MODEL_SHA256) -> Path:
    """Download the face model once and refuse any file whose checksum does not match."""
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == sha256:
        return path
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError(f"face model checksum mismatch for {url}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(path)
    return path


class FaceFinder:
    """`find(image)` returns face boxes as tracks labelled "face" with negative ids (they are not tracked)."""

    def __init__(self, model_path: Path) -> None:
        self._detector = cv2.FaceDetectorYN.create(str(model_path), "", (320, 320), MIN_SCORE)
        self._lock = threading.Lock()

    def find(self, image: np.ndarray) -> list[Track]:
        h, w = image.shape[:2]
        scale = min(1.0, DETECT_WIDTH / w)
        small = cv2.resize(image, (round(w * scale), round(h * scale))) if scale < 1.0 else image
        with self._lock:
            self._detector.setInputSize((small.shape[1], small.shape[0]))
            _, faces = self._detector.detect(small)
        if faces is None:
            return []
        return [Track(id=-(i + 1), box=(float(x / scale), float(y / scale), float((x + fw) / scale),
                                        float((y + fh) / scale)),
                      polygon=[], label="face", score=float(face[-1]), age_frames=1, first_seen_ts=0.0)
                for i, face in enumerate(faces) for x, y, fw, fh in [face[:4]]]
