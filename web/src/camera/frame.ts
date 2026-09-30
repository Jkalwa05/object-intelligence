// One camera frame as a binary WebSocket message: uint32 header length (big-endian) | JSON header | JPEG bytes.

export interface FrameHeader {
  frame_id: number;
  t_capture_ms: number;
  w: number;
  h: number;
}

export function encodeFrame(header: FrameHeader, jpeg: ArrayBuffer): ArrayBuffer {
  const head = new TextEncoder().encode(JSON.stringify(header));
  const out = new Uint8Array(4 + head.length + jpeg.byteLength);
  new DataView(out.buffer).setUint32(0, head.length); // DataView writes big-endian by default
  out.set(head, 4);
  out.set(new Uint8Array(jpeg), 4 + head.length);
  return out.buffer;
}
