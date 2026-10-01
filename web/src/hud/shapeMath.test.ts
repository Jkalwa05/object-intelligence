import { expect, test } from "vitest";
import type { ShapePart } from "../protocol";
import { fitDistance, formatSize, outlinePoints, partDescription, partGeometry, spread } from "./shapeMath";

const part = (shape: ShapePart["shape"], size: [number, number, number], extra: Partial<ShapePart> = {}): ShapePart =>
  ({ name: "Teil", shape, size_mm: size, position_mm: [1, 2, 3], rotation_deg: [90, 0, 45], color: "#9fc4e8",
    radius_mm: null, ...extra });

test("each primitive becomes three.js arguments in millimetres", () => {
  expect(partGeometry(part("box", [71.5, 146.7, 7.8])).args).toEqual([71.5, 146.7, 7.8]);
  expect(partGeometry(part("rounded_box", [71.5, 146.7, 7.8], { radius_mm: 3 })).args).toEqual([71.5, 146.7, 7.8, 3]);
  expect(partGeometry(part("cylinder", [12, 2, 12])).args).toEqual([6, 6, 2]);
  expect(partGeometry(part("cone", [40, 60, 0])).args).toEqual([0, 20, 60]);
  const sphere = partGeometry(part("sphere", [10, 20, 30]));
  expect([sphere.args, sphere.scale]).toEqual([[0.5], [10, 20, 30]]);
  expect(partGeometry(part("capsule", [20, 100, 20])).args).toEqual([10, 80]);
});

test("an oval cylinder is stretched in depth, angles turn into radians", () => {
  const oval = partGeometry(part("cylinder", [20, 5, 10]));
  expect(oval.scale).toEqual([1, 1, 0.5]);
  expect(oval.position).toEqual([1, 2, 3]);
  expect(oval.rotation[0]).toBeCloseTo(Math.PI / 2);
  expect(oval.rotation[2]).toBeCloseTo(Math.PI / 4);
});

test("the size reads like the spec", () => {
  expect(formatSize([71.5, 146.7, 7.8], "de")).toBe("71,5 × 146,7 × 7,8 mm");
  expect(formatSize([71.5, 146.7, 7.8], "en")).toBe("71.5 × 146.7 × 7.8 mm");
  expect(formatSize(null, "de")).toBe("");
});

test("the camera stands back far enough for the whole object", () => {
  const near = fitDistance([part("box", [10, 10, 10], { position_mm: [0, 0, 0] })], 35);
  const far = fitDistance([part("box", [100, 100, 100], { position_mm: [0, 0, 0] })], 35);
  expect(near).toBeGreaterThan(10);
  expect(far / near).toBeCloseTo(10, 0);
});

test("every part is described with its shape and size", () => {
  expect(partDescription(part("cylinder", [13, 2, 13]), "de")).toBe("Zylinder ⌀ 13 × 2 mm");
  expect(partDescription(part("rounded_box", [71.5, 146.7, 7.8]), "de")).toBe("Abgerundeter Quader 71,5 × 146,7 × 7,8 mm");
  expect(partDescription(part("sphere", [10, 10, 10]), "en")).toBe("Sphere ⌀ 10 mm");
  expect(partDescription(part("cone", [40, 60, 0]), "de")).toBe("Kegel ⌀ 40 → 0 × 60 mm");
  expect(partDescription(part("capsule", [20, 100, 20]), "de")).toBe("Kapsel ⌀ 20 × 100 mm");
});

test("labels that would cover each other move down, the others stay at their part", () => {
  const pin = (x: number, y: number, w = 20) => ({ x, y, w, h: 20 });
  expect(spread([pin(0, 0), pin(100, 0), pin(0, 100)], 2)).toEqual([0, 0, 0]);
  expect(spread([pin(50, 10), pin(52, 10)], 2)).toEqual([0, 22]);
  expect(spread([pin(0, 10), pin(0, 0), pin(5, 5)], 2)).toEqual([34, 0, 17]); // top to bottom order stays
  expect(spread([pin(0, 0, 120), pin(110, 5)], 2)).toEqual([0, 17]); // a long name blocks the label to its right
  expect(spread([pin(0, 0, 120), pin(130, 5)], 2)).toEqual([0, 0]);
});

test("labels also keep clear of the numbered dots, which never move", () => {
  const pin = (x: number, y: number) => ({ x, y, w: 20, h: 20 });
  expect(spread([pin(0, 0)], 2, [pin(10, 5)])).toEqual([27]);
  expect(spread([pin(0, 0), pin(0, 10)], 2, [pin(100, 0)])).toEqual([0, 12]);
});

test("round parts get rings and their outline from the front and the side, so a capsule never looks cut off", () => {
  const capsule = outlinePoints(partGeometry(part("capsule", [38, 80, 38])))!;
  expect(capsule.length % 2).toBe(0); // pairs of points: line segments
  expect(Math.max(...capsule.map((p) => p[1]))).toBeCloseTo(40); // 80 mm long: the outline reaches both tips
  expect(Math.min(...capsule.map((p) => p[1]))).toBeCloseTo(-40);
  expect(Math.max(...capsule.map((p) => p[0]))).toBeCloseTo(19);
  expect(Math.max(...capsule.map((p) => p[2]))).toBeCloseTo(19);
  const sphere = outlinePoints(partGeometry(part("sphere", [10, 10, 10])))!;
  expect(Math.max(...sphere.map((p) => p[1]))).toBeCloseTo(0.5); // the unit sphere, stretched by the piece
  expect(outlinePoints(partGeometry(part("box", [1, 2, 3])))).toBeNull(); // hard edges come from three.js
});
