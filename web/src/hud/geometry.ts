// From normalized frame coordinates (0..1) to pixels on screen, for a video shown with object-fit: contain.

import type { Box } from "../protocol";

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

// Where the video picture lies inside its element (black bars left/right or top/bottom).
export function videoContentRect(view: { w: number; h: number }, video: { w: number; h: number }): Rect {
  const scale = Math.min(view.w / video.w, view.h / video.h);
  const w = video.w * scale;
  const h = video.h * scale;
  return { x: (view.w - w) / 2, y: (view.h - h) / 2, w, h };
}

export function toScreen(box: Box, content: Rect, mirrored: boolean): Rect {
  const [x1, y1, x2, y2] = box;
  const left = x1 * content.w;
  const right = x2 * content.w; // edges first, then the width: exact where the edges are exact
  const top = y1 * content.h;
  const bottom = y2 * content.h;
  return { x: content.x + (mirrored ? content.w - right : left), y: content.y + top, w: right - left, h: bottom - top };
}

export function toScreenPoints(poly: [number, number][], content: Rect, mirrored: boolean): [number, number][] {
  return poly.map(([x, y]) => [content.x + (mirrored ? 1 - x : x) * content.w, content.y + y * content.h]);
}

// The smallest box that contains the point, so a click on an object in front of a larger one picks the front one.
export function hitTest(p: { x: number; y: number }, boxes: { id: number; rect: Rect }[]): number | null {
  const hits = boxes.filter(({ rect: r }) => p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h);
  if (hits.length === 0) return null;
  return hits.reduce((a, b) => (b.rect.w * b.rect.h < a.rect.w * a.rect.h ? b : a)).id;
}
