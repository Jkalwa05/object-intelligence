import { describe, expect, test } from "vitest";
import type { IdentityMsg, ModelManifest, ModelMsg, NoticeMsg, TracksMsg } from "./protocol";
import { applyServerMessage, initialState } from "./store";

const tracks = (seq: number): TracksMsg =>
  ({ type: "tracks", ts: 0, seq, frame_id: seq, w: 1280, h: 720, focus_id: 1, tracks: [], faces: [], hands: [] });
const identity = (trackId: number, line: string): IdentityMsg => ({
  type: "identity", ts: 0, seq: 0, track_id: trackId, status: "ready", level: "likely", display_name: "X",
  candidates: [], evidence: [], view_request: null, final: false, calls_used: 1, line, confirmed: false,
  previous_id: null,
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

test("there is something to pick unless it is certain with one name, confirmed or still analysing", async () => {
  const { pickable } = await import("./store");
  const two = [{ name: "A", share: 0.6 }, { name: "B", share: 0.4 }];
  const unsure: IdentityMsg = { ...identity(1, ""), level: "unsure", candidates: two };
  expect(pickable(unsure)).toBe(true);
  expect(pickable({ ...unsure, level: "certain", candidates: [{ name: "A", share: 1 }] })).toBe(false);
  expect(pickable({ ...unsure, level: "certain" })).toBe(true); // two names: you may still correct it
  expect(pickable({ ...unsure, confirmed: true })).toBe(false);
  expect(pickable({ ...unsure, status: "analysing" })).toBe(false);
});

const manifest: ModelManifest = { model: "Ding", slug: "ding", parts: [], size_mm: [1, 2, 3],
  sheet: { size_mm: null, size_source: null, measures: [], features: [], sources: [], drawing: null, photos: [] },
  drawing_pages: [], notes: "", verdict: "good", rounds: 1, cost_usd: 0.9, created: "", kept: false, part_map: [],
  profile: [] };
const ready = (product: string): ModelMsg =>
  ({ type: "model", ts: 0, seq: 0, product, status: "ready", round: 1, manifest });

test("model messages are kept per entry, and the full screen needs a ready model", async () => {
  const { fullscreenView } = await import("./store");
  const working: ModelMsg = { type: "model", ts: 0, seq: 0, product: "Ding 1", status: "checking", round: 1,
    manifest: null };
  let s = applyServerMessage(initialState, { ...identity(1, "x"), display_name: "Ding 1", level: "certain" });
  s = { ...applyServerMessage(s, working), fullscreen: "Ding 1" };
  expect(s.models["Ding 1"]).toBe(working);
  expect(fullscreenView(s)).toBeNull(); // still being built
  s = applyServerMessage(s, ready("Ding 1"));
  expect(fullscreenView(s)?.model.manifest?.slug).toBe("ding");
  expect(applyServerMessage(s, ready("Ding 2")).models["Ding 1"]).toEqual(ready("Ding 1"));
});

test("full screen: a click on a part labels it on the model, one or several, and the labels go away together",
  async () => {
    const { toggleLabel, useHud } = await import("./store");
    expect(initialState.labelled).toEqual([]); // no labels at first
    const s = toggleLabel(toggleLabel(toggleLabel(initialState, 3), 0), 7);
    expect(s.labelled).toEqual([3, 0, 7]);
    expect(toggleLabel(s, 0).labelled).toEqual([3, 7]); // a second click takes the label away
    const hud = useHud.getState();
    hud.setFullscreen("Ding 1");
    hud.toggleLabel(2);
    hud.toggleLabel(5);
    expect(useHud.getState().labelled).toEqual([2, 5]);
    hud.clearLabels();
    expect(useHud.getState().labelled).toEqual([]); // the button takes all of them away
    hud.toggleLabel(1);
    hud.setFullscreen(null);
    expect(useHud.getState().labelled).toEqual([]); // the next full screen starts without labels
  });

describe("the sidebar", () => {
  const named = (trackId: number, name: string, level: "likely" | "unsure" | "certain" | null = "likely") =>
    ({ ...identity(trackId, `Das ist ${name}.`), display_name: name, level });
  const focus = (id: number | null) => ({ ...tracks(99), focus_id: id });

  test("every identified object gets a pinned entry, the newest on top, at most 8", async () => {
    const { sidebarEntries } = await import("./store");
    let s = initialState;
    for (let i = 1; i <= 10; i++) s = applyServerMessage(s, named(i, `Ding ${i}`));
    s = applyServerMessage(s, focus(null));
    expect(sidebarEntries(s).map((e) => e.name)).toEqual(
      ["Ding 10", "Ding 9", "Ding 8", "Ding 7", "Ding 6", "Ding 5", "Ding 4", "Ding 3"]);
    expect(sidebarEntries(s).every((e) => !e.active && !e.expanded)).toBe(true);
  });

  test("the full-screen hologram stays open when its entry folds up, and closes once its entry is gone", async () => {
    const { fullscreenView, sidebarEntries } = await import("./store");
    const model = ready("Ding 1");
    let s = applyServerMessage(applyServerMessage(initialState, named(1, "Ding 1")), model);
    s = { ...applyServerMessage(s, focus(1)), fullscreen: "Ding 1" };
    expect(fullscreenView(s)?.model).toBe(model);
    s = applyServerMessage(s, focus(null)); // the object is put down: its entry folds up
    expect(sidebarEntries(s)[0].expanded).toBe(false);
    expect(fullscreenView(s)?.identity.display_name).toBe("Ding 1");
    for (let i = 2; i <= 9; i++) s = applyServerMessage(s, named(i, `Ding ${i}`)); // pushed out of the sidebar
    expect(fullscreenView(s)).toBeNull();
  });

  test("only the held object is expanded; a click opens or closes another one", async () => {
    const { sidebarEntries, toggleEntry } = await import("./store");
    let s = applyServerMessage(applyServerMessage(initialState, named(1, "Lampe")), named(2, "iPhone"));
    s = applyServerMessage(s, focus(2));
    expect(sidebarEntries(s).map((e) => [e.name, e.active, e.expanded])).toEqual(
      [["iPhone", true, true], ["Lampe", false, false]]);
    s = toggleEntry(s, "Lampe");
    expect(sidebarEntries(s).find((e) => e.name === "Lampe")?.expanded).toBe(true);
    s = applyServerMessage(s, focus(null));  // the iPhone is put away: collapsed, still pinned
    expect(sidebarEntries(s).map((e) => [e.name, e.expanded])).toEqual([["iPhone", false], ["Lampe", true]]);
    expect(sidebarEntries(toggleEntry(s, "Lampe")).find((e) => e.name === "Lampe")?.expanded).toBe(false);
  });

  test("an object being analysed shows on top without entering the history", async () => {
    const { sidebarEntries } = await import("./store");
    let s = applyServerMessage(initialState, named(1, "Lampe"));
    s = applyServerMessage(applyServerMessage(s, { ...named(5, "gadget", null), status: "analysing" }), focus(5));
    expect(sidebarEntries(s).map((e) => [e.name, e.active])).toEqual([["gadget", true], ["Lampe", false]]);
    s = applyServerMessage(applyServerMessage(s, focus(null)), focus(null));
    expect(sidebarEntries(s).map((e) => e.name)).toEqual(["Lampe"]);
  });

  test("picking the right model merges the entries of the same phone", async () => {
    const { sidebarEntries } = await import("./store");
    let s = applyServerMessage(applyServerMessage(initialState, named(14, "Apple iPhone 13", "unsure")),
      named(198, "Apple iPhone 14", "unsure"));
    s = applyServerMessage(s, { ...named(14, "Apple iPhone 14", "certain"), confirmed: true });
    expect(sidebarEntries(s).map((e) => [e.name, e.identity.track_id, e.identity.confirmed])).toEqual(
      [["Apple iPhone 14", 14, true]]);
  });

  test("one object seen twice ends up as one entry when the server merges it", async () => {
    const { sidebarEntries } = await import("./store");
    let s = applyServerMessage(initialState, { ...named(1, "Schwarzes Gerät", null), level: "category_only" });
    s = applyServerMessage(s, named(2, "Sony DualShock 3"));
    // the merge: the old track takes the merged name first, then the object in the hand
    s = applyServerMessage(s, named(1, "Sony DualShock 3", "certain"));
    s = applyServerMessage(s, named(2, "Sony DualShock 3", "certain"));
    expect(sidebarEntries(s).map((e) => [e.name, e.identity.track_id])).toEqual([["Sony DualShock 3", 2]]);
  });

  test("a new name for the same object replaces its entry", async () => {
    const { sidebarEntries } = await import("./store");
    let s = applyServerMessage(initialState, named(1, "Apple iPhone 14"));
    s = applyServerMessage(s, named(1, "Apple iPhone 14, Blau"));
    expect(sidebarEntries(s).map((e) => e.name)).toEqual(["Apple iPhone 14, Blau"]);
  });
});

describe("questions", () => {
  const named = (trackId: number, name: string) =>
    ({ ...identity(trackId, `Das ist ${name}.`), display_name: name, level: "likely" as const });
  const focus = (id: number | null) => ({ ...tracks(99), focus_id: id });
  const question = (qid: number, status: "transcribing" | "thinking" | "ready", answer = "") => ({
    type: "question" as const, ts: 0, seq: qid, product: "Apple iPhone 14", qid, status, question: "Wie schwer?",
    answer, sources: [], line: answer });

  test("they collect under their entry and update by number", async () => {
    const { questionsFor } = await import("./store");
    let s = applyServerMessage(initialState, question(1, "transcribing"));
    s = applyServerMessage(applyServerMessage(s, question(1, "ready", "172 g")), question(2, "thinking"));
    expect(questionsFor(s, "Apple iPhone 14").map((q) => [q.qid, q.status])).toEqual([[1, "ready"], [2, "thinking"]]);
    expect(questionsFor(s, "Lampe")).toEqual([]);
  });

  test("a question goes to the object in the hand, else to the last opened entry", async () => {
    const { askTarget, toggleEntry } = await import("./store");
    let s = applyServerMessage(applyServerMessage(initialState, named(1, "Lampe")), named(2, "iPhone"));
    expect(askTarget(applyServerMessage(s, focus(2)))).toEqual({ track_id: 2, name: "iPhone" });
    s = toggleEntry(applyServerMessage(s, focus(null)), "Lampe");
    expect(askTarget(s)).toEqual({ track_id: 1, name: "Lampe" });
    expect(askTarget(initialState)).toBeNull();
  });
});
