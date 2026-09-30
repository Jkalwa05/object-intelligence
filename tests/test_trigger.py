from dataclasses import replace

import pytest

from oi.config import Settings
from oi.trigger import Decision, TriggerInput, decide
from oi.views import ReadyCrop

NEW = ReadyCrop(jpeg=b"x", sharpness=100.0, q=0.6, dhash=0, aspect=1.0, view_id=2, is_new_view=True)
SAME = replace(NEW, view_id=1, is_new_view=False)
BASE = TriggerInput(is_focus=True, ready=NEW, final=False, in_flight_track=False, in_flight_total=0, calls_track=1,
                    calls_session=1, forced=False)


@pytest.mark.parametrize("change,expected", [
    ({"is_focus": False}, Decision.WAIT),                          # rule 1
    ({"ready": None}, Decision.WAIT),                              # rule 1
    ({"in_flight_track": True}, Decision.WAIT),                    # rule 2
    ({"in_flight_total": 2}, Decision.WAIT),                       # rule 2
    ({"calls_session": 150}, Decision.SESSION_CAP),                # rule 3
    ({"forced": True, "ready": SAME}, Decision.CALL),              # rule 4
    ({"final": True}, Decision.WAIT),                              # rule 5
    ({"calls_track": 4}, Decision.OBJECT_CAP),                     # rule 6
    ({"calls_track": 0, "ready": SAME}, Decision.CALL),            # rule 7: first call
    ({}, Decision.CALL),                                           # rule 7: new view
    ({"ready": SAME}, Decision.WAIT),                              # rule 8
])
def test_rules(change, expected):
    assert decide(replace(BASE, **change), Settings()) == expected


def test_forced_bypasses_final_and_object_cap():
    assert decide(replace(BASE, forced=True, final=True, calls_track=4, ready=SAME), Settings()) == Decision.CALL


def test_session_cap_beats_forced():
    assert decide(replace(BASE, forced=True, calls_session=150), Settings()) == Decision.SESSION_CAP
