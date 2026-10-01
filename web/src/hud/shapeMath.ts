// Hologram maths (sub-project 3): Claude's primitives in millimetres become three.js geometry arguments.

import type { Lang, ShapePart } from "../protocol";

export type Vec3 = [number, number, number];

export interface PartGeometry {
  kind: ShapePart["shape"];
  args: number[]; // constructor arguments of the three.js geometry
  scale: Vec3;
  position: Vec3;
  rotation: Vec3; // radians, applied x, y, z
  color: string;
}

const radians = (degrees: number) => (degrees * Math.PI) / 180;

export function partGeometry(p: ShapePart): PartGeometry {
  const [x, y, z] = p.size_mm;
  const base = { kind: p.shape, position: [...p.position_mm] as Vec3, rotation: p.rotation_deg.map(radians) as Vec3,
    color: p.color };
  switch (p.shape) {
    case "box":
      return { ...base, args: [x, y, z], scale: [1, 1, 1] };
    case "rounded_box": // RoundedBoxGeometry: width, height, depth, corner radius
      return { ...base, args: [x, y, z, p.radius_mm ?? Math.min(x, y, z) * 0.15], scale: [1, 1, 1] };
    case "cylinder": // CylinderGeometry: radius top, radius bottom, height; an oval one is stretched in depth
      return { ...base, args: [x / 2, x / 2, y], scale: [1, 1, z / x] };
    case "cone": // bottom diameter, height, top diameter
      return { ...base, args: [z / 2, x / 2, y], scale: [1, 1, 1] };
    case "sphere": // a unit sphere stretched to the three diameters
      return { ...base, args: [0.5], scale: [x, y, z] };
    case "capsule": // CapsuleGeometry: radius, length of the straight part
      return { ...base, args: [x / 2, Math.max(0, y - x)], scale: [1, 1, z / x] };
  }
}

export function formatSize(size: Vec3 | null, lang: Lang): string {
  if (!size) return "";
  const locale = lang === "de" ? "de-DE" : "en-US";
  return `${size.map((v) => v.toLocaleString(locale, { maximumFractionDigits: 1 })).join(" × ")} mm`;
}

// How far the camera stands back so that every part fits into its field of view, with a little margin.
export function fitDistance(parts: ShapePart[], fovDegrees: number): number {
  const reach = Math.max(1, ...parts.map((p) => Math.hypot(...p.position_mm) + Math.hypot(...p.size_mm) / 2));
  return (reach / Math.sin(radians(fovDegrees) / 2)) * 1.1;
}

// The crops paint everything that is not the object 128 grey: those pixels become transparent on the hologram.
export function clearGrey(pixels: Uint8ClampedArray, tolerance = 8): void {
  for (let i = 0; i < pixels.length; i += 4) {
    if (Math.abs(pixels[i] - 128) <= tolerance && Math.abs(pixels[i + 1] - 128) <= tolerance
      && Math.abs(pixels[i + 2] - 128) <= tolerance) pixels[i + 3] = 0;
  }
}

const SHAPE_NAMES: Record<ShapePart["shape"], Record<Lang, string>> = {
  box: { de: "Quader", en: "Box" },
  rounded_box: { de: "Abgerundeter Quader", en: "Rounded box" },
  cylinder: { de: "Zylinder", en: "Cylinder" },
  cone: { de: "Kegel", en: "Cone" },
  sphere: { de: "Kugel", en: "Sphere" },
  capsule: { de: "Kapsel", en: "Capsule" },
};

export function millimetres(value: number, lang: Lang): string {
  return value.toLocaleString(lang === "de" ? "de-DE" : "en-US", { maximumFractionDigits: 1 });
}

// "Zylinder ⌀ 13 × 2 mm": what the full-screen view lists for every part.
export function partDescription(p: ShapePart, lang: Lang): string {
  const [x, y, z] = p.size_mm.map((v) => millimetres(v, lang));
  const name = SHAPE_NAMES[p.shape][lang];
  switch (p.shape) {
    case "box":
    case "rounded_box":
      return `${name} ${x} × ${y} × ${z} mm`;
    case "cylinder":
    case "capsule":
      return `${name} ⌀ ${x} × ${y} mm`;
    case "cone":
      return `${name} ⌀ ${x} → ${z} × ${y} mm`;
    case "sphere":
      return x === y && y === z ? `${name} ⌀ ${x} mm` : `${name} ⌀ ${x} × ${y} × ${z} mm`;
  }
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
