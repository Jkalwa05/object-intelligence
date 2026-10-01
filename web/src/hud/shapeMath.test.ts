import { expect, test } from "vitest";
import type { ShapePart } from "../protocol";
import { fitDistance, formatSize, partGeometry } from "./shapeMath";

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
