import { expect, test } from "vitest";
import { CardPlacer } from "./placement";

const card = { w: 300, h: 200 };
const wide = { w: 1400, h: 600 };

test("card goes to the side with more space", () =>
  expect(new CardPlacer().place({ x: 300, y: 200, w: 200, h: 200 }, card, wide, 0)).toEqual({ x: 524, y: 200, side: "right" }));

test("switching sides waits 500 ms", () => {
  const placer = new CardPlacer();
  placer.place({ x: 300, y: 200, w: 200, h: 200 }, card, wide, 0);
  const moved = { x: 800, y: 200, w: 200, h: 200 }; // left 800, right 400
  expect(placer.place(moved, card, wide, 100).side).toBe("right");
  expect(placer.place(moved, card, wide, 500).side).toBe("right");
  expect(placer.place(moved, card, wide, 600)).toEqual({ x: 476, y: 200, side: "left" });
});

test("y is clamped to the viewport", () =>
  expect(new CardPlacer().place({ x: 300, y: 550, w: 200, h: 40 }, card, wide, 0).y).toBe(392));

test("cramped viewport: below, else above, never over the box", () => {
  const narrow = { w: 500, h: 600 };
  const below = new CardPlacer().place({ x: 150, y: 50, w: 200, h: 200 }, card, narrow, 0);
  expect(below).toEqual({ x: 150, y: 274, side: "below" });
  const above = new CardPlacer().place({ x: 150, y: 350, w: 200, h: 200 }, card, narrow, 0);
  expect(above).toEqual({ x: 150, y: 126, side: "above" });
});

test("the card never covers a face", () => {
  const box = { x: 800, y: 200, w: 200, h: 200 }; // more room on the left ...
  const face = { x: 480, y: 150, w: 250, h: 300 }; // ... but a face sits there
  expect(new CardPlacer().place(box, card, wide, 0, [face])).toEqual({ x: 1024, y: 200, side: "right" });
  expect(new CardPlacer().place(box, card, wide, 0, []).side).toBe("left");
});
