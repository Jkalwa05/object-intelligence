# Object Intelligence, Teilprojekt 1: Sehen & Identifizieren

Stand: 2026-10-01 · Status: **abgeschlossen** (auf `main`, abgenommen durch Jonas' Live-Test), Anpassungen nach den
Live-Tests in §8 bis §12

Object Intelligence ist ein voll funktionsfähiges Programm und Portfolio-Projekt: Man hält einen beliebigen Gegenstand vor die
Mac-Kamera, und das System sagt, *was* es ist und *wie sicher* es ist, zeigt ein 3D-Modell und beantwortet Fragen.
Keine feste Objektliste (Open-Vocabulary). Das Gesamtprojekt ist in Teilprojekte zerlegt, jedes mit eigener Spec und
eigenem Plan:

1. **Sehen & Identifizieren** (diese Spec, abgeschlossen) · 2. **Produkt-Steckbrief** (abgeschlossen; ersetzt
„Wissen mit Quellen“, ohne Quellen, `2026-10-01-product-profile-design.md`) · 3. 3D · 4. Fragen & Sprache ·
5. Politur & Portfolio

Teilprojekt 1 legt die Datenformate fest, an die die anderen andocken (`oi/contracts.py`, Contract-Version 1).

## 1. Ziel und Erfolgskriterien

**Ziel:** Das System umrahmt alle Objekte im Kamerabild live mit stabilen IDs. Es wählt das gehaltene Objekt als Fokus und
identifiziert es über mehrere Ansichten so genau, wie es ehrlich möglich ist (Kategorie → Marke → Modell → Variante).
Stufe, Kandidaten und Indizien erscheinen als HUD direkt am Objekt. Bei Zweifel bittet das System um eine trennende
Ansicht, und die Ergebnisse spricht es laut aus.

**Erfolg (vom Owner festgelegt):** Jonas testet live mit fünf Gegenständen (iPhone 14, P3-Controller, Xbox-Controller,
Steinlampe, Myprotein-Aminosäuren) und ist mit dem Ergebnis zufrieden. Die Abnahme-Checkliste
`docs/acceptance/sp1-checklist.md` entsteht in der Umsetzung und hält pro Objekt fest: Folgt die Box? Bleibt die ID
stabil? Passen Stufe und Name? Ist die Bitte um eine Ansicht sinnvoll? Wie lange dauert es bis zum ersten Ergebnis, und
was kostet es? Richtwerte, keine harten Schranken:

- Das Kamerabild läuft flüssig (Browser-Video ≥ 30 fps).
- Der Detektor verarbeitet ≥ 8 Bilder/s auf dem kühlen Air.
- Das erste Ergebnis kommt ≤ 6 s nach dem Ruhighalten.
- Ein Objekt kostet ≤ 10 Cent.

**Nicht im Umfang:** Fakten mit Quellen und Barcode-Lesen (Teilprojekt 2, inzwischen gestrichen), 3D (3), Mikrofon und Fragen (4). Ebenfalls
nicht dabei: ein Objekt-Gedächtnis über das Verlassen des Bildes hinaus, Hosting, mehrere Nutzer und Mobilgeräte.
Aufnahmen, Wiedergabe und Testsets aus Videos will der Owner ausdrücklich nicht. Die App läuft immer live.

**Entscheidungen aus dem Brainstorming:**

| Thema | Entscheidung |
|---|---|
| Rechenort | Hybrid: Kamera, Detection und Tracking lokal auf dem MacBook Air M5 (16 GB, ohne Lüfter). Identifikation per Cloud-API |
| Architektur | Ansatz A: die ganze KI in Python (FastAPI), Oberfläche im Browser (React + TypeScript) |
| Was wird identifiziert | Automatisch nur das Fokus-Objekt. Andere Objekte behalten ihr grobes Label, ein Klick macht sie zum Fokus |
| Cloud-Modell | Claude, Standard `claude-opus-5-5` (ein Konfigurationswert, Alternativen: `claude-sonnet-5-5`, `claude-haiku-4-5`) |
| Unsicherheit | Stufen (sicher, wahrscheinlich, unsicher, nur Kategorie) und Balken statt Prozenten. Zahlen nur in der Telemetrie |
| Ausgabe | HUD am Objekt. Die Stimme begleitet und sagt dasselbe wie die Karte |
| Look | „Glas“: weiße Systemschrift auf dunklem Milchglas, kein Glow, dezente Animationen |
| Sprache | Karte und Stimme Deutsch, umstellbar auf Englisch (`OI_LANGUAGE=en`) |
| Abnahme | Live-Test mit 5 Gegenständen, keine Aufnahmen |

## 2. Architektur

```
Browser (web/, React + TS)                          Python (oi/, FastAPI)
┌───────────────────────────┐  binär: JPEG 1280×720  ┌───────────────────────────────────────┐
│ Kamera (getUserMedia)     │ ─────── ≤ 12/s ──────▶ │ ingest:     nur das neueste Bild zählt │
│ Video 30–60 fps           │                        │ perception: YOLOE-26 PF + BoT-SORT     │
│ HUD-Canvas + Info-Karte   │ ◀──── tracks ───────── │ focus:      Fokus-Wähler               │
│ Telemetrie, Stimme        │ ◀── identity, telemetry│ views:      Ansichten-Sammler          │
└───────────────────────────┘                        │ trigger:    wann Claude gefragt wird   │
                                                     │ identify:   Identifier → Claude API    │
                                                     │ belief:     Indizien-Buch              │
                                                     │ telemetry:  Latenzen, Kosten, Protokoll│
                                                     └───────────────────────────────────────┘
```

| Modul | Aufgabe |
|---|---|
| `oi/config.py` | alle Schwellen, Gewichte, Grenzen, Preise und Modellnamen an einer Stelle. Umgebungsvariablen `OI_*` überschreiben sie (Tabelle in Abschnitt 6) |
| `oi/contracts.py` | Pydantic-Modelle, die alle Teile teilen: `Track`, `Observation`, `Candidate`, `BeliefState`, `Level`, Protokoll-Nachrichten. Contract-Version 1 |
| `oi/ingest.py` | `FrameSlot`: nimmt Bilder an, hält nur das neueste und zählt die verworfenen |
| `oi/perception.py` | `Detector`-Protocol und `YoloeDetector`: Bild → `list[Track]`. Dazu `FakeDetector` (Tracks nach Drehbuch) für Tests |
| `oi/focus.py` | `FocusSelector`: Tracks + Zeit → Fokus-ID. Reine Logik |
| `oi/views.py` | Qualitätsprüfung, `dhash`, Neuheit einer Ansicht, `ViewCollector`. Reine Logik auf Bild-Arrays |
| `oi/trigger.py` | `TriggerPolicy`: Startet jetzt ein Claude-Aufruf? Reine Logik |
| `oi/identify.py` | `Identifier`-Protocol, `ClaudeIdentifier`, `FakeIdentifier` |
| `oi/belief.py` | `Belief`: Beobachtungen → Rangliste, Anteile, Stufe, Anzeige-Name, Zeile für Karte und Stimme. Reine Logik |
| `oi/lines.py` | Satzvorlagen für Karte und Stimme, Deutsch und Englisch |
| `oi/telemetry.py` | Latenzen, fps, Aufrufe, Kosten; das Nachvollzieh-Protokoll in `runs/` |
| `oi/pipeline.py` | `Pipeline`: verbindet alles in einer asyncio-Schleife; die Identifikation läuft als Hintergrund-Task |
| `oi/server.py`, `oi/__main__.py` | FastAPI-App, WebSocket `/ws`, liefert `web/dist` aus. `python -m oi [--port 8766] [--fake-claude] [--no-browser]` |
| `oi/trackers/botsort.yaml` | Tracker-Einstellungen |
| `web/` | Vite + React + TypeScript: `src/camera/` (Aufnahme, Senden), `src/hud/` (Canvas-Overlay, Info-Karte, Telemetrie, Hinweise), `src/voice/` (Sprachausgabe), `src/store.ts` (Zustand mit Zustand), `src/protocol.ts` (Nachrichtentypen) |

### 2.1 Datenfluss und Takt

- Der Browser öffnet die Kamera mit 1280×720 (angefragt: 30 fps) und zeigt das `<video>` direkt an. Das Bild bleibt also
  flüssig, egal wie lange die KI rechnet.
- Höchstens 12-mal pro Sekunde zeichnet der Browser das aktuelle Bild in ein Canvas und schickt es als JPEG (Qualität
  0,8), aber nur, wenn im WebSocket-Puffer weniger als 1 MB liegt. Die Bilder gehen immer ungespiegelt raus.
- Aufbau einer binären Nachricht: 4 Byte Header-Länge (uint32, big-endian), dann ein UTF-8-JSON-Header
  `{"frame_id", "t_capture_ms", "w", "h"}`, dann die JPEG-Bytes.
- `FrameSlot` hält nur das neueste Bild. Die Wahrnehmungs-Schleife nimmt immer dieses („latest frame wins“), verworfene
  Bilder werden gezählt.
- YOLOE rechnet auf 640 px (`imgsz=640`) in einem Worker-Thread (`asyncio.to_thread`), damit der WebSocket reaktiv
  bleibt. Die Boxen liegen in Koordinaten des vollen Bildes. Ausschnitte für Claude kommen aus dem vollen 1280×720-Bild.
- Jedes verarbeitete Bild erzeugt eine `tracks`-Nachricht. Die Identifikation läuft als eigener asyncio-Task, die
  Wahrnehmungs-Schleife wartet nie auf Claude.

### 2.2 Wahrnehmung

- Modell: YOLOE-26, Prompt-free-Variante mit Segmentierung, Größe s (`yoloe-26s-seg-pf.pt`). Lässt sie sich nicht laden,
  wird `yoloe-11s-seg-pf.pt` verwendet. Größe m per Konfiguration, falls s im Live-Test zu ungenau ist.
- Aufruf: `model.track(frame, persist=True, tracker=<Paketordner>/trackers/botsort.yaml, imgsz=640, device="mps",
  conf=0.25, verbose=False)`. Der Tracker-Pfad wird relativ zum Paket aufgelöst, nicht zum aktuellen Arbeitsordner.
- Tracker: BoT-SORT ohne ReID, `track_buffer: 20`. Das entspricht bei 10–12 verarbeiteten Bildern/s etwa 1,5–2 s, so
  lange überlebt eine ID eine Verdeckung.
- Ein `Track` hat: `id`, `box` (x1, y1, x2, y2 in Pixeln des vollen Bildes), `polygon` (Umriss aus der Maske, vereinfacht
  auf ≤ 48 Punkte), `label`, `score`, `age_frames`, `first_seen_ts`. Weitergegeben werden nur Detektionen mit Track-ID.
  Das Label ist nur ein Hinweis, die eigentliche Identifikation macht Claude.

### 2.3 Fokus-Wähler

- **Kein Fokus möglich** für:
  - Labels aus der Ausschlussliste: Personen und Körperteile (`person, man, woman, boy, girl, child, baby, face, head,
    hand, arm, finger`), erweiterbar per Konfiguration
  - Boxen unter 1 % oder über 60 % der Bildfläche
  - Tracks, die jünger als 3 Bilder sind
- **Hand-Bonus:** Hände sind selbst kein Fokus, geben aber einen Bonus. `hand = 1`, wenn sich die Box mit einer
  erkannten Hand-Box überlappt (Schnittfläche > 10 % der kleineren Box), sonst `0`. Liefert der Detektor keine Hände,
  ist der Faktor für alle 0.
- **Bewertung** (alle Faktoren liegen zwischen 0 und 1):
  `score = 0,30·size + 0,20·center + 0,25·hand + 0,15·steady + 0,10·new`
  - `size = min(1, Flächenanteil / 0,15)`
  - `center = 1 − Abstand der Boxmitte zur Bildmitte / halbe Bilddiagonale`
  - `steady = 1 − min(1, Geschwindigkeit der Boxmitte in Bilddiagonalen pro Sekunde / 0,5)`
  - `new = 1` bei einem Alter unter 2 s, sinkt linear auf 0 bei 6 s
- **Hysterese:** Ein Herausforderer ersetzt den Fokus nur, wenn sein Score 0,5 s lang ununterbrochen mindestens
  0,15 höher liegt. Verschwindet der Fokus-Track, wird sofort der beste Kandidat gewählt.
- **Anheften:** Ein Klick auf eine Box heftet diesen Track als Fokus an, unabhängig von den Scores. Das gilt, bis der
  Track verschwindet oder man ins Leere klickt.

### 2.4 Ansichten-Sammler und Auslöser

- **Ausschnitt:** Fokus-Box plus 12 % Rand pro Seite, begrenzt auf das Bild, aus dem vollen Bild. Für Claude wird die
  lange Kante auf ≤ 1024 px skaliert, JPEG-Qualität 0,9.
- **Qualitätsprüfung** (alles muss gelten):
  1. Das Objekt ist nicht abgeschnitten: Die Box hält zu jedem Bildrand mindestens 1 % der Bildbreite Abstand.
  2. Die kürzere Box-Seite misst ≥ 120 px im vollen Bild.
  3. Schärfe (Varianz des Laplace-Filters auf dem Graustufen-Ausschnitt, skaliert auf 256 px Breite) ≥ 60. Das ist ein
     Startwert, der im ersten Live-Test kalibriert wird. Die Telemetrie zeigt dafür den aktuellen Schärfewert.
  4. `steady ≥ 0,6` seit mindestens 0,5 s.
- **Hinweis:** Scheitert die Prüfung länger als 2 s, bekommt der Fokus einen Hinweis, je nach Grund: Punkt 1 → „Bitte
  ganz ins Bild.“, Punkt 2 → „Bitte etwas näher.“, Punkt 3 oder 4 → „Halt es bitte ruhig.“
- **Bestes Bild:** Sobald die Prüfung besteht, sammelt der `ViewCollector` 0,4 s lang Ausschnitte und nimmt den
  schärfsten.
- **Neue Ansicht:** Jeder Ausschnitt bekommt einen Fingerabdruck: den 64-Bit-dHash des Graustufen-Ausschnitts (9×8) und
  das Seitenverhältnis der Box. Ein Ausschnitt gilt als *neue Ansicht*, wenn die Hamming-Distanz zu jeder schon
  gesendeten Ansicht dieses Tracks ≥ 14 ist oder sich das Seitenverhältnis um ≥ 25 % unterscheidet.
- **`TriggerPolicy`:** Ein Aufruf startet, wenn alle Regeln gelten:
  1. Der Track ist Fokus und hat einen Ausschnitt, der die Prüfung besteht.
  2. Für diesen Track läuft kein Aufruf, insgesamt laufen weniger als 2.
  3. Der Track ist noch nicht final (Abschnitt 2.6).
  4. Es ist der erste Aufruf für den Track, oder der Ausschnitt ist eine neue Ansicht.
  5. Der Track hatte weniger als 4 Aufrufe.
  6. Die Sitzung hatte weniger als 150 Aufrufe.

  „Neu prüfen“ (Klick auf der Karte) setzt die Regeln 3, 4 und 5 außer Kraft, Regel 6 nie. Blockiert Regel 5, bleibt das
  Ergebnis stehen. Blockiert Regel 6, bekommt der Track den Status `paused`, und eine `notice` meldet die Kostenbremse.

### 2.5 Identifikation

- **Schnittstelle:** `Identifier.identify(req: IdentifyRequest) -> Observation` (async). Die Anfrage enthält:
  - den Ausschnitt als JPEG
  - das grobe YOLOE-Label als Hinweis
  - eine Text-Zusammenfassung der bisherigen Beobachtungen (je Beobachtung die Top-3-Namen mit Indizien)
  - eine offene Bitte um eine Ansicht, falls es eine gibt
  - die Sprache

  Alte Bilder werden nicht erneut gesendet. An Claude geht nur der Ausschnitt, nie das ganze Bild.
- **`ClaudeIdentifier`:** Anthropic Python SDK (`AsyncAnthropic`) mit dem Modell aus der Konfiguration (Standard
  `claude-opus-5-5`). Einstellungen:
  - `output_config` mit `effort: "low"` und einem JSON-Schema (Structured Outputs)
  - 2 Wiederholungen (SDK-Standard) und ein Timeout von 20 s pro Versuch, im schlimmsten Fall also etwa 60 s bis
    zum Status `error`
  - Bei Opus 5.5 und Sonnet 5.5 ist der serverseitige Refusal-Fallback aktiv (`fallbacks: "default"`, Beta
    `server-side-fallback-2026-07-01`)
  - Der API-Key kommt aus `ANTHROPIC_API_KEY` oder einem `ant auth login`-Profil
- **System-Prompt** (fest, damit er cachebar ist): Identifiziere das Objekt so genau, wie die sichtbaren Indizien es
  erlauben, und rate nicht darüber hinaus. Nenne bis zu 4 Kandidaten nach Plausibilität. Indizien sind nur sichtbare
  Merkmale. Gib lesbaren Text wieder. Sag, ob die Top-Kandidaten von außen unterscheidbar sind. Wenn du unsicher bist,
  nenne die eine Ansicht, die die ersten beiden am besten trennt, und warum. Ist kein bestimmtes Produkt erkennbar, sag
  das und beschreibe das Objekt allgemein. Antworte in {Sprache}.
- **`Observation`**, das Schema der Antwort:
  - `category`: str, z. B. „smartphone“
  - `candidates`: 0–4 Einträge, je `brand` (str|null), `model_name` (str|null), `variant` (str|null),
    `depth` („category“ | „brand“ | „model“ | „variant“), `evidence` (list[str], ≤ 5)
  - `readable_text`: list[str], ≤ 10
  - `distinguishable`: bool
  - `next_view`: `{view, reason}` | null, z. B. `{"view": "die Unterseite", "reason": "Lightning oder USB-C"}`
  - `self_assessment`: „high“ | „medium“ | „low“
  - `generic_description`: str | null
- **Fehler:** Bei `stop_reason: "refusal"`, einem Schemafehler oder Timeout wird die Beobachtung verworfen und gezählt.
  Der Track bekommt den Status `error`, und der nächste Versuch kommt mit der nächsten neuen Ansicht oder per „Neu
  prüfen“.
- **Kosten:** `usage` mal Preistabelle aus der Konfiguration, je Aufruf und je Sitzung. Preise pro Million Tokens
  (Eingabe/Ausgabe): Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 4.5 $1/$5.
- **`FakeIdentifier`:** liefert vorbereitete Beobachtungen, in Tests nach Drehbuch, mit `--fake-claude` passend zum
  groben Label. Damit kann man kostenlos an der Oberfläche arbeiten.

### 2.6 Indizien-Buch

- Pro Track führt `Belief` eine Liste von Beobachtungen, jede mit `view_id` und Qualität `q`.
  - `q` ist die Schärfe, linear auf 0,5–1 abgebildet: die Schärfe-Schwelle → 0,5, ab dem Fünffachen der Schwelle → 1.
  - `view_id` vergibt der `ViewCollector`: Eine neue Ansicht bekommt eine neue ID. Ein Ausschnitt, der keine neue
    Ansicht ist (etwa bei „Neu prüfen“), bekommt die ID der ähnlichsten schon gesendeten Ansicht. Wer dieselbe Seite
    zweimal prüfen lässt, sammelt also keine zweite unabhängige Ansicht.
- **Kandidaten-Schlüssel:** kleingeschrieben und mit normalisierten Leerzeichen „brand model_name“. Die Variante gehört
  nicht zum Schlüssel. Sie wird angezeigt, wenn die letzten beiden Beobachtungen sie gleich nennen.
- **Punkte:** Ein Kandidat auf Rang r (0-basiert) bekommt `[1,0; 0,5; 0,25; 0,125][r] · q` Punkte, summiert über alle
  Beobachtungen. Anteil = Punkte / Summe aller Punkte. Vorsprung = Anteil des Ersten minus Anteil des Zweiten; gibt es
  keinen Zweiten, zählt dessen Anteil als 0.
- **Eindeutiges Beweisstück:** Der normalisierte `model_name` eines Kandidaten (≥ 3 Zeichen) steht als Teilstring im
  normalisierten `readable_text` derselben Beobachtung.
- **Stufen**, in dieser Reihenfolge geprüft:
  1. Noch keine Beobachtung → Status `analysing`.
  2. Kein Kandidat, oder der Top-Kandidat hat `depth = "category"` → **NUR_KATEGORIE**.
  3. Eindeutiges Beweisstück für den Top-Kandidaten → **SICHER**.
  4. Der Top-Kandidat war in ≥ 2 verschiedenen Ansichten auf Rang 1, Anteil ≥ 0,6 und Vorsprung auf Platz 2 ≥ 0,3 →
     **SICHER**.
  5. Vorsprung auf Platz 2 < 0,15, oder die letzte `self_assessment` ist „low“ → **UNSICHER**.
  6. Sonst → **WAHRSCHEINLICH**.

  Ohne eindeutiges Beweisstück kommt eine einzelne Ansicht also nie über WAHRSCHEINLICH hinaus.
- **Anzeige-Name:** nur so tief, wie der Top-Kandidat reicht. Bei `brand` „Apple-Smartphone“, bei `model` „Apple
  iPhone 14“, bei `variant` „Apple iPhone 14, Midnight“.
- **Final**, dann gibt es keine automatischen Aufrufe mehr:
  - SICHER
  - NUR_KATEGORIE in ≥ 2 Ansichten
  - UNSICHER, wenn die letzte Beobachtung `distinguishable = false` meldet („von außen kaum zu unterscheiden“)
- **Ausgabe `BeliefState`:** `level`, `display_name`, `candidates` (Top 3 mit Anteil), `evidence` (die Indizien des
  Top-Kandidaten, höchstens 6), `view_request` (`{view, reason}` | null), `final`, `calls_used`, `line`.
- **Zeilen** aus `oi/lines.py`, gleich für Karte und Stimme (Englisch analog):

| Fall | Zeile |
|---|---|
| SICHER | „Das ist {name}.“ |
| WAHRSCHEINLICH | „Das ist wahrscheinlich {name}.“ |
| UNSICHER mit Ansicht | „{a} oder {b}? Zeig mir bitte {view}.“ |
| UNSICHER, nicht unterscheidbar | „{a} oder {b}, von außen kaum zu unterscheiden.“ |
| NUR_KATEGORIE | „{Beschreibung}, ein bestimmtes Produkt erkenne ich nicht.“ |
| Hinweise | „Halt es bitte ruhig.“ · „Bitte etwas näher.“ · „Bitte ganz ins Bild.“ |
| Fehler | „Identifikation gerade nicht möglich.“ |

### 2.7 WebSocket-Protokoll

Nachrichten vom Browser an den Server:
- binäres Bild (Abschnitt 2.1)
- `{"type": "focus", "track_id": 17}` zum Anheften, `"track_id": null` zum Lösen
- `{"type": "recheck", "track_id": 17}`

Nachrichten vom Server an den Browser sind JSON, jede mit `type`, `ts` und fortlaufender `seq`. Koordinaten sind auf
0–1 normalisiert:
- `tracks`: `frame_id`, `w`, `h`, `focus_id`, `tracks: [{id, box, polygon, label, score}]`, `hint` (Zeile | null).
  Tracks mit Labels aus der Ausschlussliste (Personen, Körperteile) werden nicht gesendet, das HUD zeichnet also keine
  Klammern um Menschen.
- `identity`: `track_id`, `status` („analysing“ | „ready“ | „error“ | „paused“) und die Felder von `BeliefState`
- `telemetry` (1-mal pro Sekunde): `fps_processed`, `frames_dropped`, `det_ms`, `id_ms_last`, `sharpness_focus`,
  `calls_session`, `cost_session_usd`, `model`, `mode` („hybrid“ | „lokal“)
- `notice`: `level` („info“ | „warn“ | „error“), `text`

`web/src/protocol.ts` bildet die Typen von Hand nach. Ein pytest schreibt Beispielnachrichten nach
`tests/fixtures/protocol-examples.json`, und ein Vitest prüft, dass die TypeScript-Typprüfer sie akzeptieren. So bleiben
beide Seiten synchron.

## 3. Oberfläche (HUD)

- **Look „Glas“:**
  - Text `#fff` auf `rgba(22,22,28,.6)` mit `backdrop-filter: blur(8px)`, Radius 10 px
  - Systemschrift (`-apple-system`), einfarbig, kein Glow
  - Objekte außerhalb des Fokus: Eckklammern in Weiß mit 35 % Deckkraft und ein kleines Label „#4 cup“
  - Fokus: Die Klammern schnappen zu (200 ms), der Umriss ist 1 px weiß, und während `analysing` läuft eine weiße
    Scanlinie über das Objekt
- **Info-Karte:**
  - Sie ist mit einer Linie an das Fokus-Objekt gebunden und blendet in 200 ms ein.
  - Inhalt: der Anzeige-Name (groß) und die Stufe als kleines Label in Großbuchstaben (SICHER, WAHRSCHEINLICH,
    UNSICHER, NUR KATEGORIE; während der Analyse „ANALYSIERE …“). Dazu bis zu 3 Kandidaten-Balken nach Anteil, ohne
    Zahlen, und höchstens 6 Indizien-Kacheln, die im Abstand von 80 ms nacheinander erscheinen. Darunter die Bitte um
    eine Ansicht mit Pfeil und Begründung und der Knopf „Neu prüfen“.
- **Platzierung:** Die Karte sitzt links oder rechts der Fokus-Box, auf der Seite mit mehr freiem Platz. Die Seite
  wechselt sie nur, wenn die andere 0,5 s lang mindestens 20 % mehr Platz bietet. Vertikal steht sie auf Höhe der
  Box-Oberkante, begrenzt auf den sichtbaren Bereich. Sie verdeckt die Box nie.
- **Bewegung:** Angezeigte Boxen folgen neuen Positionen weich (exponentielle Glättung, Zeitkonstante 80 ms), gezeichnet
  im Takt des Bildschirms per `requestAnimationFrame`.
- **Spiegelung:** Das Video wird standardmäßig gespiegelt angezeigt, wie ein Spiegel (Taste `S` schaltet um). Das
  Overlay wird mitgespiegelt, die Bilder an den Server sind nie gespiegelt.
- **Telemetrie:** oben links, klein, Taste `D`. Sie zeigt Video-fps (im Browser gemessen), verarbeitete fps,
  Detektor-ms, Dauer der letzten Identifikation, Schärfewert, Aufrufe, Sitzungskosten, Modell und Modus. Dazu die
  Anteile der Fokus-Kandidaten als Zahlen, aus der `identity`-Nachricht. Nur hier stehen Zahlen, die Karte zeigt Balken.
- **Hinweise und Meldungen:** Kein API-Key, Kostenbremse, verweigerte Kamera und verlorene Verbindung erscheinen als
  kleines Glasbanner oben in der Mitte. Bei Verbindungsverlust versucht der Browser alle 2 s, sich neu zu verbinden.
- **Bedienung:** Klick auf eine Box heftet den Fokus an, Klick ins Leere löst ihn. `M` schaltet die Stimme stumm, `D`
  blendet die Telemetrie ein und aus, `S` schaltet die Spiegelung um.
- **Stimme:**
  - `speechSynthesis` mit der ersten Systemstimme der eingestellten Sprache, ohne Spaßstimmen (Lehre aus Kalwa).
  - Sie spricht die `line` des Fokus-Objekts nur, wenn sich die Zeile ändert, und nie dieselbe Zeile zweimal für
    denselben Track. Hinweise höchstens alle 5 s.
  - Ein Fokuswechsel bricht das laufende Sprechen ab.
- **Sprache:** Die Zeilen kommen vom Server. Die festen UI-Texte (Stufen-Labels, „Neu prüfen“, Meldungen) stehen in einem
  kleinen Wörterbuch im Browser, Deutsch und Englisch.

## 4. Fehlerbehandlung

| Situation | Verhalten |
|---|---|
| Claude nicht erreichbar oder überlastet | Das SDK versucht es zweimal neu. Danach Status `error`, die Karte zeigt die Fehlerzeile, Boxen und IDs laufen weiter |
| Kein API-Key | Modus „lokal“: Boxen, IDs und grobe Labels gibt es trotzdem, dazu eine `notice` und die Anzeige in der Telemetrie |
| Refusal, Schemafehler, Timeout | Die Beobachtung wird verworfen und gezählt, geraten wird nie (Abschnitt 2.5) |
| Kamera verweigert | Banner mit Anleitung (Systemeinstellungen → Datenschutz → Kamera) und „Erneut versuchen“ |
| Python-Server weg | Banner, automatischer Neuaufbau der Verbindung alle 2 s |
| Objekt kurz verdeckt oder aus dem Bild | Die ID überlebt etwa 1,5–2 s (`track_buffer`). Kommt es später zurück, bekommt es eine neue ID und wird neu identifiziert |
| Fokus wechselt während eines Aufrufs | Die Antwort landet über die Track-ID beim richtigen Objekt |
| Unscharf, zu klein, abgeschnitten | Kein Aufruf, stattdessen ein Hinweis (Abschnitt 2.4) |
| Air wird heiß und drosselt | Der Detektor verarbeitet weniger Bilder („latest frame wins“), das Video bleibt flüssig, die fps stehen in der Telemetrie |
| Kostenbremse | Höchstens 4 Aufrufe pro Objekt, 150 pro Sitzung (≈ 3 $), danach Status `paused` und eine `notice` |

**Nachvollzieh-Protokoll:** Jeder Claude-Aufruf landet unter `runs/<YYYY-MM-DD_HH-MM-SS>/` als
`<nnn>_track<id>.jpg` (der gesendete Ausschnitt) und `<nnn>_track<id>.json`. Die JSON-Datei enthält den Anfragetext, die
Antwort, `usage`, Kosten, Dauer, Modell und die Stufe nach dem Update. `runs/` steht in `.gitignore`, `OI_LOG_CALLS=0`
schaltet das Protokoll ab.

## 5. Tests

- **pytest, Standardlauf ohne Modell und ohne Netz:**
  - `belief`: Beobachtungsfolgen → Stufe, Rangliste, final, Zeilen. Dabei auch das iPhone-Beispiel (unsicher → Unterseite
    → „kaum zu unterscheiden“) und das Beweisstück per lesbarem Text
  - `focus`: Ein gehaltenes Objekt schlägt ein größeres Hintergrundobjekt; Hysterese; Anheften; Ausschlüsse; Hand-Bonus
  - `views`: scharfes gegen weichgezeichnetes Testbild, dHash-Neuheit, Erkennung abgeschnittener Objekte
  - `trigger`: alle sechs Regeln und „Neu prüfen“
  - `ingest`: „latest frame wins“ und das Zählen verworfener Bilder
  - `identify`: `ClaudeIdentifier` mit einem Fake-SDK-Client. Die Anfrage enthält nur den Ausschnitt (lange Kante
    ≤ 1024) und das Schema; Refusal, Schemafehler und Timeout führen zum Verwerfen; die Kosten werden richtig berechnet
  - `lines`: Deutsch und Englisch
  - Protokoll: Header-Parsing, Beispielnachrichten
- **Integration:** FastAPI-WebSocket-Test mit einem `FakeDetector` (Tracks nach Drehbuch) und dem `FakeIdentifier`. Die
  Reihenfolge `tracks` → `identity analysing` → `identity ready` stimmt. Ohne API-Key kommt die `notice`, und die Tracks
  fließen weiter.
- **Vitest (Browser):** Koordinaten-Umrechnung inklusive Spiegelung und Letterboxing, Karten-Platzierung (mehr Platz,
  Hysterese, keine Überdeckung), Glättung, Sprech-Regeln (nur bei Änderung, keine Wiederholung, stumm, Hinweis-Abstand)
  und die Protokoll-Beispiele.
- **Gezielt gestartet** (Marker, nicht im Standardlauf):
  - `-m model`: YOLOE-26 PF findet auf dem mitgelieferten Ultralytics-Bild `bus.jpg` mindestens ein Objekt, auf MPS
  - `-m claude`: Ein echter Aufruf auf einem Ausschnitt von `bus.jpg` liefert eine gültige `Observation` (ca. 2 Cent)
- **Keine aufgenommenen Videos** (Entscheidung des Owners). Die Abnahme ist der Live-Test aus Abschnitt 1.

## 6. Konfiguration, Start, Abhängigkeiten

| Wert | Standard | Umgebungsvariable |
|---|---|---|
| Claude-Modell | `claude-opus-5-5` | `OI_MODEL` |
| Effort | `low` | `OI_EFFORT` |
| Sprache | `de` | `OI_LANGUAGE` |
| Aufrufe pro Objekt / Sitzung / gleichzeitig | 4 / 150 / 2 | `OI_MAX_CALLS_OBJECT`, `OI_MAX_CALLS_SESSION` |
| Detektor-Datei, Fallback | `yoloe-26s-seg-pf.pt`, `yoloe-11s-seg-pf.pt` | `OI_DETECTOR` |
| `imgsz`, `conf`, `track_buffer` | 640, 0,25, 20 | – |
| Bilder pro Sekunde vom Browser, JPEG-Qualität | 12, 0,8 | – |
| Fokus-Gewichte, Hysterese | 0,30/0,20/0,25/0,15/0,10; +0,15 für 0,5 s | – |
| Schärfe-Schwelle, dHash-Distanz, Seitenverhältnis | 60, 14, 25 % | `OI_MIN_SHARPNESS` |
| Ausschnitt-Rand, lange Kante für Claude | 12 %, 1024 px | – |
| Timeout Claude | 20 s | – |
| Protokoll | an | `OI_LOG_CALLS` |
| Port | 8766 | `OI_PORT` |

**Start:**
- einmalig `uv sync` und `npm --prefix web install`
- dann `npm --prefix web run build` und `uv run python -m oi`; das öffnet `http://127.0.0.1:8766`
- Entwicklung der Oberfläche: `npm --prefix web run dev` (Vite leitet `/ws` an Port 8766 weiter)
- `--fake-claude` für kostenloses Arbeiten ohne API-Key-Verbrauch

**Abhängigkeiten:**
- Python 3.12 mit uv. Laufzeit: `fastapi`, `uvicorn[standard]`, `ultralytics`, `torch` (MPS), `opencv-python-headless`,
  `numpy`, `pydantic`, `anthropic`. Entwicklung: `pytest`, `pytest-asyncio`, `httpx`.
- Web: `react`, `react-dom`, `zustand`, `vite`, `typescript`, `vitest`. Keine weiteren UI-Bibliotheken; die Animationen
  laufen über CSS und Canvas.
- Die YOLOE-Gewichte lädt Ultralytics beim ersten Start herunter; `*.pt` steht in `.gitignore`.

## 7. Risiken und Messpunkte

| Risiko | Gegenmittel |
|---|---|
| YOLOE-PF übersieht ein Testobjekt oder vergibt seltsame Labels | Das Label ist nur ein Hinweis. `conf` senken, Größe m, beides per Konfiguration; wird im ersten Live-Test geprüft |
| Der Air drosselt | „latest frame wins“ hält das Video flüssig; notfalls `imgsz` 480 |
| Opus 5.5 antwortet zu langsam | Scanlinie und „ANALYSIERE …“ machen das Warten sichtbar; `OI_MODEL=claude-sonnet-5-5` als Ausweg |
| Die Schärfe-Schwelle passt nicht zu Kamera und Licht | Der Schärfewert steht in der Telemetrie, die Schwelle wird im ersten Live-Test kalibriert |
| Doppelgänger wie iPhone 13 und 14 | Gewolltes Verhalten: UNSICHER bzw. „kaum zu unterscheiden“. Das ist kein Fehler, sondern der Kern des Projekts |

## 8. Nachtrag 2026-09-30: Anpassungen nach dem ersten Live-Test

Diese Punkte ersetzen die betroffenen Stellen in §2.3 und §3 (Klammern für jedes Objekt, Klick zum Fokussieren).

- **Box nur für das Gehaltene.** Hände findet Apples Vision-Framework (`VNDetectHumanHandPoseRequest`), weil YOLOE
  fast nie „hand“ meldet. Fokus bekommt nur ein Objekt mit einer Hand darauf (2 s Gedächtnis). Es darf höchstens
  achtmal so groß wie die Hand sein, damit ein großer Hintergrund hinter der Hand nicht als gehalten gilt. Box und
  Karte verschwinden 2 s nach dem Loslassen. Klick zum Fokussieren entfällt.
- **Die Person wird nie markiert.** Gesichter findet OpenCVs YuNet (MIT-Lizenz, Prüfsumme fest hinterlegt). Die
  Körperzone reicht vom Gesicht verbreitert bis zum unteren Bildrand, dazu kommen die Personen-Boxen. Was dort liegt
  (Kette, T-Shirt, Brille, Haare), bekommt nie eine Box und geht nie an Claude. Ausschnitte an Claude enthalten nur
  die Pixel des Objekts, der Rest ist grau.
- **Szene einmessen.** In den ersten 5 s nach dem Verbinden (oder nach Taste `R`) sammelt `oi/scene.py` den
  Hintergrund. Was in mindestens der Hälfte der Bilder da war, wird mit dem häufigsten Label und der Median-Box
  eingefroren und statisch angezeigt. Neue Server-Nachricht `scene` (`calibrating`, `items`), neue
  Browser-Nachricht `recalibrate`. `tracks` enthält nur noch das gehaltene Objekt.
- **Weniger Hinweise.** Hinweise kommen nur beim ersten Erfassen eines Objekts und nach „Neu prüfen“. Die Telemetrie
  zeigt den Prüfgrund, die Karte legt sich nie über ein Gesicht.
- **Start.** Ist der Port belegt, bricht der Start mit einer klaren Meldung ab, statt den Browser auf einen älteren
  Server zu schicken.

## 9. Nachtrag 2026-09-30 (Abend): Hintergrund per Claude, Hand-Umrandung, Akzentfarben

Nach dem zweiten Live-Test mit echtem Claude. Die Protokolle zeigten: Lampe (3×) und Treppe (1×) gingen als
„gehaltenes Objekt“ an Claude. „Gehalten“ hieß nur, dass die Handbox eine Objektbox überlappte. Teile hinter der Hand
zählten damit als gehalten und punkteten durch Stillstand sogar vor dem iPhone. YOLOE nannte Treppenstufen „paper
towel“ und „cup“.

- **Hintergrund in einem Claude-Aufruf.** Wenn die Szene nach 5 s einfriert, geht **ein** Bild an Claude
  (höchstens 1280 px breit). Vorher werden alle Personenzonen der letzten 2 s grau übermalt (`privacy.mask_people`,
  Gesicht bis zu den Schultern und bis zum Bildrand, Personenboxen, Körperteil-Labels). Das ist die einzige
  Ausnahme von „nur Objekt-Ausschnitte verlassen den Mac“. Gesichter verlassen ihn weiterhin nie.
  - Claude antwortet mit bis zu 15 Dingen, jeweils Name und Box in 0–1000. Die Antwort wird aufgeräumt: Boxen
    werden ins Bild geklemmt und sortiert, Einträge ohne Namen oder Fläche fallen weg.
  - Während Claude arbeitet, steht oben „Hintergrund wird erkannt …“ (`scene.naming`).
  - Der Aufruf zählt zum Sitzungsbudget und landet im Aufruf-Log (`track_id` 0).
  - Ohne Claude, ohne Budget oder bei einem Fehler bleiben die YOLOE-Labels, dann mit Hinweis. Eine Antwort für
    eine alte Szene (nach Taste R) wird verworfen.
  - Gemessen: 1,3–1,7 Cent, 6–8 s.
- **Hintergrund wird nie Fokus.** Eine Erkennung mit IoU ≥ 0,5 zu einer eingefrorenen Box gilt als Hintergrund.
  Das gilt für die YOLOE-Boxen der Kalibrierung und für Claudes Boxen. Hintergrund ist nie „gehalten“.
- **Gehalten heißt: Finger auf dem Objekt.** Mindestens 3 Gelenkpunkte der Hand liegen in der Objektbox (10 %
  Rand für Finger an der Kante). Das Objekt ist höchstens 8× so groß wie die Hand. Hände ohne Gelenkpunkte
  (YOLOE-Label „hand“) behalten die alte Überlappungsregel.
- **Geprüfte Hand.** Apple Vision (`VNDetectHumanHandPoseRequest`) läuft jetzt in voller Kamerabreite: 12 statt 7
  Gelenkpunkte an einem gehaltenen iPhone, weiter ca. 5 ms. Eine Hand zählt, wenn diese Bedingungen gelten:
  - Vision-Konfidenz ≥ 0,6,
  - mindestens 6 der 21 Gelenkpunkte sichtbar (Punkt-Konfidenz > 0,3),
  - in zwei Bildern hintereinander an fast derselben Stelle (IoU ≥ 0,2).

  Die YOLOE-Hände fallen dann weg.
- **Hand-Umrandung und Akzentfarben.** `tracks.hands` trägt pro bestätigter Hand eine Umrandung aus 16 Punkten.
  Sie folgt für 16 Richtungen jeweils dem äußersten Gelenkpunkt, plus 15 % der Handgröße. Der Browser zeichnet sie
  als weiche Kurve und glättet sie Punkt für Punkt.
  - Farben: Hand Cyan (46, 230, 255), gehaltenes Objekt Neongrün (124, 255, 90), Hintergrund Violett (185, 156, 255).
  - Auf der Karte sind Stufe, Balken und „Zeig mir bitte …“ grün, der Text bleibt weiß.
- **Ähnliche Kandidaten.** Nennt Claude die Kandidaten „von außen nicht unterscheidbar“, gibt aber eine
  unterscheidende Ansicht an, ist das Ergebnis nicht mehr endgültig. Beispiel: iPhone 14 oder 15 → Unterseite
  (Lightning oder USB-C) oder Vorderseite (Notch oder Dynamic Island). Die Karte fragt dann nach dieser Ansicht.
  Übereinstimmende Ansichten machen solche Kandidaten nicht „sicher“.

## 10. Nachtrag 2026-10-01: Schnappschuss aus dem Video statt Stillhalten

Dieser Nachtrag ersetzt in §2.4 Punkt 4 der Prüfung (`steady ≥ 0,6` seit 0,5 s), das 0,4-s-Fenster und den Hinweis
„Halt es bitte ruhig.“.

Nach dem dritten Live-Test gab es in einer ganzen Sitzung keinen einzigen Aufruf für das Handy, nur „Halt es bitte
ruhig“. Das Handy musste 0,5 s ununterbrochen ruhig sein und danach 0,4 s ohne einen Ausreißer bleiben. Jedes
unruhige oder unscharfe Bild setzte alles zurück, und ein Video aus der Hand ist nie so ruhig. An der Schärfe lag
es nicht: Ein Standbild des gehaltenen Handys hatte 451 bei einer Schwelle von 60, mit 9 px Bewegungsunschärfe noch 83.

- **Kandidaten.** Jedes Bild, das das ganze Objekt zeigt, ist ein Kandidat, auch ein unscharfes. Abgeschnittene,
  zu kleine oder vom Datenschutz gesperrte Bilder werden übersprungen. Was schon gesammelt ist, bleibt erhalten.
- **Schnappschuss.** 0,5 s nach dem ersten Kandidaten geht der schärfste Kandidat an Claude (Bewegung verwischt,
  also ist das schärfste Bild das ruhigste), sofern er die Schärfeschwelle erreicht. Nach 2 s geht der schärfste
  auch ohne Schwelle (`capture_patience_s`). Sein Gewicht im Belegbuch bleibt dann das kleinste (q = 0,5).
- **Hinweise** gibt es nur noch für das, was man ändern kann: „Bitte ganz ins Bild“, „Bitte etwas näher“,
  „Personen und Gesichter …“ und „tiefer“. Ruhe und Schärfe erscheinen nur noch in der Telemetrie („zu unscharf“).
- **Neue Ansichten** und das Aufruf-Limit bleiben unverändert: Ein neuer Aufruf kommt nur für eine Ansicht mit
  dHash-Abstand ≥ 14 zu allen gesendeten Ansichten, höchstens 4 pro Objekt.

## 11. Nachtrag 2026-10-01: Wiedererkennung nach neuer Tracking-Nummer, Abschluss

Im Live-Test bekam das iPhone in 8 Minuten 10 Tracking-Nummern. Jede Nummer begann die Analyse von vorn, das waren
13 Aufrufe für ein Handy.

- **Regel.** Ein frischer Fokus ohne Aufruf übernimmt Identität, gesendete Ansichten und Aufrufzähler des zuletzt
  identifizierten Fokus-Objekts, wenn alle vier Bedingungen gelten:
  - Das alte Objekt ist nicht mehr im Bild.
  - Es wurde vor höchstens 3 s zuletzt gehalten.
  - Die neue Box ist höchstens doppelt oder halb so groß.
  - Die Farbsignatur passt: HSV-Histogramm 8×4×4 innerhalb der Umrisslinie, Korrelation ≥ 0,5 (`oi/appearance.py`).
- **Farben sind nur die letzte Prüfung.** Gemessen an 17 echten Ausschnitten trennen sie Objekte nicht: dasselbe
  iPhone von vorn und hinten 0,04, Lampe gegen iPhone bis 0,85. Im Zweifel wird neu analysiert, statt einem
  Objekt einen fremden Namen zu geben.
- **Browser.** Ein laufender Aufruf meldet sein Ergebnis an die neue Nummer. `identity.previous_id` sagt dem Browser,
  dass es dasselbe Objekt ist:
  - Die Stimme wiederholt nichts.
  - Die Karte blendet nur bei einem neuen Namen neu ein.
  - Die Box gleitet weiter, statt neu einzurasten.
  - Die Stimme bricht nur noch ab, wenn ein anderes Objekt in den Fokus kommt, nicht bei einem kurzen Aussetzer.
- **Abschluss.** Jonas hat Teilprojekt 1 am 2026-10-01 im Live-Test mit iPhone, Hand und Raum abgenommen („mehr als
  zufrieden“). Die formale Checkliste (`docs/acceptance/sp1-checklist.md`) wurde auf seinen Wunsch nicht einzeln
  abgehakt. „Wissen mit Quellen“ ist gestrichen; Teilprojekt 2 wurde noch in derselben Nacht als Produkt-Steckbrief
  ohne Quellen gebaut (eigene Spec). Weiter geht es mit Teilprojekt 3 (3D).

## 12. Nachtrag 2026-10-01: T-Shirt, keine Hinweise, Stimme aus

Nach Jonas' Test mit Steckbrief: „Der nimmt immer mein T-Shirt als Objekt“, „das Reden können wir abschalten“,
„dieses ‚Bitte ganz ins Bild‘ ist Quatsch“.

- **T-Shirt.** Gemessen an seinem Bild erkennt YOLOE unten eine große Region aus T-Shirt, Schultern und Arm (Label
  „assemble“, 16 % des Bildes). Die Hand vor der Brust legt 7 Gelenkpunkte darauf, die Region ist nur 1,3-mal so
  groß wie die Hand und liegt nur zu 44 % in der Körperzone. Sie galt also als gehalten und schlug als größere
  Fläche sogar das iPhone.
  - Apples Personen-Segmentierung hilft nicht: Sie zählt das gehaltene iPhone zu 100 % zur Person.
  - Neue Regel (`privacy.worn`): Liegt etwas zu mindestens 25 % in einer Körperzone und reicht bis an den unteren
    Bildrand (innerhalb von 2 % der Bildhöhe), ist es getragen. Getragenes ist nie gehalten und nie Fokus. Etwas, das
    vor der Brust gehalten wird, endet über dem Rand und zählt weiter.
- **Keine Hinweise mehr.** Die Hinweise „Bitte ganz ins Bild“, „Bitte etwas näher“, „Personen und Gesichter …“ und
  „Halt es bitte tiefer …“ sind entfernt, ebenso das Feld `tracks.hint`. Ob das Objekt eine Box bekommt, ist die
  Rückmeldung. Der Prüfgrund erscheint nur noch in der Telemetrie (Taste D).
- **Stimme aus.** Die Stimme ist beim Start aus und wird mit Taste M eingeschaltet. Dann steht unten links
  „Stimme an (M)“.
