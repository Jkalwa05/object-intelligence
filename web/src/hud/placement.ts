// Where the info card goes next to the focus object (spec §3): the side with more room, with hysteresis.

import type { Rect } from "./geometry";

export type Side = "left" | "right" | "below" | "above";

const GAP = 24;
const MARGIN = 8;
const SWITCH_RATIO = 1.2; // the other side needs 20 % more room ...
const HOLD_MS = 500; // ... for half a second without interruption

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

export class CardPlacer {
  private side: "left" | "right" | null = null;
  private challengeSince: number | null = null;

  place(box: Rect, card: { w: number; h: number }, viewport: { w: number; h: number }, now: number):
    { x: number; y: number; side: Side } {
    const room = { left: box.x, right: viewport.w - (box.x + box.w) };
    const fits = (space: number) => space >= card.w + GAP;
    if (this.side === null || !fits(room[this.side])) {
      this.side = room.right >= room.left ? "right" : "left";
      this.challengeSince = null;
    } else {
      const other = this.side === "left" ? "right" : "left";
      if (room[other] >= room[this.side] * SWITCH_RATIO && fits(room[other])) {
        this.challengeSince ??= now;
        if (now - this.challengeSince >= HOLD_MS) {
          this.side = other;
          this.challengeSince = null;
        }
      } else {
        this.challengeSince = null;
      }
    }

    if (fits(room[this.side])) {
      const x = this.side === "right" ? box.x + box.w + GAP : box.x - GAP - card.w;
      return { x, y: clamp(box.y, MARGIN, viewport.h - card.h - MARGIN), side: this.side };
    }
    const x = clamp(box.x, MARGIN, viewport.w - card.w - MARGIN);
    if (viewport.h - (box.y + box.h) >= card.h + GAP) return { x, y: box.y + box.h + GAP, side: "below" };
    return { x, y: Math.max(MARGIN, box.y - GAP - card.h), side: "above" };
  }
}
