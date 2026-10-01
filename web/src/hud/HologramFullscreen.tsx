// The hologram in full screen (sub-project 5): the large model with measure lines for width, height and depth and
// a numbered name tag on every part, next to everything technical about the object. Esc or ✕ closes it.

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { CSS2DRenderer } from "three/examples/jsm/renderers/CSS2DRenderer.js";
import { t, type I18nKey } from "../i18n";
import type { IdentityMsg, Lang, ProfileMsg, ShapeMsg } from "../protocol";
import { addLabels, buildModel, type Pin } from "./hologramScene";
import { fitDistance, formatSize, partDescription, spread } from "./shapeMath";

const FOV = 35;
const VIEW = new THREE.Vector3(0.55, 0.35, 0.8).normalize();
const DOT = 18; // px, the numbered dot of a name tag (styles.css .part-dot)
const TAG_LEFT = 15; // px from the dot's centre to its name (styles.css .part-tag)
const TAG_GAP = 4; // px between name tags and dots

interface Props {
  shape: ShapeMsg;
  lang: Lang;
  identity: IdentityMsg;
  profile?: ProfileMsg;
  onClose(): void;
}

export default function HologramFullscreen({ shape, lang, identity, profile, onClose }: Props) {
  const stage = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const pins = useRef<Pin[]>([]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    const el = canvas.current;
    const box = stage.current;
    if (!el || !box) return;
    let width = box.clientWidth, height = box.clientHeight;
    const renderer = new THREE.WebGLRenderer({ canvas: el, antialias: true, alpha: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    const labels = new CSS2DRenderer();
    labels.domElement.className = "label-layer";
    box.appendChild(labels.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(FOV, width / height, 1, 50000);
    camera.position.copy(VIEW).multiplyScalar(fitDistance(shape.parts, FOV) * 1.35); // room for the measures
    const resize = () => {
      width = box.clientWidth;
      height = box.clientHeight;
      renderer.setSize(width, height, false);
      labels.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    resize();
    window.addEventListener("resize", resize);
    const model = buildModel(shape);
    pins.current = addLabels(model, shape, lang);
    scene.add(model.group);
    const controls = new OrbitControls(camera, labels.domElement);
    controls.enableDamping = true;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.8;
    const anchor = new THREE.Vector3();
    const place = () => { // name tags keep clear of each other and of every numbered dot
      const at = pins.current.map(({ object }) => {
        anchor.setFromMatrixPosition(object.matrixWorld).project(camera);
        return [((anchor.x + 1) / 2) * width, ((1 - anchor.y) / 2) * height];
      });
      const dots = at.map(([x, y]) => ({ x: x - DOT / 2, y: y - DOT / 2, w: DOT, h: DOT }));
      const tags = at.map(([x, y], i) => ({ x: x + TAG_LEFT, y: y - DOT / 2, w: pins.current[i].tag.offsetWidth, h: DOT }));
      spread(tags, TAG_GAP, dots).forEach((down, i) => pins.current[i].move(down));
    };
    let raf = 0;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      controls.update();
      renderer.render(scene, camera);
      labels.render(scene, camera);
      place();
    };
    loop();
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      controls.dispose();
      model.dispose();
      renderer.dispose();
      labels.domElement.remove();
      pins.current = [];
    };
  }, [shape, lang]);

  const level = identity.level ? t(`level.${identity.level}` as I18nKey, lang) : "";
  const highlight = (part: number | null) => {
    for (const p of pins.current) p.object.element.classList.toggle("active", p.object.element.dataset.part === String(part));
  };
  return createPortal(
    <div className="fullscreen" role="dialog" aria-label={identity.display_name}>
      <div ref={stage} className="fullscreen-stage">
        <canvas ref={canvas} className="fullscreen-canvas" />
      </div>
      <aside className="fullscreen-data glass">
        <button type="button" className="icon-button close" aria-label={t("close", lang)} onClick={onClose}>✕</button>
        <div className="card-level">{level}</div>
        <h2 className="fullscreen-name">{identity.display_name}</h2>
        <p className="fullscreen-size">{formatSize(shape.size_mm, lang)}</p>
        <span className="tag">{t("hologram.simplified", lang)}</span>
        <div className="card-level section">{t("hologram.parts", lang)}</div>
        <ol className="parts">
          {shape.parts.map((part, i) => (
            <li key={`${i}-${part.name}`} onMouseEnter={() => highlight(i)} onMouseLeave={() => highlight(null)}>
              <span className="part-dot">{i + 1}</span>
              <span><b>{part.name}</b><small>{partDescription(part, lang)}</small></span>
            </li>
          ))}
        </ol>
        {profile?.status === "ready" && (
          <>
            <div className="card-level section">{t("profile.title", lang)}</div>
            <p className="profile-summary">{profile.summary}</p>
            <dl className="facts">
              {profile.facts.map((fact, i) => (
                <div key={`${i}-${fact.label}`}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>
              ))}
              {profile.released && <div><dt>{t("profile.released", lang)}</dt><dd>{profile.released}</dd></div>}
              {profile.launch_price && <div><dt>{t("profile.price", lang)}</dt><dd>{profile.launch_price}</dd></div>}
            </dl>
            {profile.trivia.length > 0 && (
              <>
                <div className="card-level section">{t("profile.trivia", lang)}</div>
                <ul className="trivia">{profile.trivia.map((x) => <li key={x}>{x}</li>)}</ul>
              </>
            )}
          </>
        )}
      </aside>
    </div>,
    document.body,
  );
}
