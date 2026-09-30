import { create } from "zustand";
import type { ConnectionStatus } from "./net/socket";
import type { IdentityMsg, NoticeMsg, ServerMsg, TelemetryMsg, TracksMsg } from "./protocol";

export interface HudState {
  tracks: TracksMsg | null;
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
  }
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
  setConnection: (connection) => set({ connection }),
  setCameraError: (cameraError) => set({ cameraError }),
}));
