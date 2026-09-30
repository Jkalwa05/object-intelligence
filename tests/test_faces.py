import hashlib

import cv2
import pytest
from ultralytics.utils import ASSETS

from oi.faces import FaceFinder, ensure_model


def test_ensure_model_downloads_and_verifies(tmp_path):
    source = tmp_path / "source.onnx"
    source.write_bytes(b"model bytes")
    good = hashlib.sha256(b"model bytes").hexdigest()
    target = tmp_path / "models" / "face.onnx"
    assert ensure_model(target, url=source.as_uri(), sha256=good) == target
    assert target.read_bytes() == b"model bytes"


def test_ensure_model_rejects_a_wrong_checksum(tmp_path):
    source = tmp_path / "source.onnx"
    source.write_bytes(b"tampered")
    target = tmp_path / "face.onnx"
    with pytest.raises(ValueError):
        ensure_model(target, url=source.as_uri(), sha256="0" * 64)
    assert not target.exists()


@pytest.mark.model
def test_face_finder_finds_faces():
    faces = FaceFinder(ensure_model()).find(cv2.imread(str(ASSETS / "zidane.jpg")))
    assert len(faces) >= 2 and all(f.label == "face" and f.id < 0 for f in faces)
