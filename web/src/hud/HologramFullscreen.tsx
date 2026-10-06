// The precision model in full screen (sub-projects 5 and 6): the large CAD model with measure lines for width,
// height and depth, next to its parts, the researched dimensions with their sources, and the profile. A click on a
// part in the list puts its numbered name tag on the model; "Alle abwählen" takes all of them away. "Behalten" keeps
// the model, so it comes again instead of being built anew (sub-project 7). Esc or ✕ closes it.

import { useEffect, useMemo, useRef } from "react";
import { createPortal } from "react-dom";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { type CSS2DObject, CSS2DRenderer } from "three/examples/jsm/renderers/CSS2DRenderer.js";
import { t, type I18nKey } from "../i18n";
import type { IdentityMsg, Lang, ModelMsg, ProfileMsg } from "../protocol";
import { useHud } from "../store";
import { addLabels, loadModel, type Pin } from "./hologramScene";
import { domain, geometryKey, kindText, photoText, sourceTag } from "./modelText";
import { fitDistance, formatSize, millimetres, partSize, spread, type Vec3 } from "./shapeMath";

const FOV = 35;
const VIEW = new THREE.Vector3(0.55, 0.35, 0.8).normalize();
const DOT = 18; // px, the numbered dot of a name tag (styles.css .part-dot)
const TAG_LEFT = 15; // px from the dot's centre to its name (styles.css .part-tag)
const TAG_GAP = 4; // px between name tags and dots

interface Props {
  model: ModelMsg; // ready, with its manifest
  lang: Lang;
  identity: IdentityMsg;
  profile?: ProfileMsg;
  onClose(): void;
  onKeep(model: string, kept: boolean): void;
}

export default function HologramFullscreen({ model, lang, identity, profile, onClose, onKeep }: Props) {
  const manifest = model.manifest!;
  const geometry = useMemo(() => manifest, [geometryKey(manifest)]); // „Behalten“ must not reload the view
  const stage = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const pins = useRef<Pin[]>([]);
  const measures = useRef<CSS2DObject[]>([]);
  const labelled = useHud((s) => s.labelled);
  const toggleLabel = useHud((s) => s.toggleLabel);
  const clearLabels = useHud((s) => s.clearLabels);

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
    let stop = false;
    let cleanup = () => {};
    void loadModel(geometry).then((loaded) => {
      if (stop) return loaded.dispose();
      let width = box.clientWidth, height = box.clientHeight;
      const renderer = new THREE.WebGLRenderer({ canvas: el, antialias: true, alpha: true });
      renderer.setPixelRatio(window.devicePixelRatio || 1);
      const labels = new CSS2DRenderer();
      labels.domElement.className = "label-layer";
      box.appendChild(labels.domElement);
      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(FOV, width / height, 1, 50000);
      const size = loaded.bounds.getSize(new THREE.Vector3()).toArray() as Vec3;
      camera.position.copy(VIEW).multiplyScalar(fitDistance(size, FOV) * 1.35); // room for the measures
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
      ({ pins: pins.current, measures: measures.current } = addLabels(loaded, geometry, lang));
      scene.add(loaded.group);
      const controls = new OrbitControls(camera, labels.domElement);
      controls.enableDamping = true;
      controls.autoRotate = true;
      controls.autoRotateSpeed = 0.8;
      const anchor = new THREE.Vector3();
      const show = () => { // only the parts chosen in the list carry their name tag
        const chosen = useHud.getState().labelled;
        pins.current.forEach((p, i) => { p.object.visible = chosen.includes(i); });
      };
      const place = () => { // the shown name tags keep clear of each other and of every shown numbered dot
        const shown = pins.current.filter((p) => p.object.visible);
        const at = shown.map(({ object }) => {
          anchor.setFromMatrixPosition(object.matrixWorld).project(camera);
          return [((anchor.x + 1) / 2) * width, ((1 - anchor.y) / 2) * height];
        });
        const dots = at.map(([x, y]) => ({ x: x - DOT / 2, y: y - DOT / 2, w: DOT, h: DOT }));
        const tags = at.map(([x, y], i) => ({ x: x + TAG_LEFT, y: y - DOT / 2, w: shown[i].tag.offsetWidth, h: DOT }));
        const labels = measures.current.map((label) => { // the measure capsules, centred on their point
          anchor.setFromMatrixPosition(label.matrixWorld).project(camera);
          const w = label.element.offsetWidth, h = label.element.offsetHeight;
          return { x: ((anchor.x + 1) / 2) * width - w / 2, y: ((1 - anchor.y) / 2) * height - h / 2, w, h };
        });
        spread(tags, TAG_GAP, [...dots, ...labels]).forEach((down, i) => shown[i].move(down));
      };
      let raf = 0;
      const loop = () => {
        raf = requestAnimationFrame(loop);
        controls.update();
        show();
        renderer.render(scene, camera);
        labels.render(scene, camera);
        place();
      };
      loop();
      cleanup = () => {
        cancelAnimationFrame(raf);
        window.removeEventListener("resize", resize);
        controls.dispose();
        loaded.dispose();
        renderer.dispose();
        labels.domElement.remove();
        pins.current = [];
      };
    }).catch(() => {}); // a part that cannot be loaded leaves the stage empty
    return () => {
      stop = true;
      cleanup();
    };
  }, [geometry, lang]);

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
        <p className="fullscreen-size">{formatSize(manifest.size_mm, lang)}</p>
        <div className="fullscreen-tags">
          <span className="tag">{sourceTag(manifest, lang)}</span>
          <button type="button" className={manifest.kept ? "pill kept" : "pill"} aria-pressed={manifest.kept}
            onClick={() => onKeep(manifest.model, !manifest.kept)}>
            {t(manifest.kept ? "model.kept" : "model.keep", lang)}
          </button>
        </div>
        <div className="card-level section parts-head">
          {t("hologram.parts", lang)}
          {labelled.length > 0
            ? <button type="button" className="pill" onClick={clearLabels}>{t("hologram.clear", lang)}</button>
            : <span>{t("hologram.choose", lang)}</span>}
        </div>
        <ol className="parts">
          {manifest.parts.map((part, i) => (
            <li key={`${i}-${part.name}`}>
              <button type="button" aria-pressed={labelled.includes(i)} onClick={() => toggleLabel(i)}
                onMouseEnter={() => highlight(i)} onMouseLeave={() => highlight(null)}>
                <span className="part-dot">{i + 1}</span>
                <span><b>{part.name}</b><small>{formatSize(partSize(part), lang)}</small></span>
              </button>
            </li>
          ))}
        </ol>
        {manifest.notes && <p className="profile-note">{manifest.notes}</p>}
        {manifest.sheet.measures.length > 0 && (
          <>
            <div className="card-level section">{t("hologram.measures", lang)}</div>
            <dl className="facts measures">
              {manifest.sheet.measures.map((m, i) => {
                const source = m.source === null ? undefined : manifest.sheet.sources[m.source];
                return (
                  <div key={`${i}-${m.label}`}>
                    <dt>{m.label}</dt>
                    <dd>
                      {millimetres(m.value_mm, lang)} mm <small>{kindText(m.kind, lang)}
                        {source && <> · <a href={source.url} target="_blank" rel="noreferrer">{domain(source.url)}</a></>}
                      </small>
                    </dd>
                  </div>
                );
              })}
            </dl>
          </>
        )}
        {manifest.sheet.sources.length + manifest.sheet.photos.length > 0 && (
          <>
            <div className="card-level section">{t("hologram.sources", lang)}</div>
            <ul className="sources">
              {manifest.sheet.sources.map((source) => (
                <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a></li>
              ))}
              {manifest.sheet.photos.map((photo) => (
                <li key={photo.url}>
                  <a href={photo.url} target="_blank" rel="noreferrer">
                    {photoText(photo, lang)} · {domain(photo.url)}
                  </a>
                </li>
              ))}
            </ul>
          </>
        )}
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
