import { expect, test } from "vitest";
import { smoothPoints, smoothRect } from "./smoothing";

const from = { x: 0, y: 0, w: 0, h: 0 };
const to = { x: 100, y: 100, w: 100, h: 100 };

test("one time constant covers about 63 % of the way", () => expect(smoothRect(from, to, 80).x).toBeCloseTo(63.21, 1));
test("no time, no movement", () => expect(smoothRect(from, to, 0)).toEqual(from));
test("a long time arrives", () => expect(smoothRect(from, to, 2000).w).toBeCloseTo(100, 5));

test("outlines glide point by point", () => {
  const moved = smoothPoints([[0, 0], [10, 0]], [[100, 0], [110, 100]], 80);
  expect(moved[0][0]).toBeCloseTo(63.21, 1);
  expect(moved[1][1]).toBeCloseTo(63.21, 1);
});
test("an outline with other points jumps to the new shape", () => {
  expect(smoothPoints([[0, 0]], [[5, 5], [6, 6]], 80)).toEqual([[5, 5], [6, 6]]);
});
