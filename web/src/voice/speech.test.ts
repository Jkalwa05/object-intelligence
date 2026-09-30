import { expect, test } from "vitest";
import { SpeechGate, pickVoice } from "./speech";

test("pickVoice skips novelty voices and matches the language", () => {
  const voices = [{ name: "Zarvox", lang: "de-DE" }, { name: "Anna (Deutsch (Deutschland))", lang: "de-DE" },
    { name: "Samantha", lang: "en-US" }];
  expect(pickVoice(voices, "de")?.name).toMatch(/^Anna/);
  expect(pickVoice(voices, "en")?.name).toBe("Samantha");
  expect(pickVoice([{ name: "Bad News", lang: "en-US" }], "en")).toBeNull();
});

test("a result line is spoken once per track, only for the focus, never when muted", () => {
  const gate = new SpeechGate();
  const result = (trackId: number, line: string) => ({ trackId, line, kind: "result" as const });
  expect(gate.consider(result(1, "Das ist X."), 0, 1, false)).toBe("Das ist X.");
  expect(gate.consider(result(1, "Das ist X."), 100, 1, false)).toBeNull();
  expect(gate.consider(result(2, "Das ist Y."), 200, 1, false)).toBeNull();
  expect(gate.consider(result(1, "Das ist Z."), 300, 1, true)).toBeNull();
  expect(gate.consider(result(1, ""), 400, 1, false)).toBeNull();
  expect(gate.consider(result(2, "Das ist Y."), 500, 2, false)).toBe("Das ist Y.");
});

test("hints at most every 5 s", () => {
  const gate = new SpeechGate();
  const hint = { trackId: 1, line: "Halt es bitte ruhig.", kind: "hint" as const };
  expect(gate.consider(hint, 0, 1, false)).toBe("Halt es bitte ruhig.");
  expect(gate.consider(hint, 4000, 1, false)).toBeNull();
  expect(gate.consider(hint, 5000, 1, false)).toBe("Halt es bitte ruhig.");
});

test("reset forgets what was spoken, for a fresh connection", () => {
  const gate = new SpeechGate();
  const line = { trackId: 1, line: "Das ist X.", kind: "result" as const };
  expect(gate.consider(line, 0, 1, false)).toBe("Das ist X.");
  gate.reset();
  expect(gate.consider(line, 1, 1, false)).toBe("Das ist X.");
});
