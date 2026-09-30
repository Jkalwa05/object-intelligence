import { readFileSync } from "node:fs";
import { expect, test } from "vitest";
import { isServerMsg } from "./protocol";

test("fixture messages are valid", () => {
  const url = new URL("../../tests/fixtures/protocol-examples.json", import.meta.url);
  const messages: unknown[] = JSON.parse(readFileSync(url, "utf8"));
  expect(messages.length).toBe(4);
  for (const message of messages) expect(isServerMsg(message)).toBe(true);
});

test("incomplete or unknown messages are rejected", () => {
  expect(isServerMsg({ type: "tracks" })).toBe(false);
  expect(isServerMsg({ type: "nope", ts: 1, seq: 1 })).toBe(false);
  expect(isServerMsg(null)).toBe(false);
  expect(isServerMsg("tracks")).toBe(false);
});
