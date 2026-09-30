# Abnahme Teilprojekt 1: Sehen & Identifizieren

Start: `uv run python -m oi`, Kamera im Browser erlauben, mit `D` die Telemetrie einblenden.
Jeden Gegenstand ganz normal in der Hand ins Bild halten (Stillhalten ist nicht nötig), dann langsam drehen. Wenn
das System um eine Ansicht bittet, diese zeigen.

## Kalibrierung (einmal am Anfang)

- Schärfewert in der Telemetrie, wenn du einen Gegenstand normal in der Hand hältst: ______
- Schärfewert, wenn du ihn schnell bewegst: ______
- Gewählte Schwelle `OI_MIN_SHARPNESS` in `.env` (Standard 60): ______

## Die fünf Gegenstände

| Gegenstand | Box folgt? | ID stabil? | Stufe und Name passend? | Bitte um Ansicht sinnvoll? | Zeit bis 1. Ergebnis | Kosten | Notizen |
|---|---|---|---|---|---|---|---|
| iPhone 14 | | | | | | | |
| P3-Controller | | | | | | | |
| Xbox-Controller | | | | | | | |
| Steinlampe | | | | | | | |
| Myprotein-Aminosäuren | | | | | | | |

Die Kosten stehen in der Telemetrie (Sitzungskosten vorher und nachher) und pro Aufruf in `runs/`.

## Richtwerte aus der Spec (keine harten Schranken)

- Das Kamerabild läuft flüssig (Video ≥ 30 fps).
- Der Detektor verarbeitet ≥ 8 Bilder/s auf dem kühlen Air.
- Das erste Ergebnis kommt ≤ 6 s, nachdem der Gegenstand im Bild ist. Der Test-Aufruf mit Opus 5.5 dauerte 9,6 s. Ist dir das zu
  langsam, trag `OI_MODEL=claude-sonnet-5-5` in `.env` ein.
- Ein Objekt kostet ≤ 10 Cent (der Test-Aufruf kostete 1,7 Cent).

## Ergebnis

Teilprojekt 1 abgenommen: ja / nein (Jonas, Datum: __________)
