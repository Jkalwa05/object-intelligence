// Server and browser messages, field for field like oi/contracts.py (contract version 1).
// tests/fixtures/protocol-examples.json is written by Python and checked here, so both sides stay in sync.

export type Lang = "de" | "en";
export type Level = "certain" | "likely" | "unsure" | "category_only";
export type Status = "analysing" | "ready" | "error" | "paused";
export type Box = [number, number, number, number];

export interface WireTrack {
  id: number;
  box: Box; // x1, y1, x2, y2 normalized to 0..1
  polygon: [number, number][];
  label: string;
  score: number;
}

export interface TracksMsg {
  type: "tracks";
  ts: number;
  seq: number;
  frame_id: number;
  w: number;
  h: number;
  focus_id: number | null;
  tracks: WireTrack[];
  faces: Box[]; // normalized face boxes: the info card never covers them
  hands: WireTrack[]; // confirmed hands; polygon is the outline to draw
}

export interface RankedCandidate {
  name: string;
  share: number;
}

export interface NextView {
  view: string;
  reason: string;
}

export interface IdentityMsg {
  type: "identity";
  ts: number;
  seq: number;
  track_id: number;
  status: Status;
  level: Level | null;
  display_name: string;
  candidates: RankedCandidate[];
  evidence: string[];
  view_request: NextView | null;
  final: boolean;
  calls_used: number;
  line: string;
  confirmed: boolean; // the person picked this candidate: certain by their word
  previous_id: number | null; // the tracker's old number for this same object: nothing new to say
}

export interface TelemetryMsg {
  type: "telemetry";
  ts: number;
  seq: number;
  fps_processed: number;
  frames_dropped: number;
  det_ms: number;
  id_ms_last: number | null;
  sharpness_focus: number | null;
  calls_session: number;
  cost_session_usd: number;
  model: string;
  gate_focus: string | null; // the quality check the focus crop fails right now, or null
  mode: "hybrid" | "lokal";
  language: Lang;
}

export interface NoticeMsg {
  type: "notice";
  ts: number;
  seq: number;
  level: "info" | "warn" | "error";
  text: string;
}

export interface SceneItem {
  label: string;
  box: Box; // normalized, frozen after the calibration
}

export interface SceneMsg {
  type: "scene";
  ts: number;
  seq: number;
  calibrating: boolean;
  naming: boolean; // Claude is naming the frozen scene right now
  items: SceneItem[];
}

export interface ProfileFact {
  label: string;
  value: string;
}

// Sub-project 2: Claude's own knowledge about one product, no sources, always shown as "laut Claude".
export interface ProfileMsg {
  type: "profile";
  ts: number;
  seq: number;
  product: string; // the display name the profile belongs to
  status: "loading" | "ready" | "unknown" | "error";
  summary: string;
  facts: ProfileFact[];
  released: string | null;
  launch_price: string | null;
  trivia: string[];
  line: string; // what the voice says once
}

// Sub-project 3: one primitive of a hologram, in millimetres around the object's centre, y pointing up.
export interface Source {
  title: string;
  url: string;
}

// Sub-project 4: a spoken question about one object and Claude's answer, shown in that object's entry.
export interface QuestionMsg {
  type: "question";
  ts: number;
  seq: number;
  product: string; // the name of the sidebar entry
  qid: number;
  status: "transcribing" | "thinking" | "ready" | "empty" | "error";
  question: string;
  answer: string;
  sources: Source[];
  line: string; // what the voice reads: the answer
}

// Sub-project 6: the precision model, researched, written in OpenSCAD, compiled and checked.
export type MeasureKind = "drawing" | "datasheet" | "estimate";

export interface Measure {
  label: string;
  value_mm: number;
  source: number | null; // index into MeasureSheet.sources
  kind: MeasureKind;
}

export type PhotoView = "front" | "back" | "side-front-left" | "side-front-right" | "top";

// A product photo the research found (sub-project 7).
export interface PhotoRef {
  url: string;
  view: PhotoView;
}

export interface MeasureSheet {
  size_mm: [number, number, number] | null; // width (x), height (y), depth (z)
  size_source: number | null;
  measures: Measure[];
  features: string[];
  sources: Source[];
  drawing: { url: string; find: string } | null;
  photos: PhotoRef[];
}

// One part as measured on the drawing and the photos, in mm from the centre of the product (sub-project 7).
export interface MeasuredPart {
  name: string;
  x: [number, number] | null; // left to right
  y: [number, number] | null; // bottom to top
  z: [number, number] | null; // back to front
  views: number;
}

export interface ModelPart {
  name: string;
  color: string;
  file: string; // "part-01.stl", served at /models/<slug>/<file>
  min_mm: [number, number, number];
  max_mm: [number, number, number];
  triangles: number;
}

export interface ModelManifest {
  model: string;
  slug: string;
  parts: ModelPart[];
  size_mm: [number, number, number];
  sheet: MeasureSheet;
  drawing_pages: number[];
  notes: string;
  verdict: "good" | "fix" | "unchecked";
  rounds: number;
  cost_usd: number;
  created: string;
  kept: boolean; // Jonas keeps it: shown again instead of being built anew (sub-project 7)
  part_map: MeasuredPart[];
}

export type ModelStatus = "queued" | "researching" | "drawing" | "measuring" | "modeling" | "building" | "checking"
  | "ready" | "failed" | "limit";

export interface ModelMsg {
  type: "model";
  ts: number;
  seq: number;
  product: string; // the name of the sidebar entry
  status: ModelStatus;
  round: number;
  manifest: ModelManifest | null; // only when ready
}

export type ServerMsg = TracksMsg | IdentityMsg | TelemetryMsg | NoticeMsg | SceneMsg | ProfileMsg | ModelMsg
  | QuestionMsg;

export interface FocusMsg {
  type: "focus";
  track_id: number | null;
}

export interface RecheckMsg {
  type: "recheck";
  track_id: number;
}

export interface RecalibrateMsg {
  type: "recalibrate";
}

// A question spoken while the space bar was held (sub-project 4): 16-bit PCM in base64 and the target entry.
export interface AskMsg {
  type: "ask";
  track_id: number | null;
  name: string | null;
  rate: number;
  audio: string;
}

// „Behalten“: the shown precision model is kept and comes again; false takes that back (sub-project 7).
export interface KeepMsg {
  type: "keep";
  model: string; // manifest.model
  kept: boolean;
}

// „Neu bauen“ after a failed precision model (sub-project 6).
export interface RebuildMsg {
  type: "rebuild";
  name: string;
}

// The person picks the right candidate of a sidebar entry (sub-project 3).
export interface ConfirmMsg {
  type: "confirm";
  track_id: number;
  name: string;
}

const REQUIRED: Record<ServerMsg["type"], string[]> = {
  tracks: ["frame_id", "w", "h", "focus_id", "tracks", "faces", "hands"],
  identity: ["track_id", "status", "level", "display_name", "candidates", "evidence", "view_request", "final",
    "calls_used", "line", "confirmed", "previous_id"],
  telemetry: ["fps_processed", "frames_dropped", "det_ms", "id_ms_last", "sharpness_focus", "calls_session",
    "cost_session_usd", "model", "gate_focus", "mode", "language"],
  notice: ["level", "text"],
  scene: ["calibrating", "naming", "items"],
  profile: ["product", "status", "summary", "facts", "released", "launch_price", "trivia", "line"],
  model: ["product", "status", "round", "manifest"],
  question: ["product", "qid", "status", "question", "answer", "sources", "line"],
};

export function isServerMsg(x: unknown): x is ServerMsg {
  if (typeof x !== "object" || x === null) return false;
  const message = x as Record<string, unknown>;
  const required = REQUIRED[message.type as ServerMsg["type"]];
  if (!required || typeof message.ts !== "number" || typeof message.seq !== "number") return false;
  return required.every((key) => key in message);
}
