# Object Intelligence, Teilprojekt 5: Politur & Portfolio

Stand: 2026-10-01 · Status: von Jonas über drei Fragen festgelegt; Umsetzung ohne weitere Rückfrage, während er weg
ist.

## 1. Umfang (Jonas)

| Teil | Entscheidung |
|---|---|
| UI-Stil | Edles Apple-Glas: weiches Milchglas, ruhige Animationen, Vision-Pro-Stil, wenig Effekte |
| Start | per Doppelklick, ohne Terminal-Befehl |
| Portfolio | README mit Architektur-Bild, Funktionsüberblick und Platzhaltern für Screenshots oder Video |
| Hologramm | ~~das Foto des Objekts als Oberfläche auf der passenden Seite~~ (wieder entfernt, siehe §2) |
| Hologramm | Vollbild mit allen Seiten, Längen und technischen Daten beschriftet |

Nicht gewählt wurde „Leiste merkt sich alles“: Nach dem Neuladen bleibt sie leer.

## 2. Foto aufs Hologramm (wieder entfernt)

> **Nachtrag 2026-10-01:** Jonas hat das Foto nach dem Bau wieder herausgenommen („das kann wieder raus“). Das
> Hologramm bleibt das reine Modell aus Claudes Grundformen; der Hologramm-Aufruf bekommt wieder die ursprüngliche
> Anweisung (aufrecht, Vorderseite zum Betrachter). Der Abschnitt bleibt als Protokoll der Entscheidung stehen.

- **Ausrichtung.** Der Hologramm-Aufruf dreht das Modell so, dass die Seite, die das Foto zeigt, zum Betrachter
  zeigt (+z), aufrecht wie im Foto.
- **Foto mitschicken.** Der Server legt den Ausschnitt (nur Objekt-Pixel) in den Hologramm-Daten ab, mit der Box
  des Objekts im Bild. Grau gilt als Hintergrund. Das Foto wird mit gespeichert, gehört also zum Modell im Cache.
- **Darstellung.** Der Browser macht den grauen Hintergrund durchsichtig, schneidet das Foto auf das Objekt zu und
  legt es als Fläche auf die +z-Seite der Modellbox. Von hinten ist es unsichtbar; dort bleibt das Hologramm.
- **Grenze.** Bei flachen Dingen passt es sehr gut, bei runden ist es ein Bild auf einer Seite.

## 3. Hologramm im Vollbild

- **Öffnen und schließen.** Der Knopf „⤢“ am Hologramm öffnet eine Vollbild-Ansicht über allem. Esc oder „✕“
  schließt sie. Sie hängt nicht am Eintrag: Legt Jonas das Objekt weg, klappt der Eintrag zu, das Vollbild bleibt
  offen (Zustand `fullscreen` im Store).
- **Links:** das große Modell. Drehen und Zoomen gehen mit Maus bzw. Trackpad.
  - Maßlinien für Breite, Höhe und Tiefe an der Modellbox, mit Endstrichen und Beschriftung in mm.
  - Jedes Teil trägt ein Namensschild: einen nummerierten Punkt auf dem Teil und daneben den Namen. Würden sich
    Schilder oder Punkte verdecken (etwa an einer Kamerainsel), rutscht der Name nach unten, und eine dünne Linie
    führt zurück zum Punkt. Der Punkt des Gehäuses sitzt an seiner Unterkante, damit er nicht unter Logo oder
    Display liegt.
- **Rechts:** alle technischen Daten.
  - Name, Stufe und Gesamtmaße;
  - alle Teile als nummerierte Liste mit Form und Maßen (z. B. „3 Hauptkamera · Zylinder ⌀ 13 × 2 mm“); zeigt die
    Maus auf eine Zeile, leuchtet das Schild am Modell auf;
  - die Steckbrief-Daten, Erscheinung, Startpreis und Wissenswertes.

## 4. Edles Apple-Glas

- **Farben:** die Systemfarben von Apple im Dunkelmodus.
  - Grün #30D158 für das gehaltene Objekt, Cyan #64D2FF für die Hand, Violett #BF5AF2 für den Hintergrund.
  - Schrift weiß, Nebentexte rgba(235, 235, 245, 0.6).
- **Glas:** dunkle, durchscheinende Flächen mit 30 px Unschärfe und kräftiger Sättigung, eine hauchdünne helle
  Kante, große Radien (16–20 px) und ein weicher Schatten.
- **Schrift:** SF Pro (System), ruhige Gewichte; kleine Überschriften in Kapitälchen mit wenig Sperrung.
- **Bewegung:** Einträge klappen weich auf und zu, Inhalte blenden sanft ein; sonst keine Effekte.
- **Kamera-Ebene:** dünnere, weichere Linien und abgerundete Ecken. Das Namensschild ist eine Glas-Kapsel mit
  Farbpunkt.
- **Seitenleiste:** ein leiser Verlauf als Grund; Einträge sind Glas-Karten, die Stufe ist eine farbige Kapsel
  (sicher und wahrscheinlich grün, unsicher gelb, nur Kategorie grau).

## 5. Start per Doppelklick

`Object Intelligence.command` im Projektordner: Ein Doppelklick im Finder startet Server und Browser. Das Skript sucht
`uv` auch dann, wenn es nicht im Pfad liegt.

## 6. Portfolio-README

Das README beschreibt:
- die Idee in einem Satz und die fünf Teilprojekte;
- die Architektur als Mermaid-Diagramm;
- die Grundsätze: ehrliche Unsicherheit, Datenschutz, gedeckelte Kosten;
- den Technik-Stack, Start, Tests;
- Bilder in `docs/media/`: das Vollbild-Hologramm und die Seitenleiste, gerendert aus echten, gespeicherten
  Claude-Antworten (DualShock 3) und ohne Kamerabild; ein Live-Video kann Jonas später ergänzen.
