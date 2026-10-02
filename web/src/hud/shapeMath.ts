// Hologram maths (sub-projects 3, 5 and 6): sizes, camera distance and name tags of the CAD model's parts.

import type { Lang, ModelPart } from "../protocol";

export type Vec3 = [number, number, number];

const radians = (degrees: number) => (degrees * Math.PI) / 180;

export function partSize(p: ModelPart): Vec3 {
  return [0, 1, 2].map((i) => p.max_mm[i] - p.min_mm[i]) as Vec3;
}

export function partCenter(p: ModelPart): Vec3 {
  return [0, 1, 2].map((i) => (p.min_mm[i] + p.max_mm[i]) / 2) as Vec3;
}

// Where the k-th of `count` large shells (frame, display, back glass) puts its dot: around the rim of its front face,
// the first at the lower edge, so that their name tags do not all start from one point.
export function rimPoint(p: ModelPart, k: number, count: number): Vec3 {
  const [w, h] = partSize(p);
  const [cx, cy] = partCenter(p);
  const angle = -Math.PI / 2 + (k * 2 * Math.PI) / Math.max(4, count);
  const clean = (v: number) => Math.round(v * 1e9) / 1e9;
  return [clean(cx + (Math.cos(angle) * w) / 2), clean(cy + (Math.sin(angle) * h) / 2), p.max_mm[2]];
}

export function formatSize(size: Vec3 | null, lang: Lang): string {
  return size ? `${size.map((v) => millimetres(v, lang)).join(" × ")} mm` : "";
}

// How far the camera stands back so that an object of this size fits into its field of view, with a little margin.
export function fitDistance(size: Vec3, fovDegrees: number): number {
  const reach = Math.max(1, Math.hypot(...size) / 2);
  return (reach / Math.sin(radians(fovDegrees) / 2)) * 1.1;
}

// Tenths of a millimetre, hundredths below 1 mm (a display film is 0,04 mm, not 0).
export function millimetres(value: number, lang: Lang): string {
  return value.toLocaleString(lang === "de" ? "de-DE" : "en-US", { maximumFractionDigits: Math.abs(value) < 1 ? 2 : 1 });
}

export interface Rect {
  x: number; // left
  y: number; // top
  w: number;
  h: number;
}

// How far each label has to move down so that no two cover each other or one of the `fixed` boxes (at least `gap`
// pixels apart), placed from top to bottom so that their order stays the order of their parts.
export function spread(rects: Rect[], gap: number, fixed: Rect[] = []): number[] {
  const order = rects.map((_, i) => i).sort((a, b) => rects[a].y - rects[b].y || a - b);
  const placed: Rect[] = [...fixed];
  const moves = rects.map(() => 0);
  for (const i of order) {
    const r = { ...rects[i] };
    for (;;) {
      const hit = placed.filter((q) => r.x < q.x + q.w + gap && q.x < r.x + r.w + gap
        && r.y < q.y + q.h + gap && q.y < r.y + r.h + gap);
      if (hit.length === 0) break;
      r.y = Math.max(...hit.map((q) => q.y + q.h)) + gap;
    }
    moves[i] = r.y - rects[i].y;
    placed.push(r);
  }
  return moves;
}
