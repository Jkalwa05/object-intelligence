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
