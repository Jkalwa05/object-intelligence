import { expect, test } from "vitest";
import type { IdentityMsg, NoticeMsg, TracksMsg } from "./protocol";
import { applyServerMessage, initialState } from "./store";

const tracks = (seq: number): TracksMsg =>
  ({ type: "tracks", ts: 0, seq, frame_id: seq, w: 1280, h: 720, focus_id: 1, tracks: [], hint: null, faces: [] });
const identity = (trackId: number, line: string): IdentityMsg => ({
  type: "identity", ts: 0, seq: 0, track_id: trackId, status: "ready", level: "likely", display_name: "X",
  candidates: [], evidence: [], view_request: null, final: false, calls_used: 1, line,
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

test("the focus hint is shown on screen too", async () => {
  const { focusHint } = await import("./store");
  expect(focusHint(initialState)).toBeNull();
  expect(focusHint(applyServerMessage(initialState, { ...tracks(1), hint: "Halt es bitte ruhig." }))).toBe("Halt es bitte ruhig.");
});
