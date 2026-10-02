import { expect, test } from "vitest";
import type { ModelManifest } from "../protocol";
import { domain, kindText, progressText, sourceTag } from "./modelText";

const manifest = (sizeSource: number | null): ModelManifest => ({
  model: "Apple iPhone 14", slug: "apple-iphone-14", parts: [], size_mm: [71.5, 146.7, 7.8],
  sheet: { size_mm: [71.5, 146.7, 7.8], size_source: sizeSource, measures: [], features: [], drawing: null,
    sources: [{ title: "Apple", url: "https://www.apple.com/de/iphone-14/specs/" }] },
  drawing_pages: [], notes: "", verdict: "good", rounds: 1, cost_usd: 0.9, created: "",
});

test("domain and badge", () => {
  expect(domain("https://www.apple.com/de/iphone-14/specs/")).toBe("apple.com");
  expect(domain("https://developer.apple.com/accessories/")).toBe("apple.com");
  expect(domain("https://support.apple.com/en-in/111850")).toBe("apple.com");
  expect(domain("https://www.amazon.co.uk/dp/1")).toBe("amazon.co.uk");
  expect(domain("kaputt")).toBe("kaputt");
  expect(sourceTag(manifest(0), "de")).toBe("CAD · Maße laut apple.com");
  expect(sourceTag(manifest(0), "en")).toBe("CAD · dimensions per apple.com");
  expect(sourceTag(manifest(null), "de")).toBe("CAD · Maße geschätzt");
  expect(sourceTag(manifest(5), "de")).toBe("CAD · Maße geschätzt"); // an index outside the sources
});

test("progress texts", () => {
  expect(progressText("waiting", 0, "de")).toBe("Das 3D-Modell entsteht, sobald das Objekt sicher erkannt ist.");
  expect(progressText("queued", 0, "de")).toBe("Wartet auf das vorherige Modell …");
  expect(progressText("researching", 0, "de")).toBe("Recherchiere Maße …");
  expect(progressText("drawing", 0, "de")).toBe("Lese technische Zeichnung …");
  expect(progressText("modeling", 0, "de")).toBe("Baue CAD-Modell …");
  expect(progressText("building", 0, "de")).toBe("Berechne Geometrie …");
  expect(progressText("checking", 1, "de")).toBe("Prüfe gegen Zeichnung und Foto (Runde 1/2) …");
  expect(progressText("failed", 0, "de")).toBe("Modell gerade nicht möglich.");
  expect(progressText("limit", 0, "de")).toBe("Höchstens 5 neue Modelle pro Sitzung.");
  expect(progressText("checking", 2, "en")).toBe("Checking against drawing and photo (round 2/2) …");
});

test("kind texts", () => {
  expect([kindText("drawing", "de"), kindText("datasheet", "de"), kindText("estimate", "de")])
    .toEqual(["Zeichnung", "Datenblatt", "geschätzt"]);
  expect(kindText("estimate", "en")).toBe("estimated");
});
