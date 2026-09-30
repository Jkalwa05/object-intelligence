"""Shared data formats, contract version 1 (spec §2.2, §2.5–§2.7).

Every part of the pipeline speaks these models; `web/src/protocol.ts` mirrors the server messages by hand and
`tests/fixtures/protocol-examples.json` keeps both sides in sync.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from oi.config import Lang

CONTRACT_VERSION = 1

Status = Literal["analysing", "ready", "error", "paused"]


class Level(StrEnum):
    CERTAIN = "certain"
    LIKELY = "likely"
    UNSURE = "unsure"
    CATEGORY_ONLY = "category_only"


class Depth(StrEnum):
    CATEGORY = "category"
    BRAND = "brand"
    MODEL = "model"
    VARIANT = "variant"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


# --- what Claude answers (§2.5) ---------------------------------------------------------------------------------

class Candidate(_Model):
    brand: str | None
    model_name: str | None
    variant: str | None
    depth: Depth
    evidence: list[str] = Field(max_length=5)


class NextView(_Model):
    view: str
    reason: str


class Observation(_Model):
    category: str
    candidates: list[Candidate] = Field(max_length=4)
    readable_text: list[str] = Field(max_length=10)
    distinguishable: bool
    next_view: NextView | None
    self_assessment: Literal["high", "medium", "low"]
    generic_description: str | None


# --- what the pipeline tracks (§2.2, §2.6) ----------------------------------------------------------------------

class Track(_Model):
    """One tracked detection; box and polygon in pixels of the full frame."""

    id: int
    box: tuple[float, float, float, float]
    polygon: list[tuple[float, float]]
    label: str
    score: float
    age_frames: int
    first_seen_ts: float


class RankedCandidate(_Model):
    name: str
    share: float


class BeliefState(_Model):
    level: Level | None
    display_name: str
    candidates: list[RankedCandidate]
    evidence: list[str]
    view_request: NextView | None
    final: bool
    calls_used: int
    line: str

    @classmethod
    def empty(cls, display_name: str) -> BeliefState:
        return cls(level=None, display_name=display_name, candidates=[], evidence=[], view_request=None, final=False,
                   calls_used=0, line="")


# --- WebSocket protocol (§2.7) ----------------------------------------------------------------------------------

class FrameHeader(_Model):
    frame_id: int
    t_capture_ms: float
    w: int
    h: int


class WireTrack(_Model):
    """A track as the browser sees it: coordinates normalized to 0..1."""

    id: int
    box: tuple[float, float, float, float]
    polygon: list[tuple[float, float]]
    label: str
    score: float

    @classmethod
    def from_track(cls, t: Track, w: int, h: int) -> WireTrack:
        x1, y1, x2, y2 = t.box
        return cls(id=t.id, box=(round(x1 / w, 4), round(y1 / h, 4), round(x2 / w, 4), round(y2 / h, 4)),
                   polygon=[(round(x / w, 4), round(y / h, 4)) for x, y in t.polygon], label=t.label,
                   score=round(t.score, 3))


class _ServerMsg(_Model):
    ts: float = 0.0
    seq: int = 0


class TracksMsg(_ServerMsg):
    type: Literal["tracks"] = "tracks"
    frame_id: int
    w: int
    h: int
    focus_id: int | None
    tracks: list[WireTrack]
    hint: str | None
    faces: list[tuple[float, float, float, float]] = Field(default_factory=list)  # normalized, the card avoids them


class IdentityMsg(_ServerMsg):
    type: Literal["identity"] = "identity"
    track_id: int
    status: Status
    level: Level | None
    display_name: str
    candidates: list[RankedCandidate]
    evidence: list[str]
    view_request: NextView | None
    final: bool
    calls_used: int
    line: str

    @classmethod
    def from_belief(cls, track_id: int, status: Status, b: BeliefState) -> IdentityMsg:
        return cls(track_id=track_id, status=status, **b.model_dump())


class TelemetryMsg(_ServerMsg):
    type: Literal["telemetry"] = "telemetry"
    fps_processed: float
    frames_dropped: int
    det_ms: float
    id_ms_last: float | None
    sharpness_focus: float | None
    calls_session: int
    cost_session_usd: float
    model: str
    gate_focus: str | None = None  # which quality check the focus crop fails right now (views.GateFailure) or None
    mode: Literal["hybrid", "lokal"]
    language: Lang  # addition to §2.7: the browser needs it for its fixed texts


class NoticeMsg(_ServerMsg):
    type: Literal["notice"] = "notice"
    level: Literal["info", "warn", "error"]
    text: str


ServerMsg = Annotated[TracksMsg | IdentityMsg | TelemetryMsg | NoticeMsg, Field(discriminator="type")]


class FocusMsg(_Model):
    type: Literal["focus"] = "focus"
    track_id: int | None


class RecheckMsg(_Model):
    type: Literal["recheck"] = "recheck"
    track_id: int


ClientMsg = Annotated[FocusMsg | RecheckMsg, Field(discriminator="type")]
_client_messages: TypeAdapter[FocusMsg | RecheckMsg] = TypeAdapter(ClientMsg)


def parse_client_message(text: str) -> FocusMsg | RecheckMsg | None:
    """A browser message, or None for anything malformed or unknown."""
    try:
        return _client_messages.validate_json(text)
    except ValidationError:
        return None


def protocol_examples() -> list[dict]:
    """One example of every server message, written to tests/fixtures/protocol-examples.json."""
    track = WireTrack(id=17, box=(0.1, 0.2, 0.3, 0.6), polygon=[(0.1, 0.2), (0.3, 0.2), (0.3, 0.6)],
                      label="cell phone", score=0.91)
    messages: list[_ServerMsg] = [
        TracksMsg(ts=1.0, seq=1, frame_id=42, w=1280, h=720, focus_id=17, tracks=[track], hint=None),
        IdentityMsg(ts=1.1, seq=2, track_id=17, status="ready", level=Level.LIKELY, display_name="Apple iPhone 14",
                    candidates=[RankedCandidate(name="Apple iPhone 14", share=0.67),
                                RankedCandidate(name="Apple iPhone 13", share=0.33)],
                    evidence=["Apple-Logo", "2 Kameras"], view_request=None, final=False, calls_used=1,
                    line="Das ist wahrscheinlich Apple iPhone 14."),
        TelemetryMsg(ts=1.2, seq=3, fps_processed=11.5, frames_dropped=3, det_ms=24.0, id_ms_last=2800.0,
                     sharpness_focus=142.0, calls_session=1, cost_session_usd=0.02, model="claude-opus-5-5",
                     mode="hybrid", language="de"),
        NoticeMsg(ts=1.3, seq=4, level="warn", text="Kein API-Key: nur lokale Erkennung."),
    ]
    return [m.model_dump(mode="json") for m in messages]
