"""The pipeline: one frame in, tracks and identities out (spec §2.1–§2.6, §8, §9).

Detection and tracking run on every frame; identification runs in the background and the frame loop never waits
for it. All timing logic uses the browser's capture time, so the behaviour does not depend on server load.
When the scene calibration ends, one Claude call names the frozen background, with every person painted grey.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import cv2
import numpy as np

from oi import appearance, lines
from oi.belief import Belief, Product
from oi.config import Settings
from oi.contracts import (AnyClientMsg, AskMsg, BeliefState, ConfirmMsg, FocusMsg, IdentityMsg, Level, NoticeMsg,
                          ProductProfile, ProfileMsg, QuestionMsg, RecalibrateMsg, SceneItemWire, SceneMsg,
                          ServerMsg, Status, Track, TracksMsg, WireTrack)
from oi.faces import FaceFinder
from oi.hands import HandConfirmer, HandFinder
from oi.focus import FocusSelector, split_tracks
from oi.identify import (AskRequest, AskResult, Identifier, IdentifyError, IdentifyRequest, IdentifyResult,
                         ProductRequest, ProductResult, SameRequest, SameResult, SceneRequest, SceneResult,
                         format_history, request_text)
from oi.ingest import Frame, FrameFormatError, FrameSlot, decode_frame
from oi.perception import Detector
from oi.privacy import label_in, mask_people, on_person, privacy_veto
from oi.profiles import ProfileStore
from oi.scene import SceneMap
from oi.speech import RATE, Transcriber, decode_pcm
from oi.telemetry import CallLog, CallRecord, Telemetry
from oi.trigger import Decision, TriggerInput, decide
from oi.views import ReadyCrop, ViewCollector, encode_for_claude

log = logging.getLogger(__name__)

Emit = Callable[[ServerMsg], Awaitable[None]]
FORGET_AFTER_S = 30.0
FORGET_IDENTIFIED_AFTER_S = 600.0  # an identified object stays 10 minutes: its sidebar entry can still be confirmed
SCENE_WIDTH = 1280  # the scene image for Claude is at most this wide
SCENE_JPEG_QUALITY = 85
PRIVATE_MEMORY_S = 2.0  # everyone seen in the last 2 s of the calibration is greyed, even if missed in the last frame
REID_WINDOW_S = 3.0  # an identified object that vanished at most 3 s ago may come back under a new number
REID_SIZE = 2.0  # ... if its box is at most twice or half as large
MAX_COMPARED = 3  # a new object is compared with at most the 3 objects seen last
COMPARE_EDGE = 384  # the crops for a comparison are this small: about 200 tokens each
MIN_QUESTION_S = 0.3  # shorter is a tap of the space bar, not a question
MAX_HISTORY = 6  # earlier questions and answers about the same object that Claude gets as context

Box = tuple[float, float, float, float]


def _normalized(box: Box, w: int, h: int) -> Box:
    return round(box[0] / w, 4), round(box[1] / h, 4), round(box[2] / w, 4), round(box[3] / h, 4)


@dataclass
class _TrackState:
    track_id: int  # changes when the tracker renumbers the object (spec §11)
    belief: Belief
    collector: ViewCollector
    label: str
    last_seen: float
    calls: int = 0
    in_flight: bool = False
    forced: bool = False
    paused_sent: bool = False
    last_jpeg: bytes | None = None  # the last crop sent to Claude: the hologram's picture after a confirmation
    compared: bool = False  # it was checked once whether it is an object seen earlier
    qa: list[tuple[str, str]] = field(default_factory=list)  # questions and answers about this object


def _scene_jpeg(image: np.ndarray, private: list[Track]) -> bytes:
    """The whole frame for the scene call: every person zone flat grey, at most 1280 pixels wide."""
    masked = mask_people(image, private)
    h, w = masked.shape[:2]
    if w > SCENE_WIDTH:
        masked = cv2.resize(masked, (SCENE_WIDTH, round(h * SCENE_WIDTH / w)), interpolation=cv2.INTER_AREA)
    ok, jpeg = cv2.imencode(".jpg", masked, [cv2.IMWRITE_JPEG_QUALITY, SCENE_JPEG_QUALITY])
    if not ok:
        raise ValueError("JPEG encoding failed")
    return jpeg.tobytes()


@dataclass(frozen=True)
class _Seen:
    """The last identified focus object: what it looked like and when it was last held."""

    track_id: int
    signature: np.ndarray
    area: float
    t: float


def _area(box: Box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _small(jpeg: bytes) -> bytes:
    image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    return encode_for_claude(image, COMPARE_EDGE, 80) if image is not None else jpeg


def _profile_msg(product: str, profile: ProductProfile) -> ProfileMsg:
    if not profile.known:
        return ProfileMsg.of(product, "unknown", profile)
    return ProfileMsg.of(product, "ready", profile, line=profile.summary)


class Pipeline:
    def __init__(self, settings: Settings, detector: Detector, identifier: Identifier | None, telemetry: Telemetry,
                 call_log: CallLog | None, emit: Emit, faces: FaceFinder | None = None,
                 hands: HandFinder | None = None, profiles: ProfileStore | None = None,
                 transcriber: Transcriber | None = None) -> None:
        self._s = settings
        self._detector = detector
        self._identifier = identifier
        self._telemetry = telemetry
        self._call_log = call_log
        self._emit = emit
        self._faces = faces
        self._hands = hands
        self._head_zone = faces is None  # with real face boxes the coarse head-zone rule is not needed
        self._focus = FocusSelector(settings, head_zone=self._head_zone)
        self._states: dict[int, _TrackState] = {}
        self._confirmer = HandConfirmer()
        self._scene = SceneMap()
        self._scene_announced = False
        self._scene_generation = 0  # a new calibration makes a late answer for the old scene worthless
        self._background: list[Box] = []  # frozen background boxes in pixels: never the focus
        self._private: list[tuple[float, list[Track]]] = []  # recent person zones during the calibration
        self._identified: _Seen | None = None
        self._visible_ids: set[int] = set()  # what is in view together can never be the same object
        self._transcriber = transcriber
        self._questions = 0
        self._profiles = profiles
        self._profiles_sent: set[str] = set()  # card names whose profile this connection has
        self._profiles_pending: dict[str, set[str]] = {}  # model being fetched -> card names waiting for it
        self._tasks: set[asyncio.Task[None]] = set()
        self._in_flight = 0
        self._calls_logged = 0

    async def handle_frame(self, frame: Frame) -> None:
        started = time.perf_counter()
        tracks = await asyncio.to_thread(self._detector.detect, frame.image, frame.t)
        self._telemetry.frame_processed((time.perf_counter() - started) * 1000.0)
        h, w = frame.image.shape[:2]
        self._frame_w, self._frame_h = w, h
        visible, hands = split_tracks(tracks, self._s)
        if self._hands is not None:  # Apple Vision's checked hands replace YOLOE's rare "hand" labels
            hands = self._confirmer.confirm(await asyncio.to_thread(self._hands.find, frame.image))
        people_labels = set(self._s.person_labels) | set(self._s.face_labels)
        people = [t for t in tracks if label_in(t.label, people_labels)]
        faces = await asyncio.to_thread(self._faces.find, frame.image) if self._faces is not None else []
        people += faces
        self._visible_ids = {t.id for t in visible}
        focus_id = self._focus.update(visible, hands, w, h, frame.t, people=people, background=self._background)
        private = people + [t for t in tracks if label_in(t.label, self._s.excluded_labels) and t not in people]
        await self._calibrate_scene(frame, visible, people, private, focus_id)
        for track in visible:
            self._remember(track, frame.t)

        focus = next((t for t in visible if t.id == focus_id), None)
        if focus is not None:
            await self._recognise_again(focus, frame, {t.id for t in visible})
        if focus is not None and self._identifier is not None:
            state = self._states[focus.id]
            blocked = None
            if privacy_veto(focus, people, self._s, self._head_zone):
                blocked = "lower" if self._focus.held(focus.id, frame.t) else "person"
            result = state.collector.offer(focus, frame.image, frame.t, blocked)
            self._telemetry.set_sharpness(result.sharpness)
            self._telemetry.set_gate(result.failing)
            if result.ready is not None:
                await self._consider(focus, state, result.ready)
        else:
            self._telemetry.set_sharpness(None)
            self._telemetry.set_gate(None)

        self._forget(frame.t)
        await self._emit(TracksMsg(frame_id=frame.frame_id, w=w, h=h, focus_id=focus_id,
                                   tracks=[WireTrack.from_track(t, w, h) for t in visible if t.id == focus_id],
                                   faces=[WireTrack.from_track(f, w, h).box for f in faces],
                                   hands=[WireTrack.from_track(hand, w, h) for hand in hands]))

    async def on_client_message(self, message: AnyClientMsg) -> None:
        if isinstance(message, RecalibrateMsg):
            self._scene.reset()
            self._scene_announced = False
            self._scene_generation += 1
            self._background = []
            self._private = []
        elif isinstance(message, FocusMsg):
            self._focus.pin(message.track_id)
        elif isinstance(message, ConfirmMsg):
            await self._confirm(message)
        elif isinstance(message, AskMsg):
            self._questions += 1
            task = asyncio.create_task(self._ask(self._questions, message))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        elif (state := self._states.get(message.track_id)) is not None:
            state.forced = True
            state.collector.force_next()

    async def run(self, slot: FrameSlot) -> None:
        while True:
            raw = await slot.get()
            try:
                frame = await asyncio.to_thread(decode_frame, raw)
            except FrameFormatError:
                continue
            try:
                await self.handle_frame(frame)
            except Exception:  # noqa: BLE001 - one broken frame must not stop the loop
                log.exception("frame %s failed", raw[0].frame_id)

    async def telemetry_tick(self, frames_dropped: int) -> None:
        await self._emit(self._telemetry.snapshot(frames_dropped))

    async def wait_idle(self) -> None:
        """Wait until every background call has finished (tests). Only unfinished tasks are awaited: a task that has
        just finished but is not yet removed from the set would make the loop spin, as awaiting it never yields."""
        while pending := [task for task in self._tasks if not task.done()]:
            await asyncio.gather(*pending, return_exceptions=True)
        await asyncio.sleep(0)  # let the finished tasks remove themselves

    async def aclose(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def _calibrate_scene(self, frame: Frame, visible: list[Track], people: list[Track], private: list[Track],
                               focus_id: int | None) -> None:
        """Collect the background during calibration: never the person, nothing worn, nothing held. When the scene
        freezes, Claude names it (people painted grey); without Claude the detector's labels stay."""
        if not self._scene.calibrating:
            return
        if not self._scene_announced:
            self._scene_announced = True
            await self._emit(SceneMsg(calibrating=True, items=[]))
        now = frame.t
        h, w = frame.image.shape[:2]
        self._private = [(t, zones) for t, zones in self._private if now - t <= PRIVATE_MEMORY_S] + [(now, private)]
        background = [t for t in visible if t.id != focus_id and not self._focus.held(t.id, now)
                      and not on_person(t, people, h) and not privacy_veto(t, people, self._s, self._head_zone)]
        if not self._scene.observe(background, now):
            return
        self._background = [i.box for i in self._scene.items]
        local = [SceneItemWire(label=i.label, box=_normalized(i.box, w, h)) for i in self._scene.items]
        if self._identifier is None or self._telemetry.calls_session >= self._s.max_calls_session:
            await self._emit(SceneMsg(calibrating=False, items=local))
            return
        await self._emit(SceneMsg(calibrating=False, naming=True, items=[]))
        self._telemetry.call_started()  # counted now, see _want_profile
        everyone = [t for _, zones in self._private for t in zones]
        task = asyncio.create_task(self._name_scene(self._scene_generation, _scene_jpeg(frame.image, everyone), local))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _name_scene(self, generation: int, jpeg: bytes, local: list[SceneItemWire]) -> None:
        assert self._identifier is not None
        try:
            result = await self._identifier.describe_scene(SceneRequest(jpeg=jpeg, language=self._s.language))
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - any failure falls back to the detector's own labels
            if not isinstance(error, IdentifyError):
                log.exception("naming the scene failed")
            self._telemetry.call_failed()
            self._write_scene_log(jpeg, None, error.reason if isinstance(error, IdentifyError) else "api")
            if generation == self._scene_generation:
                await self._emit(SceneMsg(calibrating=False, items=local))
                await self._emit(NoticeMsg(level="info", text=lines.notice_text("scene_local", self._s.language)))
            return
        self._telemetry.call_finished(result.latency_s, result.cost_usd)
        self._write_scene_log(jpeg, result, None)
        if generation != self._scene_generation:
            return
        w, h = self._frame_w, self._frame_h
        self._background += [(i.box[0] * w, i.box[1] * h, i.box[2] * w, i.box[3] * h) for i in result.items]
        await self._emit(SceneMsg(calibrating=False, items=result.items))

    def _write_scene_log(self, jpeg: bytes, result: SceneResult | None, error: str | None) -> None:
        if self._call_log is None:
            return
        self._calls_logged += 1
        self._call_log.write(CallRecord(
            n=self._calls_logged, track_id=0, jpeg=jpeg, request_text="scene",
            observation={"items": [i.model_dump(mode="json") for i in result.items]} if result else None, error=error,
            input_tokens=result.input_tokens if result else 0, output_tokens=result.output_tokens if result else 0,
            cost_usd=result.cost_usd if result else 0.0, latency_s=result.latency_s if result else 0.0,
            model=result.model if result else (self._identifier.model_label if self._identifier else "–"),
            level_after=None))

    # --- questions by voice (sub-project 4) -------------------------------------------------------------------------

    async def _ask(self, qid: int, message: AskMsg) -> None:
        """Understand the spoken question on the Mac, then let Claude answer it about the object, searching the web
        only when it needs to. Every step shows up in the object's entry."""
        lang = self._s.language
        state = self._states.get(message.track_id) if message.track_id is not None else None
        name = message.name or (self._snapshot(state).display_name if state else "")
        base: dict = {"product": name, "qid": qid, "question": "", "answer": "", "sources": [], "line": ""}
        await self._emit(QuestionMsg(status="transcribing", **base))
        samples = decode_pcm(message.audio, message.rate)
        text = ""
        if self._transcriber is not None and len(samples) >= MIN_QUESTION_S * RATE:
            text = await self._transcriber.transcribe(samples, lang)
        if not text:
            await self._emit(QuestionMsg(status="empty", **base))
            return
        base["question"] = text
        if self._identifier is None or self._telemetry.calls_session >= self._s.max_calls_session:
            await self._emit(QuestionMsg(status="error", **{**base, "answer": lines.paused_line(lang)}))
            return
        await self._emit(QuestionMsg(status="thinking", **base))
        self._telemetry.call_started()
        request = self._ask_request(text, name, state)
        try:
            result = await self._identifier.answer(request)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - the entry says so
            if not isinstance(error, IdentifyError):
                log.exception("answering a question failed")
            self._telemetry.call_failed()
            self._write_ask_log(request, None, error.reason if isinstance(error, IdentifyError) else "api")
            await self._emit(QuestionMsg(status="error", **{**base, "answer": lines.error_line(lang)}))
            return
        self._telemetry.call_finished(result.latency_s, result.cost_usd)
        self._write_ask_log(request, result, None)
        if state is not None:
            state.qa.append((text, result.answer))
        await self._emit(QuestionMsg(status="ready", **{**base, "answer": result.answer, "sources": result.sources,
                                                         "line": result.answer}))

    def _ask_request(self, question: str, name: str, state: _TrackState | None) -> AskRequest:
        lang = self._s.language
        if state is None or not state.belief.observations:
            return AskRequest(question=question, product=name or None, category=None, level=None, facts="",
                              history=[], jpeg=None, language=lang)
        snapshot = self._snapshot(state)
        product = state.belief.product()
        profile = self._profiles.get(product.model, lang) if product and self._profiles else None
        facts = "; ".join(f"{f.label}: {f.value}" for f in profile.facts) if profile and profile.known else ""
        return AskRequest(question=question, product=name or snapshot.display_name,
                          category=state.belief.observations[-1].category,
                          level=str(snapshot.level) if snapshot.level else None, facts=facts,
                          history=state.qa[-MAX_HISTORY:], jpeg=state.last_jpeg, language=lang)

    def _write_ask_log(self, request: AskRequest, result: AskResult | None, error: str | None) -> None:
        if self._call_log is None:
            return
        self._calls_logged += 1
        self._call_log.write(CallRecord(
            n=self._calls_logged, track_id=-4, jpeg=request.jpeg or b"",
            request_text=f"ask about {request.product}: {request.question}",
            observation={"answer": result.answer, "sources": [s.model_dump() for s in result.sources],
                         "searches": result.searches} if result else None, error=error,
            input_tokens=result.input_tokens if result else 0, output_tokens=result.output_tokens if result else 0,
            cost_usd=result.cost_usd if result else 0.0, latency_s=result.latency_s if result else 0.0,
            model=result.model if result else (self._identifier.model_label if self._identifier else "–"),
            level_after=None))

    async def _confirm(self, message: ConfirmMsg) -> None:
        """The person picked the right candidate in the sidebar: certain by their word, then profile and hologram.
        Works for entries whose object is gone, too, as long as its state is kept (10 minutes)."""
        state = self._states.get(message.track_id)
        if state is None or not state.belief.confirm(message.name):
            return
        await self._send_identity(state.track_id, "ready", self._snapshot(state))
        if (product := state.belief.product()) is not None:
            await self._want_profile(product)

    async def _recognise_again(self, focus: Track, frame: Frame, visible_ids: set[int]) -> None:
        """The tracker sometimes loses the held object for a moment and gives it a new number. A fresh focus is the
        last identified object if that one has vanished, was held at most 3 s ago, and size and colours still fit:
        its identity, views and calls move over, so the card stays and nothing is paid twice (spec §11)."""
        state = self._states[focus.id]
        signature = appearance.signature(frame.image, focus)
        if state.calls or state.belief.observations:
            self._identified = _Seen(focus.id, signature, _area(focus.box), frame.t)
            return
        seen = self._identified
        if seen is None or seen.track_id == focus.id or seen.track_id in visible_ids:
            return
        old = self._states.get(seen.track_id)
        ratio = _area(focus.box) / seen.area if seen.area else 0.0
        if (old is None or frame.t - seen.t > REID_WINDOW_S or not 1 / REID_SIZE <= ratio <= REID_SIZE
                or not appearance.similar(signature, seen.signature)):
            return
        del self._states[seen.track_id]
        old.track_id, old.label, old.last_seen = focus.id, focus.label, frame.t
        self._states[focus.id] = old
        self._identified = _Seen(focus.id, signature, _area(focus.box), frame.t)
        await self._emit(IdentityMsg.from_belief(focus.id, "analysing" if old.in_flight else "ready",
                                                 self._snapshot(old), previous_id=seen.track_id))

    # --- identification -----------------------------------------------------------------------------------------

    async def _consider(self, track: Track, state: _TrackState, ready: ReadyCrop) -> None:
        decision = decide(TriggerInput(is_focus=True, ready=ready, final=state.belief.is_final,
                                       in_flight_track=state.in_flight, in_flight_total=self._in_flight,
                                       calls_track=state.calls, calls_session=self._telemetry.calls_session,
                                       forced=state.forced), self._s)
        if decision == Decision.CALL:
            state.forced = False
            state.calls += 1
            state.in_flight = True
            self._in_flight += 1
            self._telemetry.call_started()
            state.collector.mark_sent(ready)
            state.last_jpeg = ready.jpeg
            await self._send_identity(track.id, "analysing", self._snapshot(state))
            task = asyncio.create_task(self._identify(state, ready))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        elif decision == Decision.BUSY:
            state.collector.rearm()
        elif decision == Decision.SESSION_CAP:
            paused = lines.paused_line(self._s.language)
            if not state.paused_sent:
                state.paused_sent = True
                await self._send_identity(track.id, "paused", self._snapshot(state).model_copy(update={"line": paused}))
            if not self._telemetry.budget.cap_notice_sent:
                self._telemetry.budget.cap_notice_sent = True
                await self._emit(NoticeMsg(level="warn", text=paused))

    async def _identify(self, state: _TrackState, ready: ReadyCrop) -> None:
        """Reports to `state.track_id` when the answer arrives: the object may have a new number by then."""
        assert self._identifier is not None
        lang = self._s.language
        pending = self._snapshot(state).view_request
        req = IdentifyRequest(jpeg=ready.jpeg, coarse_label=state.label,
                              history=format_history(state.belief.observations, lang), pending_view=pending,
                              language=lang)
        try:
            result = await self._identifier.identify(req)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - IdentifyError and anything unexpected end in status "error"
            reason = error.reason if isinstance(error, IdentifyError) else "api"
            if not isinstance(error, IdentifyError):
                log.exception("identification of track %s failed", state.track_id)
            self._telemetry.call_failed()
            self._write_log(state.track_id, ready, req, None, reason, None)
            snapshot = self._snapshot(state).model_copy(update={"line": lines.error_line(lang)})
            await self._send_identity(state.track_id, "error", snapshot)
        else:
            state.belief.add(result.observation, ready.view_id, ready.q)
            self._telemetry.call_finished(result.latency_s, result.cost_usd)
            snapshot = self._snapshot(state)
            self._write_log(state.track_id, ready, req, result, None, snapshot.level)
            await self._send_identity(state.track_id, "ready", snapshot)
            if (product := state.belief.product()) is not None:
                await self._want_profile(product)
            await self._want_compare(state)
        finally:
            state.in_flight = False
            self._in_flight -= 1

    # --- product profile (sub-project 2) ---------------------------------------------------------------------------

    async def _want_profile(self, product: Product) -> None:
        """A product reached "likely": the profile of its model comes from the store, or from one text-only Claude
        call. It is sent under the card's name, which may also carry a colour ("Apple iPhone 14, Blau")."""
        if self._profiles is None or self._identifier is None or product.name in self._profiles_sent:
            return
        cached = self._profiles.get(product.model, self._s.language)
        if cached is not None:
            self._profiles_sent.add(product.name)
            await self._emit(_profile_msg(product.name, cached))
            return
        if (waiting := self._profiles_pending.get(product.model)) is not None:
            waiting.add(product.name)
            await self._emit(ProfileMsg.of(product.name, "loading", None))
            return
        if self._telemetry.calls_session >= self._s.max_calls_session:
            return
        self._profiles_pending[product.model] = {product.name}
        self._telemetry.call_started()  # counted now: a call decided in the same frame must see it (budget)
        await self._emit(ProfileMsg.of(product.name, "loading", None))
        task = asyncio.create_task(self._fetch_profile(ProductRequest(product=product.model, category=product.category,
                                                                      language=self._s.language)))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _fetch_profile(self, req: ProductRequest) -> None:
        assert self._identifier is not None and self._profiles is not None
        try:
            result = await self._identifier.describe_product(req)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - the panel says so; the next identification may try again
            if not isinstance(error, IdentifyError):
                log.exception("the profile of %s failed", req.product)
            self._telemetry.call_failed()
            self._write_profile_log(req, None, error.reason if isinstance(error, IdentifyError) else "api")
            for name in self._profiles_pending.pop(req.product, set()):
                await self._emit(ProfileMsg.of(name, "error", None))
            return
        self._telemetry.call_finished(result.latency_s, result.cost_usd)
        self._write_profile_log(req, result, None)
        self._profiles.put(req.product, req.language, result.profile)
        for name in sorted(self._profiles_pending.pop(req.product, set())):
            self._profiles_sent.add(name)
            await self._emit(_profile_msg(name, result.profile))

    # --- one object seen twice (sub-project 3) ---------------------------------------------------------------------

    async def _want_compare(self, state: _TrackState) -> None:
        """Once per object, after its first answer: is it one of the objects seen earlier, say the same controller
        from the other side? Claude compares small crops. What is in view together is never compared."""
        if self._identifier is None or state.compared or state.last_jpeg is None:
            return
        state.compared = True
        earlier = sorted((s for s in self._states.values() if s is not state and s.belief.observations
                          and s.last_jpeg is not None and s.track_id not in self._visible_ids),
                         key=lambda s: -s.last_seen)[:MAX_COMPARED]
        if not earlier or self._telemetry.calls_session >= self._s.max_calls_session:
            return
        self._telemetry.call_started()  # counted now, see _want_profile
        req = SameRequest(new_jpeg=_small(state.last_jpeg),
                          earlier=[(self._snapshot(s).display_name, _small(s.last_jpeg or b"")) for s in earlier],
                          language=self._s.language)
        task = asyncio.create_task(self._compare(state, earlier, req))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _compare(self, state: _TrackState, earlier: list[_TrackState], req: SameRequest) -> None:
        assert self._identifier is not None
        try:
            result = await self._identifier.compare(req)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - no merge then; both entries simply stay
            if not isinstance(error, IdentifyError):
                log.exception("comparing track %s failed", state.track_id)
            self._telemetry.call_failed()
            self._write_compare_log(state, req, None, error.reason if isinstance(error, IdentifyError) else "api")
            return
        self._telemetry.call_finished(result.latency_s, result.cost_usd)
        self._write_compare_log(state, req, result, None)
        if result.same_as is None:
            return
        other = earlier[result.same_as - 1]
        if self._states.get(other.track_id) is not other or other.track_id in self._visible_ids:
            return  # gone meanwhile, or back in view next to it
        await self._merge(other, into=state)

    async def _merge(self, other: _TrackState, into: _TrackState) -> None:
        """One object, two tracks: views, evidence, calls and the person's pick join; the old entry takes the merged
        name first, so the browser folds it into the entry of the object in the hand."""
        into.belief.absorb(other.belief)
        into.calls += other.calls
        into.qa = other.qa + into.qa
        into.last_jpeg = into.last_jpeg or other.last_jpeg
        del self._states[other.track_id]
        if self._identified is not None and self._identified.track_id == other.track_id:
            self._identified = None
        snapshot = self._snapshot(into)
        await self._send_identity(other.track_id, "ready", snapshot)
        await self._send_identity(into.track_id, "analysing" if into.in_flight else "ready", snapshot)
        if (product := into.belief.product()) is not None:
            await self._want_profile(product)

    def _write_compare_log(self, state: _TrackState, req: SameRequest, result: SameResult | None,
                           error: str | None) -> None:
        if self._call_log is None:
            return
        self._calls_logged += 1
        names = [name for name, _ in req.earlier]
        self._call_log.write(CallRecord(
            n=self._calls_logged, track_id=-3, jpeg=req.new_jpeg, request_text=f"same: track {state.track_id} vs {names}",
            observation={"same_as": result.same_as, "reason": result.reason} if result else None, error=error,
            input_tokens=result.input_tokens if result else 0, output_tokens=result.output_tokens if result else 0,
            cost_usd=result.cost_usd if result else 0.0, latency_s=result.latency_s if result else 0.0,
            model=result.model if result else (self._identifier.model_label if self._identifier else "–"),
            level_after=None))

    def _write_profile_log(self, req: ProductRequest, result: ProductResult | None, error: str | None) -> None:
        if self._call_log is None:
            return
        self._calls_logged += 1
        self._call_log.write(CallRecord(
            n=self._calls_logged, track_id=-1, jpeg=b"", request_text=f"profile: {req.product} ({req.category})",
            observation=result.profile.model_dump(mode="json") if result else None, error=error,
            input_tokens=result.input_tokens if result else 0, output_tokens=result.output_tokens if result else 0,
            cost_usd=result.cost_usd if result else 0.0, latency_s=result.latency_s if result else 0.0,
            model=result.model if result else (self._identifier.model_label if self._identifier else "–"),
            level_after=None))

    def _snapshot(self, state: _TrackState) -> BeliefState:
        if not state.belief.observations:
            return BeliefState.empty(state.label).model_copy(update={"calls_used": state.calls})
        return state.belief.snapshot(state.calls)

    async def _send_identity(self, track_id: int, status: Status, snapshot: BeliefState) -> None:
        await self._emit(IdentityMsg.from_belief(track_id, status, snapshot))

    def _write_log(self, track_id: int, ready: ReadyCrop, req: IdentifyRequest, result: IdentifyResult | None,
                   error: str | None, level: Level | None) -> None:
        if self._call_log is None:
            return
        self._calls_logged += 1
        self._call_log.write(CallRecord(
            n=self._calls_logged, track_id=track_id, jpeg=ready.jpeg, request_text=request_text(req),
            observation=result.observation.model_dump(mode="json") if result else None, error=error,
            input_tokens=result.input_tokens if result else 0, output_tokens=result.output_tokens if result else 0,
            cost_usd=result.cost_usd if result else 0.0, latency_s=result.latency_s if result else 0.0,
            model=result.model if result else (self._identifier.model_label if self._identifier else "–"),
            level_after=str(level) if level else None))

    # --- bookkeeping --------------------------------------------------------------------------------------------

    def _remember(self, track: Track, now: float) -> None:
        state = self._states.get(track.id)
        if state is None:
            state = self._states[track.id] = _TrackState(track_id=track.id, belief=Belief(self._s.language),
                                                         collector=ViewCollector(self._s), label=track.label,
                                                         last_seen=now)
        state.label, state.last_seen = track.label, now

    def _forget(self, now: float) -> None:
        keep = {True: FORGET_IDENTIFIED_AFTER_S, False: FORGET_AFTER_S}
        for track_id in [i for i, s in self._states.items()
                         if not s.in_flight and now - s.last_seen > keep[bool(s.belief.observations)]]:
            del self._states[track_id]
