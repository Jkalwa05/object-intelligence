// The canvas over the video: your hands, the object in your hand with its scan line, its name tag and a line to its
// entry in the sidebar, and the frozen background (spec §3, §9, sub-project 3). Drawn every animation frame from the
// store, without React re-rendering.

import { useEffect, useRef, type RefObject } from "react";
import { t, type I18nKey } from "../i18n";
import { useHud } from "../store";
import { toScreen, toScreenPoints, videoContentRect, type Rect } from "./geometry";
import { smoothPoints, smoothRect } from "./smoothing";

const SNAP_MS = 200;
const SNAP_PX = 8;
const SCAN_MS = 2400;
const ARM = 14;

type Rgb = readonly [number, number, number];
const HAND: Rgb = [100, 210, 255]; // Apple cyan: your hand
const FOCUS: Rgb = [48, 209, 88]; // Apple green: the object in your hand, the one Claude analyses
const SCENE: Rgb = [191, 90, 242]; // Apple violet: the frozen background
const rgba = ([r, g, b]: Rgb, alpha: number) => `rgba(${r},${g},${b},${alpha})`;
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

function drawBrackets(ctx: CanvasRenderingContext2D, r: Rect, inset: number, color: string) {
  const x = r.x - inset, y = r.y - inset, w = r.w + 2 * inset, h = r.h + 2 * inset;
  const arm = Math.min(ARM, w / 3, h / 3);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
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

// A glass capsule with a coloured dot: the look of every label on the camera picture.
function drawCapsule(ctx: CanvasRenderingContext2D, text: string, r: Rect, dot: Rgb, size: number) {
  ctx.font = `${size >= 12 ? 600 : 500} ${size}px -apple-system, system-ui, sans-serif`;
  const h = size + 10, pad = 9, radius = 3;
  const w = ctx.measureText(text).width + pad * 2 + radius * 2 + 6, y = Math.max(0, r.y - h - 6);
  ctx.fillStyle = "rgba(28,28,30,0.72)";
  ctx.beginPath();
  ctx.roundRect(r.x, y, w, h, h / 2);
  ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.12)";
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.fillStyle = rgba(dot, 1);
  ctx.beginPath();
  ctx.arc(r.x + pad + radius, y + h / 2, radius, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "rgba(255,255,255,0.92)";
  ctx.fillText(text, r.x + pad + radius * 2 + 6, y + h / 2 + size * 0.36);
}

function drawLabel(ctx: CanvasRenderingContext2D, text: string, r: Rect) {
  drawCapsule(ctx, text, r, SCENE, 11);
}

// The name of the object in your hand, just above its box.
function drawTag(ctx: CanvasRenderingContext2D, text: string, r: Rect) {
  drawCapsule(ctx, text, r, FOCUS, 12);
}

// From the box to the right edge, at the height of the object's entry in the sidebar.
function drawLink(ctx: CanvasRenderingContext2D, box: Rect, y: number, right: number) {
  const from: [number, number] = [box.x + box.w, clamp(y, box.y, box.y + box.h)];
  ctx.strokeStyle = rgba(FOCUS, 0.55);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(...from);
  ctx.lineTo(from[0] + (right - from[0]) * 0.6, y);
  ctx.lineTo(right, y);
  ctx.stroke();
}

interface Props {
  video: RefObject<HTMLVideoElement | null>;
}

export default function Overlay({ video }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const rects = useRef(new Map<number, Rect>());
  const handShapes = useRef<[number, number][][]>([]);

  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    let focusId: number | null = null;
    let focusSince = 0;
    let lastFocus: { id: number; rect: Rect } | null = null; // survives a moment without focus

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
        // the tracker renumbered the same object: its box glides on instead of snapping in again
        if (msg.focus_id !== null && lastFocus && s.identities[msg.focus_id]?.previous_id === lastFocus.id) {
          rects.current.set(msg.focus_id, lastFocus.rect);
        } else if (msg.focus_id !== null) {
          focusSince = now;
        }
        focusId = msg.focus_id;
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
      if (focusRect && msg.focus_id !== null) lastFocus = { id: msg.focus_id, rect: focusRect };

      const identity = msg.focus_id === null ? undefined : s.identities[msg.focus_id];
      if (focusRect && identity) {
        const lang = s.telemetry?.language ?? "de";
        const level = identity.status === "analysing" ? t("analysing", lang)
          : identity.level ? t(`level.${identity.level}` as I18nKey, lang) : "";
        drawTag(ctx, level ? `${identity.display_name} · ${level}` : identity.display_name, focusRect);
        const head = document.querySelector(".entry.active .entry-head");
        if (head) {
          const entry = head.getBoundingClientRect(), stage = c.getBoundingClientRect();
          drawLink(ctx, focusRect, entry.top + entry.height / 2 - stage.top, vw);
        }
      }
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [video]);

  return <canvas ref={canvas} className="overlay" />;
}
