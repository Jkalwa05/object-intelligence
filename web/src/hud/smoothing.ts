import type { Rect } from "./geometry";

// Boxes glide towards their newest position instead of jumping (exponential smoothing, time constant 80 ms).
export function smoothRect(prev: Rect, target: Rect, dtMs: number, tauMs = 80): Rect {
  const a = 1 - Math.exp(-dtMs / tauMs);
  return {
    x: prev.x + (target.x - prev.x) * a,
    y: prev.y + (target.y - prev.y) * a,
    w: prev.w + (target.w - prev.w) * a,
    h: prev.h + (target.h - prev.h) * a,
  };
}
