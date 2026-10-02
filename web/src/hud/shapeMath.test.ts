import { expect, test } from "vitest";
import type { ModelPart } from "../protocol";
import { fitDistance, formatSize, millimetres, partCenter, partSize, rimPoint, spread } from "./shapeMath";

const part = (min: [number, number, number], max: [number, number, number]): ModelPart =>
  ({ name: "Teil", color: "#9fc4e8", file: "part-01.stl", min_mm: min, max_mm: max, triangles: 12 });

test("a part's size and centre come from its bounding box", () => {
  const lens = part([-30, 50, 3], [-17, 63, 5]);
  expect(partSize(lens)).toEqual([13, 13, 2]);
  expect(partCenter(lens)).toEqual([-23.5, 56.5, 4]);
});

test("the size reads like the spec", () => {
  expect(formatSize([71.5, 146.7, 7.8], "de")).toBe("71,5 × 146,7 × 7,8 mm");
  expect(formatSize([71.5, 146.7, 7.8], "en")).toBe("71.5 × 146.7 × 7.8 mm");
  expect(formatSize(null, "de")).toBe("");
});

test("the camera stands back far enough for the whole object", () => {
  const near = fitDistance([10, 10, 10], 35);
  const far = fitDistance([100, 100, 100], 35);
  expect(near).toBeGreaterThan(10);
  expect(far / near).toBeCloseTo(10, 5);
  expect(fitDistance([0, 0, 0], 35)).toBeGreaterThan(0);
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

test("large shells put their dots around the rim, not on one point", () => {
  const shell = part([-35.75, -73.35, -3.9], [35.75, 73.35, 3.9]);
  expect(rimPoint(shell, 0, 5)).toEqual([0, -73.35, 3.9]); // the first one at the lower edge, as before
  const points = [0, 1, 2, 3, 4].map((k) => rimPoint(shell, k, 5));
  expect(new Set(points.map((p) => p.map((v) => v.toFixed(1)).join())).size).toBe(5);
  for (const [x, y, z] of points) {
    expect(Math.abs(x) <= 35.75 + 1e-9 && Math.abs(y) <= 73.35 + 1e-9 && z === 3.9).toBe(true);
  }
});

test("thin parts keep their hundredths", () => {
  expect(millimetres(0.04, "de")).toBe("0,04");
  expect(millimetres(12.345, "de")).toBe("12,3");
  expect(formatSize([64.6, 139.8, 0.04], "de")).toBe("64,6 × 139,8 × 0,04 mm");
});
