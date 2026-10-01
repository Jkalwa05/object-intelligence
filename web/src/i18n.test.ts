import { expect, test } from "vitest";
import { I18N_KEYS, t } from "./i18n";

test("every text exists in German and English", () => {
  expect(I18N_KEYS.length).toBeGreaterThan(10);
  for (const key of I18N_KEYS) {
    expect(t(key, "de")).not.toBe("");
    expect(t(key, "en")).not.toBe("");
  }
  expect(t("recheck", "de")).toBe("Neu prüfen");
  expect(t("level.certain", "en")).toBe("CERTAIN");
});

test("every quality check has a readable name", () => {
  for (const key of ["gate.ok", "gate.blurry", "gate.cut", "gate.small", "gate.person", "gate.lower"]) {
    expect(I18N_KEYS).toContain(key);
  }
  expect(t("gate.blurry", "de")).toBe("zu unscharf");
});

test("calibration text", () => expect(t("calibrating", "de")).toBe("Szene wird eingemessen …"));

test("naming text", () => expect(t("naming", "de")).toBe("Hintergrund wird erkannt …"));

test("profile texts", () => {
  expect(t("profile.byClaude", "de")).toBe("laut Claude");
  expect(t("profile.unknown", "de")).toBe("Zu diesem Produkt weiß ich nichts Genaues.");
});

test("the badge says when the voice is on", () => expect(t("voiceOn", "de")).toBe("Stimme an (M)"));
