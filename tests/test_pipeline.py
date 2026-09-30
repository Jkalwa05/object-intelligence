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
    assert {m.type for m in rec.messages} == {"tracks"}


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
    await feed(pipeline, image, 25, start=1.3, first_id=13)
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


async def test_edge_object_gets_full_view_hint():
    edge_box = (5, 200, 305, 500)
    identifier = FakeIdentifier(script=[obs(I14)])
    pipeline, rec, _ = make([[trk(1, edge_box), trk(99, (50, 400, 250, 520), label="hand")]], identifier)
    await feed(pipeline, sharp_image(boxes=(edge_box,)), 22)
    hints = [m.hint for m in rec.of("tracks")]
    assert hints[19] is None and hints[20] == "Bitte ganz ins Bild."
    assert identifier.requests == []


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
    assert all(m.focus_id is None and m.tracks == [] and m.hint is None for m in rec.of("tracks"))


async def test_clicked_person_region_is_never_sent():
    person = trk(10, (300, 0, 980, 720), label="man")
    flag = trk(1, (320, 20, 960, 700), label="flag")
    identifier = FakeIdentifier(script=[obs(I14)])
    pipeline, rec, _ = make([[person, flag]], identifier)
    await pipeline.on_client_message(FocusMsg(track_id=flag.id))
    await feed(pipeline, sharp_image(boxes=((320, 20, 960, 700),)), 22)
    await pipeline.wait_idle()
    assert identifier.requests == []
    assert rec.of("tracks")[20].hint == "Personen und Gesichter identifiziere ich nicht."


async def test_held_object_in_front_of_the_face_is_not_sent_but_explained():
    person = trk(10, (300, 0, 980, 720), label="man")
    phone = trk(3, (520, 40, 700, 230), label="cell phone")
    hand = trk(99, (560, 180, 660, 300), label="hand")
    identifier = FakeIdentifier(script=[obs(I14)])
    pipeline, rec, _ = make([[person, phone, hand]], identifier)
    await feed(pipeline, sharp_image(boxes=((520, 40, 700, 230),)), 22)
    await pipeline.wait_idle()
    assert identifier.requests == []
    assert rec.of("tracks")[0].focus_id == phone.id
    assert rec.of("tracks")[20].hint == "Halt es bitte tiefer, nicht vors Gesicht."


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


async def test_no_hints_once_nothing_can_be_called():
    from tests.helpers import blurry_image
    decisive = obs(cand("Myprotein", "Essential BCAA"), readable=("Essential BCAA 2:1:1",), cat="Dose")
    pipeline, rec, _ = make([[CUP, HAND]], FakeIdentifier(script=[decisive]))
    await feed(pipeline, sharp_image(boxes=(BOX,)), 13)
    await pipeline.wait_idle()
    assert rec.of("identity")[-1].final
    await feed(pipeline, blurry_image(boxes=(BOX,)), 25, start=1.3, first_id=13)
    assert all(m.hint is None for m in rec.of("tracks"))


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
