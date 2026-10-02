# Object Intelligence – alles erklärt

Diese Datei erklärt das ganze Projekt: **was** es tut, **wie** es funktioniert und **warum** es so gebaut ist. Sie
ist aufgebaut wie dein `Road to Software Engineer`, nur für dieses eine Projekt. Du kannst sie von vorn nach hinten
lesen, darin nachschlagen und mit ihr lernen. Fachbegriffe bleiben Englisch: Beim ersten Auftauchen werden sie erklärt,
und alle stehen noch einmal im Glossar (Abschnitt 14).

Stand: 2026-10-02 · alle sechs Teilprojekte fertig · Code: https://github.com/Jkalwa05/object-intelligence

## Inhalt

0. Wie du diese Datei benutzt
1. Das Projekt in einem Satz
2. Was du als Nutzer erlebst
3. Das große Bild: zwei Programme, ein Ziel
4. Die Reise eines Kamerabilds, Schritt für Schritt
5. Das Beweisbuch: wie aus Antworten eine ehrliche Stufe wird
6. Die sechs Teilprojekte
7. Claude richtig einsetzen (AI Engineering)
8. Der Browser-Teil (TypeScript und React)
9. Datenschutz: was den Mac verlässt und was nie
10. Kosten: woher sie kommen und wie sie gedeckelt sind
11. Tests: warum, wie, woran du sie erkennst
12. Fehler, die wir unterwegs gefunden haben
13. Werkzeuge und Arbeitsweise
14. Glossar
15. Code lesen: Übungen passend zu deinem Lehrplan
16. Zahlen zum Projekt
17. Offene Punkte
18. Prompt für eine neue Session

---

## 0. Wie du diese Datei benutzt

- **Reihenfolge:** Lies zuerst die Abschnitte 1 bis 5, sie sind der Kern. Danach kannst du springen, zum Beispiel zum
  Teilprojekt, das dich gerade interessiert.
- **Was, Wie, Warum:** Fast jeder Teil beantwortet diese drei Fragen.
  - **Was** passiert?
  - **Wie** ist es gebaut (Datei, Zahlen)?
  - **Warum** so und nicht anders?
- **Dateipfade** wie `oi/focus.py` kannst du direkt in VS Code öffnen. `oi/` ist der Python-Teil, `web/src/` der
  Browser-Teil.
- **Zahlen** stammen aus dem Code (die meisten aus `oi/config.py`) oder aus echten Messungen in `runs/`. Geschätzt ist
  hier nichts, und wo eine Schätzung danebenlag, steht das dabei.
- **Code lesen:** Abschnitt 15 enthält Leseübungen nach deinem Lernprinzip „Code lesen“. Sie beginnen bei `if`,
  `elif` und `else`, also genau da, wo du im Lehrplan gerade stehst.

---

## 1. Das Projekt in einem Satz

Du hältst einen Gegenstand in die Kamera deines Macs. Das Programm findet ihn in deiner Hand und sagt ehrlich, wie
sicher es weiß, was das ist. Es recherchiert seine genauen Maße, baut daraus ein CAD-Modell (das Hologramm) und
beantwortet Fragen, die du laut stellst.

### Die Analogie: ein Detektivbüro

| Rolle | Wer im Projekt | Eigenschaften |
|---|---|---|
| **Die Augen** | die Kamera-Pipeline auf deinem Mac | schaut 12-mal pro Sekunde hin: Wo sind Dinge, wo sind Hände, was hält die Hand? Kennt keine Produktnamen, ist aber schnell und kostet nichts. |
| **Der Experte** | Claude, über das Internet | bekommt ein einziges gutes Foto, und zwar nur vom Gegenstand. Liefert Indizien („Apple-Logo, zwei Kameras diagonal, iPhone 14 oder 15“). Langsam (4–10 s) und kostet Geld. |
| **Das Beweisbuch** | reine Logik in `oi/belief.py` | sammelt die Aussagen über mehrere Ansichten und fällt das Urteil: *sicher*, *wahrscheinlich*, *unsicher* oder *nur Kategorie*. |

**Warum so und nicht einfach „Foto an die KI, Antwort anzeigen“?** Eine KI antwortet immer irgendetwas, auch wenn
sie rät. Wertvoll ist die Pipeline drumherum:
- Sie entscheidet, *welches* Bild *wann* zu Claude geht.
- Sie schützt deine Privatsphäre.
- Sie deckelt die Kosten.
- Sie macht Unsicherheit sichtbar, statt sie zu verstecken.

Genau das unterscheidet ein durchdachtes AI-Produkt von einem einzelnen API-Aufruf.

---

## 2. Was du als Nutzer erlebst

1. **Start.** Du startest auf eine von zwei Arten:
   - Doppelklick auf `Object Intelligence.command`;
   - oder im Terminal `uv run python -m oi`.

   Der Server startet, der Browser öffnet http://127.0.0.1:8766 und fragt nach der Kamera.
2. **Kalibrierung (5 Sekunden).** Das Programm misst den Hintergrund: Lampe, Regal, Treppe. Danach benennt ein
   einziger Claude-Aufruf alles auf einmal. Die violetten Markierungen bleiben eingefroren: kein Flackern, und sie
   können nie „das Objekt“ werden.
3. **Hand ins Bild.** Sobald Apple Vision deine Hand sicher erkennt, bekommt sie eine cyanfarbene Umrandung.
4. **Gegenstand greifen.** Liegen mindestens drei deiner Fingergelenke auf dem Gegenstand, bekommt er grüne Ecken
   und ein Namensschild. Während Claude nachdenkt, läuft eine Scan-Linie über die Box.
5. **Eintrag in der Seitenleiste.** Der Eintrag zeigt:
   - Stufe und Satz („Das ist wahrscheinlich ein Apple iPhone 14.“);
   - die Kandidaten mit Balken;
   - die Indizien als Chips;
   - den Knopf „Neu prüfen“.

   Eine dünne grüne Linie verbindet die Box mit dem Eintrag.
6. **Bei „unsicher“.** Das Programm bittet um die Ansicht, die entscheidet („Zeig mir bitte die Unterseite“). Oder du
   tippst den richtigen Kandidaten an. Dann ist er *sicher* und trägt die Plakette „von dir bestätigt“.
7. **Ab „wahrscheinlich“** erscheint der Steckbrief.
8. **Ab „sicher“** entsteht das Präzisionsmodell (Teilprojekt 6). Der Eintrag zeigt, was gerade passiert („Recherchiere
   Maße …“, „Baue CAD-Modell …“). Danach dreht sich das CAD-Modell im Eintrag. „⤢“ öffnet es im Vollbild: mit
   Maßlinien, einem nummerierten Schild an jedem Teil und den recherchierten Maßen samt Quelle.
9. **Fragen.** Du hältst die Leertaste, fragst („Wie schwer ist das?“) und lässt los. Die Antwort steht im Eintrag und
   wird vorgelesen.

| Taste | Wirkung |
|---|---|
| `Leertaste` halten | Frage zum Gegenstand in der Hand (sonst zum zuletzt geöffneten Eintrag) |
| `M` | Stimme an/aus (Antworten auf deine Fragen werden immer vorgelesen) |
| `D` | Telemetrie: Bildraten, Latenzen, Aufrufe, Kosten, genaue Anteile |
| `S` | Spiegelansicht |
| `R` | Hintergrund neu kalibrieren |
| `Esc` | Vollbild-Hologramm schließen |

---

## 3. Das große Bild: zwei Programme, ein Ziel

Object Intelligence besteht aus **zwei Programmen**, die beide auf deinem Mac laufen.

```
Browser (web/, TypeScript + React)                 Server (oi/, Python + FastAPI)
┌─────────────────────────────┐   Kamerabilder   ┌──────────────────────────────────────┐
│ Kamera, Mikrofon            │ ───────────────▶ │ Erkennen: YOLOE-26 + BoT-SORT         │
│ Overlay (Boxen, Hände)      │                  │ Hände: Apple Vision, Gesichter: YuNet │
│ Seitenleiste, Hologramm     │ ◀─────────────── │ Fokus, Schnappschuss, Auslöser        │
│ Stimme (Vorlesen)           │  Ergebnisse      │ Beweisbuch, Whisper, Caches, Logs     │
└─────────────────────────────┘    (WebSocket)   └──────────────┬───────────────────────┘
                                                                │ nur der Objekt-Ausschnitt
                                                                ▼
                                                           Claude API
```

**Warum zwei Programme?**
- **Der Browser** kann Kamera und Mikrofon sicher öffnen und hat die besten Werkzeuge für Oberflächen: React für die
  Seitenleiste, three.js für 3D, Canvas für Zeichnungen. Niemand muss eine App installieren.
- **Python** hat die Werkzeuge für Machine Learning:
  - PyTorch und Ultralytics für YOLOE, auf der Apple-GPU (`mps`);
  - Apple Vision über PyObjC;
  - Whisper über MLX.
- **Der API-Schlüssel** bleibt auf dem Server (in `.env`). Der Browser bekommt ihn nie zu sehen.

**Warum ein WebSocket?** Bei normalen HTTP-Anfragen fragt der Browser und der Server antwortet, jedes Mal neu. Ein
WebSocket ist eine stehende Leitung in beide Richtungen, wie ein Telefonat statt Briefen:
- Der Browser schickt 12 Bilder pro Sekunde.
- Der Server meldet Boxen, Erkennungen und Antworten, sobald sie da sind.

### Wo was liegt

| Ordner/Datei | Inhalt |
|---|---|
| `oi/` | der Python-Server: Pipeline, Logik, Claude, Whisper |
| `web/src/` | der Browser-Teil: React, Overlay, Hologramm, Stimme |
| `tests/` | Python-Tests (pytest); die Browser-Tests liegen als `*.test.ts` neben dem Code |
| `docs/superpowers/specs/` | die Design-Dokumente der sechs Teilprojekte (Entscheidungen und Gründe) |
| `docs/superpowers/plans/` | Bauanleitungen für die Teilprojekte 1–3 und 6 |
| `cache/` | gespeicherte Steckbriefe und Präzisionsmodelle (`cache/models/<produkt>/`), nicht in Git |
| `web/scad/compile.mjs` | der CAD-Compiler: OpenSCAD als WebAssembly, von Node ausgeführt |
| `runs/` | Protokoll jedes Claude-Aufrufs mit Bild, Antwort, Tokens, Kosten, Dauer (nicht in Git) |
| `models/` | das Gesichtsmodell YuNet und die CAD-Bibliothek BOSL2 (beim ersten Start geladen) |
| `.env` | dein API-Schlüssel (nie in Git, siehe `.gitignore`) |
| `Object Intelligence.command` | der Doppelklick-Starter |

---

## 4. Die Reise eines Kamerabilds, Schritt für Schritt

So sieht der Weg eines einzelnen Bildes aus:

### Schritt 1: Der Browser nimmt ein Bild auf

- **Was:** Die Kamera liefert ein Video mit 30 Bildern pro Sekunde. 12-mal pro Sekunde zeichnet der Browser das
  aktuelle Videobild auf ein unsichtbares Canvas und macht daraus ein JPEG.
- **Wie:** `web/src/camera/capture.ts`
  - höchstens 1280 Pixel breit, JPEG-Qualität 0,8;
  - nie gespiegelt: die Spiegelung gibt es nur in der Anzeige;
  - verschickt wird nur, wenn in der Leitung weniger als 1 MB wartet.
- **Warum 12 und nicht 30?** Für das Verfolgen von Dingen reichen 12 Bilder. Mehr würde nur die GPU heizen und die
  Leitung verstopfen. Die Anzeige läuft trotzdem flüssig mit 30–60 Bildern, denn das Video im Browser ist direkt
  die Kamera. Nur die Boxen kommen vom Server.

### Schritt 2: Das Bild wird verpackt

- **Was:** Jedes Bild reist als *Binärnachricht* mit drei Teilen:

  ```
  4 Bytes: Länge des Kopfes | Kopf als JSON (frame_id, t_capture_ms, w, h) | JPEG-Bytes
  ```
- **Wie:** Der Browser packt in `web/src/camera/frame.ts`, der Server packt in `oi/ingest.py` aus.
- **Warum binär?** Ein JPEG als Text (Base64) wäre ein Drittel größer. Der Kopf trägt die Aufnahmezeit
  `t_capture_ms`: Alle Zeitregeln (2 s, 3 s, 0,5 s) rechnen mit der Uhr des Browsers. So verhält sich das Programm
  gleich, egal wie beschäftigt der Server gerade ist.

### Schritt 3: Der Server nimmt nur das neueste Bild

- **Was:** Kommen Bilder schneller, als der Server sie verarbeitet, gewinnt immer das neueste. Ältere werden
  verworfen und gezählt („dropped“).
- **Wie:** `FrameSlot` in `oi/ingest.py`. Das ist ein Platz für genau ein Bild.
- **Warum:** Bei einer Live-Anzeige ist „aktuell“ wichtiger als „vollständig“. Eine Warteschlange würde sich bei Last
  füllen, und die Boxen hingen Sekunden hinterher. Wie bei einem Nachrichtenticker: Du willst die neueste Meldung, nicht
  alle verpassten nacheinander.

### Schritt 4: Erkennen und Verfolgen (YOLOE-26 + BoT-SORT)

- **Was:** Ein *Detektor* findet alle Dinge im Bild, mit Box, Umriss (*Polygon*) und grobem Namen („phone“,
  „bottle“). Ein *Tracker* gibt jedem Ding eine feste Nummer, die von Bild zu Bild gleich bleibt.
- **Wie:** `oi/perception.py`
  - Modell `yoloe-26s-seg-pf.pt`, Bildgröße 640, Mindestvertrauen 0,25, auf der Apple-GPU (`mps`);
  - Tracker BoT-SORT (`oi/trackers/botsort.yaml`).

  Der Detektor läuft in einem eigenen Thread (`asyncio.to_thread`). Der Server kann so währenddessen weiter Nachrichten
  empfangen.
- **Warum YOLOE „prompt-free“?** Ein normaler Detektor kennt nur seine Trainingsklassen, etwa 80 Stück. YOLOE ist
  *open vocabulary*: Es erkennt tausende Dinge, ohne dass man ihm vorher sagt, wonach es suchen soll.
- **Warum nicht gleich die Produktnamen von YOLOE?** Der Detektor sagt „phone“, nie „iPhone 14“. Für Namen braucht es
  Claudes Wissen.

### Schritt 5: Hände finden (Apple Vision)

- **Was:** Apples eigenes Handmodell findet bis zu 21 Gelenke pro Hand: Fingerspitzen, Knöchel, Handgelenk.
- **Wie:** `oi/hands.py`. Eine Hand zählt nur, wenn sie diese Bedingungen erfüllt:
  - Vision ist sich zu mindestens 60 % sicher;
  - mindestens 6 Gelenke sind sichtbar;
  - sie wurde in zwei Bildern hintereinander am gleichen Ort gefunden (`HandConfirmer`).

  Aus den Gelenken wird ein weicher Umriss mit 16 Punkten. Das ist die cyanfarbene Umrandung.
- **Warum nicht YOLOEs Label „hand“?** YOLOE sagt fast nie „hand“. Die Regel „nur was du hältst, wird analysiert“
  braucht aber in jedem Bild verlässliche Hände. Die Zwei-Bilder-Regel filtert „Geisterhände“, die nur ein einziges
  Bild lang auftauchen.

### Schritt 6: Gesichter und Personen (YuNet, Datenschutz)

- **Was:** Ein kleines, spezialisiertes Gesichtsmodell findet Gesichter. Zusammen mit den Personen-Labels von YOLOE
  entstehen daraus „Personenzonen“.
- **Wie:** `oi/faces.py` (OpenCV YuNet, Mindestwert 0,6) und `oi/privacy.py`.
- **Warum:** YOLOE nennt Teile eines Gesichts oft „glasses“ oder „short hair“, aber nie „face“. Das Versprechen
  „dein Gesicht verlässt den Mac nie“ hängt deshalb an einem eigenen, zuverlässigen Gesichtsmodell (Details in
  Abschnitt 9).

### Schritt 7: Den Hintergrund einfrieren (Kalibrierung)

- **Was:** In den ersten 5 Sekunden sammelt das Programm alles, was sich nicht bewegt. Was in mindestens der Hälfte
  der Bilder an derselben Stelle war, wird eine Hintergrund-Markierung und bleibt danach eingefroren.
- **Wie:**
  - `oi/scene.py`: Zwei Boxen gelten als „dieselbe Stelle“, wenn sie sich zu mindestens 50 % überlappen (*IoU*).
  - Danach benennt ein Claude-Aufruf alle Markierungen auf einmal, aus einem Bild, in dem jede Person grau übermalt
    ist.
  - Mit `R` beginnt die Kalibrierung von vorn.
- **Warum:** Im ersten Live-Test zielte das Programm ständig auf Treppe und Regal. Gleichzeitig flackerten die Labels
  des Hintergrunds. Eingefroren ist der Hintergrund ruhig, und er kann nie den Fokus stehlen. Ein Aufruf für alles
  ist billiger und konsistenter als viele kleine Aufrufe.

### Schritt 8: Der Fokus: Welches Ding hältst du?

- **Was:** Von allen erkannten Dingen bekommt höchstens eines den Fokus, also die grüne Box und die teure Analyse.
  Das ist das Ding, auf dem deine Finger liegen.
- **Wie:** `oi/focus.py`
  - **Gehalten** heißt: Mindestens 3 Gelenke einer Hand liegen in der Box des Dings (die Box ist dafür pro Seite um
    10 % vergrößert, weil Finger um Kanten greifen). Das Ding ist höchstens 8-mal so groß wie die Hand: nicht die
    Treppe hinter der Hand.
  - **Gedächtnis:** Eine Hand, die in den letzten 2 Sekunden auf dem Ding lag, zählt noch, denn die Handerkennung
    flackert.
  - **Nie gehalten:**
    - der eingefrorene Hintergrund;
    - was du *trägst*: Was zu mindestens 25 % in deiner Körperzone liegt und bis an den unteren Bildrand reicht, ist
      dein T-Shirt, nicht ein Gegenstand.
  - **Punkte:** Gibt es mehrere Kandidaten, entscheiden Punkte: Größe 30 %, Bildmitte 20 %, Hand 25 %, Ruhe 15 %,
    Neuheit 10 %.
  - **Wechsel:** Ein Herausforderer muss 0,15 Punkte besser sein und das 0,5 s lang bleiben. Diese Hysterese
    verhindert ein Hin- und Herspringen.
- **Warum:** „Nur was du hältst“ ist die einfachste Regel, die ein Mensch sofort versteht. Sie spart Geld, weil nur
  ein Ding analysiert wird, und schützt dich: Dein Körper wird nie analysiert.

### Schritt 9: Der Schnappschuss: das beste Bild statt „Halt still“

- **Was:** Aus dem laufenden Video wird ein Schnappschuss gemacht, und zwar das schärfste Bild aus einem halben
  Sekunden-Fenster.
- **Wie:** `oi/views.py`
  - **Schärfe:** Varianz des Laplace-Filters, Mindestwert 60. Bewegung macht unscharf, also ist das schärfste Bild
    automatisch das ruhigste.
  - **Geduld:** Kommt 2 s lang kein Bild über die Schwelle, geht das schärfste trotzdem raus.
  - **Ausschnitt:** Die Box plus 12 % Rand. Alles außerhalb des Umrisses des Dings wird grau (128), der Umriss ist
    dafür um 4 % geweitet. Die lange Kante hat höchstens 1024 Pixel, JPEG-Qualität 90.
  - **Neue Ansicht?** Ein *dHash* ist ein Fingerabdruck des Bildes aus 64 Bits. Unterscheiden sich zwei Fingerabdrücke
    in mindestens 14 Bits, zählt das Bild als neue Ansicht. So kostet dieselbe Seite nicht zweimal.
- **Warum:** Früher stand im Bild „Halte es ruhig“. Das war Unsinn, denn ein Gegenstand in der Hand ist nie still. Du
  hattest die Idee: Aus dem Video ein ruhiges Bild herauspicken. Hinweise wie „Bitte ganz ins Bild“ gibt es nicht
  mehr. Ob die Box erscheint, ist selbst die Rückmeldung.

### Schritt 10: Der Auslöser: Wann geht ein Bild zu Claude?

- **Was:** Sechs Regeln, in fester Reihenfolge geprüft.
- **Wie:** `oi/trigger.py`, Funktion `decide`. Das ist reine Logik, siehe Übung 1 in Abschnitt 15.

| Reihenfolge | Bedingung | Entscheidung |
|---|---|---|
| 1 | kein Fokus oder kein fertiger Schnappschuss | warten |
| 2 | für dieses Ding läuft schon ein Aufruf, oder 2 Aufrufe laufen insgesamt | beschäftigt (später erneut) |
| 3 | 150 Aufrufe in dieser Sitzung erreicht | Sitzungsgrenze |
| 4 | „Neu prüfen“ wurde geklickt | Aufruf |
| 5 | das Ergebnis ist endgültig | warten |
| 6 | 4 Aufrufe für dieses Ding erreicht | Objektgrenze |
| – | erster Aufruf oder neue Ansicht | Aufruf |

- **Warum diese Reihenfolge?** Die Sitzungsgrenze kommt vor „Neu prüfen“: Auch ein Klick darf das Budget nicht
  sprengen. „Neu prüfen“ kommt vor „endgültig“: Wenn du ausdrücklich fragst, wird geprüft.

### Schritt 11: Claude identifiziert

- **Was:** Claude bekommt den Ausschnitt und eine feste Anleitung. Zurück kommt eine *strukturierte* Antwort:
  - `category`: zum Beispiel „Smartphone“;
  - `candidates`: bis zu 4 Kandidaten mit Marke, Modell, Variante, Tiefe und sichtbaren Indizien;
  - `readable_text`: lesbarer Text auf dem Gegenstand;
  - `distinguishable`: Lassen sich die Kandidaten von außen unterscheiden?
  - `next_view`: Welche Ansicht würde entscheiden?
  - `self_assessment`: Claudes eigene Sicherheit (high, medium oder low);
  - `generic_description`: eine Beschreibung, wenn kein Produkt erkennbar ist.
- **Wie:** `oi/identify.py`, Abschnitt 7 erklärt Claude ausführlich.
- **Der Aufruf läuft im Hintergrund:** Die Bildschleife wartet nie auf Claude. Die Boxen bewegen sich weiter, während
  Claude 4–10 s nachdenkt.

### Schritt 12: Das Beweisbuch urteilt

Siehe Abschnitt 5: Aus allen Antworten wird eine Rangliste und eine ehrliche Stufe.

### Schritt 13: Nachrichten zurück an den Browser

- **Was:** Der Server meldet in jedem Bild `tracks` mit der Fokus-Box, deinen Händen und den Gesichtern. Dazu kommen
  bei Bedarf `identity`, `scene`, `profile`, `shape`, `question`, `telemetry` und `notice`.
- **Wie:** Die Formate sind in `oi/contracts.py` (Python, mit *pydantic*) und in `web/src/protocol.ts` (TypeScript)
  definiert. Die Datei `tests/fixtures/protocol-examples.json` wird von Python geschrieben und im Browser-Test geprüft.
- **Warum diese Doppelung mit Test?** Python und TypeScript können sich keine Typen teilen. Ohne den Test würde eine
  Änderung auf einer Seite die andere still kaputtmachen.

### Schritt 14: Der Browser zeichnet

- **Was:** Das Overlay zeichnet Boxen, Hände und Namensschilder über das Video. Seitenleiste und Hologramm zeigen die
  Ergebnisse.
- **Wie:**
  - `web/src/hud/Overlay.tsx` zeichnet in jedem Animationsbild auf ein Canvas.
  - Boxen gleiten weich zur neuen Position, statt zu springen (Zeitkonstante 80 ms, `smoothing.ts`).
  - Gespeichert wird alles in einem *Store* (`web/src/store.ts`).
- **Warum ein Canvas statt React-Elementen für die Boxen?** 60-mal pro Sekunde neu zu zeichnen ist für ein Canvas
  billig. React würde dafür jedes Mal seinen Komponentenbaum neu berechnen.

---

## 5. Das Beweisbuch: wie aus Antworten eine ehrliche Stufe wird

`oi/belief.py` ist das Herz der Ehrlichkeit. Es ist reine Logik: keine Kamera, kein Netz, nur Zahlen und Regeln.

### Stimmen zählen

Jede Antwort von Claude ist eine Abstimmung:
- Der Kandidat auf Platz 1 bekommt 1,0 Punkte, Platz 2 0,5, Platz 3 0,25, Platz 4 0,125.
- Jede Stimme wird mit der Bildqualität `q` (zwischen 0,5 und 1,0, aus der Schärfe) gewichtet.

Aus allen Stimmen entsteht eine Rangliste. Der *Anteil* eines Kandidaten sind seine Punkte geteilt durch alle Punkte.
Der *Vorsprung* ist sein Anteil minus der Anteil des Zweiten.

### Die vier Stufen

| Stufe | Wann |
|---|---|
| **sicher** | wenn eine der Bedingungen unten gilt |
| **wahrscheinlich** | sonst, wenn der Vorsprung mindestens 0,15 beträgt |
| **unsicher** | der Vorsprung ist kleiner als 0,15, Claude selbst sagt „low“, oder die Kandidaten sind von außen nicht zu unterscheiden |
| **nur Kategorie** | Claude erkennt kein Produkt, nur eine Art Ding („rote Keramiktasse“) |

**Sicher** wird ein Kandidat auf einem von drei Wegen:
- Sein Modellname ist auf dem Gegenstand lesbar, als ganzes Wort. Kurze Namen ohne Ziffer wie „Pro“ zählen nicht.
- Er stand in zwei *unabhängigen Ansichten* auf Platz 1, mit einem Anteil von mindestens 0,6 und einem Vorsprung von
  mindestens 0,3.
- Du hast ihn angetippt.

### Warum keine Prozentzahlen?

Eine Zahl wie „87 %“, die ein Sprachmodell nennt, ist keine gemessene Wahrscheinlichkeit, sondern ein geratenes
Gefühl. Wer „87 %“ liest, glaubt an eine Messung. Stufen sind ehrlicher: Sie sagen, *welche Art* von Beweis vorliegt.
Die genauen Anteile gibt es trotzdem, aber nur in der Telemetrie-Ecke (`D`), für Neugierige.

### Ein Beispiel: iPhone 14 oder 15?

Von hinten sehen iPhone 14 und 15 fast gleich aus. So läuft es ab:

1. **Erste Ansicht.** Claude sagt „iPhone 14, sonst 15“ und setzt `distinguishable` auf false. Dazu kommt
   `next_view`: „die Unterseite (Lightning oder USB-C)“. Das Beweisbuch sagt *unsicher* und bittet um genau diese
   Ansicht.
2. **Neue Ansicht.** Du drehst das Handy, und der Fingerabdruck des Bildes ändert sich genug. Claude sieht den
   Lightning-Anschluss und sagt erneut „iPhone 14“.
3. **Urteil.** Zwei unabhängige Ansichten, Anteil und Vorsprung reichen: *sicher*.

Oder du tippst einfach „Apple iPhone 14“ an.

**Warum zählen nur unabhängige Ansichten?** Zehnmal dasselbe Foto ist kein zehnfacher Beweis. Deshalb hat jede
Ansicht eine Nummer (`view_id`), und nur verschiedene Nummern zählen für „sicher“. Sagt Claude, die Kandidaten seien
von außen *nicht* unterscheidbar, hilft auch Einigkeit über mehrere Ansichten nicht. Das Ergebnis bleibt dann
*unsicher*, solange noch eine trennende Ansicht möglich ist.

### Zusammenführen und Bestätigen

- **Bestätigen** (`confirm`): Dein Tipp macht den Kandidaten sicher und endgültig. Keine spätere Antwort kann das
  überstimmen.
- **Zusammenführen** (`absorb`): Stellt sich heraus, dass zwei Einträge derselbe Gegenstand sind, wandern die Ansichten
  des einen in das Beweisbuch des anderen. Ihre Nummern werden dabei in einen frischen Block verschoben (+10.000). So
  zählen die Ansichten beider Spuren als unabhängig, und zwei Seiten zusammen können „sicher“ ergeben.

---

## 6. Die sechs Teilprojekte

Das Projekt wurde in sechs Teilprojekten gebaut. Jedes hat ein eigenes Design-Dokument in `docs/superpowers/specs/`, in
dem deine Entscheidungen stehen.

### Teilprojekt 1: Sehen & Identifizieren

- **Ziel:** Gegenstand in der Hand finden, verfolgen, ehrlich identifizieren.
- **Gebaut:** alles aus Abschnitt 4 und 5. Dazu kommen die Lehren aus deinen Live-Tests (Spec §8–§13):
  - Hintergrund-Kalibrierung, damit Treppe und Regal nie den Fokus bekommen;
  - Fokus nur auf gehaltene Dinge (Fingergelenke);
  - Hände mit Akzentfarbe statt Weiß;
  - Schnappschuss aus dem Video statt „Halte es ruhig“;
  - keine Hinweise mehr;
  - das T-Shirt-Problem (Regel „getragen“);
  - die Wiedererkennung.
- **Wiedererkennung:** Der Tracker verliert ein Ding manchmal kurz und gibt ihm eine neue Nummer. Dann bleiben
  Eintrag, Ergebnis und Aufrufzähler erhalten, wenn alle drei Bedingungen gelten:
  - das alte Ding ist höchstens 3 s weg;
  - es ist höchstens doppelt oder halb so groß;
  - die Farben passen (`oi/appearance.py`: ein Farb-Histogramm, Ähnlichkeit mindestens 0,5).
- **Warum Farben zuletzt?** Farben allein trennen schlecht: Ein iPhone von vorn und von hinten ist sich kaum ähnlich.
  Deshalb prüfen erst Zeit, Ort und Größe, und die Farben sind nur die letzte Bestätigung. Im Zweifel wird lieber neu
  analysiert, als einem Ding einen falschen Namen zu geben.

### Teilprojekt 2: Produkt-Steckbrief

- **Ziel:** Zu einem erkannten Produkt das Wichtigste anzeigen.
- **Deine Entscheidungen:**
  - alle vier Teile: Fakten, Zusammenfassung, Erscheinung und Startpreis, Wissenswertes;
  - aus Claudes Wissen, *ohne Quellen*;
  - ab der Stufe „wahrscheinlich“;
  - eigener Bereich, und die Zusammenfassung wird einmal vorgelesen, wenn die Stimme an ist.
- **Wie:** Ein Aufruf ganz ohne Bild, nur mit Produktname und Kategorie (`PROFILE_PROMPT` in `oi/identify.py`). Jeder
  Wert ist mit „laut Claude“ markiert.
- **Cache:** `cache/profiles.json`, Schlüssel Sprache und Modell (`de:apple iphone 14`). Jedes Produkt kostet nur
  einmal, für immer.
- **Kosten:** etwa 1,2 ct und 6 s.
- **Warum ohne Quellen?** Du wolltest die Infos ohne den Aufwand einer Recherche. Ehrlich bleibt es, weil überall
  „laut Claude“ steht. Kennt Claude das genaue Modell nicht, sagt es das, statt zu raten.

### Teilprojekt 3: Hologramm & Seitenleiste

- **Ziel:** Ein 3D-Modell des Produkts und eine Leiste, die sich jedes Objekt merkt.
- **Heute:** Das Grundformen-Hologramm wurde durch das Präzisionsmodell aus Teilprojekt 6 ersetzt. Die Seitenleiste
  ist geblieben. Der Abschnitt zeigt, wie es vorher war, weil der Vergleich lehrreich ist.
- **Hologramm vs. echter Scan:** Das Hologramm ist ein „LEGO-Nachbau aus dem Gedächtnis“. Ein Scan wäre ein „3D-Foto
  rundherum“ (Apple Object Capture). Der Scan wurde geparkt, weil das Hologramm reicht.
- **Wie das Hologramm entsteht:**
  - Claude beschreibt das Produkt aus seinem Wissen und dem Ausschnitt als höchstens 16 *Grundformen* in Millimetern.
    Die Formen sind Quader, abgerundeter Quader, Zylinder, Kegel, Kugel und Kapsel, jeweils mit Größe, Position,
    Drehung und Farbe.
  - Der Browser baut daraus mit three.js ein maßstabsgetreues Modell, mit grünen Kanten und halbdurchsichtigen Flächen
    (`web/src/hud/hologramScene.ts`, `shapeMath.ts`).
- **Cache:** `cache/shapes.json`, Schlüssel ist das Modell.
- **Kosten:** etwa 1,8 ct und 10 s.
- **Die Seitenleiste:**
  - Jedes erkannte Objekt bleibt angeheftet, höchstens 8 Einträge, das neueste oben.
  - Nur das gehaltene Objekt ist aufgeklappt; die anderen öffnest du per Klick, wie ein Drop-down.
  - Ein „unsicheres“ Objekt kannst du durch Antippen bestätigen.
  - Erkannte Objekte bleiben 10 Minuten im Speicher, alle anderen 30 Sekunden.
- **Zusammenführen:** Der Controller wurde einmal zu zwei Einträgen: einmal „schwarzes Gerät“ und einmal „DualShock 3“.
  Seitdem vergleicht Claude jedes neue Objekt einmal mit den letzten drei. Die Bilder dafür sind klein (384 px, je
  etwa 200 Tokens) und kosten 0,4–0,5 ct bei 3–5 s. Ist es dasselbe Ding von einer anderen Seite, werden die Einträge
  eins. Was gleichzeitig im Bild ist, wird nie zusammengeführt, denn das sind zwei Dinge.

### Teilprojekt 4: Fragen & Sprache

- **Ziel:** Fragen zum Gegenstand laut stellen und eine gesprochene Antwort bekommen.
- **Deine Entscheidungen:**
  - Leertaste halten;
  - Whisper lokal;
  - Claude entscheidet über die Websuche;
  - Ziel ist das Objekt in der Hand;
  - Antworten werden vorgelesen.
- **Ablauf:**
  1. **Leertaste gedrückt (ohne Tastenwiederholung):** Das Mikrofon nimmt auf (`web/src/voice/recorder.ts`).
  2. **Loslassen:**
     - Kürzer als 0,3 s war ein Tippen, keine Frage.
     - Nach spätestens 30 s endet die Aufnahme von selbst.
     - Die Aufnahme geht als `ask` an den Server: 16 kHz, Mono, 16-Bit-Zahlen, als Base64-Text.
  3. **Whisper** (`oi/speech.py`, Modell `whisper-large-v3-turbo` über MLX, etwa 1,5 GB) macht daraus Text. Für 3,7 s
     Sprache braucht es 0,4 s, auf deinem Mac. Das Modell wird beim Start im Hintergrund vorgeladen.
  4. **Claude antwortet** in höchstens drei vorlesbaren Sätzen. Es bekommt dafür:
     - Name, Stufe und Kategorie;
     - den Steckbrief;
     - den letzten Ausschnitt;
     - die letzten 6 Fragen und Antworten zu diesem Ding.
  5. **Die Antwort** erscheint unter „FRAGEN“ im Eintrag und wird vorgelesen.
- **Websuche:** Claude darf höchstens einmal suchen, mit Standort Deutschland. Nach Preisen, Verfügbarkeit und Neuem
  sucht es immer. Die Quellen kommen aus den Zitaten der Suche, oder, wenn es keine gibt, aus den gefundenen Seiten
  (höchstens 3).
- **Warum Whisper lokal?** Deine Stimme verlässt den Mac nie, nur der Text der Frage.
- **Warum Leertaste halten?** Ein immer offenes Mikrofon würde Gespräche im Raum für Fragen halten.
- **Kosten:** Ohne Suche etwa 3 ct und 4 s. Mit Suche etwa 10 ct und 14–35 s. Die Websuche ist teuer, weil die
  gefundenen Seiten rund 20.000 Tokens mitbringen. Die Schätzung vorher lag bei 3–5 ct und war zu niedrig. Deshalb
  gibt es nur eine Suche pro Antwort.

### Teilprojekt 5: Politur & Portfolio

- **Deine Entscheidungen:**
  - edles Apple-Glas;
  - Start per Doppelklick;
  - Portfolio-README;
  - Vollbild-Hologramm mit allen Maßen und technischen Daten.
- **Apple-Glas:** Dunkle, halbdurchsichtige Flächen mit Weichzeichner dahinter (`backdrop-filter: blur(30px)`) und
  haarfeinen Kanten. Die Farben sind Apples Systemfarben: Grün #30D158 für dein Objekt, Cyan #64D2FF für Hände,
  Violett #BF5AF2 für den Hintergrund. Alles steht in `web/src/styles.css`.
- **Vollbild:** Maßlinien für Breite, Höhe und Tiefe in mm und ein nummeriertes Namensschild an jedem Teil. Rechts
  stehen die Teileliste mit Form und Maßen, der Steckbrief und das Wissenswerte.
  - Schilder, die sich verdecken würden, rutschen nach unten, und eine dünne Linie führt zurück zum Teil (Funktion
    `spread` in `shapeMath.ts`, Übung 9).
  - Das Vollbild bleibt offen, auch wenn du den Gegenstand weglegst, denn sein Zustand liegt im Store, nicht im
    Eintrag.
- **Doppelklick-Starter:** `Object Intelligence.command`
  - baut die Oberfläche neu, wenn sich Quelldateien geändert haben;
  - installiert fehlende Pakete;
  - startet den Server;
  - öffnet nur den Browser, wenn die App schon läuft.
- **README:** englisch, für das Portfolio. Mit zwei Bildern aus echten, gespeicherten Claude-Antworten (DualShock 3),
  einem Architektur-Diagramm und einer Kostentabelle.
- **Gebaut und wieder entfernt:** das Foto des Gegenstands als Oberfläche auf dem Hologramm. Deine Entscheidung: Das
  Hologramm bleibt das reine Modell aus Grundformen. Der Abschnitt steht noch im Spec, als Protokoll.

### Teilprojekt 6: Präzisionsmodell

- **Ziel:** Ein 3D-Modell, auf das du technisch stolz sein kannst. Deine Idee: Sobald ein Artikel *sicher* ist,
  recherchiert Claude seine technischen Maße und die technische Zeichnung und baut daraus das Modell.
- **Deine Entscheidungen:**
  - Recherche + CAD-Modell;
  - nur Hologramm-Look;
  - bis ca. 1,50 € pro Produkt;
  - kein schnelles Platzhalter-Modell, nur Fortschritt;
  - höchstens 5 neue Modelle pro Sitzung.
- **Die Analogie:** Das alte Hologramm war ein LEGO-Nachbau aus dem Gedächtnis. Jetzt arbeitet ein Konstrukteur: Er
  schlägt das Datenblatt nach, legt die Zeichnung des Herstellers neben sich, schreibt ein CAD-Programm und vergleicht
  das Ergebnis mit Zeichnung und Foto.
- **Der Ablauf** (`oi/builder.py`, ein Auftrag nach dem anderen):
  1. **Recherche** (`oi/modelcalls.py`, mit Websuche und Web-Fetch): Heraus kommt ein *Maßblatt* (`MeasureSheet`).
     Jede Zahl hat eine Quelle und eine Art: Zeichnung, Datenblatt oder geschätzt.
  2. **Zeichnung** (`oi/drawings.py`, `oi/download.py`): Der Server lädt das PDF, sucht die Zeichnungsseite und
     rendert sie als Bild. Warum macht er das selbst?
     - Der Web-Fetch würde Claude das ganze PDF geben; laut Doku kostet schon ein PDF von 500 kB etwa 125.000
       Tokens.
     - Bei Apple sind die Maßzahlen Vektorgrafik: Als Text stünde auf der Seite nur „iPhone 14“. Als Bild sieht
       Claude jede Zahl.
  3. **CAD** (`oi/modelprompts.py`): Claude schreibt ein OpenSCAD-Programm mit der Bibliothek BOSL2, ein Block pro
     Teil, mit Rundungen, Aussparungen und Drehkörpern.
  4. **Geometrie** (`oi/scad.py`, `web/scad/compile.mjs`): OpenSCAD läuft als WebAssembly in Node und rechnet jedes
     Teil in ein STL-Netz, etwa 1 s pro Teil, 4 gleichzeitig.
  5. **Prüfung** (`oi/render.py`): Der Server rendert vier Ansichten (matplotlib). Claude vergleicht sie mit Zeichnung
     und Foto und korrigiert, in bis zu 2 Runden.
  6. **Speicher** (`oi/modelstore.py`): `cache/models/<produkt>/` mit den Teilen, dem Manifest und dem OpenSCAD-Code.
- **Warum OpenSCAD und nicht Python-CAD (CadQuery) oder three.js-Code?** Claude liest bei der Recherche fremde
  Webseiten. Eine manipulierte Seite könnte versuchen, Claude schädlichen Code schreiben zu lassen.
  - Python- oder JavaScript-Code würde auf deinem Mac laufen.
  - OpenSCAD ist eine reine CAD-Sprache und läuft abgeschottet in seinem eigenen Speicher. Getestet: Es kann keine
    Datei vom Mac lesen.
- **Sichere Downloads:** Der Server lädt nur, was die Recherche wirklich gesehen hat (oder was auf derselben Website
  liegt). Erlaubt sind nur https, nur öffentliche Adressen, nur PDF/PNG/JPEG und nur bis zu einer Größengrenze.
- **Gemessen am 2026-10-02 (iPhone 14):**
  - ohne Zeichnung: 156 s und 0,40 $ (1 Prüfrunde) bzw. 175 s und 0,66 $ (2 Prüfrunden);
  - mit Apples Maßzeichnung (2 Seiten): Recherche 52 s und 0,36 $, CAD 140 s und 0,32 $, 2 Prüfrunden 58 s und
    0,22 $. Zusammen etwa 4,5 Minuten und 0,90 $ (≈ 0,83 €), unter der Grenze von 1,60 $.
  - Das Modell hat 25 Teile: Rahmen, Displayglas, Notch, Kamerainsel mit Objektiven, Blitz, Apple-Logo, alle Tasten,
    SIM-Schacht, Lightning, Schrauben, Antennenstreifen.
- **Bausteine von GitHub:** openscad-wasm-prebuilt (OpenSCAD als WebAssembly), BOSL2, pypdfium2. Die Ideen stammen
  von CADAM (Claude + OpenSCAD) und img2threejs (Prüfrunden mit Renders).

---

## 7. Claude richtig einsetzen (AI Engineering)

Dieser Abschnitt passt zu Phase 5 deines Lehrplans: Modell- und API-Integration, Prompts und strukturierte Ausgaben,
Kostenkontrolle, Robustheit.

### Die sechs Arten von Aufrufen

| Aufruf | Bekommt | Liefert | Wann | Kosten |
|---|---|---|---|---|
| Identifizieren | Ausschnitt (nur Objekt) | Kategorie, Kandidaten, Indizien, nächste Ansicht | neue Ansicht des gehaltenen Dings | 1,3–1,7 ct |
| Szene benennen | ganzes Bild, Personen grau | Namen und Orte der Hintergrund-Dinge | einmal nach der Kalibrierung | – |
| Steckbrief | nur Text (Produktname) | Zusammenfassung, Fakten, Erscheinung, Preis, Wissenswertes | ab „wahrscheinlich“, einmal pro Modell | ≈ 1,2 ct |
| Recherche (Präzisionsmodell) | nur der Modellname | Maßblatt mit Quellen, Zeichnungs-Kandidat | ab „sicher“, einmal pro Modell | 0,18–0,36 $ |
| CAD (Präzisionsmodell) | Maßblatt, Zeichnungsseiten, Ausschnitt | OpenSCAD-Programm, ein Block pro Teil | danach | 0,17–0,32 $ |
| Prüfung (Präzisionsmodell) | vier Renders, Zeichnung, Ausschnitt, Code, Fehler | Abweichungen, korrigierte Teile | bis zu 2-mal | 0,05–0,15 $ je Runde |
| Gleiches Ding? | kleine Ausschnitte | ja/nein, welches | einmal pro neuem Objekt | 0,4–0,5 ct |
| Frage beantworten | Text der Frage, Ausschnitt, Steckbrief, Verlauf | 1–3 Sätze, Quellen | Leertaste | ≈ 3 ct, mit Suche ≈ 10 ct |

### Anatomie eines Aufrufs

Ein Aufruf ist ein Paket aus diesen Teilen:
- `model`: `claude-opus-5-5`, über `OI_MODEL` änderbar;
- ein *System-Prompt*, also die feste Anleitung;
- das Bild und ein kurzer Text;
- `max_tokens`;
- `output_config` mit dem Antwortformat und dem *Effort*.

Die Antwort muss nach 20 s da sein, sonst gilt der Aufruf als gescheitert (`claude_timeout_s`). Gebaut wird das Paket
in `_request` in `oi/identify.py`.

### Strukturierte Ausgaben: Antworten als Formular statt als Aufsatz

- **Was:** Claude bekommt ein *JSON Schema*, eine genaue Beschreibung der Felder (`OBSERVATION_SCHEMA`). Die Antwort ist
  dann garantiert gültiges JSON in genau dieser Form.
- **Warum:** Freitext müsste man mühsam auslesen, und er bricht bei jeder Formulierungsänderung. Ein Formular kann
  der Code direkt prüfen: pydantic verwandelt es in ein `Observation`-Objekt.
- **Ein Detail:** Grenzen wie „höchstens 4 Kandidaten“ stehen *nicht* im Schema. Sie werden nach der Antwort
  durchgesetzt, indem überzählige Kandidaten abgeschnitten werden. Sonst würde ein bezahlter Aufruf wegen eines
  fünften Kandidaten abgelehnt, und das Geld wäre weg.

### Prompt-Design: Regeln, die Ehrlichkeit erzwingen

Auszüge aus dem System-Prompt (`SYSTEM_PROMPT` in `oi/identify.py`):
- „Identify it as specifically as the visible evidence allows … Never go beyond what you can see.“ Lieber „Smartphone“
  als ein geratenes Modell.
- „Evidence must be features visible in this image.“ Die Indizien müssen sichtbar sein, nicht aus dem Gedächtnis
  stammen.
- „next_view.view is a short noun phrase that fits after ‚Please show me‘.“ So passt Claudes Antwort direkt in den Satz
  „Zeig mir bitte …“.
- „Write all free text in {language}.“ Die Sprache wird eingesetzt, Deutsch ist der Standard.

### Effort: wie gründlich Claude nachdenkt

- **`low`** für das Identifizieren: schnell und günstig. Genauer wird es durch mehrere Ansichten, nicht durch längeres
  Nachdenken.
- **`medium`** für Fragen: Bei `low` hat Claude nötige Websuchen ausgelassen (siehe Fehler 13).

### Werkzeuge: die Websuche

- **Was:** Die Websuche ist ein *Server-Tool*. Anthropic führt die Suche selbst aus, Claude liest die Seiten und
  zitiert sie.
- **Wie:** `{"type": "web_search_20260209", "max_uses": 1, "user_location": … Deutschland}`
- **Die Quellen:** Die Zitate (`citations`) werden als Quellen gezeigt, mit Titel und Link.

### Robustheit: Was, wenn etwas schiefgeht?

- **Startprüfung:** Beim Start prüft ein kleiner Test-Aufruf, ob der Schlüssel funktioniert. Ohne Schlüssel läuft das
  Programm im *lokalen Modus*: Boxen, Nummern und grobe Labels gehen, Namen gibt es nicht.
- **Fehler:** Jeder Fehler wird zu einem `IdentifyError` mit einem Grund. Der Eintrag zeigt dann einen Fehlersatz,
  statt abzustürzen. Mit „Neu prüfen“ geht es weiter.
- **Fallbacks:** Ist das Hauptmodell nicht verfügbar, darf die API auf ein anderes Modell ausweichen. Das ist eine
  Beta-Funktion der API (`server-side-fallback`).
- **Ein kaputtes Bild hält nichts an:** Die Bildschleife fängt Fehler pro Bild ab (`run` in `oi/pipeline.py`).
- **Ein kaputter Cache stürzt nichts ab:** Eine kaputte Cache-Datei wird ignoriert, eine nicht schreibbare Datei hält
  den Cache im Speicher (`oi/cache.py`).

### Die Attrappe für Tests

`FakeIdentifier` in `oi/identify.py` spielt Claude nach. Sie gibt vorbereitete Antworten zurück und merkt sich jede
Anfrage. So testet man die ganze Pipeline ohne Netz und ohne Kosten (Abschnitt 11). Gestartet wird sie mit
`--fake-claude`. Echte Erkennung braucht aber Claude.

---

## 8. Der Browser-Teil (TypeScript und React)

Passt zu Phase 3 deines Lehrplans.

### Die Dateien

| Datei | Aufgabe |
|---|---|
| `main.tsx`, `App.tsx` | Start; Kamera, Verbindung, Tasten, Leertaste, Vorlesen |
| `camera/capture.ts`, `camera/frame.ts` | Bilder aufnehmen und verpacken |
| `net/socket.ts` | WebSocket mit automatischem Neuverbinden |
| `protocol.ts` | alle Nachrichten-Typen, Feld für Feld wie `oi/contracts.py` |
| `store.ts` | der gemeinsame Zustand (zustand) und reine Funktionen dazu |
| `hud/Overlay.tsx` | das Canvas über dem Video: Hände, Box, Namensschild, Hintergrund |
| `hud/geometry.ts`, `hud/smoothing.ts` | Koordinaten umrechnen, Boxen gleiten lassen |
| `hud/Sidebar.tsx`, `IdentityView.tsx`, `ProfileView.tsx`, `QuestionsView.tsx` | die Seitenleiste und ihre Teile |
| `hud/Hologram.tsx`, `HologramFullscreen.tsx`, `hologramScene.ts`, `shapeMath.ts`, `modelText.ts` | das Präzisionsmodell: Fortschritt, CAD-Teile, Maße, Quellen |
| `hud/Banner.tsx`, `hud/Telemetry.tsx` | Hinweise oben, Zahlen links oben |
| `voice/recorder.ts`, `voice/speech.ts` | Mikrofon aufnehmen; wann die Stimme spricht |
| `i18n.ts` | alle festen Texte auf Deutsch und Englisch |
| `styles.css` | das Apple-Glas-Design |

### React in drei Sätzen

- Eine *Komponente* ist eine Funktion, die aus Daten (*props*) eine Oberfläche beschreibt.
- Ändern sich die Daten, zeichnet React die betroffenen Teile neu.
- Du beschreibst, *was* zu sehen sein soll, und React kümmert sich um das *Wie*.

### Der Store: eine Wahrheit für alle

- **Was:** Alles, was der Browser weiß, liegt an einer Stelle (`useHud` in `store.ts`): Tracks, Erkennungen,
  Steckbriefe, Formen, Einträge, Fragen und Einstellungen.
- **Wie:** Neue Server-Nachrichten verarbeitet die *reine Funktion* `applyServerMessage(state, message)`: alter
  Zustand plus Nachricht ergibt neuen Zustand. Genauso funktionieren `sidebarEntries`, `askTarget`, `fullscreenView`
  und `pickable`.
- **Warum:** Reine Funktionen lassen sich ohne Browser testen: Eingabe rein, Ergebnis prüfen. Die meisten
  Browser-Tests (`store.test.ts`) machen genau das.

### Koordinaten: von 0..1 zu Pixeln

Der Server schickt Boxen *normalisiert*: 0 ist der linke oder obere Rand, 1 der rechte oder untere. `geometry.ts`
rechnet das auf die Bildschirmgröße um. Dabei berücksichtigt es, dass das Video mit `object-fit: contain` eventuell
schwarze Ränder hat und gespiegelt sein kann.

### Das Hologramm mit three.js

- **Die Bühne:** Eine *Szene* enthält das Modell, eine *Kamera* schaut darauf, ein *Renderer* malt es auf ein Canvas.
- **Die Teile:** Jedes CAD-Teil kommt als STL-Datei vom Server (`/models/<produkt>/part-01.stl`, geladen mit
  `STLLoader`) und wird ein *Mesh* (Form + Material). Die Kanten liefert `EdgesGeometry`, die nur Kanten mit mehr als
  20° Knick zeigt. So bleiben die fein unterteilten Rundungen ruhig, und nur echte Kanten leuchten.
- **Namensschilder:** Jedes Teil bekommt einen nummerierten Punkt in seiner Mitte. Große Schalen (Rahmen, Display,
  Rückglas) setzen ihren Punkt verteilt auf den Rand (`rimPoint`), damit nicht alle Schilder an einer Stelle beginnen.
- **Steuerung:** `OrbitControls` erlaubt Drehen mit der Maus und dreht sonst langsam von selbst. Im Vollbild kommt Zoom
  dazu.
- **Beschriftungen:** `CSS2DRenderer` setzt normale HTML-Elemente (die Maß-Kapseln und Namensschilder) an 3D-Punkte.
- **Lazy Loading:** three.js ist groß, deshalb wird es erst geladen, wenn ein Hologramm gezeigt wird (`lazy` in
  `Sidebar.tsx`).

### Die Stimme

- **Vorlesen:** Das übernimmt der Browser (`speechSynthesis`) mit einer deutschen Stimme. Die Scherz-Stimmen von macOS
  wie „Zarvox“ werden übersprungen.
- **Wann gesprochen wird** (`voice/speech.ts`):
  - nur über das gehaltene Objekt;
  - jeder Satz nur einmal;
  - nur, wenn die Stimme mit `M` eingeschaltet ist.

  Antworten auf deine Fragen werden immer gesprochen.
- **Aufnehmen:** Ein *AudioWorklet* läuft neben der Seite und bekommt die rohen Mikrofon-Samples. `recorder.ts` rechnet
  sie auf 16.000 Samples pro Sekunde herunter (`downsample`) und macht 16-Bit-Zahlen daraus (`toPcmBase64`).

---

## 9. Datenschutz: was den Mac verlässt und was nie

| Daten | Verlässt den Mac? | Wie geschützt |
|---|---|---|
| Kamerabild | nein | Detektor, Hände, Gesichter laufen lokal |
| dein Gesicht | **nie** | YuNet findet es lokal; ein Ausschnitt, der auf einem Gesicht liegt, wird nie geschickt |
| dein Körper, T-Shirt, Haare, Kette | **nie** | Personen-Labels, Kopfzone, Körperzone, Regel „getragen“ |
| Ausschnitt des Gegenstands | ja, zu Claude | nur die Pixel des Gegenstands, alles andere grau |
| Name des Produkts (Recherche) | ja, zu Claude | für das Präzisionsmodell geht nur der Name in die Websuche |
| ganzes Bild | einmal pro Kalibrierung | jede Person wird vorher grau übermalt |
| deine Stimme | **nie** | Whisper läuft lokal |
| Text deiner Frage | ja, zu Claude | nur der Text |
| API-Schlüssel | nur zu Anthropic | liegt in `.env`, nie in Git, nie im Browser |

### Die Sicherheitsregeln im Detail (`oi/privacy.py`)

Ein Ausschnitt geht nicht zu Claude, wenn eine dieser Regeln greift:
- Er deckt mindestens 40 % einer Person ab: Dann *ist* er die Person.
- Er liegt zur Hälfte im oberen Drittel einer Person, der Kopfzone.
- Er deckt mindestens 20 % eines Gesichts ab.
- Er liegt zur Hälfte auf einem Gesicht, das um 25 % geweitet ist (für Haare, Ohren, Ohrringe).

### Labels über das letzte Wort lesen (`label_in`)

YOLOE nannte deine Haare im dunklen Raum „short hair“. Die Liste verbotener Labels enthielt „hair“, aber nicht „short
hair“, und so rutschte es durch. Seitdem zählt das *letzte Wort* eines Labels: „short hair“ ist Haar. Ein „hair dryer“
dagegen ist kein Haar, denn im Englischen benennt das letzte Wort das Ding.

### Weitere Schutzmechanismen

- **Fremde Webseiten:** Der Server nimmt WebSocket-Verbindungen nur von seiner eigenen Adresse an. Er prüft den
  Header `origin` (`oi/server.py`). Sonst könnte eine fremde Webseite in deinem Browser die Verbindung öffnen und mit
  deinem Schlüssel Claude-Aufrufe auslösen.
- **Nur eine Verbindung:** Eine neue Verbindung, etwa nach einem Neuladen oder in einem zweiten Tab, ersetzt die alte.

---

## 10. Kosten: woher sie kommen und wie sie gedeckelt sind

### Tokens: die Währung von Sprachmodellen

Ein *Token* ist ein Wortstück: etwa ¾ eines englischen Wortes, bei Deutsch etwas weniger. Bilder werden auch in
Tokens umgerechnet. Bezahlt wird pro Million Tokens. Für Claude Opus 5.5 stehen die Preise in `oi/config.py`:
- Eingabe: 4 $ pro Million Tokens;
- Ausgabe: 20 $ pro Million Tokens.

### Ein echtes Beispiel aus `runs/`

Ein Identifizier-Aufruf vom 2026-10-01 (DualShock 3, Datei `runs/2026-10-01_18-23-31/003_track169.json`):

```
Eingabe:  1.574 Tokens × 4 $ / 1.000.000  = 0,006296 $
Ausgabe:    370 Tokens × 20 $ / 1.000.000 = 0,007400 $
Summe:                                      0,013696 $ ≈ 1,4 Cent, Dauer 4,8 s
```

Genau so rechnet `oi/telemetry.py` jeden Aufruf. Die Ausgabe ist pro Token fünfmal so teuer. Deshalb sind kurze,
strukturierte Antworten auch billiger.

### Gemessene Kosten

| Aufruf | Kosten | Dauer |
|---|---|---|
| Identifizieren | 1,3–1,7 ct | 6–10 s (einzeln auch 4,8 s) |
| Steckbrief | ≈ 1,2 ct | 6 s |
| Präzisionsmodell (einmal pro Produkt) | 0,40–0,90 $ | 2,5–4,5 min |
| Gleiches Ding? | 0,4–0,5 ct | 3–5 s |
| Frage | ≈ 3 ct | 4 s |
| Frage mit Websuche | ≈ 10 ct | 14–35 s |

### Die Deckel

- **Pro Objekt:** höchstens 4 Aufrufe.
- **Pro Sitzung:** höchstens 150 Aufrufe, Fragen eingeschlossen. Danach meldet sich der Hinweis „Kostenbremse
  erreicht, Identifikation pausiert.“
- **Gleichzeitig:** höchstens 2 Aufrufe.
- **Caches:** Steckbrief und Präzisionsmodell kosten pro Modell nur einmal, für immer.
- **Präzisionsmodell:** höchstens 1,60 $ (≈ 1,50 €) pro Produkt, höchstens 5 neue pro Sitzung. Vor jedem Schritt prüft
  der Builder, ob das Budget noch für ihn reicht (`_affordable` in `oi/builder.py`).
- **Neue Ansicht:** Ein Bild geht nur raus, wenn es eine neue Ansicht zeigt.
- **Gezählt wird bei der Entscheidung,** nicht erst bei der Antwort (siehe Fehler 9).

Du siehst alles live in der Telemetrie (`D`) und im Nachhinein in `runs/`.

---

## 11. Tests: warum, wie, woran du sie erkennst

### Warum Tests?

Ein Test ist ein kleines Programm, das prüft, ob ein anderes Programm das Richtige tut. Er läuft in Sekunden und
jedes Mal gleich. Bei einer Änderung zeigt er sofort, ob etwas Altes kaputtgegangen ist (eine *Regression*). Ohne
Tests müsstest du nach jeder Änderung alles von Hand mit Kamera ausprobieren, und Claude-Aufrufe kosten Geld.

### Wie dieses Projekt testbar wurde

- **Reine Logik:** Fokus, Auslöser, Beweisbuch, Schnappschuss, Datenschutz und Szene sind *reine Logik*: Zahlen rein,
  Entscheidung raus. Kein Kamerazugriff, kein Netz.
- **Attrappen:** Detektor, Claude und Whisper stehen hinter kleinen Schnittstellen und haben Attrappen:
  - `FakeDetector` in `oi/perception.py`;
  - `FakeIdentifier` in `oi/identify.py`;
  - `FakeTranscriber` in `oi/speech.py`.

  Damit läuft die ganze Pipeline im Test, ohne Kamera, Modell oder Netz.

### Ein echter Test zum Lesen (`tests/test_trigger.py`)

```python
def test_session_cap_beats_forced():
    assert decide(replace(BASE, forced=True, calls_session=150), Settings()) == Decision.SESSION_CAP
```

- `BASE` ist eine Grundsituation. `replace` erzeugt eine Kopie mit „Neu prüfen wurde geklickt“ und „150 Aufrufe
  verbraucht“.
- `assert` prüft: Die Entscheidung muss die Sitzungsgrenze sein.

Der Name sagt in Worten, was gilt: Die Sitzungsgrenze schlägt „Neu prüfen“.

### Die Testbefehle

```bash
uv run pytest               # 327 Tests: alle Logik, kein Modell, kein Netz (ein paar Sekunden)
uv run pytest -m model      # lädt die echten YOLOE-Gewichte
uv run pytest -m claude     # ein echter Claude-Aufruf, etwa 2 Cent
uv run pytest -m scad       # der echte OpenSCAD-Compiler, auch seine Abschottung
npm --prefix web test       # 55 Browser-Tests (Vitest)
```

### Test-Driven Development (TDD)

So wurde gearbeitet:
1. **Rot:** Erst einen Test schreiben, der das gewünschte Verhalten beschreibt, und zusehen, wie er *fehlschlägt*.
2. **Grün:** Dann gerade so viel Code schreiben, dass er besteht.
3. **Aufräumen:** Danach aufräumen, und die Tests bleiben grün.

**Warum erst rot?** Ein Test, den du nie scheitern gesehen hast, prüft vielleicht gar nichts. Ein Beispiel aus diesem
Projekt: Den Test für das Ausweichen der Namensschilder habe ich absichtlich kaputt gemacht, indem ich eine Bedingung
verändert habe. Der Test schlug an, also prüft er wirklich etwas.

### Einen fehlschlagenden Test lesen

1. Den **Namen** lesen: Was sollte gelten?
2. **Expected** gegen **Received** vergleichen: Was kam stattdessen?
3. Die **Zeile** öffnen.

Das ist dieselbe Arbeit wie beim Lesen von Fehlermeldungen in deinem Lehrplan.

---

## 12. Fehler, die wir unterwegs gefunden haben

Format wie „Verstandene Fehler“ in deinem Lehrplan. Jeder dieser Fehler ist echt passiert.

1. **Treppe und Regal im Fokus**
   - Symptom: Ohne etwas in der Hand zielte die Box auf die Treppe, und oben stand „Bitte ganz ins Bild“.
   - Ursache: Der Fokus nahm das größte Ding, auch ohne Hand.
   - Lösung: Fokus nur auf gehaltene Dinge, dazu den Hintergrund kalibrieren und einfrieren.
   - Lektion: Eine einfache, für Menschen verständliche Regel schlägt eine clevere Punkteformel.
2. **„Halte es ruhig“**
   - Symptom: Der Hinweis blieb dauerhaft stehen.
   - Ursache: Das Programm wartete auf Stillstand, aber eine Hand ist nie still.
   - Lösung: Das schärfste Bild aus 0,5 s nehmen.
   - Lektion: Das Programm an den Menschen anpassen, nicht umgekehrt. Die Idee kam von dir.
3. **Das T-Shirt als Objekt**
   - Ursache: Das T-Shirt lag nah an der Hand und war groß.
   - Lösung: Was zu mindestens 25 % in der Körperzone liegt und bis zum unteren Rand reicht, gilt als „getragen“.
   - Lektion: Geometrie hilft dort, wo Labels versagen.
4. **„short hair“ rutschte durch**
   - Ursache: Die Liste verbotener Labels verglich nur exakt.
   - Lösung: das letzte Wort des Labels prüfen (`label_in`).
   - Lektion: Eine Liste ist nie vollständig. Eingaben müssen normalisiert werden, genau wie in deiner Lehrplan-Aufgabe
     mit `strip()` und `lower()`.
5. **Ein Objekt, zwei Einträge**
   - Symptom: Der Controller wurde einmal „schwarzes Gerät“ und einmal „DualShock 3“.
   - Lösung: ein kleiner Vergleichsaufruf, danach werden die Einträge zusammengeführt.
6. **iPhone 14 oder 15**
   - Symptom: Von hinten blieb das Ergebnis „unsicher“.
   - Lösung: Die trennende Ansicht erbitten, oder du tippst den Kandidaten an.
   - Lektion: Ehrliche Unsicherheit braucht einen Ausweg für den Menschen.
7. **Die Seitenleiste ließ sich nicht scrollen**
   - Ursache: Die Zeilen des CSS-Grids schrumpften.
   - Lösung: `grid-auto-rows: max-content`.
8. **Der Test-Helfer, der sich totlief**
   - Symptom: `wait_idle` wartete ewig.
   - Ursache: Er wartete auch auf Aufgaben, die schon fertig, aber noch nicht aus der Liste entfernt waren. Das Warten
     auf eine fertige Aufgabe gibt die Kontrolle nie ab.
   - Lösung: nur auf unfertige Aufgaben warten, plus ein Regressionstest.
9. **Das Budget-Rennen**
   - Symptom: Zwei Aufrufe konnten gleichzeitig unter der Grenze starten.
   - Ursache: Gezählt wurde erst, wenn die Antwort kam.
   - Lösung: zählen, sobald entschieden ist.
   - Lektion: Bei Nebenläufigkeit (Dinge passieren gleichzeitig) zählt *wann* geprüft wird.
10. **Der vergiftete Cache**
    - Symptom: Antworten aus dem Testmodus (`--fake-claude`) landeten im echten Cache.
    - Lösung: Im Testmodus bleibt der Cache im Speicher.
11. **Ein alter Server auf Port 8766**
    - Symptom: Dein Live-Test traf alten Code.
    - Ursache: Ein vergessener Server-Prozess lief noch.
    - Lösung: Das Programm startet nicht mehr auf einem belegten Port. Der Doppelklick-Starter öffnet dann nur den
      Browser.
12. **Ein Commit mit rotem Test**
    - Ursache: Ein Befehl wie `pytest | tail -1` meldet den Erfolg von `tail`, nicht den von pytest.
    - Lösung: den Exit-Code von pytest selbst prüfen.
    - Lektion: Prüfe, was du wirklich prüfst.
13. **Websuche ausgelassen**
    - Symptom: Bei „Was kostet das gebraucht?“ suchte Claude nicht.
    - Ursache: Effort `low`.
    - Lösung: Effort `medium` für Fragen, und im Prompt „bei Preisen immer suchen“.
14. **Websuche teurer als geschätzt**
    - Symptom: 10 ct statt 3–5 ct.
    - Ursache: Die gefundenen Seiten bringen etwa 20.000 Tokens mit.
    - Lösung: höchstens eine Suche, Standort Deutschland.
    - Lektion: Erst messen, dann versprechen.
15. **Whisper und ffmpeg**
    - Symptom: Whisper wollte für Audiodateien `ffmpeg`, das nicht installiert war.
    - Lösung: Die Samples direkt als Zahlenreihe übergeben, ohne Datei.
16. **Unsichtbare Hologramm-Kanten**
    - Symptom: Abgerundete Quader hatten keine Kanten, und die Griffe des Controllers sahen aus wie lose Schalen.
    - Ursache: Weiche Formen haben keine „harten“ Kanten.
    - Lösung: Knickwinkel 10° und gezeichnete Ringe und Umrisse für Kugeln und Kapseln.
17. **Überlappende Teilenamen**
    - Symptom: An der Kamerainsel lagen vier Namen übereinander.
    - Lösung: nummerierte Punkte, und die Schilder weichen nach unten aus (`spread`).
18. **Das Vollbild verschwand**
    - Symptom: Beim Weglegen des Gegenstands klappte der Eintrag zu und nahm das Vollbild mit.
    - Lösung: Der Vollbild-Zustand liegt im Store, nicht im Eintrag.
19. **Die Zeichnung stand nicht, wo Claude sie vermutete**
    - Symptom: Die Recherche nannte Apples großes Zubehör-Handbuch (33 MB, 404 Seiten) als Zeichnung.
    - Ursache: Das Handbuch enthält die Geräte-Zeichnungen gar nicht mehr. Apple veröffentlicht sie getrennt, eine PDF
      pro Gerät.
    - Lösung: Die Recherche sucht ausdrücklich nach „<Produkt> dimensional drawing“.
    - Lektion: Wissen aus dem Training kann veraltet sein; eine Suche findet den heutigen Stand.
20. **Der Server lehnte die richtige Zeichnung ab**
    - Symptom: Die Recherche fand Apples PDF, aber der Server lud sie nicht.
    - Ursache: Der Link stand auf einer abgerufenen Übersichtsseite. Erlaubt waren nur die Adressen der Such- und
      Abrufergebnisse selbst.
    - Lösung: Auch Adressen auf derselben Website wie eine gesehene Seite sind erlaubt; alle anderen Regeln bleiben.
    - Lektion: Sicherheitsregeln müssen echte Fälle durchspielen, sonst sperren sie das Richtige aus.
21. **Die Seitensuche nahm die Vertragsseite**
    - Symptom: Statt der Zeichnung wurde die Titel- und Vertragsseite gerendert.
    - Ursache: In Apples PDF stehen die Maßzahlen als Vektorgrafik, als Text nur „iPhone 14“ auf jeder Seite. Die
      Vertragsseite enthielt dieselben Wörter.
    - Lösung: Unter gleich guten Seiten gewinnt die mit dem wenigsten Text, denn eine Zeichnung ist ein Bild.
22. **Eine dünne, runde Platte brach OpenSCAD**
    - Symptom: `cuboid([30, 30, 1.2], rounding=7)` endete mit „CGAL error in applyHull“.
    - Ursache: Die Rundung ist größer als die Platte dick ist; die Hülle wird entartet.
    - Lösung: Im BOSL2-Spickzettel steht der robuste Weg (`linear_extrude` + `rect(rounding=)`), und solche Fehler gehen
      in der Prüfrunde zurück an Claude.

---

## 13. Werkzeuge und Arbeitsweise

### Werkzeuge

- **Python-Teil:**
  - **uv** verwaltet Python und die Pakete des Projekts (`pyproject.toml`, `uv.lock`). `uv sync` installiert alles,
    `uv run …` führt Befehle in der richtigen Umgebung aus.
  - **FastAPI + uvicorn:** das Web-Framework und der Server, der es ausführt.
- **Browser-Teil:**
  - **npm:** die Paketverwaltung (`web/package.json`).
  - **Vite:** baut den Browser-Teil (`npm run build` erzeugt `web/dist/`, das der Server ausliefert).
  - **Vitest:** testet ihn.
- **Git** und **GitHub:**
  - Jede Änderung ist ein *Commit* mit einer Nachricht, die sagt, *warum*.
  - Gearbeitet wurde auf *Branches*, also Abzweigungen. Fertige Teilprojekte wurden in `main` *gemergt* und
    *gepusht*.
  - Commits zählen für deine GitHub-Contributions, wenn sie im Standard-Branch `main` landen.
- **Konfiguration:** Alle Schwellen, Grenzen und Preise stehen in `oi/config.py`. Jede Einstellung lässt sich über eine
  Umgebungsvariable ändern, zum Beispiel `OI_MODEL`, `OI_LANGUAGE` oder `OI_MAX_CALLS_SESSION`, auch in `.env`.
- **Logs:**
  - `runs/<Datum_Zeit>/` enthält für jeden Claude-Aufruf ein JSON (Anfrage, Antwort, Tokens, Kosten, Dauer, Stufe
    danach) und das gesendete Bild.
  - Negative Nummern stehen für Aufrufe ohne Objekt: −1 Steckbrief, −2 Hologramm, −3 Vergleich, −4 Frage.
  - So lässt sich jede Entscheidung später nachprüfen. Das nennt man *Observability*.

### Arbeitsweise: vom Wunsch zum Code

Jedes Teilprojekt lief in denselben Schritten:
1. **Fragen:** Was willst du genau? Deine Antworten stehen als Entscheidungen im Spec.
2. **Spec** (Design-Dokument): was gebaut wird und warum, mit Zahlen.
3. **Plan:** kleine Aufgaben mit Tests, Dateien und Schnittstellen.
4. **Bauen mit TDD:** Test rot, Code, Test grün, Commit.
5. **Prüfen:** alle Tests, Build, Linter (`ruff`), Bilder aus dem Browser; danach mergen und pushen.
6. **Dein Live-Test:** Was dir auffällt, wird ein Nachtrag im Spec (zum Beispiel §8–§13 in Teilprojekt 1) und wieder
   ein kleiner Zyklus.

**Warum dieser Aufwand?** Bei AI-generiertem Code ist das größte Risiko Code, den keiner versteht. Spec und Tests
halten fest, was gelten soll. So kann man den Code später sicher ändern, und genau das ist das Ziel deines Lehrplans.

---

## 14. Glossar

| Begriff | Erklärung |
|---|---|
| **API** | Schnittstelle, über die ein Programm ein anderes benutzt; hier: Claude über das Internet |
| **API-Schlüssel** | Passwort für die API; wer ihn hat, verbraucht dein Guthaben, deshalb nur in `.env` |
| **async / await** | Python wartet auf etwas Langsames (Netz, Claude), ohne alles anzuhalten; währenddessen läuft anderes weiter |
| **AudioWorklet** | ein Stück Code, das neben der Webseite rohe Audio-Samples verarbeitet |
| **Base64** | Binärdaten als Text geschrieben; etwa ein Drittel größer |
| **BoT-SORT** | Tracker: gibt jedem erkannten Ding eine Nummer, die über Bilder hinweg gleich bleibt |
| **Bounding Box** | das Rechteck um ein Ding: x1, y1, x2, y2 |
| **Branch / Merge / Push** | Git: Abzweigung zum Arbeiten / zusammenführen / zu GitHub hochladen |
| **BOSL2** | Bibliothek für OpenSCAD: Rundungen, Fasen, Übergänge zwischen Querschnitten |
| **CAD** | Computer-Aided Design: Konstruktion am Computer, hier als Programm in OpenSCAD |
| **Cache** | Zwischenspeicher: einmal gefragt, für immer gemerkt |
| **Canvas** | eine Zeichenfläche im Browser, auf die Code Pixel malt |
| **Commit** | ein gespeicherter Schritt in Git, mit Nachricht |
| **Crop / Ausschnitt** | der herausgeschnittene Bildteil mit dem Gegenstand |
| **CSS2DRenderer** | setzt HTML-Beschriftungen an Punkte einer 3D-Szene |
| **dHash** | Fingerabdruck eines Bildes aus 64 Bits; ähnliche Bilder haben ähnliche Fingerabdrücke |
| **Detektor** | Modell, das Dinge im Bild findet (Box + grober Name) |
| **Effort** | wie gründlich Claude nachdenkt: low, medium, high |
| **Event Loop** | der Taktgeber von `async`: verteilt die Arbeit, solange niemand blockiert |
| **Fake / Attrappe** | Ersatz für ein echtes Bauteil im Test (z. B. `FakeIdentifier` statt Claude) |
| **Fixture** | feste Testdaten, z. B. `tests/fixtures/protocol-examples.json` |
| **Hamming-Abstand** | wie viele Bits sich zwischen zwei Fingerabdrücken unterscheiden |
| **Hysterese** | ein Wechsel braucht einen klaren Vorsprung über eine Zeit, damit nichts hin- und herspringt |
| **i18n** | Internationalisierung: Texte in mehreren Sprachen |
| **IoU** | Intersection over Union: wie stark zwei Boxen sich überlappen, 0 bis 1 |
| **JSON / JSON Schema** | Textformat für Daten / genaue Beschreibung, welche Felder ein JSON haben muss |
| **Laplace-Varianz** | Maß für Schärfe: viele harte Übergänge = scharf |
| **Latenz** | Wartezeit zwischen Anfrage und Antwort |
| **Lazy Loading** | Code erst laden, wenn er gebraucht wird |
| **Manifold** | schneller, robuster Geometrie-Kern in OpenSCAD (statt des alten CGAL) |
| **MLX** | Apples Framework für Machine Learning auf Apple-Chips (hier für Whisper) |
| **Mesh** | ein 3D-Körper in three.js: Form (Geometry) + Material |
| **mps** | Metal Performance Shaders: die Apple-GPU für PyTorch |
| **Normalisiert** | als Anteil 0..1 statt in Pixeln |
| **OpenSCAD** | eine Programmiersprache für 3D-Modelle: Formen per Code, ohne Datei- oder Netzzugriff |
| **Observability** | im Nachhinein sehen können, was ein System warum getan hat (hier: `runs/`, Telemetrie) |
| **Open Vocabulary** | ein Detektor, der nicht auf feste Klassen beschränkt ist |
| **PCM** | rohe Audio-Samples als Zahlen; hier 16.000 pro Sekunde, je 16 Bit |
| **Polygon / Umriss** | die Form eines Dings als Punktliste, genauer als die Box |
| **Port** | eine „Hausnummer“ für Programme auf einem Rechner; hier 8766 |
| **Prompt / System-Prompt** | die Anweisung an das Sprachmodell / die feste Grundanweisung für alle Aufrufe einer Art |
| **pydantic** | Python-Bibliothek, die Daten gegen eine Beschreibung prüft (`oi/contracts.py`) |
| **React / Komponente / Props** | Bibliothek für Oberflächen / ein Baustein davon / seine Eingaben |
| **Regression** | etwas, das schon funktionierte, ist durch eine Änderung kaputtgegangen |
| **Sandbox / abgeschottet** | ein Programm läuft in einem eigenen, geschlossenen Bereich und kommt nicht an deine Dateien |
| **SSRF** | „Server-Side Request Forgery“: jemand bringt einen Server dazu, Adressen zu laden, die er nicht laden soll |
| **STL** | Dateiformat für 3D-Netze: eine Liste von Dreiecken |
| **Reine Funktion** | gleiche Eingabe → gleiche Ausgabe, keine Nebenwirkungen; leicht zu testen |
| **Store (zustand)** | der gemeinsame Zustand des Browser-Teils |
| **Strukturierte Ausgabe** | Claude antwortet garantiert im vorgegebenen JSON-Format |
| **Thread** | ein zweiter Arbeitsstrang; hier für Detektor und Whisper, damit der Server nicht blockiert |
| **three.js** | Bibliothek für 3D im Browser |
| **Token** | Wortstück, die Abrechnungseinheit von Sprachmodellen |
| **Tracker / Track-ID** | verfolgt Dinge über Bilder / ihre feste Nummer |
| **TDD** | Test-Driven Development: erst der Test (rot), dann der Code (grün) |
| **Telemetrie** | Live-Messwerte (Taste `D`) |
| **WebAssembly (WASM)** | ein Programmformat, das abgeschottet im Browser oder in Node läuft; hier OpenSCAD |
| **WebSocket** | stehende Verbindung in beide Richtungen zwischen Browser und Server |
| **Whisper** | Spracherkennungsmodell von OpenAI, hier lokal über MLX |
| **YOLOE** | „You Only Look Once“, Variante mit offenem Vokabular; findet Dinge in einem einzigen Durchgang |
| **YuNet** | kleines, schnelles Gesichtsmodell von OpenCV |

---

## 15. Code lesen: Übungen passend zu deinem Lehrplan

Wie in deinem Lehrplan unter „Code lesen“: Lies den Code Schritt für Schritt und beantworte die Fragen *bevor* du die
Hinweise liest. Die Übungen werden schwerer. Die ersten passen genau zu deinem Stand (`if`, `elif`, `else`).

### Übung 1: Entscheidungen mit `if` (Phase 1)

Datei: `oi/trigger.py`, Funktion `decide`

1. Wie viele `if`-Abfragen gibt es, und was gibt jede zurück?
2. Was passiert, wenn `forced` (Neu prüfen) und `final` (endgültig) beide wahr sind? Warum?
3. Was passiert, wenn du die Abfrage der Sitzungsgrenze unter `forced` verschiebst? Welcher Test würde rot?
4. Warum steht am Ende `return Decision.WAIT` und kein `else`?

*Hinweis:* Eine Funktion endet beim ersten `return`. Die Reihenfolge der `if`s ist also eine Rangfolge.

### Übung 2: Strings vergleichen (Phase 1)

Datei: `oi/privacy.py`, Funktion `label_in`

1. Was machen `.lower()`, `.replace("-", " ")` und `.split()` mit dem Label „Short-Hair“?
2. Was ist `tokens[-1]`?
3. Warum ergibt `label_in("hair dryer", ["hair"])` False, `label_in("short hair", ["hair"])` aber True?
4. Was passiert bei einem leeren Label? Welcher Teil der letzten Zeile schützt davor?

*Hinweis:* Das ist dieselbe Idee wie dein `answer.strip().lower()`: Eingaben vereinheitlichen, bevor man vergleicht.

### Übung 3: Schleifen und Zählen (Phase 1)

Datei: `oi/focus.py`, Methode `_touches_hand`

1. Was ist `dx` und warum wird die Box damit größer gemacht?
2. Was zählt `sum(1 for x, y in h.joints if …)`?
3. Wofür steht `continue`, und wann wird eine Hand übersprungen?
4. Warum gibt es zwei Wege (mit Gelenken / nur mit Box)?

### Übung 4: Eine Klasse mit Zustand (Phase 1)

Datei: `oi/ingest.py`, Klasse `FrameSlot`

1. Welche drei Dinge merkt sich ein `FrameSlot` (`__init__`)?
2. Was passiert in `put`, wenn noch ein Bild auf dem Platz liegt?
3. Wie oft kann `get` dasselbe Bild liefern?
4. Wie würdest du testen, dass ein verdrängtes Bild gezählt wird?

### Übung 5: Dateien und Fehler (Phase 1/2)

Datei: `oi/cache.py`, Klasse `JsonCache`

1. Welche Fehler werden beim Laden abgefangen (`except …`), und was passiert dann?
2. Warum darf ein Cache das Programm nie abstürzen lassen?
3. Was passiert, wenn die Datei nicht geschrieben werden kann?

### Übung 6: Konfiguration und Secrets (Phase 2)

Dateien: `oi/config.py` (Klasse `Settings`, Methode `from_env`), `.env.example`, `.gitignore`

1. Woher kommt der Wert für `model`, wenn `OI_MODEL` gesetzt ist?
2. Was macht `_parse_bool` mit „yes“, „0“ und „vielleicht“?
3. Warum steht `.env` in `.gitignore`, `.env.example` aber nicht?

### Übung 7: Das Beweisbuch (Phase 2 und 5)

Datei: `oi/belief.py`, Methode `_verdict`

1. Ordne jedes `return _Verdict(...)` einer Stufe aus Abschnitt 5 zu.
2. Warum wird `indistinct` *vor* der Zwei-Ansichten-Regel geprüft?
3. Was bewirkt `EPS` bei `share >= CERTAIN_SHARE - EPS`? (Stichwort: Kommazahlen sind ungenau.)
4. Denk dir drei Antworten von Claude aus und rechne die Stufe von Hand aus.

### Übung 8: Der Store (Phase 3, TypeScript)

Datei: `web/src/store.ts`, Funktionen `toggleEntry`, `pickable`, `fullscreenView`

1. `toggleEntry` ändert `s.open` nicht, sondern gibt ein neues Objekt zurück. Warum ist das in React wichtig?
2. Wann gibt `pickable` false zurück? Schreib alle Fälle auf.
3. Warum hängt `fullscreenView` nicht davon ab, ob der Eintrag aufgeklappt ist?
4. Lies den passenden Test in `store.test.ts`. Welche Zeile würde rot, wenn `recent.includes(name)` fehlte?

### Übung 9: Ein kleiner Algorithmus (Phase 3)

Datei: `web/src/hud/shapeMath.ts`, Funktion `spread`

1. In welcher Reihenfolge werden die Schilder platziert, und warum?
2. Was ist `placed` am Anfang, und was bedeutet `fixed`?
3. Wann bricht die innere Schleife `for (;;)` ab? Kann sie ewig laufen?
4. Rechne den Test „top to bottom order stays“ in `shapeMath.test.ts` von Hand nach.

### Übung 10: Ein Claude-Aufruf (Phase 5)

Datei: `oi/identify.py`: `SYSTEM_PROMPT`, `OBSERVATION_SCHEMA`, `_request`, `ClaudeIdentifier.identify`

1. Welche Regel im Prompt sorgt dafür, dass Claude nicht über das Sichtbare hinaus rät?
2. Welche Felder sind im Schema Pflicht, und welche dürfen `null` sein?
3. Wo werden „höchstens 4 Kandidaten“ durchgesetzt, und warum nicht im Schema?
4. Öffne eine JSON-Datei in `runs/` und finde: Tokens, Kosten, Dauer, Stufe danach. Rechne die Kosten nach
   (Abschnitt 10).

### Übung 11: Sicherheit beim Download (Phase 2 und 5)

Datei: `oi/download.py`, Funktionen `fetch` und `_check`

1. Welche vier Dinge prüft der Server, bevor er etwas lädt?
2. Warum wird nach jeder Weiterleitung noch einmal geprüft?
3. Was bedeutet `is_global`, und welche Adressen fallen durch?
4. Der Kommentar oben nennt eine bekannte Lücke (DNS-Rebinding). Erkläre sie in eigenen Worten und warum sie hier
   wenig Schaden anrichten kann.

### Übung 12: Der Builder und sein Budget (Phase 5)

Datei: `oi/builder.py`, Methoden `_build` und `_affordable`

1. In welcher Reihenfolge laufen die Schritte, und welcher Status wird jeweils gemeldet?
2. Was passiert, wenn die Recherche scheitert? Und wenn der CAD-Aufruf scheitert?
3. Rechne nach: Recherche kostet 0,50 $, CAD 0,50 $. Wie viele Prüfrunden passen noch unter 1,60 $?
4. Warum werden nach einer Prüfrunde nur geänderte Teile neu kompiliert?

---

## 16. Zahlen zum Projekt

| Was | Wie viel |
|---|---|
| Python-Code (`oi/`) | etwa 5.100 Zeilen in 32 Dateien |
| Browser-Code (`web/src/`) | etwa 2.100 Zeilen TypeScript + 700 Zeilen CSS |
| Python-Tests | 327 (+ 5 mit echtem Modell, + 2 mit echtem OpenSCAD, + Live-Tests mit Claude) |
| Browser-Tests | 55 |
| Commits | über 80, alle auf `main` |
| Bilder an den Server | höchstens 12 pro Sekunde, höchstens 1280 px breit |
| Whisper | 0,4 s für 3,7 s Sprache |
| Identifizieren | 1,3–1,7 ct, 6–10 s |

---

## 17. Offene Punkte

- **Dein Live-Test** von Teilprojekt 4 und 5: Fragen per Leertaste, Vollbild und Glas-Look.
- **Eine kurze Bildschirmaufnahme** eines echten Durchlaufs wäre das beste Titelbild für das README (in `docs/media/`).
- **Kleinigkeiten aus Teilprojekt 1:**
  - Kamera-Sonderfälle: Ein ersetzter Tab lässt die Kamera an.
  - Ein Schreibfehler im Aufruf-Log lässt den Eintrag auf „analysiere“ stehen.
  - Merkwürdige Namen bei widersprüchlichen Antworten.
  - Pfade, die vom Arbeitsordner abhängen.
- **Dein Live-Test des Präzisionsmodells** mit dem Controller und anderen Dingen: Gerade organische Formen (Griffe)
  sind der härtere Fall als ein Handy.
- **Der echte 3D-Scan** (Apple Object Capture) ist geparkt. Er kommt nur, wenn dir das Präzisionsmodell nicht reicht.

---

## 18. Prompt für eine neue Session

Wie in deinem Lehrplan: Kopiere diesen Prompt in eine neue Session, um das Projekt mit Claude als Lehrer
durchzuarbeiten.

```text
Wir arbeiten im Projekt `Object-Intelligence`. Lies zuerst `ERKLAERUNG.md` und meinen Lehrplan
`AI Developing/Learning/road-to-software-engineer/LEHRPLAN.md`.

Du bist mein geduldiger, aber anspruchsvoller Lehrer. Ich will dieses Projekt so verstehen, dass ich es selbst
erklären, Fehler darin finden und Änderungen sicher umsetzen kann.

Arbeitsweise:
- Nimm dir pro Session einen Abschnitt oder eine Übung aus Abschnitt 15 vor.
- Lass mich den Code zuerst selbst lesen und die Fragen beantworten.
- Gib bei Problemen erst einen kleinen Hinweis, dann einen stärkeren, erst danach die Lösung.
- Frage nach Kontrollfluss, Datenfluss, Annahmen, Fehlerfällen und Tests.
- Wenn ich etwas ändern will: erst den Test, dann den Code, dann alle Tests laufen lassen.

Beginne mit einem kurzen Check, welche Abschnitte ich schon kenne, und schlage die nächste passende Übung vor.
```
