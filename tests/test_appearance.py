import numpy as np

from oi.appearance import signature, similar
from tests.helpers import sharp_image, trk

BOX = (400, 200, 700, 500)


def tinted(bgr: tuple[float, float, float]) -> np.ndarray:
    """A textured object in one colour on a grey frame."""
    image = sharp_image(boxes=(BOX,)).astype(np.float32)
    image[200:500, 400:700] *= np.array(bgr, np.float32) / 255
    return image.astype(np.uint8)


def test_the_same_object_looks_the_same():
    blue = tinted((255, 120, 40))
    assert similar(signature(blue, trk(1, BOX)), signature(blue, trk(2, (410, 205, 705, 510))))


def test_a_different_colour_is_a_different_object():
    blue, red = tinted((255, 120, 40)), tinted((40, 60, 255))
    assert not similar(signature(blue, trk(1, BOX)), signature(red, trk(2, BOX)))


def test_only_the_pixels_inside_the_outline_count():
    from oi.contracts import Track
    image = tinted((255, 120, 40))
    image[200:500, 400:550] = (40, 60, 255)  # the left half of the box is something red behind the object
    right_half = Track(id=1, box=BOX, polygon=[(550, 200), (700, 200), (700, 500), (550, 500)], label="cup", score=0.9,
                       age_frames=10, first_seen_ts=0.0)
    assert similar(signature(image, right_half), signature(tinted((255, 120, 40)), trk(2, (550, 200, 700, 500))))


def test_a_box_outside_the_frame_matches_nothing():
    image = tinted((255, 120, 40))
    assert not similar(signature(image, trk(1, (2000, 2000, 2100, 2100))), signature(image, trk(2, BOX)))
