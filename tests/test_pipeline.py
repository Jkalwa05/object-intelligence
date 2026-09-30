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
    pipeline, rec, _ = make([[trk(9, (0, 0, 100, 300), label="person"), CUP]], None)
    await feed(pipeline, sharp_image(boxes=(BOX,)), 1)
    (message,) = rec.of("tracks")
    assert [t.id for t in message.tracks] == [CUP.id]
    assert message.tracks[0].box == (0.3125, 0.2778, 0.5469, 0.6944)
    assert (message.w, message.h, message.focus_id) == (1280, 720, CUP.id)


async def test_holding_still_triggers_one_identification():
    identifier = FakeIdentifier(script=[obs(I14, I13)])
    pipeline, rec, telemetry = make([[CUP]], identifier)
    await feed(pipeline, sharp_image(boxes=(BOX,)), 13)
    await pipeline.wait_idle()
    identities = rec.of("identity")
    assert [m.status for m in identities] == ["analysing", "ready"]
    assert identities[1].level == "likely" and identities[1].line == "Das ist wahrscheinlich Apple iPhone 14."
    assert len(identifier.requests) == 1 and identifier.requests[0].coarse_label == "cup"
    assert identifier.requests[0].history == "none" and telemetry.calls_session == 1


async def test_no_identifier_means_tracks_only():
    pipeline, rec, _ = make([[CUP]], None)
    await feed(pipeline, sharp_image(boxes=(BOX,)), 13)
    assert {m.type for m in rec.messages} == {"tracks"}


async def test_result_stays_with_original_track_after_focus_switch():
    book = trk(2, (1000, 100, 1200, 300), label="book")
    identifier = FakeIdentifier(script=[obs(I14, I13)], delay_s=0.3)
    pipeline, rec, _ = make([[CUP, book]], identifier)
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
    pipeline, rec, _ = make([[CUP]] * 13 + [[book]] * 25, FakeIdentifier(script=[obs(I14, I13)]),
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
    pipeline, rec, _ = make([[CUP]], identifier)
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
    pipeline, rec, _ = make([[CUP]], identifier)
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
    pipeline, rec, _ = make([[trk(1, edge_box)]], identifier)
    await feed(pipeline, sharp_image(boxes=(edge_box,)), 22)
    hints = [m.hint for m in rec.of("tracks")]
    assert hints[19] is None and hints[20] == "Bitte ganz ins Bild."
    assert identifier.requests == []


async def test_two_similar_objects_do_not_flicker():
    script = [[trk(3, (300, 260, 500 + (2 if i % 2 else 0), 460)), trk(4, (780, 260, 980 + (0 if i % 2 else 2), 460))]
              for i in range(20)]
    pipeline, rec, _ = make(script, None)
    await feed(pipeline, sharp_image(), 20)
    assert len({m.focus_id for m in rec.of("tracks")}) == 1


async def test_telemetry_tick_emits_snapshot():
    pipeline, rec, _ = make([[CUP]], None)
    await pipeline.telemetry_tick(frames_dropped=2)
    (message,) = rec.of("telemetry")
    assert (message.frames_dropped, message.mode) == (2, "lokal")


async def test_person_region_is_never_sent():
    person = trk(10, (300, 0, 980, 720), label="man")
    flag = trk(1, (320, 20, 960, 700), label="flag")
    identifier = FakeIdentifier(script=[obs(I14)])
    pipeline, rec, _ = make([[person, flag]], identifier)
    await feed(pipeline, sharp_image(boxes=((320, 20, 960, 700),)), 22)
    await pipeline.wait_idle()
    assert identifier.requests == []
    assert rec.of("tracks")[20].hint == lines.hint_line("person", "de")
