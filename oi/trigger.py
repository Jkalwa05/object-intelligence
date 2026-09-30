"""When does a crop go to Claude? The six rules of spec §2.4, checked in order. Pure logic."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from oi.config import Settings
from oi.views import ReadyCrop


class Decision(StrEnum):
    CALL = "call"
    WAIT = "wait"
    BUSY = "busy"  # a call is running: keep the view and try again later
    OBJECT_CAP = "object_cap"
    SESSION_CAP = "session_cap"


@dataclass(frozen=True)
class TriggerInput:
    is_focus: bool
    ready: ReadyCrop | None
    final: bool
    in_flight_track: bool
    in_flight_total: int
    calls_track: int
    calls_session: int
    forced: bool  # "Neu prüfen" was clicked


def decide(i: TriggerInput, s: Settings) -> Decision:
    if not i.is_focus or i.ready is None:
        return Decision.WAIT
    if i.in_flight_track or i.in_flight_total >= s.max_concurrent_calls:
        return Decision.BUSY
    if i.calls_session >= s.max_calls_session:
        return Decision.SESSION_CAP
    if i.forced:
        return Decision.CALL
    if i.final:
        return Decision.WAIT
    if i.calls_track >= s.max_calls_object:
        return Decision.OBJECT_CAP
    if i.calls_track == 0 or i.ready.is_new_view:
        return Decision.CALL
    return Decision.WAIT
