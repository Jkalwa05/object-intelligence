# Object Intelligence, Teilprojekt 2: Produkt-Steckbrief

Stand: 2026-10-01 · Status: von Jonas über vier Fragen festgelegt; er hat die Umsetzung ohne weitere Rückfrage
freigegeben („klopp es dann durch und pushe es“).

Teilprojekt 2 ersetzt das gestrichene „Wissen mit Quellen“: Es gibt keine Quellenangaben. Die Ehrlichkeit bleibt
trotzdem: Die Werte stammen aus Claudes Wissen und sind sichtbar als „laut Claude“ markiert. Kennt Claude das genaue
Modell nicht, sagt das Panel das, statt zu raten.

## 1. Ziel und Erfolg

Ist ein Produkt mindestens „wahrscheinlich“ erkannt, erscheint neben der Info-Karte ein eigenes Glas-Panel
„Steckbrief“ mit vier Teilen: Kurzbeschreibung, 4–8 technische Daten, Erscheinung und Startpreis, 1–2 Punkte
Wissenswertes. Die Stimme liest die Kurzbeschreibung einmal vor.

**Erfolg:** Jonas hält sein iPhone 14 hoch. Nach der Erkennung („wahrscheinlich“ oder „sicher“) erscheint der Steckbrief
mit plausiblen Daten. Dasselbe Produkt kostet danach nie wieder einen Aufruf, auch nicht nach einem Neustart.

## 2. Entscheidungen (Jonas, 2026-10-01)

| Frage | Antwort |
|---|---|
| Inhalt | technische Daten, Kurzbeschreibung, Erscheinung & Preis, Wissenswertes |
| Wissen | Claudes eigenes Wissen, keine Websuche |
| Ab wann | ab „wahrscheinlich“ (auch „sicher“); nicht bei „unsicher“ oder „nur Kategorie“ |
| Anzeige | eigenes Panel neben der Karte, die Stimme liest die Kurzbeschreibung |

## 3. Ablauf

1. **Wann.** Nach jedem Identifikations-Ergebnis prüft `Belief.product()`, ob Stufe und Favorit passen: Stufe
   „wahrscheinlich“ oder „sicher“, der Favorit ist auf Modell- oder Varianten-Tiefe. Dann liefert sie
   (Produktname, Kategorie), sonst `None`. Auf Marken-Ebene („Apple-Smartphone“) gibt es keinen Steckbrief.
2. **Speicher.** Der `ProfileStore` (`oi/profiles.py`) wird von allen Verbindungen geteilt und liegt in
   `cache/profiles.json` (git-ignoriert).
   - Schlüssel sind Sprache und Produktname, klein geschrieben und getrimmt.
   - Bei einem Treffer kommt die `profile`-Nachricht sofort, ohne Aufruf. Jede Verbindung bekommt einen Steckbrief
     höchstens einmal.
3. **Aufruf.** Ohne Treffer geht zuerst `profile` mit `status: "loading"` raus, dann der Claude-Aufruf.
   - Nur Text geht raus, kein Bild: Produktname, Kategorie, Sprache.
   - Ergebnis: gespeichert, dann `status: "ready"` oder, wenn Claude das Modell nicht kennt, `"unknown"`.
   - Fehler: `status: "error"`, nichts wird gespeichert.
4. **Grenzen.** Ein Aufruf pro Produkt und Sprache; läuft schon einer, startet kein zweiter. Der Aufruf zählt zum
   Sitzungsbudget (150) und landet im Aufruf-Log (ohne Bilddatei). Ohne Claude oder ohne Budget gibt es keinen
   Steckbrief.

## 4. Der Claude-Aufruf

- Gleiches Modell wie die Identifikation (Standard Opus 5.5, effort low), strukturierte Ausgabe, gekürzt nach dem
  Parsen.
- Schema: `known` (bool), `summary` (1–2 Sätze), `facts` [{`label`, `value`}] (höchstens 8), `released` (Text oder
  null), `launch_price` (Text oder null), `trivia` (höchstens 2 Sätze).
- Prompt-Regeln:
  - nur Fakten zu genau diesem Modell, im Zweifel weglassen statt raten;
  - `known=false`, wenn Claude das Modell nicht sicher kennt;
  - Preis ist die UVP zum Marktstart in Deutschland in Euro, sonst mit Währung;
  - Sprache wie die Einstellung.
- Erwartet: ca. 1 Cent und 4–6 s pro Produkt.

## 5. Protokoll

Neue Server-Nachricht `profile` mit diesen Feldern:
- `product`, `status` (loading, ready, unknown, error),
- `summary`, `facts`, `released`, `launch_price`, `trivia`,
- `line`: was die Stimme sagt, also die Kurzbeschreibung; leer bei loading, unknown und error.

Der Browser speichert Steckbriefe nach Produktname. Er zeigt den zum Namen der Fokus-Identität, solange deren Stufe
„wahrscheinlich“ oder „sicher“ ist. Wechselt die Erkennung (iPhone 14 → 15), zeigt das Panel den Steckbrief zum
neuen Namen.

## 6. Oberfläche

- **Gruppe.** Karte und Panel bilden eine Gruppe, die der Platzierer gemeinsam bewegt. Das Panel liegt auf der Seite,
  die vom Objekt abgewandt ist; die Karte bleibt am Objekt, der Strich führt zu ihr.
- **Panel** (Glas, 300 px):
  - Kopf „STECKBRIEF“ mit der Pille „laut Claude“,
  - die Kurzbeschreibung,
  - eine Tabelle der Daten,
  - die Zeile „Erschienen … · Preis zum Start …“,
  - „Wissenswertes“ mit 1–2 Punkten.
- **Zustände:** Laden zeigt „Lade Steckbrief …“, unbekannt „Zu diesem Produkt weiß ich nichts Genaues.“, ein Fehler
  „Steckbrief gerade nicht verfügbar.“
- **Stimme:** Sie liest `line` einmal pro Objekt, nach dem Erkennungssatz, ohne ihn zu unterbrechen.

## 7. Fehler und Grenzen

- Claudes Wissen kann veraltet oder falsch sein, deshalb ist „laut Claude“ immer sichtbar.
- Eine kaputte Cache-Datei wird ignoriert (leerer Cache). Ein Schreibfehler hält den Steckbrief nur im Speicher.
- Für „nur Kategorie“ („rote Keramiktasse“) gibt es keinen Steckbrief.

## 8. Tests

- **Python:**
  - Anfrage: kein Bild; Name, Kategorie und Sprache im Text; Schema.
  - Parsen: Kürzen; unbekannt ergibt einen leeren Steckbrief.
  - Store: Speicher und Datei, kaputte Datei.
  - `Belief.product()`.
  - Pipeline: wahrscheinlich ergibt loading, dann ready; unsicher ergibt nichts; ein zweites Objekt gleichen Namens
    kommt aus dem Cache ohne Aufruf; ein Fehler ergibt error; das Budget gilt.
  - Protokoll-Beispiel.
- **Web:** Protokoll; Store (Steckbrief nach Name, nur bei wahrscheinlich/sicher sichtbar); Texte; Stimme.
- **Echt** (`-m claude`): Der Steckbrief für „Apple iPhone 14“ ist `known` und hat Daten.
