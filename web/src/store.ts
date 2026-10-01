import { create } from "zustand";
import type { ConnectionStatus } from "./net/socket";
import type { IdentityMsg, NoticeMsg, ProfileMsg, QuestionMsg, SceneMsg, ServerMsg, ShapeMsg, TelemetryMsg, TracksMsg }
  from "./protocol";

export const MAX_ENTRIES = 8;

export interface HudState {
  tracks: TracksMsg | null;
  scene: SceneMsg | null;
  identities: Record<number, IdentityMsg>;
  profiles: Record<string, ProfileMsg>; // by product name
  shapes: Record<string, ShapeMsg>; // by product name
  named: Record<string, IdentityMsg>; // the latest identity of every card name, for the sidebar
  recent: string[]; // card names in the sidebar, newest first
  open: string[]; // sidebar entries opened by hand
  fullscreen: string | null; // the entry whose hologram fills the screen
  questions: Record<string, QuestionMsg[]>; // spoken questions by entry name, oldest first
  listening: boolean; // the space bar is held: the microphone is open
  micError: string | null;
  flash: string | null; // a short message for the person's own action
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
  profiles: {},
  shapes: {},
  named: {},
  recent: [],
  open: [],
  fullscreen: null,
  questions: {},
  listening: false,
  micError: null,
  flash: null,
  telemetry: null,
  notices: [],
  connection: "closed",
  mirrored: true,
  muted: true, // the voice stays off until M is pressed
  showTelemetry: false,
  cameraError: null,
};

const MAX_NOTICES = 3;

export function applyServerMessage(s: HudState, m: ServerMsg): HudState {
  switch (m.type) {
    case "tracks":
      return { ...s, tracks: m };
    case "identity":
      return remember({ ...s, identities: { ...s.identities, [m.track_id]: m } }, m, s.identities[m.track_id]);
    case "telemetry":
      return { ...s, telemetry: m };
    case "notice":
      return { ...s, notices: [...s.notices, m].slice(-MAX_NOTICES) };
    case "scene":
      return { ...s, scene: m };
    case "profile":
      return { ...s, profiles: { ...s.profiles, [m.product]: m } };
    case "shape":
      return { ...s, shapes: { ...s.shapes, [m.product]: m } };
    case "question": {
      const earlier = s.questions[m.product] ?? [];
      const list = earlier.some((q) => q.qid === m.qid) ? earlier.map((q) => (q.qid === m.qid ? m : q)) : [...earlier, m];
      return { ...s, questions: { ...s.questions, [m.product]: list } };
    }
  }
}

// A new connection means a fresh server pipeline whose track IDs start again at 1: old identities must not stick
// to new objects, and boxes of a closed connection must not stay frozen on screen.
export function applyConnection(s: HudState, connection: ConnectionStatus): HudState {
  if (connection === "open") {
    return { ...s, connection, identities: {}, notices: [], scene: null, profiles: {}, shapes: {}, named: {}, recent: [],
      open: [], questions: {} };
  }
  return { ...s, connection, tracks: null };
}

// Which scene banner to show: the calibration, then Claude naming the background, then none.
export function sceneBanner(s: HudState): "calibrating" | "naming" | null {
  if (s.scene?.calibrating) return "calibrating";
  return s.scene?.naming ? "naming" : null;
}

// Every identified object stays pinned in the sidebar under its card name, the newest on top. A new name for the same
// object (a confirmed colour) replaces its entry instead of adding a second one.
function remember(s: HudState, m: IdentityMsg, before: IdentityMsg | undefined): HudState {
  if (m.level === null) return s;
  const renamed = before?.level != null && before.display_name !== m.display_name ? before.display_name : null;
  const recent = [m.display_name, ...s.recent.filter((n) => n !== m.display_name && n !== renamed)].slice(0, MAX_ENTRIES);
  return { ...s, named: { ...s.named, [m.display_name]: m }, recent, open: s.open.filter((n) => recent.includes(n)) };
}

export interface SidebarEntry {
  name: string;
  identity: IdentityMsg;
  active: boolean; // the object in the hand right now
  expanded: boolean; // active, or opened by hand
}

type SidebarSlice = Pick<HudState, "identities" | "named" | "recent" | "open">;

// The sidebar: the held object first and expanded (also while it is still being analysed), the others collapsed.
export function sidebarEntries(s: HudState): SidebarEntry[] {
  return entriesFor(s, s.tracks?.focus_id ?? null);
}

export function entriesFor(s: SidebarSlice, focusId: number | null): SidebarEntry[] {
  const held = focusId === null ? undefined : s.identities[focusId];
  const entries: SidebarEntry[] = [];
  if (held) entries.push({ name: held.display_name, identity: held, active: true, expanded: true });
  for (const name of s.recent) {
    if (held && name === held.display_name) continue;
    const identity = s.named[name];
    if (identity) entries.push({ name, identity, active: false, expanded: s.open.includes(name) });
  }
  return entries;
}

export function toggleEntry<S extends Pick<HudState, "open">>(s: S, name: string): S {
  return { ...s, open: s.open.includes(name) ? s.open.filter((n) => n !== name) : [...s.open, name] };
}

const NO_QUESTIONS: QuestionMsg[] = [];

// What the full-screen hologram shows: it does not depend on its entry being expanded (you put the object down to
// look at the screen), only on the entry still being in the sidebar with a finished hologram.
export function fullscreenView(s: Pick<HudState, "fullscreen" | "named" | "recent" | "shapes" | "profiles">):
  { identity: IdentityMsg; shape: ShapeMsg; profile?: ProfileMsg } | null {
  const name = s.fullscreen;
  if (name === null || !s.recent.includes(name)) return null;
  const identity = s.named[name], shape = s.shapes[name];
  if (!identity || shape?.status !== "ready") return null;
  return { identity, shape, profile: s.profiles[name] };
}

export function questionsFor(s: Pick<HudState, "questions">, name: string): QuestionMsg[] {
  return s.questions[name] ?? NO_QUESTIONS;
}

// Whom a spoken question is about: the object in the hand, else the entry opened last, else the newest entry.
export function askTarget(s: HudState): { track_id: number; name: string } | null {
  const id = s.tracks?.focus_id;
  const held = id == null ? undefined : s.identities[id];
  if (held) return { track_id: held.track_id, name: held.display_name };
  const name = s.open.at(-1) ?? s.recent[0];
  const identity = name === undefined ? undefined : s.named[name];
  return identity ? { track_id: identity.track_id, name } : null;
}

// The profile next to the card: the focus product's own one, only while it is likely or certain.
export function focusProfile(s: HudState): ProfileMsg | null {
  const id = s.tracks?.focus_id;
  const identity = id == null ? undefined : s.identities[id];
  if (!identity || (identity.level !== "likely" && identity.level !== "certain")) return null;
  return s.profiles[identity.display_name] ?? null;
}

interface HudActions {
  receive(m: ServerMsg): void;
  toggleMirror(): void;
  toggleMute(): void;
  toggleTelemetry(): void;
  toggleEntry(name: string): void;
  setFullscreen(name: string | null): void;
  setListening(listening: boolean): void;
  setMicError(error: string | null): void;
  setFlash(text: string | null): void;
  setConnection(c: ConnectionStatus): void;
  setCameraError(e: string | null): void;
}

export const useHud = create<HudState & HudActions>()((set) => ({
  ...initialState,
  receive: (m) => set((s) => applyServerMessage(s, m)),
  toggleMirror: () => set((s) => ({ mirrored: !s.mirrored })),
  toggleMute: () => set((s) => ({ muted: !s.muted })),
  toggleTelemetry: () => set((s) => ({ showTelemetry: !s.showTelemetry })),
  toggleEntry: (name) => set((s) => toggleEntry(s, name)),
  setFullscreen: (fullscreen) => set({ fullscreen }),
  setListening: (listening) => set({ listening }),
  setMicError: (micError) => set({ micError }),
  setFlash: (flash) => set({ flash }),
  setConnection: (connection) => set((s) => applyConnection(s, connection)),
  setCameraError: (cameraError) => set({ cameraError }),
}));
