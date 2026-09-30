from oi.config import Settings
from oi.privacy import privacy_veto
from tests.helpers import trk

PERSON = trk(10, (300, 0, 980, 720), label="man")  # head zone: the top third, y 0..240
FACE = trk(11, (560, 60, 720, 220), label="face")


def test_object_covering_the_person_is_vetoed():
    flag = trk(1, (320, 20, 960, 700), label="flag")  # the detector's name for a whole person
    assert privacy_veto(flag, [PERSON, flag], Settings())


def test_object_in_the_head_zone_is_vetoed():
    head = trk(2, (520, 20, 760, 200), label="night sky")
    assert privacy_veto(head, [PERSON, head], Settings())


def test_object_over_a_face_box_is_vetoed():
    cup = trk(3, (600, 150, 800, 400))
    assert privacy_veto(cup, [FACE, cup], Settings())


def test_object_held_at_chest_height_is_allowed():
    cup = trk(4, (560, 380, 760, 600))
    assert not privacy_veto(cup, [PERSON, FACE, cup], Settings())


def test_no_people_no_veto():
    cup = trk(5, (400, 200, 700, 500))
    assert not privacy_veto(cup, [cup], Settings())


def test_person_and_body_labels_are_excluded():
    s = Settings()
    for label in ("adult", "preacher", "selfie", "portrait", "hair", "beard", "neck", "shoulder", "forehead", "body"):
        assert label in s.excluded_labels


def test_privacy_hint_texts():
    from oi import lines
    assert lines.hint_line("person", "de") == "Personen und Gesichter identifiziere ich nicht."
    assert lines.hint_line("person", "en") == "I don't identify people or faces."
    assert lines.hint_line("lower", "de") == "Halt es bitte tiefer, nicht vors Gesicht."
    assert lines.hint_line("lower", "en") == "Please hold it lower, not in front of your face."


def test_small_object_on_a_face_is_vetoed():
    face = trk(-1, (700, 600, 1010, 1000), label="face")
    glasses = trk(7, (740, 700, 990, 800), label="glasses")
    earring = trk(8, (1020, 820, 1040, 850), label="earring")  # just outside the face box, inside the widened zone
    assert privacy_veto(glasses, [face, glasses], Settings())
    assert privacy_veto(earring, [face, earring], Settings())


def test_head_zone_rule_can_be_switched_off_when_faces_are_known():
    beside = trk(6, (700, 40, 880, 230), label="cell phone")
    assert privacy_veto(beside, [PERSON, beside], Settings())
    assert not privacy_veto(beside, [PERSON, beside], Settings(), head_zone=False)
    on_face = trk(7, (580, 100, 700, 200), label="glasses")
    assert privacy_veto(on_face, [PERSON, FACE, on_face], Settings(), head_zone=False)


def test_things_on_the_body_are_on_the_person():
    from oi.privacy import on_person
    face = trk(-1, (560, 100, 720, 300), label="face")
    necklace = trk(7, (580, 380, 700, 460), label="necklace")
    shirt = trk(8, (440, 350, 840, 720), label="t-shirt")
    lamp = trk(9, (1000, 20, 1200, 180), label="lamp")
    assert on_person(necklace, [face], frame_h=720)
    assert on_person(shirt, [face], frame_h=720)
    assert not on_person(lamp, [face], frame_h=720)


def test_inside_a_person_box_is_on_the_person():
    from oi.privacy import on_person
    chain = trk(7, (560, 400, 700, 480), label="necklace")
    assert on_person(chain, [PERSON], frame_h=720)
