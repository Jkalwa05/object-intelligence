# Object Intelligence, Teilprojekt 7: Vermessenes Präzisionsmodell

Stand: 2026-10-02 · Status: Design von Jonas freigegeben („Ja, direkt bauen“)

## 1. Ziel

Das Präzisionsmodell (Teilprojekt 6) traf das iPhone genau, den PS3-Controller nicht. Jonas: „Das ist schlecht. Wir
müssen irgendwie den Controller in ganz viele einzelne Bounding Boxen einteilen und dann dazu noch die Maße ziehen und
weiterhin validieren und auch noch Bilder aus dem Internet suchen.“

Die Ursache zeigte der Lauf von 15:30:
- Die Recherche fand eine bemaßte Zeichnung (dimensions.com, Vorder-, Seiten- und Draufsicht).
- Sie war aber ein SVG auf einem anderen Server, und der Download nimmt nur PDF, PNG und JPEG von gefundenen Adressen.
- Deshalb sind alle Detailmaße geschätzt, und nur 160 × 97 × 55 mm sind echt.

Teilprojekt 7 misst statt zu schätzen:
- **Referenzbilder aus dem Netz:** Zeichnung und Produktfotos, auch als SVG und WebP.
- **Vermessen:** Claude setzt auf jedem Referenzbild eine Box um jedes Teil, und der Server rechnet die Boxen in
  Millimeter um.
- **Prüfung mit Zahlen:** Der Server vergleicht jedes gebaute Teil mit seinen gemessenen Maßen.
- **Behalten:** Ein gutes Modell bleibt.

## 2. Entscheidungen (Jonas)

| Frage | Antwort |
|---|---|
| Gründlichkeit | Boxen und Zahlenvergleich: jedes Teil vermessen, das Modell Teil für Teil nachprüfen |
| Budget | bis 1,60 $ pro Modell wie bisher, ~5–6 min, 2 Prüfrunden |
| Wiederverwenden | „wenn ich einmal den perfekten finde, kann der ruhig immer kommen, aber bis dahin soll es immer ein neuer sein“ |
| Vorhandene Modelle | iPhone 14, iPhone 15 und die Kreatin-Dose gelten als behalten; die Controller nicht |
| Vorgehen | Spec und Plan schreiben, dann ohne weiteren Stopp bauen |

## 3. Ablauf

Neu ist **fett**.

1. Recherche (`cad_model`): Maßblatt und Zeichnung wie bisher, **dazu bis zu 4 Produktfotos** mit ihrer Ansicht.
2. Laden (Status `drawing`):
   - Zeichnung wie bisher;
   - **die Fotos;**
   - **SVG wird mit resvg zu PNG;**
   - **WebP wird angenommen.**
3. **Vermessen (Status `measuring`):** Ein Aufruf (`cad_model`) liefert für jedes Referenzbild die Ansichten mit einer
   Box um das ganze Produkt und einer Box um jedes Teil. Der Server macht daraus die *Teilekarte* (§5).
4. CAD (Status `modeling`):
   - wie bisher;
   - **dazu die Teilekarte und die Fotos;**
   - **Claude verwendet die Teilenamen der Karte.**
5. Bauen und 2 Prüfrunden (Status `building`, `checking`):
   - wie bisher;
   - **dazu die Fotos;**
   - **dazu die Liste der Abweichungen zwischen gebauten Teilen und Teilekarte (§6).**
6. Fertig:
   - **Das Manifest enthält die Teilekarte.**
   - **In den Notizen steht, wie viele Abweichungen am Ende über der Toleranz liegen.**

Gibt es kein Referenzbild oder keine Gesamtgröße, entfällt das Vermessen. Der Bau läuft dann wie in Teilprojekt 6.

## 4. Referenzbilder

### 4.1 Recherche
- Das Maßblatt (`MeasureSheet`) bekommt `photos: list[PhotoRef]`, mit `PhotoRef(url, view)`.
- `view` ist einer dieser Werte:
  - `front`;
  - `back`;
  - `side-front-left`: von der Seite, die Vorderseite zeigt im Bild nach links;
  - `side-front-right`;
  - `top`: von oben, die Vorderkante liegt unten im Bild.
- Höchstens 4 Fotos, nur https-Adressen und gültige Ansichten. Alte Manifeste ohne `photos` bleiben gültig, mit `[]`.
- Der Prompt verlangt Fotos genau dieses Produkts:
  - gerade von einer Seite aufgenommen, ganzes Produkt im Bild, schlichter Hintergrund;
  - am liebsten offiziell (Hersteller, Pressebilder), sonst Wikipedia/Wikimedia oder große Händler.

### 4.2 Erlaubte Adressen
- Erlaubt waren bisher die Adressen der Suchergebnisse und der abgerufenen Seiten, und deren Hosts.
- **Neu:** auch jede https-Adresse, die *im Text* einer abgerufenen Seite steht, etwa ein Bild-Link auf einem CDN.
- Alle anderen Regeln aus `download.py` bleiben: nur https, nur öffentliche Adressen (nach jedem Redirect geprüft),
  höchstens 3 Redirects.

### 4.3 Typen und Größen
- `image/png`, `image/jpeg`, `image/webp` und `image/svg+xml`: je höchstens 8 MB.
- PDF wie bisher.

### 4.4 SVG
- `resvg-py` (MIT, Rust) rendert das SVG zu PNG, die lange Seite 2000 px. Schriften kommen vom System, damit die
  Maßzahlen lesbar sind.
- resvg führt keine Skripte aus und lädt keine fremden Adressen.

## 5. Vermessen

### 5.1 Der Aufruf
- **Eingabe:**
  - die Bilder, nummeriert ab 1 (erst die Zeichnungsseiten, dann die Fotos mit ihrer Ansicht aus der Recherche);
  - das Maßblatt.
- **Ausgabe (structured output):** bis zu 6 Ansichten `{picture, view, object, parts: [{name, box}]}`.
  - Boxen sind `[links, oben, rechts, unten]` als Anteile von Breite und Höhe des Bildes (0…1).
  - `object` umfasst alles vom Produkt, auch Teile, die herausstehen.
  - Dasselbe Teil heißt in jeder Ansicht gleich.
  - Maßlinien und Text sind keine Teile.
  - Ansichten in Perspektive oder abgeschnitten werden weggelassen.
  - Höchstens 40 Teile pro Ansicht.
- **Effort:** `high`, `max_tokens` 16 000.
- **Reserve im Budget:** 0,25 $.

### 5.2 Prüfen der Antwort (`parse_measure`)
- Boxen ohne 4 Zahlen, außerhalb von 0…1 oder mit links ≥ rechts bzw. oben ≥ unten fallen weg.
- Ansichten mit unbekanntem `view` oder einer Bildnummer außerhalb fallen weg.
- Teile, die mehr als 2 % (relativ zur Objektbox) aus der Objektbox ragen, fallen weg.

### 5.3 Umrechnung in Millimeter (`part_map`)
- Pro Ansicht gibt es einen Maßstab k in mm pro Pixel. Eine orthografische Ansicht hat in beiden Richtungen denselben
  Maßstab.
  - `front` und `back`: kx = Breite / Boxbreite in px und ky = Höhe / Boxhöhe in px. Weichen sie mehr als 12 %
    voneinander ab, ist die Ansicht perspektivisch oder die Box falsch, und sie fällt weg. Sonst gilt x mit kx und y
    mit ky.
  - Seitenansichten: k = Höhe / Boxhöhe in px, für y und z.
  - `top`: k = Breite / Boxbreite in px, für x und z.
  - Liegt die Tiefe der Box (in mm) mehr als 25 % neben der bekannten Tiefe, fällt die Ansicht weg. 25 %, weil
    herausstehende Sticks die Tiefe vergrößern: bei dimensions.com 55 mm ohne, etwa 64 mm mit.
- Der Ursprung ist die Mitte der Objektbox in jeder Ansicht. Die Achsen sind die des CAD-Modells: x nach rechts, y nach
  oben, z nach vorn.

| Ansicht | horizontal | vertikal |
|---|---|---|
| `front` | x = +h | y = −v |
| `back` | x = −h | y = −v |
| `side-front-right` | z = +h | y = −v |
| `side-front-left` | z = −h | y = −v |
| `top` | x = +h | z = +v |

h und v sind die Abstände von der Boxmitte in mm, nach rechts bzw. nach unten im Bild.

- **Zusammenführen:** Teile werden über ihren Namen zusammengeführt (klein geschrieben, Leerzeichen zusammengefasst).
  Pro Achse ist das Ergebnis der Mittelwert der Bereiche aus allen Ansichten, die diese Achse zeigen.
- **Ergebnis:** `MeasuredPart(name, x, y, z, views)`, die Bereiche in mm oder `None` und `views` die Zahl der
  Ansichten. Die Reihenfolge ist die des ersten Auftretens.

### 5.4 Text für Claude (`map_text`)
- Eine Zeile pro Teil, zum Beispiel: `Dreieck-Taste: x 44.0…50.0, y 20.1…26.0 mm (2 views)`.
- Darüber steht die Erklärung der Achsen und des Ursprungs.

## 6. Prüfung mit Zahlen (`deviations`)

- **Gebaute Teile:** Die Boxen kommen aus den STL-Grenzen. Alle Teile werden so verschoben, dass die Mitte ihrer
  Gesamtbox im Ursprung liegt. Damit gilt derselbe Bezug wie bei der Teilekarte.
- **Toleranz pro Achse:** max(1,5 mm, 2 % der bekannten Größe auf dieser Achse).
- **Für jedes vermessene Teil:**
  - Fehlt es im Modell (kein Teil mit gleichem Namen), entsteht eine Zeile „missing“ mit den gemessenen Bereichen.
  - Liegen Anfang oder Ende auf einer bekannten Achse weiter als die Toleranz daneben, entsteht eine Zeile mit dem
    gebauten und dem gemessenen Bereich, zum Beispiel:
    `Dreieck-Taste: x model 46.0…52.0, measured 44.0…50.0 mm (off by 2.0 mm)`.
- **Sortierung:** größte Abweichung zuerst, höchstens 20 Zeilen.
- **Wofür:**
  - Die Liste geht in jede Prüfrunde.
  - Nach der letzten Runde wird sie noch einmal berechnet. Ihre Länge kommt in die Notizen: „Noch 3 Abweichungen über
    der Toleranz.“

## 7. Behalten und neu bauen

- **Manifest:** `kept: bool = False`, `part_map: list[MeasuredPart] = []`. Alte Manifeste bleiben gültig.
- **`ModelStore.set_kept(model, kept)`:** schreibt das Manifest neu. **`ModelStore.kept()`:** alle behaltenen Manifeste
  im Speicher und auf der Platte.
- **Wenn ein Produkt sicher ist** (`Pipeline._want_model`):
  1. **Ohne Builder** (kein Node, `--fake-claude`) wird ein gespeichertes Modell gezeigt, wie bisher.
  2. **Ein behaltenes Modell desselben Produkts wird gezeigt.**
     - Zuerst zählt der eigene Name.
     - Sonst entscheidet ein kleiner Aufruf (`same_product`, `cad_model`, nur Text), ob einer der behaltenen Namen
       dasselbe Produkt meint.
     - Die Antwort gilt pro Name für den ganzen Serverlauf.
  3. Wurde der Name in diesem Serverlauf schon angefragt, zeigt der Builder seinen Stand.
  4. Sonst wird neu gebaut, auch wenn ein nicht behaltenes Modell gespeichert ist. Das neue ersetzt es.
- **Jedes Produkt höchstens einmal pro Serverlauf:** Damit kostet nicht jedes Hochheben etwa 0,90 $. Die Grenze von
  5 neuen Modellen pro Sitzung bleibt.
- **Nachricht vom Browser:** `KeepMsg {type: "keep", model, kept}`.
  - `model` ist `manifest.model` des gezeigten Modells.
  - Der Server setzt `kept` und schickt das Manifest an alle Einträge, die dieses Modell zeigen.
- **Übernahme:** `apple-iphone-14`, `apple-iphone-15` und `neosupps-creatine-monohydrate` bekommen `kept: true`.

## 8. Darstellung

- **Fortschritt:**
  - `drawing`: „Lade Zeichnung und Fotos …“;
  - **`measuring`: „Vermesse die Teile auf Zeichnung und Fotos …“;**
  - `checking`: „Prüfe gegen Maße, Zeichnung und Fotos (Runde n/2) …“.
- **Tag:** „CAD · Maße laut dimensions.com · 18 Teile vermessen“, sobald die Teilekarte nicht leer ist.
- **Vollbild:**
  - Neben dem Tag steht ein Knopf: „Behalten“, behalten „✓ Behalten“. Ein Klick wechselt.
  - Unter QUELLEN stehen die Fotos mit Ansicht und Domain.

## 9. Kosten und Zeit

| Schritt | Reserve |
|---|---|
| Recherche | 0,45 $ |
| Vermessen | 0,25 $ |
| CAD | 0,45 $ |
| jede Prüfrunde | 0,35 $ |

- Die Obergrenze bleibt 1,60 $.
- **Geschätzt** für den Controller: Er kostet etwa 0,85–0,95 $ (bisher 0,59 $) und braucht etwa 6 Minuten. Das kommt
  von etwa 5 Bildern mehr pro Aufruf und dem Vermessen.

## 10. Fehlerfälle

- Fotos, die nicht laden: Sie werden übersprungen (Log), der Bau läuft weiter.
- Ein Vermessen-Aufruf, der scheitert (Fehler, Schema, Zeitlimit): Die Teilekarte ist leer, und der Bau läuft ohne
  Zahlenprüfung weiter.
- Ein SVG, das resvg nicht lesen kann: Es zählt wie eine nicht ladbare Zeichnung.
- Ein Namensvergleich, der scheitert: Es gibt keinen Treffer, also wird neu gebaut.

## 11. Sicherheit

- Neue Adressen kommen nur aus Seiten, die Claude selbst abgerufen hat, und werden mit den bisherigen Regeln geladen.
- SVG wird nie im Browser angezeigt, nur auf dem Server zu PNG gerendert.
- Fotos und Zeichnungen gehen nur an Claude. Sie werden nicht gespeichert und nicht veröffentlicht. Im Manifest stehen
  nur ihre Adressen.

## 12. Tests

- **Rein (pytest):**
  - `parse_measure`;
  - `part_map`: jede Ansicht, die 12 %- und die 25 %-Regel, Zusammenführen, Teile außerhalb;
  - `deviations`: Toleranz, fehlende Teile, Sortierung, Grenze 20;
  - `map_text`;
  - Adressen aus dem Seitentext;
  - SVG zu PNG;
  - WebP- und SVG-Typen;
  - `parse_research` mit Fotos;
  - Laden der Fotos;
  - Anfragen für Vermessen, CAD und Prüfung;
  - Store (`set_kept`, `kept`);
  - Builder (Vermessen-Schritt, Reserve, Abweichungen in der Prüfung, Behalten und neu bauen, Namensvergleich);
  - Pipeline (`KeepMsg`, Wiederverwenden).
- **Web (Vitest):** Tag mit Teilezahl, Fortschrittstexte.
- **Echt:** Der DualShock 3 wird aus einem gespeicherten Ausschnitt neu gebaut und mit dem bisherigen Modell
  verglichen.
