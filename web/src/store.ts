import { create } from "zustand";
import type { ConnectionStatus } from "./net/socket";
import type { IdentityMsg, NoticeMsg, SceneMsg, ServerMsg, TelemetryMsg, TracksMsg } from "./protocol";

export interface HudState {
  tracks: TracksMsg | null;
  scene: SceneMsg | null;
  identities: Record<number, IdentityMsg>;
  telemetry: TelemetryMsg | null;
  notices: NoticeMsg[];
  connection: ConnectionStatus;
  mirrored: boolean;
  muted: boolean;
  showTelemetry: boolean;
  cameraError: string | null;
}

export const initialState: HudState = {
  tracks: null,
  scene: null,
  identities: {},
  telemetry: null,
  notices: [],
  connection: "closed",
  mirrored: true,
  muted: false,
  showTelemetry: false,
  cameraError: null,
};

const MAX_NOTICES = 3;

export function applyServerMessage(s: HudState, m: ServerMsg): HudState {
  switch (m.type) {
    case "tracks":
      return { ...s, tracks: m };
    case "identity":
      return { ...s, identities: { ...s.identities, [m.track_id]: m } };
    case "telemetry":
      return { ...s, telemetry: m };
    case "notice":
      return { ...s, notices: [...s.notices, m].slice(-MAX_NOTICES) };
    case "scene":
      return { ...s, scene: m };
  }
}

// A new connection means a fresh server pipeline whose track IDs start again at 1: old identities must not stick
// to new objects, and boxes of a closed connection must not stay frozen on screen.
export function applyConnection(s: HudState, connection: ConnectionStatus): HudState {
  if (connection === "open") return { ...s, connection, identities: {}, notices: [], scene: null };
  return { ...s, connection, tracks: null };
}

// Which scene banner to show: the calibration, then Claude naming the background, then none.
export function sceneBanner(s: HudState): "calibrating" | "naming" | null {
  if (s.scene?.calibrating) return "calibrating";
  return s.scene?.naming ? "naming" : null;
}

// The hint for the focus object, shown as a banner as well as spoken (the voice may be muted).
export function focusHint(s: HudState): string | null {
  return s.tracks?.hint ?? null;
}

interface HudActions {
  receive(m: ServerMsg): void;
  toggleMirror(): void;
  toggleMute(): void;
  toggleTelemetry(): void;
  setConnection(c: ConnectionStatus): void;
  setCameraError(e: string | null): void;
}

export const useHud = create<HudState & HudActions>()((set) => ({
  ...initialState,
  receive: (m) => set((s) => applyServerMessage(s, m)),
  toggleMirror: () => set((s) => ({ mirrored: !s.mirrored })),
  toggleMute: () => set((s) => ({ muted: !s.muted })),
  toggleTelemetry: () => set((s) => ({ showTelemetry: !s.showTelemetry })),
  setConnection: (connection) => set((s) => applyConnection(s, connection)),
  setCameraError: (cameraError) => set({ cameraError }),
}));
