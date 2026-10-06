import { expect, test } from "vitest";
import type { MeasuredPart, ModelManifest, ProfileBand } from "../protocol";
import { domain, geometryKey, kindText, photoText, progressText, sourceTag, viewText } from "./modelText";

const band = (sources: number): ProfileBand => ({ y: [43.65, 48.5], x: [-20, 20], z: null, sources });

const manifest = (sizeSource: number | null, measured = 0, profile: ProfileBand[] = []): ModelManifest => ({
  model: "Apple iPhone 14", slug: "apple-iphone-14", parts: [], size_mm: [71.5, 146.7, 7.8],
  sheet: { size_mm: [71.5, 146.7, 7.8], size_source: sizeSource, measures: [], features: [], drawing: null,
    sources: [{ title: "Apple", url: "https://www.apple.com/de/iphone-14/specs/" }], photos: [] },
  drawing_pages: [], notes: "", verdict: "good", rounds: 1, cost_usd: 0.9, created: "", kept: false,
  part_map: Array.from({ length: measured }, (_, i): MeasuredPart => ({ name: `Teil ${i}`, x: [0, 1], y: null, z: null,
    views: 1 })), profile,
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
  expect(sourceTag(manifest(0, 18), "de")).toBe("CAD · Maße laut apple.com · 18 Teile vermessen");
  expect(sourceTag(manifest(0, 1), "en")).toBe("CAD · dimensions per apple.com · 1 part measured");
  expect(sourceTag(manifest(0, 18, [band(2), band(3)]), "de"))
    .toBe("CAD · Maße laut apple.com · 18 Teile vermessen · Umriss aus 3 Bildern");
  expect(sourceTag(manifest(null, 0, [band(1)]), "de")).toBe("CAD · Maße geschätzt · Umriss aus 1 Bild");
  expect(sourceTag(manifest(0, 0, [band(3)]), "en")).toBe("CAD · dimensions per apple.com · outline from 3 pictures");
});

test("progress texts", () => {
  expect(progressText("waiting", 0, "de")).toBe("Das 3D-Modell entsteht, sobald das Objekt sicher erkannt ist.");
  expect(progressText("queued", 0, "de")).toBe("Wartet auf das vorherige Modell …");
  expect(progressText("researching", 0, "de")).toBe("Recherchiere Maße …");
  expect(progressText("drawing", 0, "de")).toBe("Lade Zeichnung und Fotos …");
  expect(progressText("measuring", 0, "de")).toBe("Vermesse Teile und Umriss …");
  expect(progressText("measuring", 0, "en")).toBe("Measuring the parts and the outline …");
  expect(progressText("modeling", 0, "de")).toBe("Baue CAD-Modell …");
  expect(progressText("building", 0, "de")).toBe("Berechne Geometrie …");
  expect(progressText("checking", 1, "de")).toBe("Prüfe gegen Maße, Zeichnung und Fotos (Runde 1/2) …");
  expect(progressText("failed", 0, "de")).toBe("Modell gerade nicht möglich.");
  expect(progressText("limit", 0, "de")).toBe("Höchstens 5 neue Modelle pro Sitzung.");
  expect(progressText("checking", 2, "en")).toBe("Checking against measures, drawing and photos (round 2/2) …");
});

test("view texts", () => {
  expect([viewText("front", "de"), viewText("back", "de"), viewText("side-front-left", "de"),
    viewText("side-front-right", "de"), viewText("top", "de")]).toEqual(["vorn", "hinten", "Seite", "Seite", "oben"]);
  expect(viewText("top", "en")).toBe("top");
  expect(photoText({ url: "https://cdn.example/a.jpg", view: "front" }, "de")).toBe("Foto (vorn)");
  expect(photoText({ url: "https://cdn.example/a.jpg", view: null }, "de")).toBe("Foto"); // found on a page
  expect(photoText({ url: "https://cdn.example/a.jpg", view: null }, "en")).toBe("Photo");
});

test("kind texts", () => {
  expect([kindText("drawing", "de"), kindText("datasheet", "de"), kindText("estimate", "de")])
    .toEqual(["Zeichnung", "Datenblatt", "geschätzt"]);
  expect(kindText("estimate", "en")).toBe("estimated");
});

test("the 3D view reloads only for new geometry, not when the model is kept", () => {
  const model = manifest(0);
  expect(geometryKey({ ...model, kept: true })).toBe(geometryKey(model));
  expect(geometryKey({ ...model, created: "2026-10-06T10:00:00" })).not.toBe(geometryKey(model));
  expect(geometryKey({ ...model, slug: "sony-dualshock-3" })).not.toBe(geometryKey(model));
});
