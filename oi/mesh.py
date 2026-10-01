"""Triangle meshes of the precision model (sub-project 6): binary STL from OpenSCAD, bounding boxes, size checks."""

from __future__ import annotations

import numpy as np

from oi.contracts import Vec3

STL_HEADER, STL_RECORD = 84, 50  # 80-byte header + triangle count; normal, 3 vertices, attribute per triangle
_RECORD = np.dtype([("normal", "<f4", 3), ("vertices", "<f4", (3, 3)), ("attribute", "<u2")])
AXES = ("Breite", "Höhe", "Tiefe")
Box = tuple[Vec3, Vec3]


def read_stl(data: bytes) -> np.ndarray:
    """The triangles of a binary STL as an (n, 3, 3) float32 array. A size that does not fit its count is broken."""
    if len(data) < STL_HEADER:
        raise ValueError("not a binary STL: too short")
    count = int.from_bytes(data[80:84], "little")
    if len(data) != STL_HEADER + STL_RECORD * count:
        raise ValueError(f"broken STL: {len(data)} bytes for {count} triangles")
    records = np.frombuffer(data, dtype=_RECORD, count=count, offset=STL_HEADER)
    return records["vertices"].astype(np.float32)


def bounds(triangles: np.ndarray) -> Box:
    if len(triangles) == 0:
        raise ValueError("no triangles: empty geometry")
    points = triangles.reshape(-1, 3)
    low, high = points.min(axis=0), points.max(axis=0)
    return (float(low[0]), float(low[1]), float(low[2])), (float(high[0]), float(high[1]), float(high[2]))


def union(boxes: list[Box]) -> Box:
    lows = np.array([low for low, _ in boxes], dtype=float).min(axis=0)
    highs = np.array([high for _, high in boxes], dtype=float).max(axis=0)
    return (float(lows[0]), float(lows[1]), float(lows[2])), (float(highs[0]), float(highs[1]), float(highs[2]))


def _mm(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def size_hint(size: Vec3, expected: Vec3 | None, tolerance: float = 0.10) -> str | None:
    """A sentence for the next check round when the model's size is off by more than 10 % on any axis."""
    if expected is None:
        return None
    off = [f"{AXES[i]} {_mm(size[i])} mm statt {_mm(expected[i])} mm" for i in range(3)
           if expected[i] > 0 and abs(size[i] - expected[i]) / expected[i] > tolerance]
    return f"Das Modell weicht von den recherchierten Maßen ab: {', '.join(off)}." if off else None
