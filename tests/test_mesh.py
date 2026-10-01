import io
import struct
import time

import numpy as np
import pytest
from PIL import Image

from oi.mesh import bounds, read_stl, size_hint, union
from oi.render import VIEWS, render_views


def cube_stl(size: float = 10.0, offset: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> bytes:
    """A binary STL of an axis-aligned cube: 12 triangles."""
    h = size / 2
    ox, oy, oz = offset
    v = [(ox + x * h, oy + y * h, oz + z * h) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6),
             (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    data = bytearray(b"\0" * 80) + struct.pack("<I", len(faces))
    for a, b, c in faces:
        data += struct.pack("<12fH", 0, 0, 0, *v[a], *v[b], *v[c], 0)
    return bytes(data)


def test_read_stl_and_bounds():
    tri = read_stl(cube_stl(10.0, (5.0, 0.0, 0.0)))
    assert tri.shape == (12, 3, 3) and tri.dtype == np.float32
    assert bounds(tri) == ((0.0, -5.0, -5.0), (10.0, 5.0, 5.0))
    assert union([((0, 0, 0), (1, 1, 1)), ((-2, 0.5, 0), (0.5, 3, 0.5))]) == ((-2, 0, 0), (1, 3, 1))


def test_broken_stl_raises():
    good = cube_stl()
    for broken in (b"", good[:83], good[:-10], good + b"x" * 50):
        with pytest.raises(ValueError):
            read_stl(broken)
    with pytest.raises(ValueError):
        bounds(np.zeros((0, 3, 3), np.float32))


def test_size_hint():
    hint = size_hint((80.0, 146.7, 7.8), (71.5, 146.7, 7.8))
    assert hint is not None and "Breite" in hint and "80" in hint and "71,5" in hint
    assert size_hint((74.0, 140.0, 7.5), (71.5, 146.7, 7.8)) is None  # every axis within 10 %
    assert size_hint((80.0, 146.7, 7.8), None) is None


def _png(data: bytes) -> Image.Image:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return Image.open(io.BytesIO(data)).convert("RGB")


def test_render_views_are_four_png_of_the_right_size_and_not_blank():
    views = render_views([(read_stl(cube_stl()), "#9fc4e8")], size=256)
    assert len(views) == len(VIEWS) == 4
    for data in views:
        image = _png(data)
        assert image.size == (256, 256)
        assert len(np.unique(np.asarray(image).reshape(-1, 3), axis=0)) > 1


def test_front_and_back_differ_for_an_asymmetric_model():
    body = read_stl(cube_stl(40.0))
    nose = read_stl(cube_stl(12.0, (10.0, 10.0, 24.0)))  # sticks out of the front (+z), up and to the right
    front, back, right, top = (np.asarray(_png(v)) for v in render_views([(body, "#9fc4e8"), (nose, "#d0453a")],
                                                                          size=200))
    assert not np.array_equal(front, back)
    assert not np.array_equal(front, np.fliplr(back))  # not only mirrored: the nose sits on one side only


def test_a_big_model_renders_in_time():
    parts = [(read_stl(cube_stl(5.0, (x * 6.0, y * 6.0, 0.0))), "#9fc4e8") for x in range(65) for y in range(65)]
    started = time.perf_counter()
    render_views(parts, size=512)  # about 50 000 triangles
    elapsed = time.perf_counter() - started
    print(f"\nfour views of {65 * 65 * 12} triangles: {elapsed:.1f} s")
    assert elapsed < 20.0
