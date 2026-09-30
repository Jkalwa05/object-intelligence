"""The pipeline: one frame in, tracks and identities out (spec §2.1–§2.6).

Detection and tracking run on every frame; identification runs in the background and the frame loop never waits
for it. All timing logic uses the browser's capture time, so the behaviour does not depend on server load.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from oi import lines
from oi.belief import Belief
from oi.config import Settings
from oi.contracts import (BeliefState, FocusMsg, IdentityMsg, Level, NoticeMsg, RecheckMsg, ServerMsg, Status, Track,
                          TracksMsg, WireTrack)
from oi.focus import FocusSelector, split_tracks
from oi.identify import Identifier, IdentifyError, IdentifyRequest, IdentifyResult, format_history, request_text
from oi.ingest import Frame, FrameFormatError, FrameSlot, decode_frame
from oi.perception import Detector
from oi.telemetry import CallLog, CallRecord, Telemetry
from oi.trigger import Decision, TriggerInput, decide
from oi.views import ReadyCrop, ViewCollector

log = logging.getLogger(__name__)

Emit = Callable[[ServerMsg], Awaitable[None]]
FORGET_AFTER_S = 30.0


@dataclass
class _TrackState:
    belief: Belief
    collector: ViewCollector
    label: str
    last_seen: float
    calls: int = 0
    in_flight: bool = False
    forced: bool = False
    paused_sent: bool = False


class Pipeline:
    def __init__(self, settings: Settings, detector: Detector, identifier: Identifier | None, telemetry: Telemetry,
                 call_log: CallLog | None, emit: Emit) -> None:
        self._s = settings
        self._detector = detector
        self._identifier = identifier
        self._telemetry = telemetry
        self._call_log = call_log
        self._emit = emit
        self._focus = FocusSelector(settings)
        self._states: dict[int, _TrackState] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._in_flight = 0
        self._calls_logged = 0
        self._cap_notice_sent = False

    async def handle_frame(self, frame: Frame) -> None:
        started = time.perf_counter()
        tracks = await asyncio.to_thread(self._detector.detect, frame.image, frame.t)
        self._telemetry.frame_processed((time.perf_counter() - started) * 1000.0)
        h, w = frame.image.shape[:2]
        visible, hands = split_tracks(tracks, self._s)
        focus_id = self._focus.update(visible, hands, w, h, frame.t)
        for track in visible:
            self._remember(track, frame.t)

        hint = None
        focus = next((t for t in visible if t.id == focus_id), None)
        if focus is not None and self._identifier is not None:
            state = self._states[focus.id]
            result = state.collector.offer(focus, frame.image, self._focus.steady(focus.id), frame.t)
            self._telemetry.set_sharpness(result.sharpness)
            if result.hint is not None:
                hint = lines.hint_line(result.hint, self._s.language)
            if result.ready is not None:
                await self._consider(focus, state, result.ready)
        else:
            self._telemetry.set_sharpness(None)

        self._forget(frame.t)
        await self._emit(TracksMsg(frame_id=frame.frame_id, w=w, h=h, focus_id=focus_id,
                                   tracks=[WireTrack.from_track(t, w, h) for t in visible], hint=hint))

    async def on_client_message(self, message: FocusMsg | RecheckMsg) -> None:
        if isinstance(message, FocusMsg):
            self._focus.pin(message.track_id)
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
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def aclose(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*list(self._tasks), return_exceptions=True)

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
            await self._send_identity(track.id, "analysing", self._snapshot(state))
            task = asyncio.create_task(self._identify(track.id, state, ready))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        elif decision == Decision.SESSION_CAP:
            paused = lines.paused_line(self._s.language)
            if not state.paused_sent:
                state.paused_sent = True
                await self._send_identity(track.id, "paused", self._snapshot(state).model_copy(update={"line": paused}))
            if not self._cap_notice_sent:
                self._cap_notice_sent = True
                await self._emit(NoticeMsg(level="warn", text=paused))

    async def _identify(self, track_id: int, state: _TrackState, ready: ReadyCrop) -> None:
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
                log.exception("identification of track %s failed", track_id)
            self._telemetry.call_failed()
            self._write_log(track_id, ready, req, None, reason, None)
            snapshot = self._snapshot(state).model_copy(update={"line": lines.error_line(lang)})
            await self._send_identity(track_id, "error", snapshot)
        else:
            state.belief.add(result.observation, ready.view_id, ready.q)
            self._telemetry.call_finished(result.latency_s, result.cost_usd)
            snapshot = self._snapshot(state)
            self._write_log(track_id, ready, req, result, None, snapshot.level)
            await self._send_identity(track_id, "ready", snapshot)
        finally:
            state.in_flight = False
            self._in_flight -= 1

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
            state = self._states[track.id] = _TrackState(belief=Belief(self._s.language),
                                                         collector=ViewCollector(self._s), label=track.label,
                                                         last_seen=now)
        state.label, state.last_seen = track.label, now

    def _forget(self, now: float) -> None:
        for track_id in [i for i, s in self._states.items() if now - s.last_seen > FORGET_AFTER_S and not s.in_flight]:
            del self._states[track_id]
