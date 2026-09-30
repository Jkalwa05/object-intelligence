import cv2
import numpy as np
import pytest

from oi.config import Settings
from oi.views import (ViewCollector, crop_box, dhash, encode_for_claude, hamming, quality_q, sharpness)
from tests.helpers import blurry_image, gradient_image, sharp_image, trk

BOX = (400, 200, 700, 500)


def gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def test_sharpness_separates_sharp_from_blurred():
    full = ((0, 0, 256, 256),)
    assert sharpness(gray(sharp_image((256, 256), full))) > 60 > sharpness(gray(blurry_image((256, 256), full)))


def test_dhash_identical_zero_mirrored_far():
    g = gradient_image()
    assert hamming(dhash(g), dhash(g)) == 0
    assert hamming(dhash(g), dhash(np.fliplr(g))) >= 14


def test_crop_margin_and_clamp():
    image = sharp_image()
    assert crop_box(image, (100, 100, 200, 200), 0.12).shape[:2] == (124, 124)
    corner = crop_box(image, (0, 0, 50, 50), 0.12)
    assert corner.shape[:2] == (56, 56)  # clamped at 0 on the top/left, margin kept on the bottom/right


def test_encode_limits_long_edge():
    jpeg = encode_for_claude(np.zeros((1000, 2000, 3), np.uint8), long_edge=1024, quality=90)
    decoded = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert max(decoded.shape[:2]) == 1024


@pytest.mark.parametrize("box,reason", [((2, 100, 300, 400), "cut"), ((500, 300, 560, 360), "small")])
def test_gate_reasons(box, reason):
    result = ViewCollector(Settings()).offer(trk(1, box), sharp_image(boxes=(box,)), now=0.0)
    assert result.failing == reason and result.ready is None


def test_blurry_frame_is_only_reported():
    result = ViewCollector(Settings()).offer(trk(1, BOX), blurry_image(boxes=(BOX,)), now=0.0)
    assert (result.failing, result.hint, result.ready) == ("blurry", None, None)


def offer_series(collector, image, start, end):
    results, i = [], 0
    while (t := start + i * 0.1) <= end + 1e-9:
        results.append((t, collector.offer(trk(1, BOX), image, now=t)))
        i += 1
    return results


def test_releases_once_after_the_window():
    results = offer_series(ViewCollector(Settings()), sharp_image(boxes=(BOX,)), 0.0, 2.0)
    released = [t for t, r in results if r.ready is not None]
    assert released == [pytest.approx(0.5)]


def test_a_shaky_video_still_gets_its_snapshot():
    # Live test 2026-10-01: a hand-held phone is never still for a whole second, so nothing was ever sent. The video
    # is fine as it is: the sharpest frame of a short window is the stillest one, and it goes out without a hint.
    collector, results = ViewCollector(Settings()), []
    for i in range(8):
        image = sharp_image(boxes=(BOX,)) if i == 3 else blurry_image(boxes=(BOX,))
        results.append(collector.offer(trk(1, BOX), image, now=i * 0.1))
    ready = [r.ready for r in results if r.ready]
    assert len(ready) == 1 and ready[0].sharpness == max(r.sharpness for r in results)
    assert all(r.hint is None for r in results)


def test_only_blurry_frames_still_give_a_snapshot_after_two_seconds():
    results = offer_series(ViewCollector(Settings()), blurry_image(boxes=(BOX,)), 0.0, 3.0)
    assert [t for t, r in results if r.ready is not None] == [pytest.approx(2.0)]
    assert all(r.hint is None for _, r in results)


def test_release_is_the_sharpest_of_its_window():
    collector, seen = ViewCollector(Settings()), []
    for i in range(10):
        image = sharp_image(boxes=(BOX,), cell=4 if i % 2 else 8)
        result = collector.offer(trk(1, BOX), image, now=i * 0.1)
        if result.sharpness is not None:
            seen.append(result.sharpness)
        if result.ready is not None:
            assert result.ready.sharpness == max(seen)
            return
    pytest.fail("no crop released")


def test_new_view_after_turning():
    collector = ViewCollector(Settings())
    first = next(r.ready for _, r in offer_series(collector, sharp_image(boxes=(BOX,)), 0.0, 1.0) if r.ready)
    assert (first.is_new_view, first.view_id) == (True, 1)
    collector.mark_sent(first)
    turned = next(r.ready for _, r in offer_series(collector, sharp_image(boxes=(BOX,), mirrored=True), 1.1, 2.0)
                  if r.ready)
    assert (turned.is_new_view, turned.view_id) == (True, 2)
    collector.mark_sent(turned)
    collector.force_next()
    again = next(r.ready for _, r in offer_series(collector, sharp_image(boxes=(BOX,)), 2.1, 3.0) if r.ready)
    assert (again.is_new_view, again.view_id) == (False, 1)


def test_hints_only_for_what_the_user_can_change():
    cut, collector = (2, 100, 300, 400), ViewCollector(Settings())
    by_step = [collector.offer(trk(1, cut), sharp_image(boxes=(cut,)), now=i * 0.1) for i in range(21)]
    assert by_step[19].hint is None and by_step[20].hint == "cut"
    assert all(r.hint is None for _, r in offer_series(ViewCollector(Settings()), blurry_image(boxes=(BOX,)), 0.0, 3.0))


def test_quality_q_mapping():
    assert quality_q(60, 60) == 0.5
    assert quality_q(300, 60) == 1.0
    assert quality_q(1000, 60) == 1.0


def test_privacy_block_never_releases_and_hints():
    collector = ViewCollector(Settings())
    image = sharp_image(boxes=(BOX,))
    results = [collector.offer(trk(1, BOX), image, now=i * 0.1, blocked="person") for i in range(22)]
    assert all(r.ready is None and r.failing == "person" for r in results)
    assert results[19].hint is None and results[20].hint == "person"


def test_released_crop_contains_only_the_object():
    from oi.contracts import Track
    image = sharp_image(boxes=(BOX,))
    image[166:184, 400:700] = 255  # a bright "face" above the object, inside the crop margin
    track = Track(id=1, box=BOX, polygon=[(400, 200), (700, 200), (700, 500), (400, 500)], label="cup", score=0.9,
                  age_frames=10, first_seen_ts=0.0)
    collector = ViewCollector(Settings())
    ready = next(r.ready for r in (collector.offer(track, image, i * 0.1) for i in range(12)) if r.ready)
    crop = cv2.imdecode(np.frombuffer(ready.jpeg, np.uint8), cv2.IMREAD_GRAYSCALE)  # crop starts at (364, 164)
    assert abs(float(crop[3:18, 60:300].mean()) - 128) < 15  # the bright band is painted grey
    assert float(crop[60:300, 60:300].std()) > 20  # the object keeps its texture
