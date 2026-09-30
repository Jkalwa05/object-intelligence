// The canvas over the video: your hands, the object in your hand with its scan line and the line to the info card,
// and the frozen background (spec §3, §9). Drawn every animation frame from the store, without React re-rendering.

import { useEffect, useRef, type RefObject } from "react";
import { useHud } from "../store";
import { toScreen, toScreenPoints, videoContentRect, type Rect } from "./geometry";
import { CardPlacer, type Side } from "./placement";
import { smoothPoints, smoothRect } from "./smoothing";

const SNAP_MS = 200;
const SNAP_PX = 8;
const SCAN_MS = 2400;
const ARM = 14;
const FALLBACK_CARD = { w: 300, h: 200 };

type Rgb = readonly [number, number, number];
const HAND: Rgb = [46, 230, 255]; // cyan: your hand
const FOCUS: Rgb = [124, 255, 90]; // neon green: the object in your hand, the one Claude analyses
const SCENE: Rgb = [185, 156, 255]; // violet: the frozen background
const rgba = ([r, g, b]: Rgb, alpha: number) => `rgba(${r},${g},${b},${alpha})`;
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

function drawBrackets(ctx: CanvasRenderingContext2D, r: Rect, inset: number, color: string) {
  const x = r.x - inset, y = r.y - inset, w = r.w + 2 * inset, h = r.h + 2 * inset;
  const arm = Math.min(ARM, w / 3, h / 3);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x, y + arm); ctx.lineTo(x, y); ctx.lineTo(x + arm, y);
  ctx.moveTo(x + w - arm, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + arm);
  ctx.moveTo(x + w, y + h - arm); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w - arm, y + h);
  ctx.moveTo(x + arm, y + h); ctx.lineTo(x, y + h); ctx.lineTo(x, y + h - arm);
  ctx.stroke();
}

function drawOutline(ctx: CanvasRenderingContext2D, points: [number, number][], dx: number, dy: number) {
  ctx.strokeStyle = rgba(FOCUS, 0.9);
  ctx.lineWidth = 1;
  ctx.beginPath();
  points.forEach(([x, y], i) => (i ? ctx.lineTo(x + dx, y + dy) : ctx.moveTo(x + dx, y + dy)));
  ctx.closePath();
  ctx.stroke();
}

function drawScan(ctx: CanvasRenderingContext2D, r: Rect, now: number) {
  const y = r.y + r.h * ((now % SCAN_MS) / SCAN_MS);
  ctx.strokeStyle = rgba(FOCUS, 0.8);
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(r.x, y);
  ctx.lineTo(r.x + r.w, y);
  ctx.stroke();
}

// A hand: a soft closed curve through the midpoints of its outline, lightly filled.
function drawHand(ctx: CanvasRenderingContext2D, points: [number, number][]) {
  const n = points.length;
  if (n < 3) return;
  const mid = (i: number): [number, number] =>
    [(points[i][0] + points[(i + 1) % n][0]) / 2, (points[i][1] + points[(i + 1) % n][1]) / 2];
  ctx.beginPath();
  ctx.moveTo(...mid(n - 1));
  points.forEach(([x, y], i) => ctx.quadraticCurveTo(x, y, ...mid(i)));
  ctx.closePath();
  ctx.fillStyle = rgba(HAND, 0.1);
  ctx.fill();
  ctx.strokeStyle = rgba(HAND, 0.95);
  ctx.lineWidth = 2;
  ctx.stroke();
}

function drawLabel(ctx: CanvasRenderingContext2D, text: string, r: Rect) {
  ctx.font = "11px -apple-system, system-ui, sans-serif";
  const w = ctx.measureText(text).width + 12, h = 18, y = Math.max(0, r.y - h - 4);
  ctx.fillStyle = "rgba(22,22,28,0.6)";
  ctx.beginPath();
  ctx.roundRect(r.x, y, w, h, 6);
  ctx.fill();
  ctx.fillStyle = rgba(SCENE, 0.95);
  ctx.fillText(text, r.x + 6, y + 13);
}

function drawLeader(ctx: CanvasRenderingContext2D, box: Rect, card: Rect, side: Side) {
  const midX = clamp(box.x + box.w / 2, card.x, card.x + card.w);
  const rowY = card.y + 18;
  const [from, to]: [number, number][] =
    side === "right" ? [[box.x + box.w, clamp(rowY, box.y, box.y + box.h)], [card.x, rowY]]
      : side === "left" ? [[box.x, clamp(rowY, box.y, box.y + box.h)], [card.x + card.w, rowY]]
        : side === "below" ? [[box.x + box.w / 2, box.y + box.h], [midX, card.y]]
          : [[box.x + box.w / 2, box.y], [midX, card.y + card.h]];
  ctx.strokeStyle = rgba(FOCUS, 0.6);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(...from);
  ctx.lineTo(...to);
  ctx.stroke();
}

interface Props {
  video: RefObject<HTMLVideoElement | null>;
  card: RefObject<HTMLDivElement | null>;
}

export default function Overlay({ video, card }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const rects = useRef(new Map<number, Rect>());
  const handShapes = useRef<[number, number][][]>([]);

  useEffect(() => {
    const placer = new CardPlacer();
    let raf = 0;
    let last = performance.now();
    let focusId: number | null = null;
    let focusSince = 0;

    const draw = (now: number) => {
      raf = requestAnimationFrame(draw);
      const c = canvas.current;
      const ctx = c?.getContext("2d");
      if (!c || !ctx || !video.current) return;
      const dpr = window.devicePixelRatio || 1;
      const vw = c.clientWidth, vh = c.clientHeight;
      if (c.width !== Math.round(vw * dpr) || c.height !== Math.round(vh * dpr)) {
        c.width = Math.round(vw * dpr);
        c.height = Math.round(vh * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, vw, vh);
      const dt = now - last;
      last = now;

      const s = useHud.getState();
      const msg = s.tracks;
      if (!msg) return;
      const content = videoContentRect({ w: vw, h: vh }, { w: msg.w, h: msg.h });
      if (msg.focus_id !== focusId) {
        focusId = msg.focus_id;
        focusSince = now;
      }
      // the frozen background: static, never smoothed, never updated until the next calibration
      for (const item of s.scene?.calibrating ? [] : s.scene?.items ?? []) {
        const r = toScreen(item.box, content, s.mirrored);
        drawBrackets(ctx, r, 0, rgba(SCENE, 0.55));
        drawLabel(ctx, item.label, r);
      }
      // your hands, as soon as they are confirmed; each outline glides like the boxes do
      handShapes.current = msg.hands.map((hand, i) => {
        const target = toScreenPoints(hand.polygon, content, s.mirrored);
        const shape = smoothPoints(handShapes.current[i] ?? target, target, dt);
        drawHand(ctx, shape);
        return shape;
      });
      const seen = new Set<number>();
      let focusRect: Rect | null = null;
      for (const t of msg.tracks) { // the server sends only the object in your hand
        seen.add(t.id);
        const target = toScreen(t.box, content, s.mirrored);
        const r = smoothRect(rects.current.get(t.id) ?? target, target, dt);
        rects.current.set(t.id, r);
        focusRect = r;
        drawBrackets(ctx, r, SNAP_PX * (1 - Math.min(1, (now - focusSince) / SNAP_MS)), rgba(FOCUS, 1));
        if (t.polygon.length > 2) {
          drawOutline(ctx, toScreenPoints(t.polygon, content, s.mirrored), r.x - target.x, r.y - target.y);
        }
        if (s.identities[t.id]?.status === "analysing") drawScan(ctx, r, now);
      }
      for (const id of [...rects.current.keys()]) if (!seen.has(id)) rects.current.delete(id);

      const el = card.current;
      if (focusRect && el && msg.focus_id !== null && s.identities[msg.focus_id]) {
        const size = el.offsetWidth ? { w: el.offsetWidth, h: el.offsetHeight } : FALLBACK_CARD;
        const faces = msg.faces.map((f) => toScreen(f, content, s.mirrored));
        const pos = placer.place(focusRect, size, { w: vw, h: vh }, now, faces);
        el.style.transform = `translate(${Math.round(pos.x)}px, ${Math.round(pos.y)}px)`;
        drawLeader(ctx, focusRect, { x: pos.x, y: pos.y, ...size }, pos.side);
      }
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [video, card]);

  return <canvas ref={canvas} className="overlay" />;
}
