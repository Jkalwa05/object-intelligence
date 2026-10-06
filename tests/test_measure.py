import json

import pytest

from oi.contracts import MeasuredPart
from oi.identify import IdentifyError
from oi.measure import (SLICES, ViewBoxes, deviations, map_text, outline_deviations, parse_measure, part_map,
                        profile, profile_text)

SIZE = (160.0, 97.0, 55.0)  # DualShock 3: width, height, depth in mm
PICTURE = [(2000, 1000)]  # one picture, 2000 × 1000 px


def view(name: str, whole, parts, picture: int = 1) -> ViewBoxes:
    return ViewBoxes(picture=picture, view=name, object=whole, parts=parts)


def only(parts: list[MeasuredPart]) -> MeasuredPart:
    assert len(parts) == 1, parts
    return parts[0]


def close(actual, expected) -> bool:
    return actual is not None and all(a == pytest.approx(e, abs=0.01) for a, e in zip(actual, expected, strict=True))


def test_front_view_in_millimetres():
    whole = (0.1, 0.0, 0.9, 0.97)  # 1600 × 970 px: 0.1 mm per pixel both ways
    part = only(part_map([view("front", whole, [("Gehäuse-Ecke", (0.1, 0.0, 0.2, 0.097))])], PICTURE, SIZE))
    assert close(part.x, (-80.0, -60.0)) and close(part.y, (38.8, 48.5)) and part.z is None
    assert (part.name, part.views) == ("Gehäuse-Ecke", 1)


def test_back_view_mirrors_x():
    whole = (0.1, 0.0, 0.9, 0.97)
    part = only(part_map([view("back", whole, [("Ecke", (0.1, 0.0, 0.2, 0.097))])], PICTURE, SIZE))
    assert close(part.x, (60.0, 80.0)) and close(part.y, (38.8, 48.5))


def test_side_view_scales_by_height_and_tolerates_protruding_parts():
    whole = (0.3, 0.0, 0.62, 0.97)  # 640 × 970 px: 0.1 mm per pixel, 64 mm deep with the sticks (16 % over 55 mm)
    stick = ("Analogstick", (0.6, 0.4, 0.62, 0.5))
    right = only(part_map([view("side-front-right", whole, [stick])], PICTURE, SIZE))
    assert close(right.z, (28.0, 32.0)) and close(right.y, (-1.5, 8.5)) and right.x is None
    left = only(part_map([view("side-front-left", whole, [stick])], PICTURE, SIZE))
    assert close(left.z, (-32.0, -28.0))


def test_top_view_gives_x_and_z():
    whole = (0.1, 0.2, 0.9, 0.75)  # 1600 × 550 px: 160 × 55 mm
    corner = only(part_map([view("top", whole, [("Ecke", (0.1, 0.7, 0.15, 0.75))])], PICTURE, SIZE))
    assert close(corner.x, (-80.0, -70.0)) and close(corner.z, (22.5, 27.5)) and corner.y is None


def test_views_out_of_proportion_are_left_out():
    part = [("Taste", (0.2, 0.2, 0.3, 0.3))]
    assert part_map([view("front", (0.1, 0.0, 0.9, 0.776), part)], PICTURE, SIZE) == []  # scales differ by 20 %
    assert part_map([view("side-front-right", (0.1, 0.0, 0.55, 0.97), part)], PICTURE, SIZE) == []  # 90 mm deep


def test_one_picture_with_three_views():
    front = view("front", (0.1, 0.1, 0.5, 0.585), [("Dreieck-Taste", (0.41, 0.16, 0.425, 0.19))])  # 0.2 mm/px
    top = view("top", (0.1, 0.65, 0.5, 0.925), [("Dreieck-Taste", (0.411, 0.87, 0.426, 0.9))])
    side = view("side-front-right", (0.6, 0.1, 0.74, 0.585), [("USB-Buchse", (0.66, 0.1, 0.68, 0.12))])
    triangle, usb = part_map([front, top, side], PICTURE, SIZE)
    assert close(triangle.x, (44.2, 50.2)) and triangle.views == 2  # x from front and top, averaged
    assert close(triangle.y, (30.5, 36.5)) and close(triangle.z, (16.5, 22.5))
    assert usb.name == "USB-Buchse" and close(usb.z, (-4.0, 4.0)) and close(usb.y, (44.5, 48.5))


def test_names_merge_case_and_space_insensitively():
    whole = (0.1, 0.0, 0.9, 0.97)
    views = [view("front", whole, [("Dreieck-Taste", (0.5, 0.1, 0.6, 0.2))]),
             view("back", whole, [(" dreieck-taste ", (0.4, 0.1, 0.5, 0.2))])]
    part = only(part_map(views, PICTURE, SIZE))
    assert (part.name, part.views) == ("Dreieck-Taste", 2) and close(part.x, (0.0, 20.0))


def answer(views, notes: str = "") -> str:
    return json.dumps({"views": views, "notes": notes})


def test_parse_measure_drops_bad_boxes():
    whole = [0.1, 0.0, 0.9, 0.97]
    parts = [{"name": "A", "box": [0.1, 0.1, 0.2, 0.2]}, {"name": "B", "box": [0.1, 0.1, 0.2]},
             {"name": "C", "box": [0.1, 0.1, 1.2, 0.2]}, {"name": "D", "box": [0.3, 0.1, 0.2, 0.2]},
             {"name": " ", "box": [0.1, 0.1, 0.2, 0.2]}, {"name": "E", "box": ["a", 0.1, 0.2, 0.2]}]
    raw = [{"picture": 1, "view": "front", "object": whole, "parts": parts},
           {"picture": 1, "view": "bottom", "object": whole, "parts": []},
           {"picture": 0, "view": "front", "object": whole, "parts": []},
           {"picture": 3, "view": "front", "object": whole, "parts": []},
           {"picture": True, "view": "front", "object": whole, "parts": []},
           {"picture": 2, "view": "top", "object": [0.5, 0.0, 0.4, 0.97], "parts": []}]
    views, notes = parse_measure(answer(raw, "Zeichnung von dimensions.com"), pictures=2)
    assert views == [ViewBoxes(1, "front", (0.1, 0.0, 0.9, 0.97), [("A", (0.1, 0.1, 0.2, 0.2))])]
    assert notes == "Zeichnung von dimensions.com"


def test_parse_measure_cuts_views_and_parts():
    many = [{"name": f"Teil {i}", "box": [0.2, 0.2, 0.3, 0.3]} for i in range(45)]
    raw = [{"picture": 1, "view": "front", "object": [0.1, 0.0, 0.9, 0.97], "parts": many} for _ in range(8)]
    views, _ = parse_measure(answer(raw), pictures=1)
    assert len(views) == 6 and all(len(v.parts) == 40 for v in views)
    with pytest.raises(IdentifyError):
        parse_measure("keine Antwort", pictures=1)


def test_parts_outside_the_object_are_dropped():
    raw = [{"picture": 1, "view": "front", "object": [0.1, 0.0, 0.5, 0.97],
            "parts": [{"name": "drin", "box": [0.45, 0.1, 0.505, 0.2]},  # 1.25 % of the box out: still in
                      {"name": "daneben", "box": [0.52, 0.1, 0.55, 0.2]}]}]  # 12.5 % out
    views, _ = parse_measure(answer(raw), pictures=1)
    assert [name for name, _ in views[0].parts] == ["drin"]


def test_map_text_lines():
    parts = [MeasuredPart(name="Dreieck-Taste", x=(44.0, 50.0), y=(20.06, 26.0), z=None, views=2),
             MeasuredPart(name="USB-Buchse", x=None, y=(44.5, 48.5), z=(-2.0, 2.0), views=1)]
    lines = map_text(parts).splitlines()
    assert "centre" in lines[0] and "x left to right" in lines[0]
    assert lines[1:] == ["Dreieck-Taste: x 44.0…50.0, y 20.1…26.0 mm (2 views)",
                         "USB-Buchse: y 44.5…48.5, z -2.0…2.0 mm (1 view)"]
    assert map_text([]) == ""


def test_deviations_tolerance_missing_and_order():
    body = ((-80.0, -48.5, -27.5), (80.0, 48.5, 27.5))
    shift = 10.0  # the whole model is built 10 mm too far right: compared from the centre, that does not count
    built = {name: (tuple(a + (shift if i == 0 else 0) for i, a in enumerate(low)),
                    tuple(b + (shift if i == 0 else 0) for i, b in enumerate(high)))
             for name, (low, high) in {"Gehäuse": body, "Dreieck-Taste": ((48.0, 20.0, 20.0), (54.0, 26.0, 23.0)),
                                       "Kreis-Taste": ((58.0, 10.0, 20.0), (64.0, 16.0, 23.0))}.items()}
    parts = [MeasuredPart(name="Kreis-Taste", x=(56.0, 62.0), y=(10.0, 16.0), z=None, views=1),  # 2 mm: within 3.2
             MeasuredPart(name="dreieck-taste", x=(44.0, 50.0), y=(20.0, 26.0), z=None, views=2),  # 4 mm in x
             MeasuredPart(name="Steuerkreuz", x=(-62.0, -32.0), y=(2.0, 30.0), z=None, views=1)]
    assert deviations(built, parts, SIZE) == [
        "Steuerkreuz: missing in the model (measured x -62.0…-32.0, y 2.0…30.0 mm)",
        "dreieck-taste: x model 48.0…54.0, measured 44.0…50.0 mm (off by 4.0 mm)"]
    crowd = [MeasuredPart(name=f"Teil {i}", x=(0.0, 1.0), y=None, z=None, views=1) for i in range(25)]
    assert len(deviations(built, crowd, SIZE)) == 20
    assert deviations(built, [], SIZE) == []


# --- sub-project 8: the outline in 20 slices -----------------------------------------------------------------------

def sliced(name: str, whole, edges: dict[int, tuple[float, float]], picture: int = 1) -> ViewBoxes:
    return ViewBoxes(picture=picture, view=name, object=whole, parts=[],
                     slices=[edges.get(i) for i in range(SLICES)])


FRONT_BOX = (0.1, 0.0, 0.9, 0.97)  # 1600 × 970 px of 2000 × 1000: 0.1 mm per pixel


def test_front_slices_in_millimetres():
    [band] = profile([sliced("front", FRONT_BOX, {0: (0.4, 0.6)})], PICTURE, SIZE, ranks=[2])
    assert close(band.y, (43.65, 48.5)) and close(band.x, (-20.0, 20.0)) and band.z is None and band.sources == 1


def test_side_slices_give_depth():
    whole = (0.3, 0.0, 0.62, 0.97)  # 0.1 mm per pixel from the height, 64 mm deep with the sticks
    [right] = profile([sliced("side-front-right", whole, {3: (0.5, 0.6)})], PICTURE, SIZE, ranks=[3])
    assert close(right.z, (8.0, 28.0)) and right.x is None
    [left] = profile([sliced("side-front-left", whole, {3: (0.5, 0.6)})], PICTURE, SIZE, ranks=[3])
    assert close(left.z, (-28.0, -8.0))


def test_hidden_bands_are_skipped():
    [band] = profile([sliced("front", FRONT_BOX, {5: (0.4, 0.6)})], PICTURE, SIZE, ranks=[2])
    assert close(band.y, (19.4, 24.25))  # band 5 of 20, counted from the top


def test_cross_validation_drops_the_outlier():
    camera = sliced("front", FRONT_BOX, {0: (0.4, 0.6)}, picture=1)  # 40 mm
    drawing = sliced("front", FRONT_BOX, {0: (0.39875, 0.60125)}, picture=2)  # 40.5 mm
    crate = sliced("front", FRONT_BOX, {0: (0.325, 0.675)}, picture=3)  # 70 mm: a crate of bottles
    [band] = profile([camera, drawing, crate], PICTURE * 3, SIZE, ranks=[2, 3, 1])
    assert close(band.x, (-20.125, 20.125)) and band.sources == 2


def test_two_sources_prefer_the_higher_rank():
    photo = sliced("front", FRONT_BOX, {0: (0.325, 0.675)}, picture=1)
    camera = sliced("front", FRONT_BOX, {0: (0.4, 0.6)}, picture=2)
    [band] = profile([photo, camera], PICTURE * 2, SIZE, ranks=[1, 2])
    assert close(band.x, (-20.0, 20.0)) and band.sources == 1
    agreeing = sliced("front", FRONT_BOX, {0: (0.399, 0.601)}, picture=1)
    [both] = profile([agreeing, camera], PICTURE * 2, SIZE, ranks=[1, 2])
    assert both.sources == 2 and close(both.x, (-20.1, 20.1))  # 40.4 and 40 mm agree: their mean


def test_parse_slices():
    whole = [0.1, 0.0, 0.9, 0.97]
    good = [[0.4, 0.6]] + [None] * 18 + [[0.6, 0.4]]
    raw = [{"picture": 1, "view": "front", "object": whole, "parts": [], "slices": good},
           {"picture": 1, "view": "back", "object": whole, "parts": [], "slices": [[0.4, 0.6]] * 19},
           {"picture": 1, "view": "top", "object": whole, "parts": [], "slices": [[0.4, 0.6]] * 20},
           {"picture": 1, "view": "front", "object": whole, "parts": [], "slices": [[0.0, 0.95]] + [None] * 19}]
    front, back, top, outside = parse_measure(answer(raw), pictures=1)[0]
    assert front.slices[0] == (0.4, 0.6) and front.slices[19] is None and len(front.slices) == 20
    assert back.slices == [] and top.slices == []  # 19 entries; no slices from above
    assert outside.slices[0] is None  # far outside the product's box
    assert parse_measure(answer([{"picture": 1, "view": "front", "object": whole, "parts": []}]), 1)[0][0].slices == []


def box_mesh(width: float, height: float, depth: float):
    from oi.mesh import read_stl
    from oi.scad import cube_stl
    return read_stl(cube_stl(1.0, (0.0, 0.0, 0.0))) * [width, height, depth]


def test_outline_deviations_measure_each_band():
    bands = profile([sliced("front", FRONT_BOX, {0: (0.4, 0.6), 1: (0.1, 0.9)})], PICTURE, SIZE, ranks=[2])
    assert outline_deviations(box_mesh(160.0, 97.0, 55.0), bands, SIZE) == [  # band 1 fits the box
        "height 98 % (y 43.6…48.5 mm): x model -80.0…80.0, measured -20.0…20.0 mm (off by 60.0 mm)"]
    many = profile([sliced("front", FRONT_BOX, {i: (0.4, 0.6) for i in range(SLICES)})], PICTURE, SIZE, ranks=[2])
    assert len(outline_deviations(box_mesh(160.0, 97.0, 55.0), many, SIZE)) == 10
    short = outline_deviations(box_mesh(160.0, 48.5, 55.0), bands, SIZE)  # the model is half as tall
    assert short[0].startswith("height 98 % (y 43.6…48.5 mm): no model here")


def test_profile_text():
    bands = profile([sliced("front", FRONT_BOX, {0: (0.4, 0.6)}, picture=1),
                     sliced("front", FRONT_BOX, {0: (0.4, 0.6)}, picture=2)], PICTURE * 2, SIZE, ranks=[2, 1])
    lines = profile_text(bands, SIZE).splitlines()
    assert "20 bands" in lines[0]
    assert lines[1:] == ["height 98 % (y 43.6…48.5 mm): x -20.0…20.0 mm (2 pictures)"]
    assert profile_text([], SIZE) == ""
