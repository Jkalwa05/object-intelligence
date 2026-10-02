# Object Intelligence, Teilprojekt 6: Präzisionsmodell

Stand: 2026-10-01 · Status: Design von Jonas freigegeben („Ja, passt“), Spezifikation zur Durchsicht

## 1. Ziel

Das Hologramm aus Teilprojekt 3 ist ein Nachbau aus höchstens 16 Grundformen, die Claude aus dem Gedächtnis
beschreibt. Jonas: „Da kann ich so technisch nicht stolz drauf sein … der macht manche Sachen nicht gut.“ Das
Präzisionsmodell ersetzt es durch ein echtes CAD-Modell:

- **Maße aus Quellen.** Sobald ein Artikel *sicher* ist, recherchiert Claude seine technischen Maße und, wo es eine
  gibt, die technische Zeichnung.
- **CAD statt Grundformen.** Claude schreibt daraus ein CAD-Programm (OpenSCAD mit der Bibliothek BOSL2), mit
  abgerundeten Kanten, Aussparungen und Drehkörpern. Ein echter CAD-Kern berechnet daraus das 3D-Netz.
- **Sichtprüfung.** Das Modell wird aus mehreren Richtungen gerendert. Claude vergleicht es mit Zeichnung und Foto und
  korrigiert es.

## 2. Entscheidungen (Jonas)

| Frage | Antwort |
|---|---|
| Ansatz | Recherche + CAD-Modell (OpenSCAD + BOSL2) mit Sichtprüfung |
| Auslöser | sobald der Artikel *sicher* ist (durch Beweise oder durch sein Antippen) |
| Aussehen | nur Hologramm-Look: leuchtend grüne Kanten, halbdurchsichtige Flächen, aber echte CAD-Geometrie |
| Budget | bis ca. 1,50 € pro Produkt, einmalig; danach aus dem Speicher |
| Wartezeit | nur Fortschritt, kein Platzhalter: das schnelle Hologramm aus Teilprojekt 3 fällt weg |
| Sitzungsgrenze | höchstens 5 neue Präzisionsmodelle pro Sitzung (mein Vorschlag, freigegeben) |
| GitHub | Bausteine aus freien Repos: openscad-wasm-prebuilt, BOSL2, pypdfium2; Ideen von CADAM und img2threejs |

## 3. Ablauf

```
sicher erkannt ──▶ Recherche ──▶ Zeichnung ──▶ CAD ──▶ Geometrie ──▶ Prüfung (bis 2 Runden) ──▶ Speicher ──▶ Browser
                  (Claude +     (Server lädt  (Claude  (OpenSCAD in   (Renders + Claude:
                   Websuche)     PDF/Bild)     schreibt  Node, je Teil)  Abweichungen korrigieren)
                                               OpenSCAD)
```

- **Start.** Die Erkennung eines Objekts erreicht die Stufe *sicher* (auch durch Antippen) und nennt ein Modell
  (`Belief.product()` mit Stufe sicher). Liegt das Modell schon im Speicher, geht es sofort an den Browser.
- **Vorher.** Bei *wahrscheinlich* und *unsicher* zeigt der Hologramm-Bereich: „Das 3D-Modell entsteht, sobald das
  Objekt sicher erkannt ist.“
- **Ein Auftrag nach dem anderen.** Es läuft immer nur ein Modellauftrag. Weitere warten in einer Schlange.
- **Unabhängig vom Browser.** Der Auftrag läuft auf dem Server weiter, auch wenn der Gegenstand weggelegt oder der Tab
  geschlossen wird. Das Ergebnis landet im Speicher.
- **Fortschritt.** Jeder Schritt schickt eine `model`-Nachricht mit seinem Status:

| Status | Text im Eintrag |
|---|---|
| `waiting` | Das 3D-Modell entsteht, sobald das Objekt sicher erkannt ist. |
| `queued` | Wartet auf das vorherige Modell … |
| `researching` | Recherchiere Maße … |
| `drawing` | Lese technische Zeichnung … |
| `modeling` | Baue CAD-Modell … |
| `building` | Berechne Geometrie … |
| `checking` | Prüfe gegen Zeichnung und Foto (Runde n/2) … |
| `ready` | (das Modell) |
| `failed` | Modell gerade nicht möglich. (+ Knopf „Neu bauen“) |
| `limit` | Höchstens 5 neue Modelle pro Sitzung. |

- **Dauer.** Gemessen am 2026-10-02 (iPhone 14): 2,6–2,9 Minuten ohne Zeichnung, etwa 4,5 Minuten mit Apples
  Maßzeichnung (Recherche 52 s, CAD 140 s, zwei Prüfrunden 58 s).

## 4. Recherche

### 4.1 Der Recherche-Aufruf

- **Werkzeuge:**
  - die Websuche (`web_search_20260209`, höchstens 3 Suchen, Standort Deutschland);
  - den einfachen Web-Fetch (`web_fetch_20250910`, höchstens 3 Abrufe, `max_content_tokens` 15.000). Die einfache
    Version führt kein zusätzliches Programm aus (keine Code-Ausführung zum Filtern); ihre Kosten sind deshalb
    planbar.
- **Eingabe:** Modellname und Kategorie, **kein Bild**. Effort `medium`.
- **Keine PDFs über den Fetch.** Der Fetch liefert ein PDF als ganzes Dokument, und `max_content_tokens` begrenzt nur
  Text. Laut Doku kostet ein PDF von 500 kB etwa 125.000 Tokens. Die Anweisung lautet deshalb: PDFs nicht öffnen,
  sondern als Kandidaten in `drawing` melden. Der Server holt die Zeichnungsseite selbst (4.3). Hält Claude sich nicht
  daran, begrenzt die Kostengrenze aus Abschnitt 9 den Schaden.
- **Auftrag:** offizielle Maße finden (Hersteller-Datenblatt vor Händlerseiten) und eine technische Zeichnung, falls
  es eine gibt. Bei Apple sind das die *Accessory Design Guidelines* (PDF, 33 MB, mit maßgenauen Zeichnungen jedes
  iPhones).
- **Antwort: das Maßblatt** (siehe 4.2) als freier Text, der mit genau einem JSON-Objekt in einem ```json-Block
  endet. Der Server liest es heraus und prüft es mit pydantic. Ist es unlesbar, gilt die Recherche als gescheitert
  (Abschnitt 10).
  - **Warum kein erzwungenes JSON wie sonst?** Die Websuche hängt immer Zitate an. Ob das mit erzwungenem JSON
    zusammengeht, sagt die Doku nicht. Ein echter Test (Marker `claude`) prüft den Aufruf.
- **Herkunft jeder Zahl:** Jede Zahl trägt ihre Quelle und ihre Art:
  - `drawing`: aus einer technischen Zeichnung;
  - `datasheet`: aus einem Datenblatt;
  - `estimate`: geschätzt.

### 4.2 Das Maßblatt (`MeasureSheet`)

| Feld | Inhalt |
|---|---|
| `size_mm` | Gesamtmaße Breite, Höhe, Tiefe in mm, oder `null` |
| `size_source` | Index in `sources`, oder `null` bei geschätzt |
| `measures` | bis zu 30 Einträge: `label` („Kameraplateau Breite“), `value_mm`, `source` (Index), `kind` (drawing, datasheet, estimate) |
| `features` | bis zu 20 Beschreibungen in Worten mit mm: Lage, Form und Größe sichtbarer Merkmale (Tasten, Linsen, Anschlüsse) |
| `sources` | bis zu 6 Quellen: `title`, `url` |
| `drawing` | Kandidat für die Zeichnung: `url` (PDF oder Bild) und `find` (Text, der auf der richtigen PDF-Seite steht, z. B. „iPhone 14 Dimensional Drawing“), oder `null` |

Grenzen wie „höchstens 30 Maße“ werden nach der Antwort durch Abschneiden durchgesetzt, nicht im Schema. Das ist die
Regel aus Teilprojekt 1: Ein bezahlter Aufruf wird nie wegen eines Eintrags zu viel verworfen.

### 4.3 Die technische Zeichnung

Der Web-Fetch liefert aus PDFs nur Text, die Zeichnung selbst sieht Claude damit nicht. Deshalb holt der Server sie
selbst:

- **PDF:** Laden, dann die Seiten nach dem `find`-Text durchsuchen (pypdfium2) und höchstens 2 passende Seiten mit
  150 dpi als Bild rendern.
- **Bild:** direkt laden.
- **Danach:** Die Bilder gehen in den CAD-Aufruf und in jede Prüfrunde.
- **Kein Treffer:** Gibt es keinen Kandidaten oder schlägt etwas fehl, geht es ohne Zeichnung weiter. Das ist kein
  Fehler.

### 4.4 Sichere Downloads (`oi/download.py`)

Der Server lädt nur, was diese Regeln erfüllt:
- nur `https`, nur die URL aus dem Maßblatt, die in den Such- oder Abrufergebnissen dieses Aufrufs vorkam;
- kein `localhost`, keine privaten oder lokalen IP-Adressen (auch nicht nach einer Weiterleitung), höchstens 3
  Weiterleitungen;
- Inhaltstyp `application/pdf`, `image/png` oder `image/jpeg`;
- PDF höchstens 60 MB, Bild höchstens 8 MB, 30 s Zeitlimit;
- geladene Dateien liegen nur im Arbeitsspeicher, werden nie ausgeführt und gehen nur als Bild an Claude.

## 5. Das CAD-Modell

### 5.1 Der CAD-Aufruf

- **Eingaben:** das Maßblatt (Text), die Zeichnungsseiten (Bilder) und der letzte Ausschnitt des Objekts (nur
  Objekt-Pixel, wie bei der Erkennung). Dazu kommt ein kurzer BOSL2-Spickzettel: die nützlichsten Module mit
  Signaturen, zum Beispiel `cuboid(rounding=, edges=)`, `cyl(rounding=, chamfer=)`, `offset_sweep`, `skin`, `hull`
  und `rotate_extrude`.
- **Effort:** `high`, ohne Werkzeuge.
- **Koordinaten:** Ursprung in der Mitte, x nach rechts, y nach oben, z zum Betrachter. Die Vorderseite des Produkts
  zeigt nach +z, aufrecht.
- **Antwort (JSON nach Schema):**
  - `shared`: OpenSCAD-Code, der vor jedes Teil gesetzt wird (gemeinsame Maße als Variablen, gemeinsame Module);
  - `parts`: bis zu 40 Teile, je `name` (in der Sprache der App), `color` (`#rrggbb`) und `scad` (OpenSCAD-Anweisungen,
    die genau dieses Teil erzeugen);
  - `notes`: was angenähert ist.
- **Längengrenzen:** `shared` höchstens 20.000 Zeichen, jedes Teil höchstens 12.000.

### 5.2 Der Compiler: OpenSCAD in Node (`web/scad/compile.mjs`)

- **Was:** OpenSCAD 2025.01.19 als WebAssembly (npm `openscad-wasm-prebuilt` 1.2.0) mit dem Manifold-Kern
  (`--backend=manifold`).
- **Wie:** Der Server ruft pro Teil einen Node-Prozess auf, höchstens 4 gleichzeitig.
  - Eingabe als JSON über stdin: Code, BOSL2-Ordner.
  - Ausgabe als JSON: binäres STL (Base64), Dreieckszahl, Dauer oder Fehlermeldungen.
  - Die Datei wird so zusammengesetzt: `include <BOSL2/std.scad>`, `$fn = 48;`, dann `shared`, dann das Teil.
- **BOSL2:** eine feste Version (Commit fest im Code), beim ersten Gebrauch von GitHub geladen nach
  `models/BOSL2-<commit>/`, wie das Gesichtsmodell YuNet.
- **Grenzen:** 30 s pro Teil (danach wird der Prozess beendet), höchstens 200.000 Dreiecke pro Teil, höchstens
  600.000 im ganzen Modell.
- **Abgeschottet:**
  - OpenSCAD sieht nur sein eigenes Dateisystem im Arbeitsspeicher. Geprüft am 2026-10-01: Selbst mit
    `--enable=import-function` kann es keine Datei vom Mac lesen.
  - Es hat keinen Netzzugriff.
  - Der Code von Claude läuft nirgends sonst: nicht in Python, nicht im Browser.
- **Gemessen (Machbarkeitsprüfung):** 0,76 s für ein Teil mit BOSL2 (abgerundeter Quader mit Aussparung), davon
  0,04 s Geometrie; Laden des Moduls 45 ms.

### 5.3 Meshes und Maße (`oi/mesh.py`)

- **STL lesen:** Das STL wird gelesen, die Bounding Box jedes Teils bestimmt.
- **Gesamtmaße:** Die Größe des ganzen Modells ergibt sich aus der Vereinigung aller Bounding Boxes.
- **Plausibilität:** Weichen die Gesamtmaße mehr als 10 % von `size_mm` aus dem Maßblatt ab, geht das als Hinweis in
  die nächste Prüfrunde.

## 6. Sichtprüfung

- **Renders:** Der Server rendert das Modell aus 4 Richtungen: vorn, hinten, rechts und schräg von oben. Die Bilder
  sind orthografisch, 512 × 512, hellgrau schattiert mit den Teilfarben (matplotlib, ist schon installiert).
- **Der Prüf-Aufruf (Effort `high`) bekommt:**
  - die Renders und die Zeichnungsseiten;
  - den Ausschnitt;
  - das Maßblatt und den aktuellen Code;
  - Compiler-Fehler und den Maß-Hinweis aus 5.3.
- **Die Antwort:**
  - `verdict`: `good` oder `fix`;
  - `issues`: bis zu 10 Abweichungen in Worten;
  - Ersatz für `shared` (oder `null`);
  - `parts`: neue oder geänderte Teile, gleicher Name ersetzt;
  - `remove`: zu löschende Teile.
- **Ablauf:** Höchstens 2 Runden. Bei `good` endet die Prüfung früher.
- **Teile, die nicht kompilieren:** Ein Teil, das nach der letzten Runde noch nicht kompiliert, fällt weg und wird in
  `notes` genannt. Kompiliert gar nichts, ist der Auftrag gescheitert.

## 7. Speicher und Auslieferung

- **Speicher:** `cache/models/<slug>/` (nicht in Git). `slug` ist der Modellname in Kleinbuchstaben, mit `-` statt
  Leerzeichen, nur `a-z0-9-`.
  - `manifest.json`: Modell, Teile mit Name, Farbe, Datei und Bounding Box, Gesamtmaße, Maße mit Quellen, Quellen,
    Zeichnung (Titel, URL, Seite), `notes`, `verdict`, Runden, Kosten, Datum;
  - `part-01.stl`, `part-02.stl`, …;
  - `model.scad`: der vollständige Code, zum Nachlesen.
- **Auslieferung:** Neue HTTP-Route `GET /models/{slug}/{file}` vor dem Mount der Weboberfläche.
  - Sie liefert nur Dateien, die im Manifest stehen, und nur mit den Mustern `slug = [a-z0-9-]+` und
    `file = part-\d{2}\.stl` oder `model.scad`.
  - Alles andere ergibt 404, auch Pfade mit `..`.
- **Die `model`-Nachricht:**
  - `product`: der Name des Eintrags;
  - `status` und `round`;
  - bei `ready` das Manifest ohne den Code, mit den URLs der Teile.

## 8. Darstellung im Browser

- **Laden:** Der Hologramm-Bereich lädt bei `ready` die Teile mit `STLLoader` (three.js-Beispiele).
- **Look:** wie bisher: halbdurchsichtige Flächen in der Teilfarbe (Deckkraft 0,28) und grüne Kanten
  (`EdgesGeometry`, Knickwinkel 20°, damit Rundungen ruhig bleiben).
- **Seitenleiste:**
  - Das Modell dreht sich langsam, Größe und Plakette darunter.
  - Plakette: „CAD · Maße laut <Domain>“, wenn `size_source` gesetzt ist, sonst „CAD · Maße geschätzt“.
  - Während des Aufbaus steht dort der Fortschritt (Abschnitt 3).
- **Vollbild:**
  - Maßlinien für Breite, Höhe und Tiefe, mit dem Wert aus dem Maßblatt. Fehlt er, gilt die gemessene Bounding Box.
  - Ein nummeriertes Namensschild pro Teil, in der Mitte seiner Bounding Box. Die Schilder weichen wie bisher aus
    (`spread`).
  - Rechts:
    - die Teileliste mit den Maßen jedes Teils;
    - **Maße**: die Liste der recherchierten Maße mit Quelle und Art (Zeichnung, Datenblatt, geschätzt);
    - **Quellen**: die Links;
    - danach wie bisher Steckbrief und Wissenswertes.
- **Neu bauen:** Nur bei `failed` gibt es den Knopf „Neu bauen“. Er schickt `rebuild` (Name). Das zählt als neuer
  Auftrag, und die Sitzungsgrenze gilt.

## 9. Kosten und Grenzen

- **Erwartete Kosten pro Produkt:**
  - Recherche ca. 0,30 $;
  - CAD ca. 0,30 $;
  - je Prüfrunde ca. 0,22 $;
  - zusammen ca. 1 $.

  Gemessen am 2026-10-02 (iPhone 14): 0,40 $ und 0,66 $ ohne Zeichnung (1 bzw. 2 Prüfrunden), 0,90 $ mit Zeichnung
  (Recherche 0,36 $, CAD 0,32 $, zwei Prüfrunden 0,22 $).
- **Harte Grenze pro Produkt:** 1,60 $ (`max_model_cost_usd`, ≈ 1,50 €).
  - Vor jedem Schritt wird geprüft, ob noch Platz für ihn ist. Geschätzter Bedarf: Recherche 0,45 $, CAD 0,45 $,
    Prüfrunde 0,35 $.
  - Ist kein Platz mehr, bleibt das beste bisherige Modell.
- **Pro Sitzung:** höchstens 5 neue Präzisionsmodelle (`max_models_session`). Modelle aus dem Speicher zählen nicht.
- **Sitzungsbudget:** Jeder Aufruf zählt wie bisher zu den 150 Aufrufen der Sitzung und zu den Kosten in der
  Telemetrie.
- **Aufruf-Log:** in `runs/` mit `track_id` −2. Der Anfragetext beginnt mit `model research:`, `model cad:` oder
  `model check n:`.

## 10. Fehlerfälle

| Fall | Verhalten |
|---|---|
| Recherche scheitert oder findet nichts | weiter mit Claudes Wissen und dem Foto; alle Maße gelten als `estimate` |
| Zeichnung nicht ladbar oder nicht gefunden | weiter ohne Zeichnung |
| CAD-Aufruf scheitert | Status `failed` |
| einzelne Teile kompilieren nicht | Fehler gehen in die nächste Prüfrunde; danach fallen sie weg |
| gar nichts kompiliert | Status `failed` |
| Prüf-Aufruf scheitert | das bisherige Modell bleibt |
| Budget erreicht | das beste bisherige Modell bleibt (`notes` sagt es) |
| `node` fehlt oder `web/node_modules` fehlt | Präzisionsmodell aus, ein Hinweis beim Start |
| Browser getrennt | Auftrag läuft weiter, Ergebnis landet im Speicher |

## 11. Datenschutz und Sicherheit

- **Was den Mac verlässt:**
  - Die Recherche bekommt nur den Modellnamen.
  - CAD- und Prüf-Aufruf bekommen denselben Objekt-Ausschnitt wie die Erkennung (nur Objekt-Pixel).
  - Die Renders zeigen nur das CAD-Modell.
- **Fremde Seiten:** Inhalte fremder Webseiten sind Daten, keine Anweisungen. Der schlimmste Fall einer manipulierten
  Seite ist ein falsches Modell, denn Claudes Code läuft nur im abgeschotteten OpenSCAD (5.2).
- **Downloads** nach 4.4, Auslieferung nach 7.

## 12. Was wegfällt

Das schnelle Hologramm aus Teilprojekt 3 wird durch das Präzisionsmodell ersetzt. Wegfallen:
- im Server: `SHAPE_PROMPT`, `describe_shape`, `ShapeRequest`, `ShapeResult`, `ProductShape`, `ShapePart`,
  `ShapeMsg`, `ShapeStore` und `cache/shapes.json` (die Datei bleibt liegen, wird aber nicht mehr gelesen);
- im Browser: die Grundformen-Mathematik `partGeometry` und `outlinePoints` (für die neuen Teile nicht mehr nötig).

Es bleiben: `spread`, `millimetres`, `formatSize`, `fitDistance` (auf Bounding Boxes umgestellt), die Namensschilder
und das Vollbild.

## 13. Neue Abhängigkeiten und Lizenzen

| Baustein | Lizenz | Wofür |
|---|---|---|
| `openscad-wasm-prebuilt` 1.2.0 (npm, in `web/`) | GPL-2.0-or-later | OpenSCAD als WebAssembly; als eigener Prozess aufgerufen |
| BOSL2 (fester Commit) | BSD-2-Clause | Rundungen, Fasen, Übergänge |
| `pypdfium2` (pip) | Apache-2.0 / BSD-3 | PDF-Seiten durchsuchen und als Bild rendern |
| matplotlib (schon da) | PSF-basiert | Renders für die Sichtprüfung |

Alle sind mit AGPL-3.0 vereinbar. Ideen ohne Code-Übernahme stammen aus:
- CADAM (GPL-3.0): Claude plus OpenSCAD-WASM;
- img2threejs (Apache-2.0): Prüfrunden mit Renders.

## 14. Tests

- **Reine Logik:**
  - Maßblatt, CAD und Prüfung parsen, mit Grenzen und Abschneiden;
  - Slug;
  - Budget-Entscheidung vor jedem Schritt;
  - Sitzungsgrenze;
  - Warteschlange.
- **Ablauf mit Attrappen:**
  - Eine Claude-Attrappe spielt Recherche, CAD und Prüfung nach, eine Compiler-Attrappe liefert STL oder Fehler.
  - Geprüft wird die ganze Kette: Fortschrittsnachrichten in der richtigen Reihenfolge, frühes Ende bei `good`,
    Fehler-Rückkopplung, Wegfall kaputter Teile, Budget-Stopp, Recherche-Fehler führt zu „geschätzt“, Ergebnis im
    Speicher.
- **Downloads:** Ein Fake-Transport prüft, dass `http`, `localhost`, private IPs, falsche Inhaltstypen, zu große
  Dateien und unbekannte URLs abgelehnt werden.
- **PDF:** matplotlib erzeugt ein PDF mit zwei Seiten, und der Finder liefert die Seite mit dem `find`-Text.
- **Meshes und Renders:** STL lesen und Bounding Box bestimmen; ein Render hat die richtige Größe und ist nicht leer.
- **Server:** Die Route liefert nur Dateien aus dem Manifest, `..` und unbekannte Dateien ergeben 404.
- **Echt (Marker `scad`, wie `model`):**
  - OpenSCAD-WASM kompiliert ein BOSL2-Teil;
  - OpenSCAD kann keine Datei vom Mac lesen.
- **Browser (Vitest):**
  - `model`-Nachrichten im Store;
  - Fortschrittstexte;
  - Plakette mit Domain oder „geschätzt“;
  - Bounding-Box-Mathematik für Schilder und Maßlinien.

## 15. Nachtrag 2026-10-02: was die echten Läufe zeigten

Drei echte Bauten für das iPhone 14 haben sechs Dinge aufgedeckt. Alle sind behoben und getestet.

1. **Die Zeichnung steht nicht im Handbuch.** Apples Accessory Design Guidelines (33 MB) enthalten keine
   Geräte-Zeichnungen mehr. Apple veröffentlicht eine PDF pro Gerät
   (`developer.apple.com/download/files/accessories/dimensional-drawings/<gerät>.pdf`). Die Recherche sucht deshalb
   ausdrücklich nach der Maßzeichnung und meldet nur Links aus ihren Ergebnissen.
2. **Links auf gesehenen Seiten.** Die PDF stand als Link auf einer abgerufenen Übersichtsseite. Erlaubt sind jetzt
   auch Adressen auf demselben Host wie eine gesehene Seite (4.4); alle anderen Regeln bleiben.
3. **Zeichnungen sind Bilder.** In Apples PDF sind die Maßzahlen Vektorgrafik; als Text steht nur „iPhone 14“ auf
   jeder Seite. Unter gleich guten Seiten gewinnt deshalb die mit dem wenigsten Text, nicht die Vertragsseite (4.3).
4. **Lange Antworten brauchen einen Stream.** Ohne Stream blieb der CAD-Aufruf mit Zeichnung 26 Minuten hängen: Das
   SDK wiederholt Zeitüberschreitungen automatisch zweimal, und eine stille Verbindung von über zwei Minuten kam nicht
   zurück. Recherche, CAD und Prüfung laufen jetzt als Stream, ohne automatische Wiederholung, mit `model_timeout_s`
   als Frist für den ganzen Aufruf. Gemessen danach: 140 s für den CAD-Aufruf mit Zeichnung.
5. **CGAL und dünne Platten.** Ein abgerundeter Quader, der dünner ist als seine Rundung, bricht OpenSCADs Hülle. Der
   BOSL2-Spickzettel nennt den robusten Weg (`linear_extrude` + `rect(rounding=)`).
6. **Lesbarkeit im Vollbild.** Große Schalen setzen ihre Punkte verteilt auf den Rand. Namensschilder weichen auch den
   Maß-Kapseln aus. Die Plakette nennt die Website ohne Subdomain („apple.com“), und dünne Teile zeigen Hundertstel.

