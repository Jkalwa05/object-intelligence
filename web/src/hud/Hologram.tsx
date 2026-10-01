// The hologram of one product in its sidebar entry (sub-projects 3 and 5): Claude's primitives as a slowly turning
// model you can drag around; "⤢" opens the full-screen view with every measure.

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { t } from "../i18n";
import type { Lang, ShapeMsg } from "../protocol";
import { useHud } from "../store";
import { buildModel } from "./hologramScene";
import { fitDistance, formatSize } from "./shapeMath";

const FOV = 35;
const VIEW = new THREE.Vector3(0.55, 0.35, 0.8).normalize(); // a little from above and from the right
const NOTE = { loading: "hologram.loading", unknown: "hologram.unknown", error: "hologram.error", ready: null } as const;

export default function Hologram({ shape, lang }: { shape: ShapeMsg; lang: Lang }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const showFullscreen = useHud((s) => s.setFullscreen);
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
    const model = buildModel(shape);
    scene.add(model.group);
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
      model.dispose();
      renderer.dispose();
    };
  }, [shape, drawable]);

  const note = NOTE[shape.status];
  return (
    <div className="entry-part">
      <div className="profile-head">
        <span className="card-level">{t("hologram.title", lang)}</span>
        <span className="tag">{t("hologram.simplified", lang)}</span>
        {drawable && (
          <button type="button" className="icon-button" aria-label={t("hologram.full", lang)}
            title={t("hologram.full", lang)} onClick={() => showFullscreen(shape.product)}>⤢</button>
        )}
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
