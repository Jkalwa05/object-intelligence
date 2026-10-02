// The precision model of one product in its sidebar entry (sub-project 6): while it is being built, what happens;
// then the CAD model as a slowly turning hologram you can drag around, its size and the source of its dimensions.
// "⤢" opens the full-screen view with every measure.

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { t } from "../i18n";
import type { IdentityMsg, Lang, ModelMsg } from "../protocol";
import { useHud } from "../store";
import { loadModel } from "./hologramScene";
import { progressText, sourceTag } from "./modelText";
import { fitDistance, formatSize, type Vec3 } from "./shapeMath";

const FOV = 35;
const VIEW = new THREE.Vector3(0.55, 0.35, 0.8).normalize(); // a little from above and from the right

interface Props {
  name: string; // the sidebar entry
  level: IdentityMsg["level"];
  model?: ModelMsg;
  lang: Lang;
  onRebuild(name: string): void;
}

export default function Hologram({ name, level, model, lang, onRebuild }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const showFullscreen = useHud((s) => s.setFullscreen);
  const manifest = model?.status === "ready" ? model.manifest : null;

  useEffect(() => {
    const el = canvas.current;
    if (!el || !manifest) return;
    let stop = false;
    let cleanup = () => {};
    void loadModel(manifest).then((loaded) => {
      if (stop) return loaded.dispose();
      const renderer = new THREE.WebGLRenderer({ canvas: el, antialias: true, alpha: true });
      renderer.setPixelRatio(window.devicePixelRatio || 1);
      renderer.setSize(el.clientWidth, el.clientHeight, false);
      const scene = new THREE.Scene();
      scene.add(loaded.group);
      const camera = new THREE.PerspectiveCamera(FOV, el.clientWidth / el.clientHeight, 1, 50000);
      const size = loaded.bounds.getSize(new THREE.Vector3()).toArray() as Vec3;
      camera.position.copy(VIEW).multiplyScalar(fitDistance(size, FOV));
      const controls = new OrbitControls(camera, el);
      controls.enableZoom = false; // the wheel scrolls the sidebar
      controls.enablePan = false;
      controls.autoRotate = true;
      controls.autoRotateSpeed = 1.5;
      let raf = 0;
      const loop = () => {
        raf = requestAnimationFrame(loop);
        controls.update();
        renderer.render(scene, camera);
      };
      loop();
      cleanup = () => {
        cancelAnimationFrame(raf);
        controls.dispose();
        loaded.dispose();
        renderer.dispose();
      };
    }).catch(() => {}); // a part that cannot be loaded leaves the canvas empty
    return () => {
      stop = true;
      cleanup();
    };
  }, [manifest]);

  if (!model && level === "certain") return null; // no precision models here: a notice at the start says why
  const status = model?.status ?? "waiting";
  return (
    <div className="entry-part">
      <div className="profile-head">
        <span className="card-level">{t("hologram.title", lang)}</span>
        {manifest && <span className="tag">{sourceTag(manifest, lang)}</span>}
        {manifest && (
          <button type="button" className="icon-button" aria-label={t("hologram.full", lang)}
            title={t("hologram.full", lang)} onClick={() => showFullscreen(name)}>⤢</button>
        )}
      </div>
      {manifest ? (
        <>
          <canvas ref={canvas} className="hologram-canvas" />
          <p className="hologram-size">{formatSize(manifest.size_mm, lang)}</p>
        </>
      ) : (
        <div className="model-progress" data-status={status}>
          <p className="profile-note">{progressText(status, model?.round ?? 0, lang)}</p>
          {status === "failed" && (
            <button type="button" className="pill" onClick={() => onRebuild(name)}>{t("model.rebuild", lang)}</button>
          )}
        </div>
      )}
    </div>
  );
}
