import { expect, test } from "vitest";
import { encodeFrame } from "./frame";

test("encodeFrame layout: big-endian header length, JSON header, JPEG bytes", () => {
  const header = { frame_id: 7, t_capture_ms: 1234.5, w: 1280, h: 720 };
  const buf = encodeFrame(header, new Uint8Array([0xff, 0xd8, 0xff]).buffer);
  const n = new DataView(buf).getUint32(0);
  expect(JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, n)))).toEqual(header);
  expect([...new Uint8Array(buf, 4 + n)]).toEqual([0xff, 0xd8, 0xff]);
});
