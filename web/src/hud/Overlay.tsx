// The canvas over the video: corner brackets, focus outline, scan line and the line to the info card (spec §3).
// Drawn every animation frame from the store, without React re-rendering.

import { useEffect, useRef, type MouseEvent, type RefObject } from "react";
import { useHud } from "../store";
import { hitTest, toScreen, toScreenPoints, videoContentRect, type Rect } from "./geometry";
import { CardPlacer, type Side } from "./placement";
import { smoothRect } from "./smoothing";

const SNAP_MS = 200;
const SNAP_PX = 8;
const SCAN_MS = 2400;
const ARM = 14;
const FALLBACK_CARD = { w: 300, h: 200 };

const white = (alpha: number) => `rgba(255,255,255,${alpha})`;
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

function drawBrackets(ctx: CanvasRenderingContext2D, r: Rect, inset: number, alpha: number) {
  const x = r.x - inset, y = r.y - inset, w = r.w + 2 * inset, h = r.h + 2 * inset;
  const arm = Math.min(ARM, w / 3, h / 3);
  ctx.strokeStyle = white(alpha);
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x, y + arm); ctx.lineTo(x, y); ctx.lineTo(x + arm, y);
  ctx.moveTo(x + w - arm, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + arm);
  ctx.moveTo(x + w, y + h - arm); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w - arm, y + h);
  ctx.moveTo(x + arm, y + h); ctx.lineTo(x, y + h); ctx.lineTo(x, y + h - arm);
  ctx.stroke();
}

function drawOutline(ctx: CanvasRenderingContext2D, points: [number, number][], dx: number, dy: number) {
  ctx.strokeStyle = white(0.9);
  ctx.lineWidth = 1;
  ctx.beginPath();
  points.forEach(([x, y], i) => (i ? ctx.lineTo(x + dx, y + dy) : ctx.moveTo(x + dx, y + dy)));
  ctx.closePath();
  ctx.stroke();
}

function drawScan(ctx: CanvasRenderingContext2D, r: Rect, now: number) {
  const y = r.y + r.h * ((now % SCAN_MS) / SCAN_MS);
  ctx.strokeStyle = white(0.8);
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(r.x, y);
  ctx.lineTo(r.x + r.w, y);
  ctx.stroke();
}

function drawLabel(ctx: CanvasRenderingContext2D, text: string, r: Rect) {
  ctx.font = "11px -apple-system, system-ui, sans-serif";
  const w = ctx.measureText(text).width + 12, h = 18, y = Math.max(0, r.y - h - 4);
  ctx.fillStyle = "rgba(22,22,28,0.6)";
  ctx.beginPath();
  ctx.roundRect(r.x, y, w, h, 6);
  ctx.fill();
  ctx.fillStyle = white(0.85);
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
  ctx.strokeStyle = white(0.6);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(...from);
  ctx.lineTo(...to);
  ctx.stroke();
}

interface Props {
  video: RefObject<HTMLVideoElement | null>;
  card: RefObject<HTMLDivElement | null>;
  onFocus(trackId: number | null): void;
}

export default function Overlay({ video, card, onFocus }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const rects = useRef(new Map<number, Rect>());

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
      const seen = new Set<number>();
      let focusRect: Rect | null = null;
      for (const t of msg.tracks) {
        seen.add(t.id);
        const target = toScreen(t.box, content, s.mirrored);
        const r = smoothRect(rects.current.get(t.id) ?? target, target, dt);
        rects.current.set(t.id, r);
        if (t.id !== msg.focus_id) {
          drawBrackets(ctx, r, 0, 0.35);
          drawLabel(ctx, `#${t.id} ${t.label}`, r);
          continue;
        }
        focusRect = r;
        drawBrackets(ctx, r, SNAP_PX * (1 - Math.min(1, (now - focusSince) / SNAP_MS)), 1);
        if (t.polygon.length > 2) {
          drawOutline(ctx, toScreenPoints(t.polygon, content, s.mirrored), r.x - target.x, r.y - target.y);
        }
        if (s.identities[t.id]?.status === "analysing") drawScan(ctx, r, now);
      }
      for (const id of [...rects.current.keys()]) if (!seen.has(id)) rects.current.delete(id);

      const el = card.current;
      if (focusRect && el && msg.focus_id !== null && s.identities[msg.focus_id]) {
        const size = el.offsetWidth ? { w: el.offsetWidth, h: el.offsetHeight } : FALLBACK_CARD;
        const pos = placer.place(focusRect, size, { w: vw, h: vh }, now);
        el.style.transform = `translate(${Math.round(pos.x)}px, ${Math.round(pos.y)}px)`;
        drawLeader(ctx, focusRect, { x: pos.x, y: pos.y, ...size }, pos.side);
      }
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [video, card]);

  const onClick = (event: MouseEvent<HTMLCanvasElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const point = { x: event.clientX - bounds.left, y: event.clientY - bounds.top };
    onFocus(hitTest(point, [...rects.current].map(([id, rect]) => ({ id, rect }))));
  };

  return <canvas ref={canvas} className="overlay" onClick={onClick} />;
}
