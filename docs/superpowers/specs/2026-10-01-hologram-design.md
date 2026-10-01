# Object Intelligence, Teilprojekt 3: Hologramm und Seitenleiste

Stand: 2026-10-01 · Status: mit Jonas abgestimmt („lass erstmal das Hologramm bauen“). Der echte Scan (Apple Object
Capture) ist zurückgestellt; er entfällt, wenn das Hologramm überzeugt.

## 1. Ziel

Ab „wahrscheinlich“ erscheint zu einem Produkt ein drehbares 3D-Hologramm. Es ist ein maßstabsgetreues, vereinfachtes
Modell aus Grundformen, das Claude aus seinem Wissen und dem Ausschnitt des Objekts beschreibt. Erkennung, Steckbrief
und Hologramm stehen in einer festen Seitenleiste rechts. Jeder Gegenstand bleibt dort als aufklappbarer Eintrag
angeheftet.

## 2. Entscheidungen

| Frage | Antwort |
|---|---|
| Modell | Hologramm aus Bausteinen; ein echter Scan kommt nur, falls das Hologramm nicht reicht |
| Ort | rechte Seitenleiste; ausgeklappt nur, solange das Objekt aktiv gezeigt wird, danach eingeklappt und angeheftet, per Klick (Dropdown) wieder aufklappbar |
| UI-Überarbeitung | später (Teilprojekt 5) |
| Schwebende Karte | entfällt (Ruling, Empfehlung A; Jonas ließ die Frage offen, seine Antwort „Infos … an der rechten Seitenleiste fixiert“ passt dazu). Am Objekt bleiben grüne Box, Namensschild und eine Linie zum Eintrag. |

## 3. Hologramm

- **Auslöser** wie beim Steckbrief: `Belief.product()`, also Stufe „wahrscheinlich“ oder „sicher“ auf
  Modell-Tiefe. Ein Aufruf pro Modell, gespeichert in `cache/shapes.json`; er zählt zum Budget.
- **Claude bekommt** den Modellnamen, die Kategorie und den zuletzt gesendeten Ausschnitt (nur Objekt-Pixel, wie bei
  der Erkennung). Die Antwort ist strukturiert:
  - `known`, `size_mm` [Breite, Höhe, Tiefe] und bis zu 16 `parts`;
  - jedes Teil hat `name`, `shape` (box, rounded_box, cylinder, cone, sphere, capsule), `size_mm` [x, y, z],
    `position_mm` [x, y, z], `rotation_deg` [x, y, z], `color` (#rrggbb) und `radius_mm` (nur bei rounded_box);
  - Koordinaten: Mitte des Teils, y nach oben, der Ursprung ist die Objektmitte.
- **Bedeutung von `size_mm` je Form:**
  - box und rounded_box: Breite, Höhe, Tiefe;
  - cylinder: Durchmesser, Höhe, Durchmesser (stehend entlang y);
  - cone: Durchmesser unten, Höhe, Durchmesser oben;
  - sphere: Durchmesser in x, y und z;
  - capsule: Durchmesser, Gesamtlänge, Durchmesser (entlang y).
- **Prüfung nach dem Parsen:**
  - Größen müssen größer als 0 und höchstens 3000 mm sein.
  - Positionen und Winkel werden begrenzt.
  - Unbekannte Formen fallen weg; ungültige Farben werden neutralgrau.
  - Bei `known=false` gibt es keine Teile.
- **Nachricht:** Neue Server-Nachricht `shape` mit `product`, `status` (loading, ready, unknown, error),
  `size_mm` und `parts`. Sie wird wie `profile` unter dem Kartennamen gesendet.
- **Darstellung (Three.js):**
  - Kanten neongrün, Flächen in der Teilfarbe halb durchsichtig.
  - Das Modell dreht sich langsam und lässt sich mit der Maus drehen.
  - Darunter steht zum Beispiel „146,7 × 71,5 × 7,8 mm · vereinfacht · laut Claude“.
- **Kosten:** ca. 2–3 Cent und 10–15 s pro Modell, einmalig.

## 4. Seitenleiste

- **Platz:** Die Leiste steht fest rechts und ist 360 px breit. Das Kamerabild wird daneben kleiner, sodass nichts
  hinter der Leiste verschwindet.
- **Einträge:** einer pro Kartenname; das zuletzt Gesehene steht oben; höchstens 8.
- **Aktiver Eintrag** ist der gehaltene Gegenstand. Er steht oben und ist ausgeklappt; während der Analyse steht
  dort „ANALYSIERE …“.
- **Ausgeklappt** zeigt ein Eintrag drei Teile:
  - die Erkennung: Stufe, Name, Satz, Balken, Belege, „Zeig mir bitte …“ und „Neu prüfen“ (nur beim aktiven
    Eintrag);
  - den Steckbrief;
  - das Hologramm.
- **Nicht aktive Einträge** sind eingeklappt und zeigen nur die Kopfzeile (Name und Stufe). Ein Klick klappt sie auf
  und zu.
- **Am Objekt:** grüne Box, ein Namensschild (Name · Stufe) und eine dünne grüne Linie zum aktiven Eintrag.
- **Neuladen:** Danach ist die Leiste leer. Speichern kommt später, falls gewünscht.

## 5. Tests

- **Python:**
  - Anfrage: Bild und Name.
  - Parsen: Klemmen, Formen, Farben, unbekannt.
  - Cache.
  - Pipeline: wahrscheinlich ergibt loading, dann ready; Cache; Fehler; Budget; Kartenname mit Farbe.
  - Protokoll.
- **Web:**
  - Protokoll.
  - Leisten-Logik: Einträge, Reihenfolge, aktiv, auf und zu, höchstens 8.
  - Hologramm-Mathematik: Teile werden zu Geometrie-Parametern, dazu der Maße-Text.
- **Echt:** Form fürs iPhone 14 mit einem echten Ausschnitt, dazu eine Sichtprüfung des gerenderten Hologramms.
