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


class ProfileFact(_Model):
    label: str
    value: str


class ProductProfile(_Model):
    """What Claude knows about one product (sub-project 2): no sources, so it is always shown as "laut Claude"."""

    known: bool  # False: Claude does not know this exact model and says so instead of guessing
    summary: str
    facts: list[ProfileFact] = Field(max_length=8)
    released: str | None
    launch_price: str | None
    trivia: list[str] = Field(max_length=2)


Vec3 = tuple[float, float, float]
ShapeKind = Literal["box", "rounded_box", "cylinder", "cone", "sphere", "capsule"]


class ShapePart(_Model):
    """One primitive of a hologram (sub-project 3), in millimetres around the object's centre, y pointing up."""

    name: str
    shape: ShapeKind
    size_mm: Vec3  # box: width, height, depth · cylinder/capsule: diameter, height, diameter · cone: bottom
    #                diameter, height, top diameter · sphere: the diameters along x, y, z
    position_mm: Vec3
    rotation_deg: Vec3
    color: str  # "#rrggbb"
    radius_mm: float | None = None  # rounded_box only


class ProductShape(_Model):
    """A simplified, true-to-scale model of one product built from primitives: always "vereinfacht · laut Claude"."""

    known: bool
    size_mm: Vec3 | None
    parts: list[ShapePart] = Field(max_length=16)


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
    joints: list[tuple[float, float]] = Field(default_factory=list)  # hands only: the visible joints, in pixels


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
    confirmed: bool = False  # the person picked this candidate: certain because they said so

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
    faces: list[tuple[float, float, float, float]] = Field(default_factory=list)  # normalized, the card avoids them
    hands: list[WireTrack] = Field(default_factory=list)  # confirmed hands; polygon is the outline to draw


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
    confirmed: bool = False  # the person picked this candidate in the sidebar (sub-project 3)
    previous_id: int | None = None  # the tracker's old number for this same object (spec §11): nothing new to say

    @classmethod
    def from_belief(cls, track_id: int, status: Status, b: BeliefState, previous_id: int | None = None
                    ) -> IdentityMsg:
        return cls(track_id=track_id, status=status, previous_id=previous_id, **b.model_dump())


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


class SceneItemWire(_Model):
    label: str
    box: tuple[float, float, float, float]  # normalized


class SceneMsg(_ServerMsg):
    """The frozen background: sent with calibrating=True when a calibration starts, with naming=True while Claude names
    the frozen scene, and once more with the final items."""

    type: Literal["scene"] = "scene"
    calibrating: bool
    naming: bool = False
    items: list[SceneItemWire]


ProfileStatus = Literal["loading", "ready", "unknown", "error"]


class ProfileMsg(_ServerMsg):
    """The product profile for one product name (sub-project 2); the browser shows it next to the card."""

    type: Literal["profile"] = "profile"
    product: str
    status: ProfileStatus
    summary: str
    facts: list[ProfileFact]
    released: str | None
    launch_price: str | None
    trivia: list[str]
    line: str  # what the voice says once: the summary when ready, else nothing

    @classmethod
    def of(cls, product: str, status: ProfileStatus, profile: ProductProfile | None, line: str = "") -> ProfileMsg:
        if profile is None:
            return cls(product=product, status=status, summary="", facts=[], released=None, launch_price=None,
                       trivia=[], line=line)
        return cls(product=product, status=status, summary=profile.summary, facts=profile.facts,
                   released=profile.released, launch_price=profile.launch_price, trivia=profile.trivia, line=line)


class ShapeMsg(_ServerMsg):
    """The hologram of one product name (sub-project 3); the browser shows it in the sidebar entry of that name."""

    type: Literal["shape"] = "shape"
    product: str
    status: ProfileStatus
    size_mm: Vec3 | None
    parts: list[ShapePart]

    @classmethod
    def of(cls, product: str, status: ProfileStatus, shape: ProductShape | None) -> ShapeMsg:
        if shape is None:
            return cls(product=product, status=status, size_mm=None, parts=[])
        return cls(product=product, status=status, size_mm=shape.size_mm, parts=shape.parts)


ServerMsg = Annotated[TracksMsg | IdentityMsg | TelemetryMsg | NoticeMsg | SceneMsg | ProfileMsg | ShapeMsg,
                      Field(discriminator="type")]


class FocusMsg(_Model):
    type: Literal["focus"] = "focus"
    track_id: int | None


class RecheckMsg(_Model):
    type: Literal["recheck"] = "recheck"
    track_id: int


class RecalibrateMsg(_Model):
    type: Literal["recalibrate"] = "recalibrate"


class ConfirmMsg(_Model):
    """The person picks the right candidate of an entry: that object is certain, by their word (sub-project 3)."""

    type: Literal["confirm"] = "confirm"
    track_id: int
    name: str


ClientMsg = Annotated[FocusMsg | RecheckMsg | RecalibrateMsg | ConfirmMsg, Field(discriminator="type")]
_client_messages: TypeAdapter[FocusMsg | RecheckMsg | RecalibrateMsg | ConfirmMsg] = TypeAdapter(ClientMsg)


def parse_client_message(text: str) -> FocusMsg | RecheckMsg | RecalibrateMsg | ConfirmMsg | None:
    """A browser message, or None for anything malformed or unknown."""
    try:
        return _client_messages.validate_json(text)
    except ValidationError:
        return None


def protocol_examples() -> list[dict]:
    """One example of every server message, written to tests/fixtures/protocol-examples.json."""
    track = WireTrack(id=17, box=(0.1, 0.2, 0.3, 0.6), polygon=[(0.1, 0.2), (0.3, 0.2), (0.3, 0.6)],
                      label="cell phone", score=0.91)
    hand = WireTrack(id=-101, box=(0.2, 0.4, 0.35, 0.7), polygon=[(0.2, 0.4), (0.35, 0.45), (0.3, 0.7)],
                     label="hand", score=1.0)
    messages: list[_ServerMsg] = [
        TracksMsg(ts=1.0, seq=1, frame_id=42, w=1280, h=720, focus_id=17, tracks=[track], hands=[hand]),
        IdentityMsg(ts=1.1, seq=2, track_id=17, status="ready", level=Level.LIKELY, display_name="Apple iPhone 14",
                    candidates=[RankedCandidate(name="Apple iPhone 14", share=0.67),
                                RankedCandidate(name="Apple iPhone 13", share=0.33)],
                    evidence=["Apple-Logo", "2 Kameras"], view_request=None, final=False, calls_used=1,
                    line="Das ist wahrscheinlich Apple iPhone 14."),
        TelemetryMsg(ts=1.2, seq=3, fps_processed=11.5, frames_dropped=3, det_ms=24.0, id_ms_last=2800.0,
                     sharpness_focus=142.0, calls_session=1, cost_session_usd=0.02, model="claude-opus-5-5",
                     mode="hybrid", language="de"),
        NoticeMsg(ts=1.3, seq=4, level="warn", text="Kein API-Key: nur lokale Erkennung."),
        SceneMsg(ts=1.4, seq=5, calibrating=False, naming=False,
                 items=[SceneItemWire(label="Pendelleuchte", box=(0.4, 0.02, 0.55, 0.25))]),
        ProfileMsg.of("Apple iPhone 14", "ready", ProductProfile(
            known=True, summary="Ein Smartphone von Apple aus dem Jahr 2022.",
            facts=[ProfileFact(label="Chip", value="A15 Bionic"), ProfileFact(label="Display", value="6,1 Zoll OLED")],
            released="September 2022", launch_price="999 € (128 GB)", trivia=["Erstes iPhone mit Unfallerkennung."]),
            line="Ein Smartphone von Apple aus dem Jahr 2022.").model_copy(update={"ts": 1.5, "seq": 6}),
        ShapeMsg.of("Apple iPhone 14", "ready", ProductShape(known=True, size_mm=(71.5, 146.7, 7.8), parts=[
            ShapePart(name="Gehäuse", shape="rounded_box", size_mm=(71.5, 146.7, 7.8), position_mm=(0, 0, 0),
                      rotation_deg=(0, 0, 0), color="#9fc4e8", radius_mm=10.0),
            ShapePart(name="Kameralinse", shape="cylinder", size_mm=(12, 2, 12), position_mm=(-22, 60, -4.5),
                      rotation_deg=(90, 0, 0), color="#1b1b1f")])).model_copy(update={"ts": 1.6, "seq": 7}),
    ]
    return [m.model_dump(mode="json") for m in messages]
