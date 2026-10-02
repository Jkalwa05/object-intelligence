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
    d = TracksMsg(frame_id=1, w=1280, h=720, focus_id=None, tracks=[]).model_dump(mode="json")
    assert "hint" not in d  # no hints: the box itself is the feedback
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
    message = TracksMsg(frame_id=1, w=1280, h=720, focus_id=None, tracks=[], hands=[hand])
    assert message.model_dump(mode="json")["hands"][0]["polygon"][2] == [0.5, 0.9]
    assert TracksMsg(frame_id=1, w=1280, h=720, focus_id=None, tracks=[]).hands == []


def test_profile_message_travels():
    from oi.contracts import ProductProfile, ProfileFact, ProfileMsg
    profile = ProductProfile(known=True, summary="Ein Smartphone von Apple.", facts=[ProfileFact(label="Chip",
                             value="A15 Bionic")], released="September 2022", launch_price="999 €", trivia=[])
    data = ProfileMsg.of("Apple iPhone 14", "ready", profile, line=profile.summary).model_dump(mode="json")
    assert data["type"] == "profile" and data["facts"] == [{"label": "Chip", "value": "A15 Bionic"}]
    assert (data["product"], data["line"], data["released"]) == ("Apple iPhone 14", "Ein Smartphone von Apple.",
                                                                 "September 2022")
    loading = ProfileMsg.of("Apple iPhone 14", "loading", None)
    assert (loading.summary, loading.facts, loading.trivia, loading.line) == ("", [], [], "")


def test_model_message_travels():
    from oi.contracts import Measure, MeasureSheet, ModelManifest, ModelMsg, ModelPart, Source
    sheet = MeasureSheet(size_mm=(71.5, 146.7, 7.8), size_source=0,
                         measures=[Measure(label="Kameraplateau Breite", value_mm=30.4, source=0, kind="drawing")],
                         features=["Kameraplateau oben links, 4 mm vom Rand"],
                         sources=[Source(title="Accessory Design Guidelines", url="https://developer.apple.com/a.pdf")],
                         drawing=None)
    part = ModelPart(name="Gehäuse", color="#9fc4e8", file="part-01.stl", min_mm=(-35.75, -73.35, -3.9),
                     max_mm=(35.75, 73.35, 3.9), triangles=1200)
    manifest = ModelManifest(model="Apple iPhone 14", slug="apple-iphone-14", parts=[part], size_mm=(71.5, 146.7, 7.8),
                             sheet=sheet, drawing_pages=[212], notes="", verdict="good", rounds=1, cost_usd=0.92,
                             created="2026-10-01T22:00:00")
    data = ModelMsg(product="Apple iPhone 14", status="ready", round=1, manifest=manifest).model_dump(mode="json")
    assert data["type"] == "model" and data["manifest"]["parts"][0]["file"] == "part-01.stl"
    assert data["manifest"]["sheet"]["measures"][0]["kind"] == "drawing"
    assert ModelMsg.model_validate(data).manifest == manifest
    queued = ModelMsg(product="Apple iPhone 14", status="queued")
    assert (queued.round, queued.manifest) == (0, None)
    assert MeasureSheet.estimated() == MeasureSheet(size_mm=None, size_source=None, measures=[], features=[],
                                                    sources=[], drawing=None)


def test_old_manifest_still_loads():
    from oi.contracts import ModelManifest
    old = {"model": "Apple iPhone 14", "slug": "apple-iphone-14", "parts": [], "size_mm": [71.5, 146.7, 7.8],
           "sheet": {"size_mm": None, "size_source": None, "measures": [], "features": [], "sources": [],
                     "drawing": None},
           "drawing_pages": [], "notes": "", "verdict": "good", "rounds": 1, "cost_usd": 0.9, "created": ""}
    manifest = ModelManifest.model_validate(old)  # written before sub-project 7
    assert (manifest.kept, manifest.part_map, manifest.sheet.photos) == (False, [], [])


def test_keep_is_a_client_message():
    from oi.contracts import KeepMsg
    assert parse_client_message('{"type":"keep","model":"Sony DualShock 3","kept":true}') == \
        KeepMsg(model="Sony DualShock 3", kept=True)
    assert parse_client_message('{"type":"keep","model":"Sony DualShock 3"}') is None


def test_rebuild_is_a_client_message():
    from oi.contracts import RebuildMsg
    assert parse_client_message('{"type":"rebuild","name":"Apple iPhone 14"}') == RebuildMsg(name="Apple iPhone 14")
    assert parse_client_message('{"type":"rebuild"}') is None


def test_confirm_message_from_the_browser():
    from oi.contracts import ConfirmMsg, IdentityMsg
    assert parse_client_message('{"type":"confirm","track_id":14,"name":"Apple iPhone 14"}') == ConfirmMsg(
        track_id=14, name="Apple iPhone 14")
    assert parse_client_message('{"type":"confirm","track_id":14}') is None
    assert "confirmed" in IdentityMsg.model_fields


def test_question_messages():
    from oi.contracts import AskMsg, QuestionMsg, Source
    ask = parse_client_message('{"type":"ask","track_id":14,"name":"Apple iPhone 14","rate":16000,"audio":"AAA="}')
    assert ask == AskMsg(track_id=14, name="Apple iPhone 14", rate=16000, audio="AAA=")
    assert parse_client_message('{"type":"ask","track_id":null,"name":null,"rate":16000,"audio":""}') is not None
    message = QuestionMsg(product="Apple iPhone 14", qid=1, status="ready", question="Wie schwer ist das?",
                          answer="Es wiegt 172 Gramm.", sources=[Source(title="Apple", url="https://apple.com")],
                          line="Es wiegt 172 Gramm.")
    assert message.model_dump(mode="json")["sources"] == [{"title": "Apple", "url": "https://apple.com"}]
