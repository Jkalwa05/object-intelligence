import cv2
import pytest
from ultralytics.utils import ASSETS

from oi.hands import HandFinder


@pytest.mark.model
def test_hand_finder_finds_the_hands_yoloe_misses():
    hands = HandFinder().find(cv2.imread(str(ASSETS / "zidane.jpg")))
    assert len(hands) >= 1 and all(h.label == "hand" and h.id < 0 for h in hands)
    x1, y1, x2, y2 = hands[0].box
    assert 0 <= x1 < x2 <= 1280 and 0 <= y1 < y2 <= 720
