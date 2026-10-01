import { expect, test } from "vitest";
import type { IdentityMsg, NoticeMsg, TracksMsg } from "./protocol";
import { applyServerMessage, initialState } from "./store";

const tracks = (seq: number): TracksMsg =>
  ({ type: "tracks", ts: 0, seq, frame_id: seq, w: 1280, h: 720, focus_id: 1, tracks: [], faces: [], hands: [] });
const identity = (trackId: number, line: string): IdentityMsg => ({
  type: "identity", ts: 0, seq: 0, track_id: trackId, status: "ready", level: "likely", display_name: "X",
  candidates: [], evidence: [], view_request: null, final: false, calls_used: 1, line, previous_id: null,
});
const notice = (text: string): NoticeMsg => ({ type: "notice", ts: 0, seq: 0, level: "info", text });

test("reducer: tracks replace, identities per track, three newest notices", () => {
  let s = applyServerMessage(initialState, tracks(1));
  s = applyServerMessage(s, tracks(2));
  expect(s.tracks?.seq).toBe(2);
  s = applyServerMessage(s, identity(1, "a"));
  s = applyServerMessage(s, identity(2, "b"));
  s = applyServerMessage(s, identity(1, "c"));
  expect(s.identities[1].line).toBe("c");
  expect(s.identities[2].line).toBe("b");
  for (const text of ["1", "2", "3", "4"]) s = applyServerMessage(s, notice(text));
  expect(s.notices.map((n) => n.text)).toEqual(["2", "3", "4"]);
  expect(initialState.tracks).toBeNull(); // pure: the initial state is untouched
});

test("closing clears the boxes; reopening forgets old identities and notices", async () => {
  const { applyConnection } = await import("./store");
  let s = applyServerMessage(initialState, tracks(1));
  s = applyServerMessage(s, identity(1, "Das ist Apple iPhone 14."));
  s = applyServerMessage(s, notice("alt"));
  s = applyConnection(s, "closed");
  expect(s.tracks).toBeNull();
  expect(s.connection).toBe("closed");
  s = applyConnection(s, "open");
  expect(s.identities).toEqual({});
  expect(s.notices).toEqual([]);
  expect(s.connection).toBe("open");
});

test("the frozen scene is kept until a new connection calibrates again", async () => {
  const { applyConnection } = await import("./store");
  const scene = { type: "scene" as const, ts: 0, seq: 1, calibrating: false, naming: false,
    items: [{ label: "lamp", box: [0.4, 0.02, 0.55, 0.25] as [number, number, number, number] }] };
  let s = applyServerMessage(initialState, scene);
  expect(s.scene?.items[0].label).toBe("lamp");
  s = applyConnection(s, "open");
  expect(s.scene).toBeNull();
});

test("the scene banner follows calibration, then naming, then nothing", async () => {
  const { sceneBanner } = await import("./store");
  const scene = (calibrating: boolean, naming: boolean) =>
    applyServerMessage(initialState, { type: "scene", ts: 0, seq: 1, calibrating, naming, items: [] });
  expect(sceneBanner(initialState)).toBeNull();
  expect(sceneBanner(scene(true, false))).toBe("calibrating");
  expect(sceneBanner(scene(false, true))).toBe("naming");
  expect(sceneBanner(scene(false, false))).toBeNull();
});

test("the profile panel shows the focus product's own profile while it is likely or certain", async () => {
  const { focusProfile } = await import("./store");
  const profile = { type: "profile" as const, ts: 0, seq: 0, product: "X", status: "ready" as const, summary: "S",
    facts: [], released: null, launch_price: null, trivia: [], line: "S" };
  let s = applyServerMessage(applyServerMessage(initialState, tracks(1)), identity(1, "Das ist wahrscheinlich X."));
  expect(focusProfile(s)).toBeNull();
  s = applyServerMessage(s, profile);
  expect(focusProfile(s)?.summary).toBe("S");
  expect(focusProfile(applyServerMessage(s, { ...identity(1, "X oder Y?"), level: "unsure" }))).toBeNull();
  expect(focusProfile(applyServerMessage(s, { ...identity(1, "Das ist Z."), display_name: "Z" }))).toBeNull();
});

test("the voice stays off until M is pressed", () => expect(initialState.muted).toBe(true));
