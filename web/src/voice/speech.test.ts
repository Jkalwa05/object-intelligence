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
  const result = (trackId: number, line: string) => ({ trackId, line });
  expect(gate.consider(result(1, "Das ist X."), 1, false)).toBe("Das ist X.");
  expect(gate.consider(result(1, "Das ist X."), 1, false)).toBeNull();
  expect(gate.consider(result(2, "Das ist Y."), 1, false)).toBeNull();
  expect(gate.consider(result(1, "Das ist Z."), 1, true)).toBeNull();
  expect(gate.consider(result(1, ""), 1, false)).toBeNull();
  expect(gate.consider(result(2, "Das ist Y."), 2, false)).toBe("Das ist Y.");
});

test("reset forgets what was spoken, for a fresh connection", () => {
  const gate = new SpeechGate();
  const line = { trackId: 1, line: "Das ist X." };
  expect(gate.consider(line, 1, false)).toBe("Das ist X.");
  gate.reset();
  expect(gate.consider(line, 1, false)).toBe("Das ist X.");
});

test("an object under a new tracker number does not repeat what was said", () => {
  const gate = new SpeechGate();
  const result = (trackId: number, line: string) => ({ trackId, line });
  expect(gate.consider(result(1, "Das ist X."), 1, false)).toBe("Das ist X.");
  gate.carry(1, 7);
  expect(gate.consider(result(7, "Das ist X."), 7, false)).toBeNull();
  expect(gate.consider(result(7, "Das ist sicher X."), 7, false)).toBe("Das ist sicher X.");
});

test("carrying keeps what the new number already said", () => {
  const gate = new SpeechGate();
  const result = (trackId: number, line: string) => ({ trackId, line });
  gate.consider(result(7, "Ich analysiere."), 7, false);
  gate.consider(result(1, "Das ist X."), 1, false);
  gate.carry(1, 7);
  expect(gate.consider(result(7, "Ich analysiere."), 7, false)).toBeNull();
  expect(gate.consider(result(7, "Das ist X."), 7, false)).toBeNull();
});
