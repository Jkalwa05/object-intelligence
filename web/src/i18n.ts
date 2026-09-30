// The browser's fixed texts; everything the voice says comes from the server (oi/lines.py).

import type { Lang } from "./protocol";

const TEXTS = {
  "level.certain": { de: "SICHER", en: "CERTAIN" },
  "level.likely": { de: "WAHRSCHEINLICH", en: "LIKELY" },
  "level.unsure": { de: "UNSICHER", en: "UNSURE" },
  "level.category_only": { de: "NUR KATEGORIE", en: "CATEGORY ONLY" },
  analysing: { de: "ANALYSIERE …", en: "ANALYSING …" },
  recheck: { de: "Neu prüfen", en: "Check again" },
  showMe: { de: "Zeig mir bitte", en: "Please show me" },
  cameraDenied: {
    de: "Kein Kamerazugriff. Erlaube ihn unter Systemeinstellungen → Datenschutz & Sicherheit → Kamera.",
    en: "No camera access. Allow it in System Settings → Privacy & Security → Camera.",
  },
  retry: { de: "Erneut versuchen", en: "Try again" },
  reconnecting: { de: "Verbindung verloren, verbinde neu …", en: "Connection lost, reconnecting …" },
  replaced: { de: "In einem anderen Tab geöffnet. Lade diese Seite neu, um hier weiterzumachen.",
    en: "Opened in another tab. Reload this page to continue here." },
  muted: { de: "Stimme aus (M)", en: "Voice off (M)" },
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
  "gate.unsteady": { de: "zu wackelig", en: "too shaky" },
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
