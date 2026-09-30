import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from oi.contracts import (Candidate, FocusMsg, Observation, RecheckMsg, Track, TracksMsg, WireTrack,
                          parse_client_message, protocol_examples)


def _cand(model: str) -> Candidate:
    return Candidate(brand="Apple", model_name=model, variant=None, depth="model", evidence=[])


def test_observation_limits():
    with pytest.raises(ValidationError):
        Observation(category="smartphone", candidates=[_cand(f"iPhone {i}") for i in range(5)], readable_text=[],
                    distinguishable=True, next_view=None, self_assessment="medium", generic_description=None)


def test_wire_track_is_normalized():
    t = Track(id=1, box=(128, 72, 640, 360), polygon=[(128, 72)], label="cup", score=0.9, age_frames=3,
              first_seen_ts=0.0)
    w = WireTrack.from_track(t, 1280, 720)
    assert w.box == pytest.approx((0.1, 0.1, 0.5, 0.5))
    assert w.polygon[0] == pytest.approx((0.1, 0.1))


def test_server_message_dump_has_type():
    d = TracksMsg(frame_id=1, w=1280, h=720, focus_id=None, tracks=[], hint=None).model_dump(mode="json")
    assert d["type"] == "tracks" and d["seq"] == 0 and d["ts"] == 0.0


def test_parse_client_message():
    assert parse_client_message('{"type":"focus","track_id":3}') == FocusMsg(track_id=3)
    assert parse_client_message('{"type":"focus","track_id":null}') == FocusMsg(track_id=None)
    assert parse_client_message('{"type":"recheck","track_id":4}') == RecheckMsg(track_id=4)
    assert parse_client_message('{"type":"nope"}') is None
    assert parse_client_message("kaputt") is None


def test_protocol_examples_fixture_is_current():
    fixture = Path(__file__).parent / "fixtures" / "protocol-examples.json"
    assert json.loads(fixture.read_text()) == protocol_examples()


def test_scene_and_recalibrate_messages():
    from oi.contracts import RecalibrateMsg, SceneItemWire, SceneMsg
    message = SceneMsg(calibrating=False, items=[SceneItemWire(label="lamp", box=(0.1, 0.1, 0.2, 0.2))])
    assert message.model_dump(mode="json")["type"] == "scene"
    assert parse_client_message('{"type":"recalibrate"}') == RecalibrateMsg()


def test_scene_naming_and_hand_outlines_travel_to_the_browser():
    from oi.contracts import SceneMsg, TracksMsg, WireTrack
    assert SceneMsg(calibrating=False, items=[]).naming is False  # default: nothing is being named
    assert SceneMsg(calibrating=False, naming=True, items=[]).model_dump(mode="json")["naming"] is True
    hand = WireTrack(id=-101, box=(0.4, 0.5, 0.6, 0.9), polygon=[(0.4, 0.5), (0.6, 0.5), (0.5, 0.9)], label="hand",
                     score=1.0)
    message = TracksMsg(frame_id=1, w=1280, h=720, focus_id=None, tracks=[], hint=None, hands=[hand])
    assert message.model_dump(mode="json")["hands"][0]["polygon"][2] == [0.5, 0.9]
    assert TracksMsg(frame_id=1, w=1280, h=720, focus_id=None, tracks=[], hint=None).hands == []
