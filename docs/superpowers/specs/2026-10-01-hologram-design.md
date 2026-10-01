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
- **Kosten:** gemessen 1,8 Cent und ca. 10 s pro Modell, einmalig (iPhone 14: 7 Teile, 71,5 × 146,7 × 7,8 mm).

## 4. Seitenleiste

- **Platz:** Die Leiste steht fest rechts und ist 360 px breit. Das Kamerabild wird daneben kleiner, sodass nichts
  hinter der Leiste verschwindet.
- **Einträge:** einer pro Kartenname; das zuletzt Gesehene steht oben; höchstens 8.
- **Aktiver Eintrag** ist der gehaltene Gegenstand. Er steht oben und ist ausgeklappt; während der Analyse steht
  dort „ANALYSIERE …“.
- **Ausgeklappt** zeigt ein Eintrag drei Teile:
  - die Erkennung: Stufe, Name, Satz, Balken, Belege, „Zeig mir bitte …“ und „Neu prüfen“ (nur beim aktiven
    Eintrag);
  - das Hologramm;
  - den Steckbrief.

  Das Hologramm steht vor dem Steckbrief, damit man es auf einem Laptop-Bildschirm ohne Scrollen sieht (Ruling nach
  der Sichtprüfung).
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

## 6. Nachtrag 2026-10-01: das richtige Modell antippen

Im Live-Test blieb Jonas' iPhone von hinten „unsicher“ (iPhone 14, 15 oder 13?). Deshalb kamen weder Steckbrief noch
Hologramm, denn beide gibt es erst ab „wahrscheinlich“. Seine Lösung: „Sorg dafür, dass ich auswählen kann, welches es
ist, sodass es dann auf sicher steht. Und dann kommt das Hologramm.“

- **Antippen.** Im aufgeklappten Eintrag stehen über den Kandidaten die Worte „Welches ist es? Tippe es an.“ Ein
  Klick auf einen Namen schickt `confirm` (`track_id`, `name`). Das geht auch in älteren, eingeklappten Einträgen:
  Erkannte Objekte bleiben 10 Minuten im Speicher, alle anderen wie bisher 30 s.
- **Sicher durch dein Wort.** `Belief.confirm(name)` macht den Kandidaten sicher und endgültig, kein weiterer Aufruf
  für dieses Objekt. Eine spätere Antwort von Claude kann das nicht mehr ändern.
  - Die Karte zeigt nur noch diesen Namen mit 100 % und die Plakette „von dir bestätigt“ (`identity.confirmed`).
  - Ehrlich bleibt es, weil sichtbar ist, woher die Sicherheit kommt.
- **Dann Steckbrief und Hologramm.** Wie bei „wahrscheinlich“ kommen sie für das gewählte Modell, aus dem Speicher
  oder mit je einem Aufruf. Das Hologramm bekommt den zuletzt gesendeten Ausschnitt des Objekts.
- **Einträge verschmelzen.** Wählst du im Eintrag „Apple iPhone 13“ das iPhone 14, heißt der Eintrag danach so, und
  ein bestehender Eintrag gleichen Namens wird mit ihm zu einem.

## 7. Nachtrag 2026-10-01: dasselbe Objekt zweimal gesehen

Im Live-Test ergab der Controller zwei Einträge. Ein sehr dunkles Bild hieß „Unbekanntes schwarzes Objekt“, kurz
darauf kam unter neuer Tracking-Nummer der „Sony DualShock 3“. Jonas: „Da muss KI eingreifen und gleiche Artikel
zusammenfassen.“

- **Vergleich.** Hat ein Objekt sein erstes Ergebnis, fragt die Pipeline Claude genau einmal, ob es eines der bis zu
  3 zuletzt gesehenen Objekte ist, nur aus einem anderen Winkel oder in anderem Licht.
  - Claude sieht die Ausschnitte (nur Objekt-Pixel, auf 384 px verkleinert) und die Namen der Einträge.
  - Antwort: `same_as` (Nummer oder null) und ein kurzer Grund.
  - Was gerade gleichzeitig im Bild ist, wird nie verglichen.
  - Der Vergleich zählt zum Budget und landet im Aufruf-Log (`track_id` −3).
  - Gemessen mit Jonas' Ausschnitten: 0,4–0,5 Cent und 3–5 s pro Vergleich. Das dunkle Objekt wurde dem DualShock 3
    zugeordnet, das iPhone nicht.
- **Verschmelzen.** Das Objekt in der Hand übernimmt alles vom früheren:
  - die Beobachtungen, als eigene Ansichten (`Belief.absorb`), sodass Vorder- und Rückseite zusammen „sicher“
    ergeben können;
  - die Aufrufe;
  - deine Bestätigung.

  Der Server schickt zuerst die Identität des alten Eintrags unter dem gemeinsamen Namen, dann die des Objekts in
  der Hand. Die Umbenennungslogik des Browsers macht daraus einen Eintrag. Steckbrief und Hologramm folgen dem
  gemeinsamen Produkt.
- **Grenze.** Zwei baugleiche Dinge nacheinander kann auch Claude nicht unterscheiden; sie werden zusammengelegt.
- **Nebenbei gefunden.** Die Test-Hilfe `Pipeline.wait_idle` drehte sich endlos, wenn ein Auftrag gerade fertig, aber
  noch nicht ausgetragen war. Sie wartet jetzt nur auf laufende Aufträge (Regressionstest). Der echte Betrieb nutzt
  sie nicht.
