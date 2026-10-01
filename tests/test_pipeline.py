from oi import lines
from oi.config import Settings
from oi.contracts import FocusMsg, RecheckMsg
from oi.identify import FakeIdentifier, IdentifyError
from oi.ingest import Frame
from oi.perception import FakeDetector
from oi.pipeline import Pipeline
from oi.telemetry import Telemetry
from tests.helpers import cand, obs, sharp_image, trk

BOX = (400, 200, 700, 500)
CUP = trk(1, BOX)
HAND = trk(99, (450, 400, 650, 520), label="hand")  # the cup is held: only held objects get focus
I14, I13 = cand("Apple", "iPhone 14"), cand("Apple", "iPhone 13")


class Recorder:
    def __init__(self) -> None:
        self.messages = []

    async def __call__(self, message) -> None:
        self.messages.append(message)

    def of(self, kind: str) -> list:
        return [m for m in self.messages if m.type == kind]


def make(script, identifier, settings=None):
    settings = settings or Settings()
    recorder = Recorder()
    telemetry = Telemetry(settings, "hybrid" if identifier else "lokal", "fake")
    pipeline = Pipeline(settings, FakeDetector(script), identifier, telemetry, None, recorder)
    return pipeline, recorder, telemetry


async def feed(pipeline, image, n, start=0.0, step=0.1, first_id=0):
    for i in range(n):
        await pipeline.handle_frame(Frame(frame_id=first_id + i, t=start + i * step, image=image))


async def test_tracks_message_excludes_people_and_normalizes():
    pipeline, rec, _ = make([[trk(9, (0, 0, 100, 300), label="person"), CUP, HAND]], None)
    await feed(pipeline, sharp_image(boxes=(BOX,)), 1)
    (message,) = rec.of("tracks")
    assert [t.id for t in message.tracks] == [CUP.id]
    assert message.tracks[0].box == (0.3125, 0.2778, 0.5469, 0.6944)
    assert (message.w, message.h, message.focus_id) == (1280, 720, CUP.id)


async def test_holding_still_triggers_one_identification():
    identifier = FakeIdentifier(script=[obs(I14, I13)])
    pipeline, rec, telemetry = make([[CUP, HAND]], identifier)
    await feed(pipeline, sharp_image(boxes=(BOX,)), 13)
    await pipeline.wait_idle()
    identities = rec.of("identity")
    assert [m.status for m in identities] == ["analysing", "ready"]
    assert identities[1].level == "likely" and identities[1].line == "Das ist wahrscheinlich Apple iPhone 14."
    assert len(identifier.requests) == 1 and identifier.requests[0].coarse_label == "cup"
    assert identifier.requests[0].history == "none" and telemetry.calls_session == 1


async def test_no_identifier_means_tracks_only():
    pipeline, rec, _ = make([[CUP, HAND]], None)
    await feed(pipeline, sharp_image(boxes=(BOX,)), 13)
    assert {m.type for m in rec.messages} == {"tracks", "scene"}


async def test_result_stays_with_original_track_after_focus_switch():
    book = trk(2, (1000, 100, 1200, 300), label="book")
    identifier = FakeIdentifier(script=[obs(I14, I13)], delay_s=0.3)
    pipeline, rec, _ = make([[CUP, HAND, book]], identifier)
    image = sharp_image(boxes=(BOX, (1000, 100, 1200, 300)))
    await feed(pipeline, image, 10)
    assert [m.status for m in rec.of("identity")] == ["analysing"]
    await pipeline.on_client_message(FocusMsg(track_id=book.id))
    await feed(pipeline, image, 2, start=1.0, first_id=10)
    assert rec.of("tracks")[-1].focus_id == book.id
    await pipeline.wait_idle()
    ready = [m for m in rec.of("identity") if m.status == "ready"]
    assert ready[0].track_id == CUP.id


async def test_session_cap_pauses_and_notifies_once():
    book = trk(2, BOX, label="book")
    pipeline, rec, _ = make([[CUP, HAND]] * 13 + [[book, HAND]] * 25, FakeIdentifier(script=[obs(I14, I13)]),
                            Settings(max_calls_session=1))
    image = sharp_image(boxes=(BOX,))
    await feed(pipeline, image, 13)
    await feed(pipeline, _tint(image, (40, 60, 255)), 25, start=1.3, first_id=13)  # a red book, not the cup again
    await pipeline.wait_idle()
    paused = [m for m in rec.of("identity") if m.status == "paused"]
    assert [m.track_id for m in paused] == [book.id] and paused[0].line == lines.paused_line("de")
    assert [n.text for n in rec.of("notice")] == [lines.paused_line("de")]


async def test_recheck_calls_again():
    decisive = obs(cand("Myprotein", "Essential BCAA"), readable=("Essential BCAA 2:1:1",), cat="Dose")
    identifier = FakeIdentifier(script=[decisive])
    pipeline, rec, _ = make([[CUP, HAND]], identifier)
    image = sharp_image(boxes=(BOX,))
    await feed(pipeline, image, 13)
    await pipeline.wait_idle()
    assert rec.of("identity")[-1].level == "certain" and len(identifier.requests) == 1
    await feed(pipeline, image, 5, start=1.3, first_id=13)
    assert len(identifier.requests) == 1  # final: no automatic calls
    await pipeline.on_client_message(RecheckMsg(track_id=CUP.id))
    await feed(pipeline, image, 6, start=1.8, first_id=18)
    await pipeline.wait_idle()
    assert len(identifier.requests) == 2 and identifier.requests[1].history != "none"


async def test_identify_error_then_retry_on_new_view():
    identifier = FakeIdentifier(script=[IdentifyError("timeout"), obs(I14, I13)])
    pipeline, rec, _ = make([[CUP, HAND]], identifier)
    await feed(pipeline, sharp_image(boxes=(BOX,)), 13)
    await pipeline.wait_idle()
    error = rec.of("identity")[-1]
    assert (error.status, error.line) == ("error", lines.error_line("de"))
    await feed(pipeline, sharp_image(boxes=(BOX,), mirrored=True), 8, start=1.3, first_id=13)
    await pipeline.wait_idle()
    assert rec.of("identity")[-1].status == "ready" and len(identifier.requests) == 2


async def test_an_object_cut_off_by_the_edge_is_not_sent():
    edge_box = (5, 200, 305, 500)
    identifier = FakeIdentifier(script=[obs(I14)])
    pipeline, rec, _ = make([[trk(1, edge_box), trk(99, (50, 400, 250, 520), label="hand")]], identifier)
    await feed(pipeline, sharp_image(boxes=(edge_box,)), 22)
    assert identifier.requests == [] and rec.of("tracks")[-1].focus_id == 1  # the box shows it; nobody nags


async def test_two_similar_objects_do_not_flicker():
    hands = [trk(97, (320, 400, 420, 520), label="hand"), trk(98, (800, 400, 900, 520), label="hand")]
    script = [[trk(3, (300, 260, 500 + (2 if i % 2 else 0), 460)), trk(4, (780, 260, 980 + (0 if i % 2 else 2), 460)),
               *hands] for i in range(20)]
    pipeline, rec, _ = make(script, None)
    await feed(pipeline, sharp_image(), 20)
    focus_ids = {m.focus_id for m in rec.of("tracks")}
    assert len(focus_ids) == 1 and None not in focus_ids


async def test_telemetry_tick_emits_snapshot():
    pipeline, rec, _ = make([[CUP, HAND]], None)
    await pipeline.telemetry_tick(frames_dropped=2)
    (message,) = rec.of("telemetry")
    assert (message.frames_dropped, message.mode) == (2, "lokal")


async def test_person_region_is_never_sent():
    """Sitting still with nothing in hand: regions on the body get no focus, no brackets, no hint, no call."""
    person = trk(10, (300, 0, 980, 720), label="man")
    flag = trk(1, (320, 20, 960, 700), label="flag")
    face = trk(2, (520, 20, 760, 200), label="night sky")
    identifier = FakeIdentifier(script=[obs(I14)])
    pipeline, rec, _ = make([[person, flag, face]], identifier)
    await feed(pipeline, sharp_image(boxes=((320, 20, 960, 700),)), 30)
    await pipeline.wait_idle()
    assert identifier.requests == []
    assert all(m.focus_id is None and m.tracks == [] for m in rec.of("tracks"))


async def test_clicked_person_region_is_never_sent():
    person = trk(10, (300, 0, 980, 720), label="man")
    flag = trk(1, (320, 20, 960, 700), label="flag")
    identifier = FakeIdentifier(script=[obs(I14)])
    pipeline, rec, _ = make([[person, flag]], identifier)
    await pipeline.on_client_message(FocusMsg(track_id=flag.id))
    await feed(pipeline, sharp_image(boxes=((320, 20, 960, 700),)), 22)
    await pipeline.wait_idle()
    assert identifier.requests == []


async def test_held_object_in_front_of_the_face_is_never_marked_or_sent():
    person = trk(10, (300, 0, 980, 720), label="man")
    phone = trk(3, (520, 40, 700, 230), label="cell phone")
    hand = trk(99, (560, 180, 660, 300), label="hand")
    identifier = FakeIdentifier(script=[obs(I14)])
    pipeline, rec, _ = make([[person, phone, hand]], identifier)
    await feed(pipeline, sharp_image(boxes=((520, 40, 700, 230),)), 22)
    await pipeline.wait_idle()
    assert identifier.requests == []
    assert all(m.focus_id is None and m.tracks == [] for m in rec.of("tracks"))


async def test_view_shown_during_call_is_sent_afterwards():
    identifier = FakeIdentifier(script=[obs(I14, I13)], delay_s=0.3)
    pipeline, _, _ = make([[CUP, HAND]], identifier)
    await feed(pipeline, sharp_image(boxes=(BOX,)), 10)  # view A, the call starts at t 0.9
    turned = sharp_image(boxes=(BOX,), mirrored=True)
    await feed(pipeline, turned, 8, start=1.0, first_id=10)  # view B while the call is running
    await pipeline.wait_idle()
    await feed(pipeline, turned, 6, start=1.8, first_id=18)  # the call is back: view B goes out now
    await pipeline.wait_idle()
    assert len(identifier.requests) == 2


async def test_recheck_during_analysis_is_not_lost():
    decisive = obs(cand("Myprotein", "Essential BCAA"), readable=("Essential BCAA",), cat="Dose")
    identifier = FakeIdentifier(script=[decisive], delay_s=0.3)
    pipeline, _, _ = make([[CUP, HAND]], identifier)
    image = sharp_image(boxes=(BOX,))
    await feed(pipeline, image, 10)
    await pipeline.on_client_message(RecheckMsg(track_id=CUP.id))
    await feed(pipeline, image, 6, start=1.0, first_id=10)
    await pipeline.wait_idle()
    await feed(pipeline, image, 6, start=1.6, first_id=16)
    await pipeline.wait_idle()
    assert len(identifier.requests) == 2


class FakeFaces:
    def __init__(self, boxes):
        from oi.contracts import Track
        self._faces = [Track(id=-(i + 1), box=b, polygon=[], label="face", score=0.9, age_frames=1, first_seen_ts=0.0)
                       for i, b in enumerate(boxes)]

    def find(self, image):
        return self._faces


async def test_face_finder_keeps_glasses_on_the_face_private():
    glasses = trk(7, (740, 300, 990, 400), label="glasses")
    hand = trk(99, (900, 350, 1000, 470), label="hand")  # touching the glasses
    identifier = FakeIdentifier(script=[obs(I14)])
    settings = Settings()
    rec = Recorder()
    pipeline = Pipeline(settings, FakeDetector([[glasses, hand]]), identifier,
                        Telemetry(settings, "hybrid", "fake"), None, rec, faces=FakeFaces([(700, 200, 1010, 600)]))
    await feed(pipeline, sharp_image(boxes=((740, 300, 990, 400),)), 22)
    await pipeline.wait_idle()
    assert identifier.requests == []


async def test_hand_finder_makes_the_held_phone_the_focus():
    phone = trk(5, BOX, label="gadget")  # YOLOE names no hand at all
    hands = FakeFaces([(450, 400, 650, 520)])  # same shape of result: boxes from a dedicated detector
    for t in hands._faces:
        t.label = "hand"
    identifier = FakeIdentifier(script=[obs(I14)])
    settings = Settings()
    pipeline = Pipeline(settings, FakeDetector([[phone]]), identifier, Telemetry(settings, "hybrid", "fake"), None,
                        Recorder(), hands=hands)
    await feed(pipeline, sharp_image(boxes=(BOX,)), 13)
    await pipeline.wait_idle()
    assert len(identifier.requests) == 1


async def test_phone_beside_the_face_is_fine_when_faces_are_known():
    person = trk(10, (300, 0, 980, 720), label="man")
    phone = trk(3, (700, 40, 880, 230), label="cell phone")  # head height, beside the face
    hand = trk(99, (740, 180, 840, 300), label="hand")
    identifier = FakeIdentifier(script=[obs(I14)])
    settings = Settings()
    pipeline = Pipeline(settings, FakeDetector([[person, phone, hand]]), identifier,
                        Telemetry(settings, "hybrid", "fake"), None, Recorder(), faces=FakeFaces([(450, 60, 650, 300)]))
    await feed(pipeline, sharp_image(boxes=((700, 40, 880, 230),)), 13)
    await pipeline.wait_idle()
    assert len(identifier.requests) == 1


async def test_telemetry_names_the_failing_check():
    from tests.helpers import blurry_image
    pipeline, rec, telemetry = make([[CUP, HAND]], FakeIdentifier(script=[obs(I14)]))
    await feed(pipeline, blurry_image(boxes=(BOX,)), 5)
    await pipeline.telemetry_tick(frames_dropped=0)
    assert rec.of("telemetry")[-1].gate_focus == "blurry"


async def test_tracks_carry_face_boxes_for_the_card():
    settings = Settings()
    rec = Recorder()
    pipeline = Pipeline(settings, FakeDetector([[CUP, HAND]]), None, Telemetry(settings, "lokal", "–"), None, rec,
                        faces=FakeFaces([(128, 72, 256, 216)]))
    await feed(pipeline, sharp_image(boxes=(BOX,)), 1)
    assert rec.of("tracks")[0].faces == [(0.1, 0.1, 0.2, 0.3)]


async def test_hud_shows_only_the_held_object_and_a_frozen_scene():
    from oi.contracts import SceneMsg
    lamp = trk(20, (1000, 20, 1200, 180), label="lamp")
    necklace = trk(21, (930, 470, 1010, 540), label="necklace")  # on the person, below the face
    settings = Settings()
    rec = Recorder()
    pipeline = Pipeline(settings, FakeDetector([[CUP, HAND, lamp, necklace]]), None,
                        Telemetry(settings, "lokal", "–"), None, rec, faces=FakeFaces([(900, 250, 1040, 420)]))
    image = sharp_image(boxes=(BOX,))
    for i in range(12):
        await pipeline.handle_frame(Frame(frame_id=i, t=i * 0.5, image=image))
    scenes = [m for m in rec.messages if isinstance(m, SceneMsg)]
    assert scenes[0].calibrating and scenes[0].items == []
    assert not scenes[-1].calibrating and [i.label for i in scenes[-1].items] == ["lamp"]
    assert all([t.id for t in m.tracks] == [CUP.id] for m in rec.of("tracks"))


async def test_recalibrate_starts_a_new_scene():
    from oi.contracts import RecalibrateMsg, SceneMsg
    settings = Settings()
    rec = Recorder()
    lamp = trk(20, (1000, 20, 1200, 180), label="lamp")
    pipeline = Pipeline(settings, FakeDetector([[lamp]]), None, Telemetry(settings, "lokal", "–"), None, rec)
    for i in range(11):
        await pipeline.handle_frame(Frame(frame_id=i, t=i * 0.5, image=sharp_image()))
    await pipeline.on_client_message(RecalibrateMsg())
    await pipeline.handle_frame(Frame(frame_id=20, t=10.0, image=sharp_image()))
    scenes = [m for m in rec.messages if isinstance(m, SceneMsg)]
    assert [s.calibrating for s in scenes] == [True, False, True]


# --- live test 2026-09-30: Claude names the whole background in one call; the background never gets focus ------------

LAMP = trk(20, (1000, 20, 1200, 180), label="lamp")


def _named():
    from oi.contracts import SceneItemWire
    return [SceneItemWire(label="Pendelleuchte", box=(0.78, 0.03, 0.94, 0.25))]


async def _calibrate(pipeline, image, n=12, start=0.0):
    for i in range(n):
        await pipeline.handle_frame(Frame(frame_id=i, t=start + i * 0.5, image=image))


async def test_scene_is_named_by_one_claude_call_with_the_person_greyed():
    import cv2
    import numpy as np
    identifier = FakeIdentifier(scene=_named())
    settings = Settings()
    rec = Recorder()
    telemetry = Telemetry(settings, "hybrid", "fake")
    pipeline = Pipeline(settings, FakeDetector([[LAMP]]), identifier, telemetry, None, rec,
                        faces=FakeFaces([(500, 100, 600, 220)]))
    await _calibrate(pipeline, np.full((720, 1280, 3), 200, np.uint8))
    await pipeline.wait_idle()
    scenes = rec.of("scene")
    assert [(s.calibrating, s.naming) for s in scenes] == [(True, False), (False, True), (False, False)]
    assert scenes[-1].items == _named()
    assert len(identifier.scene_requests) == 1 and telemetry.calls_session == 1
    sent = cv2.imdecode(np.frombuffer(identifier.scene_requests[0].jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert sent.shape == (720, 1280, 3)
    assert abs(int(sent[500, 550].mean()) - 128) <= 3  # below the face: the body is grey before it leaves the Mac
    assert abs(int(sent[150, 550].mean()) - 128) <= 3  # the face itself
    assert abs(int(sent[50, 100].mean()) - 200) <= 3  # the room is not


async def test_scene_falls_back_to_local_names_when_claude_fails():
    identifier = FakeIdentifier(scene=IdentifyError("connection"))
    settings = Settings()
    rec = Recorder()
    pipeline = Pipeline(settings, FakeDetector([[LAMP]]), identifier, Telemetry(settings, "hybrid", "fake"), None, rec)
    await _calibrate(pipeline, sharp_image())
    await pipeline.wait_idle()
    last = rec.of("scene")[-1]
    assert (last.naming, [i.label for i in last.items]) == (False, ["lamp"])
    assert rec.of("notice")[-1].text == lines.notice_text("scene_local", "de")


async def test_no_scene_call_without_claude_or_once_the_budget_is_used_up():
    settings = Settings(max_calls_session=0)
    identifier = FakeIdentifier(scene=_named())
    rec = Recorder()
    pipeline = Pipeline(settings, FakeDetector([[LAMP]]), identifier, Telemetry(settings, "hybrid", "fake"), None, rec)
    await _calibrate(pipeline, sharp_image())
    await pipeline.wait_idle()
    assert identifier.scene_requests == [] and [i.label for i in rec.of("scene")[-1].items] == ["lamp"]


async def test_a_new_calibration_drops_the_answer_for_the_old_one():
    from oi.contracts import RecalibrateMsg
    identifier = FakeIdentifier(scene=_named(), delay_s=0.05)
    settings = Settings()
    rec = Recorder()
    pipeline = Pipeline(settings, FakeDetector([[LAMP]]), identifier, Telemetry(settings, "hybrid", "fake"), None, rec)
    await _calibrate(pipeline, sharp_image())
    await pipeline.on_client_message(RecalibrateMsg())
    await pipeline.handle_frame(Frame(frame_id=50, t=20.0, image=sharp_image()))
    await pipeline.wait_idle()
    assert rec.of("scene")[-1].calibrating  # the late answer described the old scene


async def test_background_from_the_calibration_never_becomes_the_focus():
    lamp = trk(20, BOX, label="lamp")  # hangs exactly where the hand will be
    identifier = FakeIdentifier(script=[obs(I14)])
    settings = Settings()
    rec = Recorder()
    detector = FakeDetector([[lamp]] * 11 + [[lamp, HAND]])
    pipeline = Pipeline(settings, detector, identifier, Telemetry(settings, "hybrid", "fake"), None, rec)
    image = sharp_image(boxes=(BOX,))
    await _calibrate(pipeline, image, n=11)
    await feed(pipeline, image, 20, start=6.0, first_id=20)
    await pipeline.wait_idle()
    assert identifier.requests == [] and all(m.focus_id is None for m in rec.of("tracks"))


class FakeHands:
    def __init__(self, joints):
        from oi.hands import hand_track
        self._hand = hand_track(joints, 1.0, 0, 1280, 720)

    def find(self, image):
        return [self._hand]


async def test_tracks_carry_the_outline_of_every_confirmed_hand():
    joints = [(600, 500), (570, 470), (560, 440), (555, 410), (550, 390), (590, 450), (590, 410), (590, 385),
              (610, 450), (612, 405), (614, 380), (630, 455)]
    settings = Settings()
    rec = Recorder()
    pipeline = Pipeline(settings, FakeDetector([[CUP]]), None, Telemetry(settings, "lokal", "–"), None, rec,
                        hands=FakeHands(joints))
    await feed(pipeline, sharp_image(boxes=(BOX,)), 2)
    first, second = rec.of("tracks")
    assert first.hands == []  # seen once: not yet a hand
    assert [h.label for h in second.hands] == ["hand"] and len(second.hands[0].polygon) == 16
    assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in second.hands[0].polygon)


async def test_a_face_missed_in_the_last_frame_is_still_greyed():
    import cv2
    import numpy as np

    class FlakyFaces(FakeFaces):  # the face detector misses the face exactly when the scene freezes
        calls = 0

        def find(self, image):
            self.calls += 1
            return [] if self.calls == 11 else self._faces

    identifier = FakeIdentifier(scene=_named())
    settings = Settings()
    pipeline = Pipeline(settings, FakeDetector([[LAMP]]), identifier, Telemetry(settings, "hybrid", "fake"), None,
                        Recorder(), faces=FlakyFaces([(500, 100, 600, 220)]))
    await _calibrate(pipeline, np.full((720, 1280, 3), 200, np.uint8), n=11)
    await pipeline.wait_idle()
    sent = cv2.imdecode(np.frombuffer(identifier.scene_requests[0].jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert abs(int(sent[150, 550].mean()) - 128) <= 3


async def test_a_shaky_hand_held_object_is_identified_without_nagging():
    from tests.helpers import blurry_image
    identifier = FakeIdentifier(script=[obs(I14)])
    pipeline, rec, _ = make([[CUP, HAND]], identifier)
    for i in range(15):  # a video: now and then one sharp frame between blurred ones
        image = sharp_image(boxes=(BOX,)) if i % 4 == 0 else blurry_image(boxes=(BOX,))
        await pipeline.handle_frame(Frame(frame_id=i, t=i * 0.1, image=image))
    await pipeline.wait_idle()
    assert len(identifier.requests) == 1 and rec.of("identity")[-1].status == "ready"


# --- the tracker gives the held object a new number: it keeps its identity (live test 2026-09-30: 10 numbers) -------

CUP2 = trk(2, (410, 205, 705, 505))  # the same cup, found again under a new number


def _tint(image, bgr):
    import numpy as np
    out = image.astype(np.float32)
    out[200:500, 400:700] *= np.array(bgr, np.float32) / 255
    return out.astype(np.uint8)


async def _held_then_renumbered(identifier, gap_frames=2, second_colour=(255, 120, 40)):
    script = [[CUP, HAND]] * 13 + [[HAND]] * gap_frames + [[CUP2, HAND]]
    pipeline, rec, _ = make(script, identifier)
    blue = _tint(sharp_image(boxes=(BOX,)), (255, 120, 40))
    await feed(pipeline, blue, 13)
    await feed(pipeline, blue, gap_frames, start=1.3, first_id=13)
    await feed(pipeline, _tint(sharp_image(boxes=(BOX,)), second_colour), 15, start=1.3 + gap_frames * 0.1,
               first_id=13 + gap_frames)
    await pipeline.wait_idle()
    return pipeline, rec


async def test_the_same_object_under_a_new_number_keeps_its_identity():
    identifier = FakeIdentifier(script=[obs(I14, I13)])
    _, rec = await _held_then_renumbered(identifier)
    assert len(identifier.requests) == 1  # nothing is paid twice
    carried = [m for m in rec.of("identity") if m.track_id == CUP2.id]
    assert carried and carried[0].previous_id == CUP.id and carried[0].display_name == "Apple iPhone 14"
    assert rec.of("tracks")[-1].focus_id == CUP2.id


async def test_a_different_object_is_analysed_anew():
    identifier = FakeIdentifier(script=[obs(I14, I13)])
    _, rec = await _held_then_renumbered(identifier, second_colour=(40, 60, 255))
    assert len(identifier.requests) == 2
    assert all(m.previous_id is None for m in rec.of("identity"))


async def test_after_three_seconds_it_is_a_new_object():
    identifier = FakeIdentifier(script=[obs(I14, I13)])
    await _held_then_renumbered(identifier, gap_frames=35)
    assert len(identifier.requests) == 2


async def test_a_running_call_reports_to_the_new_number():
    identifier = FakeIdentifier(script=[obs(I14, I13)], delay_s=0.2)
    _, rec = await _held_then_renumbered(identifier)
    assert len(identifier.requests) == 1
    last = rec.of("identity")[-1]
    assert (last.track_id, last.status, last.display_name) == (CUP2.id, "ready", "Apple iPhone 14")


async def test_an_object_put_down_in_view_is_not_taken_over():
    identifier = FakeIdentifier(script=[obs(I14, I13)])
    on_table = trk(1, (100, 450, 350, 700))  # the first cup, put down but still in view
    pipeline, _, _ = make([[CUP, HAND]] * 13 + [[on_table, CUP2, HAND]], identifier)
    import numpy as np
    blue = sharp_image(boxes=(BOX, (100, 450, 350, 700))).astype(np.float32)
    for x1, y1, x2, y2 in (BOX, (100, 450, 350, 700)):  # both cups look exactly alike
        blue[y1:y2, x1:x2] *= np.array((255, 120, 40), np.float32) / 255
    blue = blue.astype(np.uint8)
    await feed(pipeline, blue, 13)
    await feed(pipeline, blue, 30, start=1.3, first_id=13)
    await pipeline.wait_idle()
    assert len(identifier.requests) == 2  # two cups that look alike, both in view: two objects


# --- sub-project 2: the product profile ------------------------------------------------------------------------------

def _profile(known=True):
    from oi.contracts import ProductProfile, ProfileFact
    if not known:
        return ProductProfile(known=False, summary="", facts=[], released=None, launch_price=None, trivia=[])
    return ProductProfile(known=True, summary="Ein Smartphone von Apple.", facts=[ProfileFact(label="Chip",
                          value="A15 Bionic")], released="September 2022", launch_price="999 €", trivia=[])


def _with_profiles(identifier, store=None, settings=None):
    from oi.profiles import ProfileStore
    settings = settings or Settings()
    rec = Recorder()
    telemetry = Telemetry(settings, "hybrid", "fake")
    pipeline = Pipeline(settings, FakeDetector([[CUP, HAND]]), identifier, telemetry, None, rec,
                        profiles=store if store is not None else ProfileStore(None))
    return pipeline, rec, telemetry


async def _identify_cup(pipeline):
    await feed(pipeline, sharp_image(boxes=(BOX,)), 13)
    await pipeline.wait_idle()


async def test_a_likely_product_gets_its_profile():
    identifier = FakeIdentifier(script=[obs(I14, I13)], profile=_profile())
    pipeline, rec, telemetry = _with_profiles(identifier)
    await _identify_cup(pipeline)
    profiles = rec.of("profile")
    assert [(p.product, p.status) for p in profiles] == [("Apple iPhone 14", "loading"), ("Apple iPhone 14", "ready")]
    assert profiles[-1].line == "Ein Smartphone von Apple." and profiles[-1].facts[0].value == "A15 Bionic"
    assert identifier.product_requests[0].category == "Smartphone" and telemetry.calls_session == 2


async def test_an_unsure_product_gets_no_profile():
    identifier = FakeIdentifier(script=[obs(I14, I13, sa="low")], profile=_profile())
    pipeline, rec, _ = _with_profiles(identifier)
    await _identify_cup(pipeline)
    assert rec.of("profile") == [] and identifier.product_requests == []


async def test_the_same_product_again_costs_nothing():
    from oi.profiles import ProfileStore
    store = ProfileStore(None)
    await _identify_cup(_with_profiles(FakeIdentifier(script=[obs(I14, I13)], profile=_profile()), store)[0])
    later = FakeIdentifier(script=[obs(I14, I13)], profile=_profile())  # another connection, the same phone
    pipeline, rec, _ = _with_profiles(later, store)
    await _identify_cup(pipeline)
    assert later.product_requests == [] and [p.status for p in rec.of("profile")] == ["ready"]


async def test_an_unknown_product_says_so():
    pipeline, rec, _ = _with_profiles(FakeIdentifier(script=[obs(I14, I13)], profile=_profile(known=False)))
    await _identify_cup(pipeline)
    assert (rec.of("profile")[-1].status, rec.of("profile")[-1].line) == ("unknown", "")


async def test_a_failed_profile_says_so_and_is_not_kept():
    from oi.profiles import ProfileStore
    store = ProfileStore(None)
    pipeline, rec, _ = _with_profiles(FakeIdentifier(script=[obs(I14, I13)], profile=IdentifyError("connection")),
                                      store)
    await _identify_cup(pipeline)
    assert [p.status for p in rec.of("profile")] == ["loading", "error"] and store.get("Apple iPhone 14", "de") is None


async def test_no_profile_once_the_budget_is_used_up():
    identifier = FakeIdentifier(script=[obs(I14, I13)], profile=_profile())
    pipeline, rec, _ = _with_profiles(identifier, settings=Settings(max_calls_session=1))
    await _identify_cup(pipeline)
    assert identifier.product_requests == [] and rec.of("profile") == []


async def test_a_confirmed_colour_needs_no_second_profile():
    blue = cand("Apple", "iPhone 14", depth="variant", variant="Blau")
    identifier = FakeIdentifier(script=[obs(blue, I13), obs(blue, I13)], profile=_profile())
    pipeline, rec, _ = _with_profiles(identifier)
    await _identify_cup(pipeline)
    await feed(pipeline, sharp_image(boxes=(BOX,), mirrored=True), 13, start=1.3, first_id=13)  # the other side
    await pipeline.wait_idle()
    assert len(identifier.requests) == 2 and len(identifier.product_requests) == 1
    assert identifier.product_requests[0].product == "Apple iPhone 14"
    ready = [p.product for p in rec.of("profile") if p.status == "ready"]
    assert ready == ["Apple iPhone 14", "Apple iPhone 14, Blau"]  # the card's new name gets the same profile


# --- sub-project 3: the hologram -------------------------------------------------------------------------------------

def _shape(known=True):
    from oi.contracts import ProductShape, ShapePart
    if not known:
        return ProductShape(known=False, size_mm=None, parts=[])
    return ProductShape(known=True, size_mm=(71.5, 146.7, 7.8), parts=[ShapePart(
        name="Gehäuse", shape="rounded_box", size_mm=(71.5, 146.7, 7.8), position_mm=(0, 0, 0),
        rotation_deg=(0, 0, 0), color="#9fc4e8", radius_mm=8.0)])


def _with_shapes(identifier, store=None, settings=None):
    from oi.profiles import ProfileStore, ShapeStore
    settings = settings or Settings()
    rec = Recorder()
    telemetry = Telemetry(settings, "hybrid", "fake")
    pipeline = Pipeline(settings, FakeDetector([[CUP, HAND]]), identifier, telemetry, None, rec,
                        profiles=ProfileStore(None), shapes=store if store is not None else ShapeStore(None))
    return pipeline, rec, telemetry


async def test_a_likely_product_gets_its_hologram_from_the_crop():
    identifier = FakeIdentifier(script=[obs(I14, I13)], profile=_profile(), shape=_shape())
    pipeline, rec, telemetry = _with_shapes(identifier)
    await _identify_cup(pipeline)
    shapes = rec.of("shape")
    assert [(s.product, s.status) for s in shapes] == [("Apple iPhone 14", "loading"), ("Apple iPhone 14", "ready")]
    assert shapes[-1].parts[0].shape == "rounded_box" and shapes[-1].size_mm == (71.5, 146.7, 7.8)
    request = identifier.shape_requests[0]
    assert (request.product, request.category) == ("Apple iPhone 14", "Smartphone")
    assert request.jpeg == identifier.requests[0].jpeg  # the same object-only crop as the identification
    assert telemetry.calls_session == 3


async def test_an_unsure_product_gets_no_hologram():
    identifier = FakeIdentifier(script=[obs(I14, I13, sa="low")], shape=_shape())
    pipeline, rec, _ = _with_shapes(identifier)
    await _identify_cup(pipeline)
    assert rec.of("shape") == [] and identifier.shape_requests == []


async def test_the_same_model_again_needs_no_second_hologram():
    from oi.profiles import ShapeStore
    store = ShapeStore(None)
    await _identify_cup(_with_shapes(FakeIdentifier(script=[obs(I14, I13)], shape=_shape()), store)[0])
    later = FakeIdentifier(script=[obs(I14, I13)], shape=_shape())
    pipeline, rec, _ = _with_shapes(later, store)
    await _identify_cup(pipeline)
    assert later.shape_requests == [] and [s.status for s in rec.of("shape")] == ["ready"]


async def test_an_unknown_or_failed_hologram_says_so():
    from oi.profiles import ShapeStore
    pipeline, rec, _ = _with_shapes(FakeIdentifier(script=[obs(I14, I13)], shape=_shape(known=False)))
    await _identify_cup(pipeline)
    assert rec.of("shape")[-1].status == "unknown"
    store = ShapeStore(None)
    pipeline, rec, _ = _with_shapes(FakeIdentifier(script=[obs(I14, I13)], shape=IdentifyError("api")), store)
    await _identify_cup(pipeline)
    assert [s.status for s in rec.of("shape")] == ["loading", "error"] and store.get("Apple iPhone 14") is None


async def test_no_hologram_without_budget():
    identifier = FakeIdentifier(script=[obs(I14, I13)], profile=_profile(), shape=_shape())
    pipeline, rec, _ = _with_shapes(identifier, settings=Settings(max_calls_session=2))  # identification + profile
    await _identify_cup(pipeline)
    assert identifier.shape_requests == [] and rec.of("shape") == []


# --- the person picks the right candidate: certain, then profile and hologram ---------------------------------------

I15 = cand("Apple", "iPhone 15")


async def test_a_picked_candidate_is_certain_and_brings_profile_and_hologram():
    from oi.contracts import ConfirmMsg
    unsure = obs(I14, I15, dist=False, view="die Vorderseite", reason="Notch oder Dynamic Island")
    identifier = FakeIdentifier(script=[unsure], profile=_profile(), shape=_shape())
    pipeline, rec, _ = _with_shapes(identifier)
    await _identify_cup(pipeline)
    assert rec.of("profile") == [] and rec.of("shape") == []  # unsure: nothing yet
    await pipeline.on_client_message(ConfirmMsg(track_id=CUP.id, name="Apple iPhone 15"))
    await pipeline.wait_idle()
    last = rec.of("identity")[-1]
    assert (last.track_id, last.level, last.confirmed, last.final, last.display_name) == (
        CUP.id, "certain", True, True, "Apple iPhone 15")
    assert identifier.product_requests[0].product == "Apple iPhone 15"
    assert identifier.shape_requests[0].jpeg == identifier.requests[0].jpeg  # the crop of the identification
    await feed(pipeline, sharp_image(boxes=(BOX,), mirrored=True), 13, start=1.3, first_id=13)  # a new side
    await pipeline.wait_idle()
    assert len(identifier.requests) == 1  # confirmed is final: no more calls for this object


async def test_an_entry_can_be_confirmed_after_the_object_is_gone():
    from oi.contracts import ConfirmMsg
    identifier = FakeIdentifier(script=[obs(I14, I15, dist=False, view="die Vorderseite", reason="Notch")])
    pipeline, rec, _ = _with_shapes(identifier)
    pipeline._detector = FakeDetector([[CUP, HAND]] * 13 + [[]])  # then the phone is put away
    await _identify_cup(pipeline)
    await feed(pipeline, sharp_image(), 10, start=1.3, first_id=13, step=60.0)  # ten minutes without it
    await pipeline.on_client_message(ConfirmMsg(track_id=CUP.id, name="Apple iPhone 14"))
    assert rec.of("identity")[-1].confirmed


async def test_a_wrong_pick_changes_nothing():
    from oi.contracts import ConfirmMsg
    pipeline, rec, _ = _with_shapes(FakeIdentifier(script=[obs(I14, I15, dist=False, view="x", reason="y")]))
    await _identify_cup(pipeline)
    before = len(rec.messages)
    await pipeline.on_client_message(ConfirmMsg(track_id=CUP.id, name="Samsung Galaxy S23"))
    await pipeline.on_client_message(ConfirmMsg(track_id=777, name="Apple iPhone 14"))
    assert len(rec.messages) == before


# --- one object seen twice becomes one sidebar entry (Claude compares the crops) ------------------------------------

DS3 = cand("Sony", "DualShock 3")
SIXAXIS = cand("Sony", "Sixaxis")


async def _two_objects_one_after_the_other(identifier, second=None, gap_s=4.0):
    """Track 1 is held and identified, then put away for `gap_s` (longer than the re-identification window), then
    track 2 is held and identified."""
    second = second or trk(2, (420, 210, 690, 490))
    gap = round(gap_s / 0.1)
    script = [[CUP, HAND]] * 13 + [[]] * gap + [[second, HAND]]
    pipeline, rec, telemetry = make(script, identifier)
    await feed(pipeline, sharp_image(boxes=(BOX,)), 13)
    await pipeline.wait_idle()
    await feed(pipeline, sharp_image(), gap, start=1.3, first_id=13)
    await feed(pipeline, sharp_image(boxes=(BOX,), mirrored=True), 13, start=1.3 + gap_s, first_id=13 + gap)
    await pipeline.wait_idle()
    return pipeline, rec, telemetry


async def test_the_same_object_seen_twice_becomes_one_entry():
    dark = obs(desc="schwarzes, unregelmäßig geformtes Objekt", cat="Unbekanntes Objekt")
    identifier = FakeIdentifier(script=[dark, obs(DS3, SIXAXIS)], same=1)
    pipeline, rec, _ = await _two_objects_one_after_the_other(identifier)
    assert len(identifier.same_requests) == 1
    request = identifier.same_requests[0]
    assert [name for name, _ in request.earlier] == ["Schwarzes, unregelmäßig geformtes Objekt"]
    merged = rec.of("identity")[-2:]  # the old entry takes the merged name first, then the object in the hand
    assert [(m.track_id, m.display_name) for m in merged] == [(1, "Sony DualShock 3"), (2, "Sony DualShock 3")]
    assert 1 not in pipeline._states


async def test_a_different_object_stays_its_own_entry():
    identifier = FakeIdentifier(script=[obs(DS3, SIXAXIS), obs(I14, I13)], same=None)
    pipeline, rec, _ = await _two_objects_one_after_the_other(identifier)
    assert len(identifier.same_requests) == 1 and 1 in pipeline._states
    assert rec.of("identity")[-1].display_name == "Apple iPhone 14"


async def test_two_sides_of_one_controller_merge_into_a_certain_one():
    identifier = FakeIdentifier(script=[obs(DS3, SIXAXIS), obs(DS3, SIXAXIS)], same=1)
    _, rec, _ = await _two_objects_one_after_the_other(identifier)
    assert (rec.of("identity")[-1].display_name, rec.of("identity")[-1].level) == ("Sony DualShock 3", "certain")


async def test_objects_in_view_together_are_never_compared():
    identifier = FakeIdentifier(script=[obs(DS3, SIXAXIS), obs(I14, I13)], same=1)
    other = trk(5, (900, 200, 1100, 450))
    hand_on_other = trk(98, (950, 400, 1050, 520), label="hand")
    pipeline, rec, _ = make([[CUP, HAND]] * 13 + [[CUP, other, hand_on_other]], identifier)
    await feed(pipeline, sharp_image(boxes=(BOX, (900, 200, 1100, 450))), 40)
    await pipeline.wait_idle()
    assert identifier.same_requests == []  # the cup is still in view: the second object cannot be the cup


async def test_no_comparison_without_budget():
    identifier = FakeIdentifier(script=[obs(DS3, SIXAXIS), obs(DS3, SIXAXIS)], same=1)
    settings = Settings(max_calls_session=2)  # just the two identifications
    second = trk(2, (420, 210, 690, 490))
    script = [[CUP, HAND]] * 13 + [[]] * 40 + [[second, HAND]]
    rec = Recorder()
    pipeline = Pipeline(settings, FakeDetector(script), identifier, Telemetry(settings, "hybrid", "fake"), None, rec)
    await feed(pipeline, sharp_image(boxes=(BOX,)), 13)
    await pipeline.wait_idle()
    await feed(pipeline, sharp_image(), 40, start=1.3, first_id=13)
    await feed(pipeline, sharp_image(boxes=(BOX,), mirrored=True), 13, start=5.3, first_id=53)
    await pipeline.wait_idle()
    assert identifier.same_requests == []


def test_waiting_never_spins_on_a_task_that_has_just_finished():
    # Found while checking the comparison: a task that finished after wait_idle was woken, but before its own
    # clean-up ran, made `while self._tasks: await gather(...)` spin forever (awaiting a finished task never yields).
    import asyncio
    import threading

    async def scenario():
        pipeline, _, _ = make([[CUP]], None)

        async def quick():
            return None

        first = asyncio.create_task(asyncio.sleep(0))
        pipeline._tasks.add(first)
        first.add_done_callback(pipeline._tasks.discard)

        def spawn(_):
            second = asyncio.create_task(quick())
            pipeline._tasks.add(second)
            second.add_done_callback(pipeline._tasks.discard)

        first.add_done_callback(spawn)
        await pipeline.wait_idle()

    worker = threading.Thread(target=lambda: asyncio.run(scenario()), daemon=True)
    worker.start()
    worker.join(3)
    assert not worker.is_alive()


# --- sub-project 4: questions by voice -----------------------------------------------------------------------------

def _audio(seconds=1.0):
    import base64
    import numpy as np
    noise = (np.random.default_rng(1).normal(0, 0.05, int(16000 * seconds)) * 32767).astype("<i2")
    return base64.b64encode(noise.tobytes()).decode()


def _asking(identifier, transcriber, settings=None):
    from oi.profiles import ProfileStore
    settings = settings or Settings()
    rec = Recorder()
    pipeline = Pipeline(settings, FakeDetector([[CUP, HAND]]), identifier, Telemetry(settings, "hybrid", "fake"), None,
                        rec, profiles=ProfileStore(None), transcriber=transcriber)
    return pipeline, rec


def _ask(track_id=CUP.id, name="Apple iPhone 14", seconds=1.0):
    from oi.contracts import AskMsg
    return AskMsg(track_id=track_id, name=name, rate=16000, audio=_audio(seconds))


async def test_a_spoken_question_gets_an_answer_about_the_object():
    from oi.speech import FakeTranscriber
    identifier = FakeIdentifier(script=[obs(I14, I13)], answer="Es wiegt 172 Gramm.")
    pipeline, rec = _asking(identifier, FakeTranscriber("Wie schwer ist das?"))
    await _identify_cup(pipeline)
    await pipeline.on_client_message(_ask())
    await pipeline.wait_idle()
    questions = rec.of("question")
    assert [q.status for q in questions] == ["transcribing", "thinking", "ready"]
    last = questions[-1]
    assert (last.product, last.question, last.answer, last.line) == (
        "Apple iPhone 14", "Wie schwer ist das?", "Es wiegt 172 Gramm.", "Es wiegt 172 Gramm.")
    request = identifier.ask_requests[0]
    assert (request.product, request.category, request.level) == ("Apple iPhone 14", "Smartphone", "likely")
    assert request.jpeg == identifier.requests[0].jpeg  # the object-only crop, never the whole picture


async def test_a_follow_up_question_knows_the_earlier_answer():
    from oi.speech import FakeTranscriber
    identifier = FakeIdentifier(script=[obs(I14, I13)], answer="Es wiegt 172 Gramm.")
    pipeline, _ = _asking(identifier, FakeTranscriber("Wie schwer ist das?"))
    await _identify_cup(pipeline)
    await pipeline.on_client_message(_ask())
    await pipeline.wait_idle()
    await pipeline.on_client_message(_ask())
    await pipeline.wait_idle()
    assert identifier.ask_requests[1].history == [("Wie schwer ist das?", "Es wiegt 172 Gramm.")]


async def test_silence_or_a_tap_is_no_question():
    from oi.speech import FakeTranscriber
    identifier = FakeIdentifier(script=[obs(I14, I13)])
    pipeline, rec = _asking(identifier, FakeTranscriber(""))
    await _identify_cup(pipeline)
    await pipeline.on_client_message(_ask())
    await pipeline.on_client_message(_ask(seconds=0.1))
    await pipeline.wait_idle()
    assert [q.status for q in rec.of("question")] == ["transcribing", "empty", "transcribing", "empty"]
    assert identifier.ask_requests == []


async def test_no_answer_once_the_budget_is_used_up():
    from oi.speech import FakeTranscriber
    identifier = FakeIdentifier(script=[obs(I14, I13)], answer="x")
    pipeline, rec = _asking(identifier, FakeTranscriber("Wie schwer ist das?"), Settings(max_calls_session=1))
    await _identify_cup(pipeline)
    await pipeline.on_client_message(_ask())
    await pipeline.wait_idle()
    assert rec.of("question")[-1].status == "error" and identifier.ask_requests == []


async def test_an_entry_whose_object_is_gone_can_still_be_asked_about():
    from oi.speech import FakeTranscriber
    identifier = FakeIdentifier(answer="Eine Pendelleuchte hängt an der Decke.")
    pipeline, rec = _asking(identifier, FakeTranscriber("Was ist das?"))
    await pipeline.on_client_message(_ask(track_id=777, name="Pendelleuchte"))
    await pipeline.wait_idle()
    request = identifier.ask_requests[0]
    assert (request.product, request.category, request.jpeg) == ("Pendelleuchte", None, None)
    assert rec.of("question")[-1].product == "Pendelleuchte"


# --- sub-project 5: the photo of the object on its hologram --------------------------------------------------------

def test_the_photo_is_cut_to_the_object():
    import base64
    import cv2
    import numpy as np
    from oi.pipeline import object_photo
    crop = np.full((400, 300, 3), 128, np.uint8)  # grey: everything that is not the object
    crop[100:300, 50:200] = (200, 120, 40)
    photo = cv2.imdecode(np.frombuffer(base64.b64decode(object_photo(cv2.imencode(".jpg", crop)[1].tobytes())),
                                       np.uint8), cv2.IMREAD_COLOR)
    h, w = photo.shape[:2]
    assert 200 <= h <= 220 and 150 <= w <= 170  # the object plus a thin margin
    assert object_photo(cv2.imencode(".jpg", np.full((50, 50, 3), 128, np.uint8))[1].tobytes()) is None


async def test_the_hologram_carries_the_photo_of_the_object():
    identifier = FakeIdentifier(script=[obs(I14, I13)], shape=_shape())
    pipeline, rec, _ = _with_shapes(identifier)
    await _identify_cup(pipeline)
    ready = [s for s in rec.of("shape") if s.status == "ready"][0]
    assert ready.photo and len(ready.photo) > 100  # base64 jpeg of the object
