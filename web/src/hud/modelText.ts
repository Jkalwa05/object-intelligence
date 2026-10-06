// The precision model's words in the sidebar (sub-project 6): progress, the source badge, the kind of a measure.

import type { Lang, MeasureKind, ModelManifest, ModelStatus, PhotoView } from "../protocol";

const CHECK_ROUNDS = 2; // the server's default (OI_MODEL_CHECK_ROUNDS)

const PROGRESS: Record<ModelStatus | "waiting", Record<Lang, string>> = {
  waiting: { de: "Das 3D-Modell entsteht, sobald das Objekt sicher erkannt ist.",
    en: "The 3D model is built once the object is identified for certain." },
  queued: { de: "Wartet auf das vorherige Modell …", en: "Waiting for the previous model …" },
  researching: { de: "Recherchiere Maße …", en: "Researching dimensions …" },
  drawing: { de: "Lade Zeichnung und Fotos …", en: "Loading the drawing and photos …" },
  measuring: { de: "Vermesse die Teile auf Zeichnung und Fotos …",
    en: "Measuring the parts on drawing and photos …" },
  modeling: { de: "Baue CAD-Modell …", en: "Building the CAD model …" },
  building: { de: "Berechne Geometrie …", en: "Computing the geometry …" },
  checking: { de: "Prüfe gegen Maße, Zeichnung und Fotos (Runde {round}/{rounds}) …",
    en: "Checking against measures, drawing and photos (round {round}/{rounds}) …" },
  ready: { de: "", en: "" },
  failed: { de: "Modell gerade nicht möglich.", en: "The model is not possible right now." },
  limit: { de: "Höchstens 5 neue Modelle pro Sitzung.", en: "At most 5 new models per session." },
};

const KINDS: Record<MeasureKind, Record<Lang, string>> = {
  drawing: { de: "Zeichnung", en: "drawing" },
  datasheet: { de: "Datenblatt", en: "data sheet" },
  estimate: { de: "geschätzt", en: "estimated" },
};

const VIEWS: Record<PhotoView, Record<Lang, string>> = {
  front: { de: "vorn", en: "front" },
  back: { de: "hinten", en: "back" },
  "side-front-left": { de: "Seite", en: "side" },
  "side-front-right": { de: "Seite", en: "side" },
  top: { de: "oben", en: "top" },
};

const SECOND_LEVEL = new Set(["co", "com", "org", "net", "gov", "ac", "edu"]); // amazon.co.uk, not co.uk

// The site's own domain without subdomains: "support.apple.com" -> "apple.com".
export function domain(url: string): string {
  let host: string;
  try {
    host = new URL(url).hostname;
  } catch {
    return url;
  }
  const labels = host.split(".");
  const keep = labels.length >= 3 && SECOND_LEVEL.has(labels.at(-2)!) && labels.at(-1)!.length === 2 ? 3 : 2;
  return labels.slice(-keep).join(".");
}

// „CAD · Maße laut apple.com“ when the overall size has a source, else „CAD · Maße geschätzt“; then how many parts were
// measured on the drawing and the photos (sub-project 7).
export function sourceTag(m: ModelManifest, lang: Lang): string {
  const index = m.sheet.size_source;
  const source = index === null ? undefined : m.sheet.sources[index];
  const sizes = !source ? (lang === "de" ? "CAD · Maße geschätzt" : "CAD · dimensions estimated")
    : lang === "de" ? `CAD · Maße laut ${domain(source.url)}` : `CAD · dimensions per ${domain(source.url)}`;
  const count = m.part_map.length;
  if (!count) return sizes;
  return lang === "de" ? `${sizes} · ${count} Teile vermessen`
    : `${sizes} · ${count} ${count === 1 ? "part" : "parts"} measured`;
}

export function progressText(status: ModelStatus | "waiting", round: number, lang: Lang): string {
  return PROGRESS[status][lang].replace("{round}", String(round)).replace("{rounds}", String(CHECK_ROUNDS));
}

// What the 3D view is built from: a finished build of one product. Keeping the model (sub-project 7) sends a new
// manifest with the same geometry, and the view must not reload for it.
export function geometryKey(m: ModelManifest): string {
  return `${m.slug}@${m.created}`;
}

export function viewText(view: PhotoView, lang: Lang): string {
  return VIEWS[view][lang];
}

export function kindText(kind: MeasureKind, lang: Lang): string {
  return KINDS[kind][lang];
}
