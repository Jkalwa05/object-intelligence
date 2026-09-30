import { expect, test } from "vitest";
import { smoothRect } from "./smoothing";

const from = { x: 0, y: 0, w: 0, h: 0 };
const to = { x: 100, y: 100, w: 100, h: 100 };

test("one time constant covers about 63 % of the way", () => expect(smoothRect(from, to, 80).x).toBeCloseTo(63.21, 1));
test("no time, no movement", () => expect(smoothRect(from, to, 0)).toEqual(from));
test("a long time arrives", () => expect(smoothRect(from, to, 2000).w).toBeCloseTo(100, 5));
