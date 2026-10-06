"""Measuring a product on its reference images (sub-project 7, spec §5–6).

Claude puts a box around the whole product and around every visible part, in each straight view of a technical
drawing or a photo. One orthographic view has the same scale in both directions, so the known size of the product
turns every box into millimetres: the part map. It holds every part with its range on x (left to right), y (bottom to
top) and z (back to front), measured from the centre of the product's box. The built model is compared with it part
by part.

Sub-project 8 adds the outline: in each view from the front, back or side, Claude marks the left and right edge of
the product in 20 bands of equal height. Every picture gives its own outline, the pictures check each other band
by band (a crate of bottles on a shop photo loses against the camera and the drawing), and the built model is
measured in the same bands.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass, field
from typing import Any, get_args

import numpy as np

from oi.contracts import MeasuredPart, PhotoView, ProfileBand, Range, Vec3
from oi.identify import IdentifyError

ASPECT_TOLERANCE = 0.12  # front and back: the scales from width and height may differ this much (no perspective)
DEPTH_TOLERANCE = 0.25  # side and top views: the measured depth may differ this much (sticks stick out)
OUTSIDE = 0.02  # a part may reach this far out of the product's box (share of the box)
MIN_TOLERANCE_MM = 1.5
RELATIVE_TOLERANCE = 0.02  # of the product's size on that axis
MAX_DEVIATIONS = 20
MAX_VIEWS = 6
MAX_VIEW_PARTS = 40
MAX_NAME = 60
MAX_TILT = 30.0  # degrees: a picture leaning more than that is not taken as upright
VIEWS: tuple[str, ...] = get_args(PhotoView)
AXES = ("x", "y", "z")
SLICES = 20  # bands of equal height, top to bottom (sub-project 8)
AGREE = 0.08  # pictures agree on a band when their widths differ at most this much from the median …
AGREE_MIN_MM = 1.5  # … or this many millimetres
CENTRE_AGREE = 0.04  # and their middles at most this share of the product's size
MAX_OUTLINE_DEVIATIONS = 10
SLICED = {"front": (0, 1), "back": (0, -1), "side-front-right": (2, 1), "side-front-left": (2, -1)}  # axis, sign
PROFILE_HEAD = ("Measured outline in 20 bands from top to bottom, in mm from the centre of the product's box; x is the "
                "width (left to right), z the depth (back to front):")
MAP_HEAD = ("Measured parts, in mm from the centre of the product's box (everything that sticks out included); "
            "x left to right, y bottom to top, z back to front:")

Box2 = tuple[float, float, float, float]  # left, top, right, bottom as shares of the picture's width and height


@dataclass(frozen=True)
class ViewBoxes:
    picture: int  # 1-based, in the order the pictures were sent
    view: PhotoView
    object: Box2  # everything of the product
    parts: list[tuple[str, Box2]]
    slices: list[tuple[float, float] | None] = field(default_factory=list)  # left and right edge per band, or None
    tilt: float = 0.0  # degrees the product leans to the right in the picture (a hand-held camera photo)


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _box(raw: Any) -> Box2 | None:
    if not isinstance(raw, list) or len(raw) != 4 or not all(_number(v) for v in raw):
        return None
    left, top, right, bottom = (float(v) for v in raw)
    if not (0.0 <= left < right <= 1.0 and 0.0 <= top < bottom <= 1.0):
        return None
    return left, top, right, bottom


def _inside(box: Box2, whole: Box2) -> bool:
    margin_x, margin_y = OUTSIDE * (whole[2] - whole[0]), OUTSIDE * (whole[3] - whole[1])
    return (box[0] >= whole[0] - margin_x and box[2] <= whole[2] + margin_x
            and box[1] >= whole[1] - margin_y and box[3] <= whole[3] + margin_y)


def _name(raw: Any) -> str:
    return " ".join(raw.split())[:MAX_NAME] if isinstance(raw, str) else ""


def _key(name: str) -> str:
    return " ".join(name.split()).casefold()


def parse_measure(text: str, pictures: int) -> tuple[list[ViewBoxes], str]:
    """Claude's boxes, checked: bad boxes, unknown views or pictures and parts outside the product drop out."""
    try:
        data = json.loads(text)
    except ValueError as error:
        raise IdentifyError("schema") from error
    if not isinstance(data, dict):
        raise IdentifyError("schema")
    views: list[ViewBoxes] = []
    for raw in data.get("views") or []:
        if not isinstance(raw, dict):
            continue
        picture, name, whole = raw.get("picture"), raw.get("view"), _box(raw.get("object"))
        if (not isinstance(picture, int) or isinstance(picture, bool) or not 1 <= picture <= pictures
                or name not in VIEWS or whole is None):
            continue
        parts = []
        for part in raw.get("parts") or []:
            label = _name(part.get("name")) if isinstance(part, dict) else ""
            box = _box(part.get("box")) if label else None
            if box is not None and _inside(box, whole):
                parts.append((label, box))
        tilt = float(raw["tilt"]) if _number(raw.get("tilt")) else 0.0
        views.append(ViewBoxes(picture=picture, view=name, object=whole, parts=parts[:MAX_VIEW_PARTS],
                               slices=_slices(raw.get("slices"), whole) if name in SLICED else [],
                               tilt=max(-MAX_TILT, min(MAX_TILT, tilt))))
    notes = data.get("notes")
    return views[:MAX_VIEWS], notes.strip() if isinstance(notes, str) else ""


def _slices(raw: Any, whole: Box2) -> list[tuple[float, float] | None]:
    """20 bands of left and right edges; a band that is hidden or out of the product's box becomes None."""
    if not isinstance(raw, list) or len(raw) != SLICES:
        return []
    margin = OUTSIDE * (whole[2] - whole[0])
    edges: list[tuple[float, float] | None] = []
    for entry in raw:
        ok = (isinstance(entry, list) and len(entry) == 2 and all(_number(v) for v in entry)
              and whole[0] - margin <= entry[0] < entry[1] <= whole[2] + margin)
        edges.append((float(entry[0]), float(entry[1])) if ok else None)
    return edges


def _scales(view: str, box_w: float, box_h: float, size: Vec3) -> tuple[float, float] | None:
    """Millimetres per pixel across and down the picture, or None for a view out of proportion."""
    width, height, depth = size
    if view in ("front", "back"):
        across, down = width / box_w, height / box_h
        return (across, down) if abs(across / down - 1.0) <= ASPECT_TOLERANCE else None
    scale = width / box_w if view == "top" else height / box_h
    measured_depth = (box_h if view == "top" else box_w) * scale
    return (scale, scale) if abs(measured_depth / depth - 1.0) <= DEPTH_TOLERANCE else None


def _axes(view: str, across: Range, down: Range) -> list[tuple[int, Range]]:
    """The model axes a view shows: (axis index, range). Across runs right in the picture, down runs downwards."""
    up = (-down[1], -down[0])
    mirrored = (-across[1], -across[0])
    return {"front": [(0, across), (1, up)], "back": [(0, mirrored), (1, up)],
            "side-front-right": [(2, across), (1, up)], "side-front-left": [(2, mirrored), (1, up)],
            "top": [(0, across), (2, down)]}[view]


def part_map(views: list[ViewBoxes], sizes_px: list[tuple[int, int]], size_mm: Vec3) -> list[MeasuredPart]:
    """Every measured part in mm from the centre of the product, merged by name over all views (spec §5.3)."""
    names: dict[str, str] = {}  # key -> the first spelling
    seen: dict[str, int] = {}
    ranges: dict[str, list[list[Range]]] = {}
    for view in views:
        picture_w, picture_h = sizes_px[view.picture - 1]
        left, top, right, bottom = view.object
        scales = _scales(view.view, (right - left) * picture_w, (bottom - top) * picture_h, size_mm)
        if scales is None:
            continue
        centre_x, centre_y = (left + right) / 2 * picture_w, (top + bottom) / 2 * picture_h
        lean = math.tan(math.radians(view.tilt)) if view.view != "top" else 0.0
        for name, (l, t, r, b) in view.parts:
            shift = (centre_y - (t + b) / 2 * picture_h) * lean  # pixels the leaning pushed this part to the right
            across = ((l * picture_w - shift - centre_x) * scales[0], (r * picture_w - shift - centre_x) * scales[0])
            down = ((t * picture_h - centre_y) * scales[1], (b * picture_h - centre_y) * scales[1])
            key = _key(name)
            names.setdefault(key, name)
            seen[key] = seen.get(key, 0) + 1
            axes = ranges.setdefault(key, [[], [], []])
            for axis, span in _axes(view.view, across, down):
                axes[axis].append(span)

    def mean(spans: list[Range]) -> Range | None:
        if not spans:
            return None
        return sum(s[0] for s in spans) / len(spans), sum(s[1] for s in spans) / len(spans)

    return [MeasuredPart(name=names[key], x=mean(axes[0]), y=mean(axes[1]), z=mean(axes[2]), views=seen[key])
            for key, axes in ranges.items()]


def _spans(part: MeasuredPart) -> str:
    return ", ".join(f"{axis} {span[0]:.1f}…{span[1]:.1f}" for axis, span in zip(AXES, (part.x, part.y, part.z),
                                                                              strict=True) if span is not None)


def map_text(parts: list[MeasuredPart]) -> str:
    """The part map for Claude, one line per part; the empty string when nothing was measured."""
    if not parts:
        return ""
    lines = [f"{p.name}: {_spans(p)} mm ({p.views} view{'' if p.views == 1 else 's'})" for p in parts]
    return "\n".join([MAP_HEAD, *lines])


def deviations(built: dict[str, tuple[Vec3, Vec3]], parts: list[MeasuredPart], size_mm: Vec3) -> list[str]:
    """What the built model gets wrong compared with the part map, the largest first (spec §6).

    `built` holds every compiled part's box. Both sides are measured from the centre of the whole product's box, so a
    model that is merely shifted counts as right."""
    if not built:
        return []
    low = [min(box[0][i] for box in built.values()) for i in range(3)]
    high = [max(box[1][i] for box in built.values()) for i in range(3)]
    centre = [(a + b) / 2 for a, b in zip(low, high, strict=True)]
    boxes = {_key(name): box for name, box in built.items()}
    found: list[tuple[float, str]] = []
    for part in parts:
        box = boxes.get(_key(part.name))
        if box is None:
            found.append((math.inf, f"{part.name}: missing in the model (measured {_spans(part)} mm)"))
            continue
        for axis, target in enumerate((part.x, part.y, part.z)):
            if target is None:
                continue
            start, end = box[0][axis] - centre[axis], box[1][axis] - centre[axis]
            off = max(abs(start - target[0]), abs(end - target[1]))
            if off > max(MIN_TOLERANCE_MM, RELATIVE_TOLERANCE * size_mm[axis]):
                found.append((off, f"{part.name}: {AXES[axis]} model {start:.1f}…{end:.1f}, measured "
                                   f"{target[0]:.1f}…{target[1]:.1f} mm (off by {off:.1f} mm)"))
    found.sort(key=lambda item: -item[0])
    return [text for _, text in found[:MAX_DEVIATIONS]]


# --- the outline in 20 bands (sub-project 8) ---------------------------------------------------------------------

def _agree(spans: list[tuple[Range, int]], size: float) -> tuple[Range, int] | None:
    """One band of one axis from all pictures: (range, how many agreed). From 3 pictures on, the median decides; of
    2 that disagree, the higher rank wins (drawing 3, camera 2, photo 1); of equal rank, neither."""
    if not spans:
        return None

    def fits(span: Range, width: float, middle: float) -> bool:
        return (abs((span[1] - span[0]) - width) <= max(AGREE_MIN_MM, AGREE * width)
                and abs((span[0] + span[1]) / 2 - middle) <= CENTRE_AGREE * size)

    if len(spans) >= 3:
        width = statistics.median(b - a for (a, b), _ in spans)
        middle = statistics.median((a + b) / 2 for (a, b), _ in spans)
        kept = [s for s in spans if fits(s[0], width, middle)] or [max(spans, key=lambda s: s[1])]
    elif len(spans) == 2:
        (first, rank1), (second, rank2) = spans
        if fits(first, second[1] - second[0], (second[0] + second[1]) / 2):
            kept = spans
        elif rank1 == rank2:
            return None
        else:
            kept = [spans[0] if rank1 > rank2 else spans[1]]
    else:
        kept = spans
    low = sum(span[0] for span, _ in kept) / len(kept)
    high = sum(span[1] for span, _ in kept) / len(kept)
    return (low, high), len(kept)


def profile(views: list[ViewBoxes], sizes_px: list[tuple[int, int]], size_mm: Vec3,
            ranks: list[int]) -> list[ProfileBand]:
    """The outline in 20 bands, from top to bottom, cross-checked over the pictures (spec 8 §3.3–3.5). `ranks` holds
    the rank of every picture; bands no picture shows are left out."""
    found: list[list[list[tuple[Range, int]]]] = [[[], [], []] for _ in range(SLICES)]
    for view in views:
        if view.view not in SLICED or len(view.slices) != SLICES:
            continue
        picture_w, picture_h = sizes_px[view.picture - 1]
        left, top, right, bottom = view.object
        scales = _scales(view.view, (right - left) * picture_w, (bottom - top) * picture_h, size_mm)
        if scales is None:
            continue
        centre_x, box_h = (left + right) / 2 * picture_w, (bottom - top) * picture_h
        lean = math.tan(math.radians(view.tilt))
        axis, sign = SLICED[view.view]
        for band, edges in enumerate(view.slices):
            if edges is None:
                continue
            shift = (box_h / 2 - (band + 0.5) / SLICES * box_h) * lean  # the band's middle above the box's middle
            start, end = ((e * picture_w - shift - centre_x) * scales[0] for e in edges)
            found[band][axis].append(((start, end) if sign > 0 else (-end, -start), ranks[view.picture - 1]))
    height = size_mm[1]
    bands = []
    for band, axes in enumerate(found):
        x, z = _agree(axes[0], size_mm[0]), _agree(axes[2], size_mm[2])
        if x is None and z is None:
            continue
        top_y = height / 2 - band * height / SLICES
        bands.append(ProfileBand(y=(top_y - height / SLICES, top_y), x=x[0] if x else None, z=z[0] if z else None,
                                 sources=max(x[1] if x else 0, z[1] if z else 0)))
    return bands


def _height(band: ProfileBand, size_mm: Vec3) -> str:
    share = ((band.y[0] + band.y[1]) / 2 + size_mm[1] / 2) / size_mm[1]
    return f"height {share * 100:.0f} % (y {band.y[0]:.1f}…{band.y[1]:.1f} mm)"


def _band_spans(band: ProfileBand) -> str:
    return ", ".join(f"{axis} {span[0]:.1f}…{span[1]:.1f}" for axis, span in (("x", band.x), ("z", band.z))
                     if span is not None)


def profile_text(bands: list[ProfileBand], size_mm: Vec3) -> str:
    """The outline for Claude, one line per band; the empty string when nothing was measured."""
    if not bands:
        return ""
    lines = [f"{_height(b, size_mm)}: {_band_spans(b)} mm ({b.sources} picture{'' if b.sources == 1 else 's'})"
             for b in bands]
    return "\n".join([PROFILE_HEAD, *lines])


def _slab(triangles: np.ndarray, low: float, high: float) -> tuple[np.ndarray, np.ndarray] | None:
    """The smallest and largest x, y, z of the mesh between two heights: its corners in between and the points where
    its edges cross either height. None when no part of the mesh lies there."""
    corners = triangles.reshape(-1, 3)
    points = [corners[(corners[:, 1] >= low) & (corners[:, 1] <= high)]]
    starts, ends = corners, np.roll(triangles, -1, axis=1).reshape(-1, 3)
    for level in (low, high):
        above, below = starts[:, 1] - level, ends[:, 1] - level
        crossing = above * below < 0
        share = (above[crossing] / (above[crossing] - below[crossing]))[:, None]
        points.append(starts[crossing] + share * (ends[crossing] - starts[crossing]))
    found = np.concatenate(points)
    return (found.min(axis=0), found.max(axis=0)) if len(found) else None


def outline_deviations(triangles: np.ndarray, bands: list[ProfileBand], size_mm: Vec3) -> list[str]:
    """Where the built model's outline leaves the measured one, the largest first, at most 10 lines. `triangles` is
    the whole model; like the parts, it is measured from the centre of its own box."""
    if not bands or not len(triangles):
        return []
    corners = triangles.reshape(-1, 3)
    centred = triangles - (corners.min(axis=0) + corners.max(axis=0)) / 2
    found: list[tuple[float, str]] = []
    for band in bands:
        extent = _slab(centred, band.y[0], band.y[1])
        if extent is None:
            found.append((math.inf, f"{_height(band, size_mm)}: no model here, measured {_band_spans(band)} mm"))
            continue
        for axis, span in ((0, band.x), (2, band.z)):
            if span is None:
                continue
            start, end = float(extent[0][axis]), float(extent[1][axis])
            off = max(abs(start - span[0]), abs(end - span[1]))
            if off > max(MIN_TOLERANCE_MM, RELATIVE_TOLERANCE * size_mm[axis]):
                found.append((off, f"{_height(band, size_mm)}: {AXES[axis]} model {start:.1f}…{end:.1f}, measured "
                                   f"{span[0]:.1f}…{span[1]:.1f} mm (off by {off:.1f} mm)"))
    found.sort(key=lambda item: -item[0])
    return [text for _, text in found[:MAX_OUTLINE_DEVIATIONS]]
