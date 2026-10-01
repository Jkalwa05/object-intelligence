// The three.js model of a hologram (sub-projects 3 and 5): Claude's primitives, the photo of the object on the side
// that faces the viewer, and for the full-screen view the measure lines and a numbered name tag on every part.

import * as THREE from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { CSS2DObject } from "three/examples/jsm/renderers/CSS2DRenderer.js";
import type { Lang, ShapeMsg } from "../protocol";
import { clearGrey, millimetres, outlinePoints, partGeometry, type PartGeometry } from "./shapeMath";

export const EDGE = 0x30d158; // the green of the object in your hand
const EDGE_ANGLE = 10; // degrees: low enough that the soft corners of a rounded box still get their outline
const ROUND = 48; // segments around round parts: 7.5° steps stay below EDGE_ANGLE, so only their rims are drawn

function geometryOf(g: PartGeometry): THREE.BufferGeometry {
  switch (g.kind) {
    case "box":
      return new THREE.BoxGeometry(g.args[0], g.args[1], g.args[2]);
    case "rounded_box":
      return new RoundedBoxGeometry(g.args[0], g.args[1], g.args[2], 3, g.args[3]);
    case "cylinder":
    case "cone":
      return new THREE.CylinderGeometry(g.args[0], g.args[1], g.args[2], ROUND, 1);
    case "sphere":
      return new THREE.SphereGeometry(g.args[0], ROUND, ROUND / 2);
    case "capsule":
      return new THREE.CapsuleGeometry(g.args[0], g.args[1], 8, ROUND);
  }
}

export interface Model {
  group: THREE.Group;
  bounds: THREE.Box3;
  dispose(): void;
}

export function buildModel(shape: ShapeMsg): Model {
  const group = new THREE.Group();
  const garbage: { dispose(): void }[] = [];
  shape.parts.forEach((part, index) => {
    const g = partGeometry(part);
    const geometry = geometryOf(g);
    const round = outlinePoints(g);
    const edges = round
      ? new THREE.BufferGeometry().setFromPoints(round.map(([x, y, z]) => new THREE.Vector3(x, y, z)))
      : new THREE.EdgesGeometry(geometry, EDGE_ANGLE);
    const fill = new THREE.MeshBasicMaterial({ color: g.color, transparent: true, opacity: 0.28, depthWrite: false });
    const line = new THREE.LineBasicMaterial({ color: EDGE, transparent: true, opacity: 0.85 });
    const piece = new THREE.Group();
    piece.add(new THREE.Mesh(geometry, fill), new THREE.LineSegments(edges, line));
    piece.scale.set(...g.scale);
    piece.position.set(...g.position);
    piece.rotation.set(...g.rotation);
    piece.userData.part = index;
    group.add(piece);
    garbage.push(geometry, edges, fill, line);
  });
  group.updateMatrixWorld(true);
  const bounds = new THREE.Box3().setFromObject(group);
  return { group, bounds, dispose: () => garbage.forEach((g) => g.dispose()) };
}

// The photo of the object, its grey surroundings made transparent, on the side of the box that faces the viewer.
export async function addPhoto(model: Model, photo: string): Promise<void> {
  const image = new Image();
  image.src = `data:image/jpeg;base64,${photo}`;
  await image.decode();
  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  const context = canvas.getContext("2d");
  if (!context) return;
  context.drawImage(image, 0, 0);
  const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
  clearGrey(pixels.data);
  context.putImageData(pixels, 0, 0);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const size = model.bounds.getSize(new THREE.Vector3());
  const center = model.bounds.getCenter(new THREE.Vector3());
  const plane = new THREE.PlaneGeometry(size.x, size.y);
  const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false });
  const mesh = new THREE.Mesh(plane, material); // front side only: from behind the hologram stays
  mesh.position.set(center.x, center.y, model.bounds.max.z + 0.3);
  model.group.add(mesh);
  const before = model.dispose;
  model.dispose = () => {
    before();
    plane.dispose();
    material.dispose();
    texture.dispose();
  };
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
export function addLabels(model: Model, shape: ShapeMsg, lang: Lang): Pin[] {
  const { min, max } = model.bounds;
  const extent = model.bounds.getSize(new THREE.Vector3());
  const size = shape.size_mm ?? [extent.x, extent.y, extent.z];
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
    model.group.add(text);
  }
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  const material = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.7 });
  model.group.add(new THREE.LineSegments(geometry, material));
  const pieces = model.group.children.filter((piece) => typeof piece.userData.part === "number");
  const pins = pieces.map((piece) => {
    const index: number = piece.userData.part;
    const p = pin(index, shape.parts[index].name);
    const box = new THREE.Box3().setFromObject(piece);
    const own = box.getSize(new THREE.Vector3());
    // the body's centre would sit under the parts on its face (a logo, a display): its dot goes to its lower edge
    const body = own.x >= LARGE * extent.x && own.y >= LARGE * extent.y;
    p.object.position.copy(body ? V((box.min.x + box.max.x) / 2, box.min.y, box.max.z) : piece.position);
    model.group.add(p.object);
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
