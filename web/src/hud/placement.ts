// Where the info card goes next to the focus object (spec §3): the side with more room, with hysteresis.

import type { Rect } from "./geometry";

export type Side = "left" | "right" | "below" | "above";

const GAP = 24;
const MARGIN = 8;
const SWITCH_RATIO = 1.2; // the other side needs 20 % more room ...
const HOLD_MS = 500; // ... for half a second without interruption

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
const intersects = (a: Rect, b: Rect) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

export class CardPlacer {
  private side: "left" | "right" | null = null;
  private challengeSince: number | null = null;

  // `avoid`: screen rects the card must not cover (faces)
  place(box: Rect, card: { w: number; h: number }, viewport: { w: number; h: number }, now: number,
    avoid: Rect[] = []): { x: number; y: number; side: Side } {
    const room = { left: box.x, right: viewport.w - (box.x + box.w) };
    const y = clamp(box.y, MARGIN, viewport.h - card.h - MARGIN);
    const rectFor = (side: "left" | "right"): Rect =>
      ({ x: side === "right" ? box.x + box.w + GAP : box.x - GAP - card.w, y, w: card.w, h: card.h });
    const free = (r: Rect) => !avoid.some((a) => intersects(r, a));
    const fits = (side: "left" | "right") => room[side] >= card.w + GAP && free(rectFor(side));
    if (this.side === null || !fits(this.side)) {
      const preferred = room.right >= room.left ? "right" : "left";
      const other = preferred === "right" ? "left" : "right";
      this.side = fits(preferred) || !fits(other) ? preferred : other;
      this.challengeSince = null;
    } else {
      const other = this.side === "left" ? "right" : "left";
      if (room[other] >= room[this.side] * SWITCH_RATIO && fits(other)) {
        this.challengeSince ??= now;
        if (now - this.challengeSince >= HOLD_MS) {
          this.side = other;
          this.challengeSince = null;
        }
      } else {
        this.challengeSince = null;
      }
    }

    if (fits(this.side)) return { x: rectFor(this.side).x, y, side: this.side };
    const x = clamp(box.x, MARGIN, viewport.w - card.w - MARGIN);
    const below = { x, y: box.y + box.h + GAP, w: card.w, h: card.h };
    const above = { x, y: Math.max(MARGIN, box.y - GAP - card.h), w: card.w, h: card.h };
    const belowFits = viewport.h - (box.y + box.h) >= card.h + GAP;
    if (belowFits && free(below)) return { x, y: below.y, side: "below" };
    if (!belowFits || free(above)) return { x, y: above.y, side: "above" };
    return { x, y: below.y, side: "below" };
  }
}
