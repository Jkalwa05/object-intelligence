import { expect, test } from "vitest";
import { downsample, toPcmBase64 } from "./recorder";

test("audio is brought to 16 kHz for Whisper", () => {
  const second = new Float32Array(48000).fill(0.5);
  const out = downsample(second, 48000);
  expect(out.length).toBe(16000);
  expect(out[100]).toBeCloseTo(0.5);
  expect(downsample(new Float32Array(16000), 16000).length).toBe(16000);
});

test("samples travel as 16-bit PCM in base64, clipped", () => {
  const b64 = toPcmBase64(new Float32Array([0, 1, -1, 0.5, 2]));
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  expect(Array.from(new Int16Array(bytes.buffer))).toEqual([0, 32767, -32767, 16384, 32767]);
});
