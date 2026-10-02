// The precision model's words in the sidebar (sub-project 6): progress, the source badge, the kind of a measure.

import type { Lang, MeasureKind, ModelManifest, ModelStatus } from "../protocol";

const CHECK_ROUNDS = 2; // the server's default (OI_MODEL_CHECK_ROUNDS)

const PROGRESS: Record<ModelStatus | "waiting", Record<Lang, string>> = {
  waiting: { de: "Das 3D-Modell entsteht, sobald das Objekt sicher erkannt ist.",
    en: "The 3D model is built once the object is identified for certain." },
  queued: { de: "Wartet auf das vorherige Modell …", en: "Waiting for the previous model …" },
  researching: { de: "Recherchiere Maße …", en: "Researching dimensions …" },
  drawing: { de: "Lese technische Zeichnung …", en: "Reading the technical drawing …" },
  modeling: { de: "Baue CAD-Modell …", en: "Building the CAD model …" },
  building: { de: "Berechne Geometrie …", en: "Computing the geometry …" },
  checking: { de: "Prüfe gegen Zeichnung und Foto (Runde {round}/{rounds}) …",
    en: "Checking against drawing and photo (round {round}/{rounds}) …" },
  ready: { de: "", en: "" },
  failed: { de: "Modell gerade nicht möglich.", en: "The model is not possible right now." },
  limit: { de: "Höchstens 5 neue Modelle pro Sitzung.", en: "At most 5 new models per session." },
};

const KINDS: Record<MeasureKind, Record<Lang, string>> = {
  drawing: { de: "Zeichnung", en: "drawing" },
  datasheet: { de: "Datenblatt", en: "data sheet" },
  estimate: { de: "geschätzt", en: "estimated" },
};

export function domain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

// „CAD · Maße laut apple.com“ when the overall size has a source, else „CAD · Maße geschätzt“.
export function sourceTag(m: ModelManifest, lang: Lang): string {
  const index = m.sheet.size_source;
  const source = index === null ? undefined : m.sheet.sources[index];
  if (!source) return lang === "de" ? "CAD · Maße geschätzt" : "CAD · dimensions estimated";
  return lang === "de" ? `CAD · Maße laut ${domain(source.url)}` : `CAD · dimensions per ${domain(source.url)}`;
}

export function progressText(status: ModelStatus | "waiting", round: number, lang: Lang): string {
  return PROGRESS[status][lang].replace("{round}", String(round)).replace("{rounds}", String(CHECK_ROUNDS));
}

export function kindText(kind: MeasureKind, lang: Lang): string {
  return KINDS[kind][lang];
}
