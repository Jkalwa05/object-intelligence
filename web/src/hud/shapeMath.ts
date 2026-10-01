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
