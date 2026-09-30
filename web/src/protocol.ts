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
  hint: string | null;
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

export type ServerMsg = TracksMsg | IdentityMsg | TelemetryMsg | NoticeMsg | SceneMsg;

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

const REQUIRED: Record<ServerMsg["type"], string[]> = {
  tracks: ["frame_id", "w", "h", "focus_id", "tracks", "hint", "faces", "hands"],
  identity: ["track_id", "status", "level", "display_name", "candidates", "evidence", "view_request", "final",
    "calls_used", "line", "previous_id"],
  telemetry: ["fps_processed", "frames_dropped", "det_ms", "id_ms_last", "sharpness_focus", "calls_session",
    "cost_session_usd", "model", "gate_focus", "mode", "language"],
  notice: ["level", "text"],
  scene: ["calibrating", "naming", "items"],
};

export function isServerMsg(x: unknown): x is ServerMsg {
  if (typeof x !== "object" || x === null) return false;
  const message = x as Record<string, unknown>;
  const required = REQUIRED[message.type as ServerMsg["type"]];
  if (!required || typeof message.ts !== "number" || typeof message.seq !== "number") return false;
  return required.every((key) => key in message);
}
