"""Four check views of a precision model for Claude's visual check (sub-project 6).

matplotlib draws the triangles orthographically with simple Lambert shading in each part's colour on a light grey
background. The model's axes (x right, y up, z towards the viewer) become matplotlib's (x, -z, y), so "vorn" looks
at the model's front.
"""

from __future__ import annotations

import io

import numpy as np
from matplotlib.colors import to_rgb
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

VIEWS = ("vorn", "hinten", "rechts", "oben")
ANGLES = ((0.0, -90.0), (0.0, 90.0), (0.0, 0.0), (35.0, -55.0))  # (elevation, azimuth) per view
BACKGROUND = "#eceff1"
LIGHT = np.array([0.35, -0.55, 0.75]) / np.linalg.norm([0.35, -0.55, 0.75])  # from front, right, above
MAX_DRAWN = 60_000  # beyond this, only every n-th triangle is drawn: the check views stay fast


def render_views(parts: list[tuple[np.ndarray, str]], size: int = 512) -> list[bytes]:
    """PNG images of the model from the front, the back, the right and from above, `size` pixels square."""
    triangles = np.concatenate([tri for tri, _ in parts]).astype(float)
    colours = np.concatenate([np.tile(to_rgb(colour), (len(tri), 1)) for tri, colour in parts])
    if len(triangles) > MAX_DRAWN:
        step = int(np.ceil(len(triangles) / MAX_DRAWN))
        triangles, colours = triangles[::step], colours[::step]
    triangles = triangles[:, :, [0, 2, 1]] * np.array([1.0, -1.0, 1.0])  # model (x, y, z) -> matplotlib (x, -z, y)
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0)
    shade = 0.35 + 0.65 * np.abs(normals @ LIGHT)  # two-sided: the winding of every part does not matter
    faces = np.clip(colours * shade[:, None], 0.0, 1.0)
    points = triangles.reshape(-1, 3)
    centre = (points.min(axis=0) + points.max(axis=0)) / 2
    radius = float((points.max(axis=0) - points.min(axis=0)).max()) / 2 or 1.0
    return [_view(triangles, faces, centre, radius, elevation, azimuth, size) for elevation, azimuth in ANGLES]


def _view(triangles: np.ndarray, faces: np.ndarray, centre: np.ndarray, radius: float, elevation: float,
          azimuth: float, size: int) -> bytes:
    figure = Figure(figsize=(size / 100, size / 100), dpi=100, facecolor=BACKGROUND)
    axes = figure.add_subplot(projection="3d", facecolor=BACKGROUND)
    axes.set_proj_type("ortho")
    axes.add_collection3d(Poly3DCollection(triangles, facecolors=faces, edgecolors="none"))
    for setter, middle in zip((axes.set_xlim, axes.set_ylim, axes.set_zlim), centre, strict=True):
        setter(middle - radius, middle + radius)
    axes.set_box_aspect((1, 1, 1), zoom=1.35)
    axes.view_init(elev=elevation, azim=azimuth)
    axes.set_axis_off()
    figure.subplots_adjust(left=0, right=1, bottom=0, top=1)
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", facecolor=BACKGROUND)
    return buffer.getvalue()
