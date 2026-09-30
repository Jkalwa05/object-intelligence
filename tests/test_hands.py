import cv2
import numpy as np
import pytest
from ultralytics.utils import ASSETS

from oi.hands import HandFinder


@pytest.mark.model
def test_hand_finder_finds_the_hands_yoloe_misses():
    hands = HandFinder().find(cv2.imread(str(ASSETS / "zidane.jpg")))
    assert len(hands) >= 1 and all(h.label == "hand" and h.id < 0 for h in hands)
    x1, y1, x2, y2 = hands[0].box
    assert 0 <= x1 < x2 <= 1280 and 0 <= y1 < y2 <= 720


# --- pure hand logic, no Vision needed ----------------------------------------------------------------------------

from oi.hands import HandConfirmer, hand_outline, hand_track  # noqa: E402

W, H = 1280, 720
JOINTS = [(600, 500), (570, 470), (560, 440), (555, 410), (550, 390), (590, 450), (590, 410), (590, 385),
          (610, 450), (612, 405), (614, 380), (630, 455), (634, 415), (636, 392)]  # wrist, thumb and three fingers


def test_only_a_confident_hand_with_enough_joints_counts():
    assert hand_track(JOINTS, 0.9, 0, W, H) is not None
    assert hand_track(JOINTS, 0.5, 0, W, H) is None  # Vision itself is unsure
    assert hand_track(JOINTS[:5], 0.9, 0, W, H) is None  # five points are no hand shape
    hand = hand_track(JOINTS, 0.9, 1, W, H)
    assert (hand.label, hand.id, hand.joints) == ("hand", -102, JOINTS)


def test_outline_surrounds_every_joint_with_room_for_the_skin():
    outline = hand_outline(JOINTS, W, H)
    assert len(outline) == 16
    contour = np.array(outline, np.float32).reshape(-1, 1, 2)
    assert all(cv2.pointPolygonTest(contour, (float(x), float(y)), True) >= 8 for x, y in JOINTS)
    hand = hand_track(JOINTS, 0.9, 0, W, H)
    assert hand.polygon == outline and hand.box == (min(x for x, _ in outline), min(y for _, y in outline),
                                                    max(x for x, _ in outline), max(y for _, y in outline))


def test_outline_stays_inside_the_frame():
    corner = [(x - 540, y - 370) for x, y in JOINTS]  # the hand reaches into the top-left corner
    assert all(0 <= x <= W and 0 <= y <= H for x, y in hand_outline(corner, W, H))


def test_a_hand_counts_from_its_second_frame_on():
    confirmer = HandConfirmer()
    first = hand_track(JOINTS, 0.9, 0, W, H)
    moved = hand_track([(x + 12, y - 8) for x, y in JOINTS], 0.9, 0, W, H)
    ghost = hand_track([(x + 500, y) for x, y in JOINTS], 0.9, 1, W, H)
    assert confirmer.confirm([first]) == []
    assert confirmer.confirm([moved, ghost]) == [moved]  # the ghost appeared elsewhere, only for one frame
    assert confirmer.confirm([]) == []
    assert confirmer.confirm([first]) == []  # after a gap it has to be seen twice again
