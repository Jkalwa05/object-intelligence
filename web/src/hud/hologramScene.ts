// The three.js model of a precision model (sub-projects 3, 5 and 6): the CAD parts (STL from the server) in the
// hologram look, and for the full-screen view the measure lines and a numbered name tag on every part.

import * as THREE from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { CSS2DObject } from "three/examples/jsm/renderers/CSS2DRenderer.js";
import type { Lang, ModelManifest } from "../protocol";
import { millimetres, partCenter, partSize } from "./shapeMath";

export const EDGE = 0x30d158; // the green of the object in your hand
const EDGE_ANGLE = 20; // degrees: CAD meshes are finely divided; only real edges get a line, roundings stay calm

export interface Model {
  group: THREE.Group; // what goes into the scene: centred on the origin
  content: THREE.Group; // the parts in CAD millimetres; labels go here too
  bounds: THREE.Box3; // in CAD millimetres
  dispose(): void;
}

export function boundsOf(manifest: ModelManifest): THREE.Box3 {
  const box = new THREE.Box3();
  for (const part of manifest.parts) {
    box.expandByPoint(new THREE.Vector3(...part.min_mm)).expandByPoint(new THREE.Vector3(...part.max_mm));
  }
  return box;
}

export async function loadModel(manifest: ModelManifest): Promise<Model> {
  const loader = new STLLoader();
  const geometries = await Promise.all(manifest.parts.map((part) =>
    loader.loadAsync(`/models/${manifest.slug}/${part.file}`)));
  const content = new THREE.Group();
  const garbage: { dispose(): void }[] = [];
  geometries.forEach((geometry, index) => {
    const edges = new THREE.EdgesGeometry(geometry, EDGE_ANGLE);
    const fill = new THREE.MeshBasicMaterial({ color: manifest.parts[index].color, transparent: true, opacity: 0.28,
      depthWrite: false });
    const line = new THREE.LineBasicMaterial({ color: EDGE, transparent: true, opacity: 0.85 });
    const piece = new THREE.Group();
    piece.add(new THREE.Mesh(geometry, fill), new THREE.LineSegments(edges, line));
    piece.userData.part = index;
    content.add(piece);
    garbage.push(geometry, edges, fill, line);
  });
  const bounds = boundsOf(manifest);
  content.position.copy(bounds.getCenter(new THREE.Vector3())).negate();
  const group = new THREE.Group();
  group.add(content);
  return { group, content, bounds, dispose: () => garbage.forEach((g) => g.dispose()) };
}

function label(text: string, className: string): CSS2DObject {
  const element = document.createElement("div");
  element.className = className;
  element.textContent = text;
  return new CSS2DObject(element);
}

const LARGE = 0.6; // a part this wide and tall compared with the whole object is its body

// A part's name tag: a numbered dot on the part (the number of its line in the list next to the model) and the name
// beside it. When tags would cover each other, the name moves down and a thin line leads back to the dot.
export interface Pin {
  object: CSS2DObject;
  tag: HTMLElement;
  move(down: number): void;
}

function pin(index: number, name: string): Pin {
  const element = document.createElement("div");
  element.className = "part-pin";
  element.dataset.part = String(index);
  const dot = document.createElement("span");
  dot.className = "part-dot";
  dot.textContent = String(index + 1);
  const lead = document.createElement("span");
  lead.className = "part-lead";
  const tag = document.createElement("span");
  tag.className = "part-tag";
  tag.textContent = name;
  element.append(lead, dot, tag);
  return {
    object: new CSS2DObject(element),
    tag,
    move(down) {
      tag.style.transform = down ? `translateY(${down}px)` : "";
      lead.style.height = `${down}px`;
    },
  };
}

// Measure lines for width, height and depth along the box, and a name tag on every part (full screen).
export function addLabels(model: Model, manifest: ModelManifest, lang: Lang): Pin[] {
  const { min, max } = model.bounds;
  const extent = model.bounds.getSize(new THREE.Vector3());
  const size = manifest.size_mm;
  const gap = 0.12 * Math.max(extent.x, extent.y);
  const tick = gap * 0.35;
  const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);
  const measures: [THREE.Vector3, THREE.Vector3, THREE.Vector3, number][] = [
    [V(min.x, min.y - gap, max.z), V(max.x, min.y - gap, max.z), V(0, tick, 0), size[0]], // width
    [V(max.x + gap, min.y, max.z), V(max.x + gap, max.y, max.z), V(tick, 0, 0), size[1]], // height
    [V(max.x + gap, min.y - gap, min.z), V(max.x + gap, min.y - gap, max.z), V(0, tick, 0), size[2]], // depth
  ];
  const points: THREE.Vector3[] = [];
  for (const [from, to, across, value] of measures) {
    points.push(from, to, from.clone().sub(across), from.clone().add(across), to.clone().sub(across),
      to.clone().add(across));
    const text = label(`${millimetres(value, lang)} mm`, "measure");
    text.position.copy(from.clone().add(to).multiplyScalar(0.5));
    model.content.add(text);
  }
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  const material = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.7 });
  model.content.add(new THREE.LineSegments(geometry, material));
  const pins = manifest.parts.map((part, index) => {
    const p = pin(index, part.name);
    const [w, h] = partSize(part);
    const [cx, cy, cz] = partCenter(part);
    // the body's centre would sit under the parts on its face (a logo, a display): its dot goes to its lower edge
    const body = w >= LARGE * extent.x && h >= LARGE * extent.y;
    p.object.position.copy(body ? V(cx, part.min_mm[1], part.max_mm[2]) : V(cx, cy, cz));
    model.content.add(p.object);
    return p;
  });
  const before = model.dispose;
  model.dispose = () => {
    before();
    geometry.dispose();
    material.dispose();
  };
  return pins;
}
