# Object Intelligence, Teilprojekt 4: Fragen & Sprache

Stand: 2026-10-01 · Status: von Jonas über sechs Fragen festgelegt; er hat die Umsetzung ohne weitere Rückfrage
freigegeben („bis ich zurück bin, sind Teilprojekt 4 und 5 fertig“).

## 1. Ziel

Jonas hält einen Gegenstand in die Kamera, drückt die Leertaste, fragt „Wie schwer ist das?“ und lässt los. Kurz
danach steht die Antwort im Eintrag des Objekts in der Seitenleiste und wird vorgelesen. Braucht die Frage etwas
Aktuelles („Was kostet das heute gebraucht?“), sucht Claude im Web und nennt die Quelle.

## 2. Entscheidungen (Jonas)

| Frage | Antwort |
|---|---|
| Start | Leertaste gedrückt halten, sprechen, loslassen |
| Erkennung | lokal mit Whisper (MLX, `whisper-large-v3-turbo`), die Stimme verlässt den Mac nie |
| Antworten | Claude entscheidet: meist aus seinem Wissen, bei Aktuellem mit Websuche und Quelle |
| Thema | das Objekt in der Hand; ohne Objekt in der Hand der zuletzt geöffnete Eintrag |
| Vorlesen | Antworten auf gesprochene Fragen werden vorgelesen; Erkennung und Steckbrief bleiben stumm (M) |

## 3. Ablauf

1. **Aufnahme (Browser).** Leertaste gedrückt (ohne Wiederholung): Das Mikrofon nimmt mit 16 kHz mono auf. Beim
   Loslassen geht die Aufnahme als `ask` an den Server: Int16-PCM in Base64, `rate`, dazu `track_id` und `name` des
   Ziel-Eintrags.
   - Unter 0,3 s wird verworfen, nach 30 s endet die Aufnahme von selbst.
   - Ziel ist das Objekt in der Hand, sonst der zuletzt geöffnete Eintrag, sonst der oberste.
   - Ohne Eintrag passiert nichts außer einem kurzen „Kein Objekt zum Fragen“.
2. **Erkennung (Server).** Whisper läuft in einem eigenen Thread, damit die Kamera weiterläuft. Es wird beim Start
   im Hintergrund vorgeladen; gemessen auf dem M5: 0,4 s für 3,7 s Sprache. Bei leerem Text gilt `empty` („Nichts
   verstanden“).
3. **Antwort (Claude).** Ein Aufruf mit diesem Kontext:
   - Name, Stufe und Kategorie des Objekts,
   - die Steckbrief-Daten, falls vorhanden,
   - der letzte Ausschnitt des Objekts (nur Objekt-Pixel),
   - der bisherige Frage-Antwort-Verlauf dieses Objekts.

   Werkzeug ist die Websuche (`web_search_20260209`, höchstens 2 Suchen). Claude antwortet in 1–3 kurzen,
   vorlesbaren Sätzen. Quellen kommen aus den Zitaten der Websuche (Titel und Link).
4. **Anzeige.** Neue Server-Nachricht `question`: `product` (Name des Eintrags), `qid`, `status` (transcribing,
   thinking, ready, empty, error), `question`, `answer`, `sources`, `line`. Der Eintrag zeigt unter „FRAGEN“ den
   Verlauf; die Stimme liest `line` vor, auch wenn sie sonst aus ist.
5. **Kosten.** Eine Antwort kostet ca. 1–2 Cent, mit Suche zusätzlich 1 Cent pro Suche und mehr Text. Antworten
   zählen zum Sitzungsbudget und landen im Aufruf-Log (`track_id` −4).

## 4. Datenschutz

- Die Sprache wird lokal erkannt, zu Claude geht nur der Text der Frage.
- Das Bild ist derselbe Objekt-Ausschnitt wie bei der Erkennung, nie das ganze Bild und nie ein Gesicht.
- Das Mikrofon ist nur offen, solange die Leertaste gedrückt ist.

## 5. Tests

- **Python:**
  - Audio dekodieren und umrechnen.
  - Erkennung mit einem Fake.
  - Anfrage: Websuche-Werkzeug, Bild, Verlauf und Steckbrief im Text.
  - Antwort parsen: Text und Quellen, Suchkosten.
  - Protokoll.
  - Pipeline: transcribing, thinking, ready; leer; Budget; Verlauf.
- **Web:** Umrechnen auf 16 kHz und Int16/Base64, Ziel-Eintrag, Fragen im Store.
- **Echt:** Whisper mit gesprochenem Deutsch (macOS-Stimme), ein echter Aufruf mit Websuche.
