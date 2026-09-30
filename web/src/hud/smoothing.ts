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

// Outlines (hands) glide the same way, point by point; a different number of points means a new shape: jump.
export function smoothPoints(prev: [number, number][], target: [number, number][], dtMs: number, tauMs = 80):
  [number, number][] {
  if (prev.length !== target.length) return target;
  const a = 1 - Math.exp(-dtMs / tauMs);
  return target.map(([x, y], i) => [prev[i][0] + (x - prev[i][0]) * a, prev[i][1] + (y - prev[i][1]) * a]);
}
