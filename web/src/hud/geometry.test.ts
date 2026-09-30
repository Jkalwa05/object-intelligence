import { expect, test } from "vitest";
import { hitTest, toScreen, toScreenPoints, videoContentRect } from "./geometry";

test("contain: letterbox in a wide view", () =>
  expect(videoContentRect({ w: 1000, h: 600 }, { w: 1280, h: 720 })).toEqual({ x: 0, y: 18.75, w: 1000, h: 562.5 }));

test("contain: pillarbox in a very wide view", () => {
  const r = videoContentRect({ w: 2000, h: 600 }, { w: 1280, h: 720 });
  expect(r.h).toBe(600);
  expect(r.w).toBeCloseTo(1066.67, 1);
  expect(r.x).toBeCloseTo(466.67, 1);
});

test("mapping, mirrored and not", () => {
  const content = { x: 0, y: 0, w: 1000, h: 500 };
  expect(toScreen([0.1, 0.2, 0.3, 0.4], content, true)).toEqual({ x: 700, y: 100, w: 200, h: 100 });
  expect(toScreen([0.1, 0.2, 0.3, 0.4], content, false)).toEqual({ x: 100, y: 100, w: 200, h: 100 });
  expect(toScreenPoints([[0.1, 0.2]], { x: 10, y: 20, w: 1000, h: 500 }, true)).toEqual([[910, 120]]);
});

test("hitTest picks the smallest box containing the point", () => {
  const boxes = [{ id: 1, rect: { x: 0, y: 0, w: 500, h: 500 } }, { id: 2, rect: { x: 100, y: 100, w: 50, h: 50 } }];
  expect(hitTest({ x: 120, y: 120 }, boxes)).toBe(2);
  expect(hitTest({ x: 400, y: 400 }, boxes)).toBe(1);
  expect(hitTest({ x: 600, y: 600 }, boxes)).toBeNull();
});
