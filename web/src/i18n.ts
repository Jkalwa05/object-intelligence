// The browser's fixed texts; everything the voice says comes from the server (oi/lines.py).

import type { Lang } from "./protocol";

const TEXTS = {
  "level.certain": { de: "SICHER", en: "CERTAIN" },
  "level.likely": { de: "WAHRSCHEINLICH", en: "LIKELY" },
  "level.unsure": { de: "UNSICHER", en: "UNSURE" },
  "level.category_only": { de: "NUR KATEGORIE", en: "CATEGORY ONLY" },
  analysing: { de: "ANALYSIERE …", en: "ANALYSING …" },
  recheck: { de: "Neu prüfen", en: "Check again" },
  pickOne: { de: "Welches ist es? Tippe es an.", en: "Which one is it? Tap it." },
  confirmedByYou: { de: "von dir bestätigt", en: "confirmed by you" },
  showMe: { de: "Zeig mir bitte", en: "Please show me" },
  cameraDenied: {
    de: "Kein Kamerazugriff. Erlaube ihn unter Systemeinstellungen → Datenschutz & Sicherheit → Kamera.",
    en: "No camera access. Allow it in System Settings → Privacy & Security → Camera.",
  },
  retry: { de: "Erneut versuchen", en: "Try again" },
  reconnecting: { de: "Verbindung verloren, verbinde neu …", en: "Connection lost, reconnecting …" },
  replaced: { de: "In einem anderen Tab geöffnet. Lade diese Seite neu, um hier weiterzumachen.",
    en: "Opened in another tab. Reload this page to continue here." },
  voiceOn: { de: "Stimme an (M)", en: "Voice on (M)" },
  calibrating: { de: "Szene wird eingemessen …", en: "Calibrating the scene …" },
  naming: { de: "Hintergrund wird erkannt …", en: "Recognising the background …" },
  "profile.title": { de: "STECKBRIEF", en: "PROFILE" },
  "profile.byClaude": { de: "laut Claude", en: "according to Claude" },
  "profile.loading": { de: "Lade Steckbrief …", en: "Loading the profile …" },
  "profile.unknown": { de: "Zu diesem Produkt weiß ich nichts Genaues.", en: "I know nothing specific about this product." },
  "profile.error": { de: "Steckbrief gerade nicht verfügbar.", en: "The profile is not available right now." },
  "profile.released": { de: "Erschienen", en: "Released" },
  "profile.price": { de: "Preis zum Start", en: "Launch price" },
  "profile.trivia": { de: "WISSENSWERTES", en: "GOOD TO KNOW" },
  "sidebar.title": { de: "OBJEKTE", en: "OBJECTS" },
  "hologram.title": { de: "HOLOGRAMM", en: "HOLOGRAM" },
  "hologram.simplified": { de: "vereinfacht · laut Claude", en: "simplified · according to Claude" },
  "hologram.loading": { de: "Baue Hologramm …", en: "Building the hologram …" },
  "hologram.unknown": { de: "Für dieses Objekt kenne ich keine Form.", en: "I know no shape for this object." },
  "hologram.error": { de: "Hologramm gerade nicht verfügbar.", en: "The hologram is not available right now." },
  "tel.fpsVideo": { de: "Video", en: "Video" },
  "tel.fpsProcessed": { de: "Verarbeitet", en: "Processed" },
  "tel.detMs": { de: "Detektor", en: "Detector" },
  "tel.idLast": { de: "Letzte ID", en: "Last ID" },
  "tel.sharpness": { de: "Schärfe", en: "Sharpness" },
  "tel.calls": { de: "Aufrufe", en: "Calls" },
  "tel.cost": { de: "Kosten", en: "Cost" },
  "tel.model": { de: "Modell", en: "Model" },
  "tel.mode": { de: "Modus", en: "Mode" },
  "tel.dropped": { de: "Verworfen", en: "Dropped" },
  "tel.shares": { de: "Anteile", en: "Shares" },
  "tel.gate": { de: "Prüfung", en: "Check" },
  "gate.ok": { de: "ok", en: "ok" },
  "gate.blurry": { de: "zu unscharf", en: "too blurry" },
  "gate.cut": { de: "abgeschnitten", en: "cut off" },
  "gate.small": { de: "zu klein", en: "too small" },
  "gate.person": { de: "Person/Gesicht", en: "person/face" },
  "gate.lower": { de: "vor dem Gesicht", en: "in front of the face" },
} satisfies Record<string, Record<Lang, string>>;

export type I18nKey = keyof typeof TEXTS;
export const I18N_KEYS = Object.keys(TEXTS) as I18nKey[];

export function t(key: I18nKey, lang: Lang): string {
  return TEXTS[key][lang];
}
