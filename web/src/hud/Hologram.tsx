// The hologram of one product (sub-project 3): Claude's primitives as a slowly turning model you can drag around.
// Neon-green edges like the box of the object in your hand, faces in the part's own colour, half transparent.

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { t } from "../i18n";
import type { Lang, ShapeMsg } from "../protocol";
import { fitDistance, formatSize, partGeometry, type PartGeometry } from "./shapeMath";

const FOV = 35;
const EDGE = 0x7cff5a; // the neon green of the object in your hand
const VIEW = new THREE.Vector3(0.55, 0.35, 0.8).normalize(); // a little from above and from the right
const NOTE = { loading: "hologram.loading", unknown: "hologram.unknown", error: "hologram.error", ready: null } as const;

function geometryOf(g: PartGeometry): THREE.BufferGeometry {
  switch (g.kind) {
    case "box":
      return new THREE.BoxGeometry(g.args[0], g.args[1], g.args[2]);
    case "rounded_box":
      return new RoundedBoxGeometry(g.args[0], g.args[1], g.args[2], 3, g.args[3]);
    case "cylinder":
    case "cone":
      return new THREE.CylinderGeometry(g.args[0], g.args[1], g.args[2], 28, 1);
    case "sphere":
      return new THREE.SphereGeometry(g.args[0], 20, 14);
    case "capsule":
      return new THREE.CapsuleGeometry(g.args[0], g.args[1], 6, 20);
  }
}

export default function Hologram({ shape, lang }: { shape: ShapeMsg; lang: Lang }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const drawable = shape.status === "ready" && shape.parts.length > 0;

  useEffect(() => {
    const el = canvas.current;
    if (!el || !drawable) return;
    const renderer = new THREE.WebGLRenderer({ canvas: el, antialias: true, alpha: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.setSize(el.clientWidth, el.clientHeight, false);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(FOV, el.clientWidth / el.clientHeight, 1, 50000);
    camera.position.copy(VIEW).multiplyScalar(fitDistance(shape.parts, FOV));
    const garbage: { dispose(): void }[] = [];
    for (const part of shape.parts) {
      const g = partGeometry(part);
      const geometry = geometryOf(g);
      const edges = new THREE.EdgesGeometry(geometry, 25);
      const fill = new THREE.MeshBasicMaterial({ color: g.color, transparent: true, opacity: 0.28, depthWrite: false });
      const line = new THREE.LineBasicMaterial({ color: EDGE, transparent: true, opacity: 0.9 });
      const piece = new THREE.Group();
      piece.add(new THREE.Mesh(geometry, fill), new THREE.LineSegments(edges, line));
      piece.scale.set(...g.scale);
      piece.position.set(...g.position);
      piece.rotation.set(...g.rotation);
      scene.add(piece);
      garbage.push(geometry, edges, fill, line);
    }
    const controls = new OrbitControls(camera, el);
    controls.enableZoom = false; // the wheel scrolls the sidebar
    controls.enablePan = false;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 1.5;
    controls.update();
    let raf = 0;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      controls.update();
      renderer.render(scene, camera);
    };
    loop();
    return () => {
      cancelAnimationFrame(raf);
      controls.dispose();
      garbage.forEach((g) => g.dispose());
      renderer.dispose();
    };
  }, [shape, drawable]);

  const note = NOTE[shape.status];
  return (
    <div className="entry-part">
      <div className="profile-head">
        <span className="card-level">{t("hologram.title", lang)}</span>
        <span className="tag">{t("hologram.simplified", lang)}</span>
      </div>
      {drawable ? (
        <>
          <canvas ref={canvas} className="hologram-canvas" />
          <p className="hologram-size">{formatSize(shape.size_mm, lang)}</p>
        </>
      ) : (
        <p className="profile-note">{t(note ?? "hologram.unknown", lang)}</p>
      )}
    </div>
  );
}
