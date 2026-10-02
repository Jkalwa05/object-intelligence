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

export function formatSize(size: Vec3 | null, lang: Lang): string {
  if (!size) return "";
  const locale = lang === "de" ? "de-DE" : "en-US";
  return `${size.map((v) => v.toLocaleString(locale, { maximumFractionDigits: 1 })).join(" × ")} mm`;
}

// How far the camera stands back so that an object of this size fits into its field of view, with a little margin.
export function fitDistance(size: Vec3, fovDegrees: number): number {
  const reach = Math.max(1, Math.hypot(...size) / 2);
  return (reach / Math.sin(radians(fovDegrees) / 2)) * 1.1;
}

export function millimetres(value: number, lang: Lang): string {
  return value.toLocaleString(lang === "de" ? "de-DE" : "en-US", { maximumFractionDigits: 1 });
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
