from oi.config import Settings
from oi.focus import FocusSelector, split_tracks
from tests.helpers import trk

W, H = 1280, 720
CUP = trk(1, (520, 264, 760, 456))  # 5 % of the frame, centred
HAND_ON_CUP = trk(9, (600, 400, 700, 520), label="hand")
MONITOR = trk(2, (0, 0, 576, 480), label="monitor")  # 30 % of the frame, off-centre
LEFT = trk(3, (300, 260, 500, 460))  # two equal objects, mirrored around the centre
RIGHT = trk(4, (780, 260, 980, 460))
HAND_ON_RIGHT = trk(8, (800, 400, 900, 520), label="hand")
HAND_ON_LEFT = trk(7, (320, 400, 420, 520), label="hand")


def times(start: float, n: int) -> list[float]:
    return [start + i * 0.1 for i in range(n)]


def test_split_excludes_people_and_collects_hands():
    visible, hands = split_tracks([trk(5, (0, 0, 10, 10), label="Person"), HAND_ON_CUP, CUP], Settings())
    assert [t.id for t in visible] == [CUP.id]
    assert [t.id for t in hands] == [HAND_ON_CUP.id]


def test_held_object_beats_larger_background_object():
    fs = FocusSelector(Settings())
    assert fs.update([CUP, MONITOR], [HAND_ON_CUP], W, H, 10.0) == CUP.id
    assert fs.update([CUP, MONITOR], [HAND_ON_CUP], W, H, 10.1) == CUP.id


def test_ignores_too_small_too_large_and_too_young():
    tiny = trk(1, (600, 300, 696, 348))  # 0.5 %
    huge = trk(2, (40, 90, 1240, 630))  # 70 %
    young = trk(3, (520, 264, 760, 456), age=2)
    assert FocusSelector(Settings()).update([tiny, huge, young], [], W, H, 10.0) is None


def test_hysteresis_needs_margin_for_half_second():
    fs = FocusSelector(Settings())
    assert fs.update([LEFT], [HAND_ON_LEFT], W, H, 10.0) == LEFT.id  # the user put LEFT down, then picks up RIGHT
    focus = {round(t, 1): fs.update([LEFT, RIGHT], [HAND_ON_RIGHT], W, H, t) for t in times(10.1, 6)}
    assert focus[10.5] == LEFT.id and focus[10.6] == RIGHT.id


def test_hysteresis_timer_restarts_when_lead_drops():
    fs = FocusSelector(Settings())
    fs.update([LEFT], [HAND_ON_LEFT], W, H, 10.0)
    for t in times(10.1, 2):
        fs.update([LEFT, RIGHT], [HAND_ON_RIGHT], W, H, t)
    assert fs.update([LEFT, RIGHT], [], W, H, 10.3) == LEFT.id  # lead gone: timer resets
    focus = {round(t, 1): fs.update([LEFT, RIGHT], [HAND_ON_RIGHT], W, H, t) for t in times(10.4, 6)}
    assert focus[10.8] == LEFT.id and focus[10.9] == RIGHT.id


def test_focus_lost_switches_immediately():
    fs = FocusSelector(Settings())
    assert fs.update([CUP, MONITOR], [HAND_ON_CUP], W, H, 10.0) == CUP.id
    other = trk(3, (560, 380, 760, 600))
    assert fs.update([other, MONITOR], [trk(9, (600, 500, 700, 620), label="hand")], W, H, 10.1) == other.id
    assert fs.update([MONITOR], [], W, H, 10.2) is None  # nothing held: no automatic focus


def test_pin_overrides_until_track_disappears():
    fs = FocusSelector(Settings())
    fs.update([CUP, MONITOR], [HAND_ON_CUP], W, H, 10.0)
    fs.pin(MONITOR.id)
    assert fs.update([CUP, MONITOR], [HAND_ON_CUP], W, H, 10.1) == MONITOR.id
    assert fs.update([CUP], [HAND_ON_CUP], W, H, 10.2) == CUP.id
    assert fs.update([CUP, MONITOR], [HAND_ON_CUP], W, H, 10.3) == CUP.id  # the pin ended with the track
    fs.pin(MONITOR.id)
    fs.pin(None)
    assert fs.update([CUP, MONITOR], [HAND_ON_CUP], W, H, 10.4) == CUP.id


def test_steady_from_velocity():
    fs = FocusSelector(Settings())
    for t in times(10.0, 5):
        fs.update([CUP], [], W, H, t)
    assert fs.steady(CUP.id) == 1.0
    step = 0.5 * (W ** 2 + H ** 2) ** 0.5 * 0.1  # 0.5 frame diagonals per second, 0.1 s per frame
    for i, t in enumerate(times(20.0, 11)):
        fs.update([trk(7, (100 + i * step, 300, 200 + i * step, 420))], [], W, H, t)
    assert fs.steady(7) < 0.1
    assert fs.steady(12345) == 0.0


STAIRS = trk(20, (800, 60, 1240, 660), label="stairs")  # background, never held
PERSON = trk(10, (300, 0, 980, 720), label="man")
FACE_REGION = trk(21, (520, 20, 760, 200), label="night sky")  # the detector's name for a face


def test_static_background_never_gets_automatic_focus():
    fs = FocusSelector(Settings())
    assert all(fs.update([STAIRS], [], W, H, t) is None for t in times(0.0, 30))


def test_face_region_never_gets_automatic_focus():
    fs = FocusSelector(Settings())
    for t in times(0.0, 30):
        assert fs.update([FACE_REGION], [], W, H, t, people=[PERSON]) is None


def test_held_object_in_front_of_the_face_is_allowed():
    phone = trk(22, (520, 40, 700, 230), label="cell phone")
    hand = trk(9, (560, 180, 660, 300), label="hand")
    assert FocusSelector(Settings()).update([phone], [hand], W, H, 0.0, people=[PERSON]) == phone.id


def test_held_object_keeps_focus_after_the_hand_is_gone():
    fs = FocusSelector(Settings())
    assert fs.update([CUP, STAIRS], [HAND_ON_CUP], W, H, 0.0) == CUP.id
    assert all(fs.update([CUP, STAIRS], [], W, H, t) == CUP.id for t in times(0.1, 60))
