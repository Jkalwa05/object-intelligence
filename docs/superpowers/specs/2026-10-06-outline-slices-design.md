# Object Intelligence, Teilprojekt 8: Umriss in Scheiben und Kreuzprüfung

Stand: 2026-10-06 · Status: Design von Jonas freigegeben („20 Scheiben, direkt bauen“)

## 1. Ziel

Die Mineralwasserflasche „mineau Maria-Quelle, medium“ wurde ganz geschätzt:
- Logo und Schriftzug klebten seitlich am Etikett.
- Die Recherche fand nur zwei Händlerseiten und kein Foto, also gab es nichts zu vermessen.

Jonas: „Man sieht ja auf den Bildern im Web klar und deutlich, wie diese Flasche gebaut ist … die Flasche in Zehntel
aufteilen, und jedes dieser Zehntel sind Bounding Boxes, … von Bildern aus dem Web auch die gleichen Zehntel nehmen
und die dann gegenseitig validieren.“

Gemessen:
- Beide Händlerseiten nennen ihr Produktbild im JSON-LD.
- Es ist aber nur 250 × 219 px groß und zeigt einen ganzen Kasten mit blauen Deckeln.
- Netzbilder allein sind also unsicher. Das Kamerabild zeigt dagegen sicher den echten Gegenstand.

## 2. Entscheidungen (Jonas)

| Frage | Antwort |
|---|---|
| Design | freigegeben |
| Feinheit | 20 Scheiben |
| Vorgehen | Spec und Plan schreiben, dann ohne Stopp bauen |

## 3. Was neu ist

1. **Produktbilder der Seiten:**
   - Der Server liest auf bis zu 3 gefundenen Seiten (`sheet.sources`, nur erlaubte Adressen) die Bilder selbst aus:
     JSON-LD `image`, `og:image` und `twitter:image`.
   - Laden: `download.fetch_page`, nur `text/html` oder `application/xhtml+xml`, höchstens 3 MB, sonst dieselben
     Regeln wie `fetch`.
   - Die gefundenen Adressen werden erlaubt.
   - Zusammen mit den Fotos der Recherche sind es höchstens 4 Netzfotos.
   - Neue Fotos kommen als `PhotoRef(url, view=None)` ins Maßblatt. `view` darf jetzt `None` sein; die Ansicht
     bestimmt dann das Vermessen.
2. **Das Kamerabild vermisst immer mit:** Der Ausschnitt geht als letztes Bild ins Vermessen, beschriftet als „camera
   photo of the real object (everything else is grey; may be tilted or partly covered by a hand)“. Vermessen läuft
   jetzt, sobald ein Kamerabild oder ein Referenzbild da ist und die Gesamtgröße bekannt ist.
3. **Scheiben:**
   - Jede Ansicht `front`, `back`, `side-front-left` und `side-front-right` bekommt `slices`: 20 Einträge von oben
     nach unten.
   - Eintrag i ist der Streifen der Objektbox von i/20 bis (i+1)/20 ihrer Höhe.
   - Jeder Eintrag ist `[links, rechts]` (Anteile der Bildbreite, links < rechts, höchstens 2 % außerhalb der
     Objektbox) oder `null`, wenn der Rand verdeckt ist.
   - Draufsichten haben keine Scheiben.
4. **Umrechnung** mit Maßstab und Mitte der Ansicht wie bei den Teilen (Spec 7 §5.3):
   - Die Höhe des Streifens wird zu y in mm.
   - Die Ränder werden zu x (vorn, hinten gespiegelt) oder z (Seiten, Vorzeichen nach `side-front-left` oder
     `side-front-right`).
5. **Kreuzprüfung** pro Streifen und Achse, über alle Ansichten:
   - Ab 3 Quellen gelten der Median der Breiten und der Median der Mitten.
   - Eine Quelle zählt nur, wenn ihre Breite höchstens 8 % (mindestens 1,5 mm) vom Median abweicht und ihre Mitte
     höchstens 4 % der Größe auf dieser Achse.
   - Ergebnis ist der Mittelwert der übrigen.
   - Bei 2 Quellen, die nicht übereinstimmen, gilt die mit höherem Rang: Zeichnung vor Kamera vor Netzfoto.
   - Ergebnis: `ProfileBand(y, x, z, sources)`, mit `sources` = Zahl der Bilder, die übereinstimmen.
6. **CAD:** Das Profil geht als Text mit (`profile_text`). Regel im Prompt: Der Umriss folgt dem Profil; runde
   Produkte entstehen mit `rotate_extrude` aus diesen Radien.
7. **Prüfung:**
   - Der Server berechnet die Breite des gebauten Modells in jedem Streifen genau: aus den Ecken im Streifen und
     den Schnittpunkten der Dreieckskanten mit dessen Ober- und Unterkante.
   - Bezug ist die Mitte des ganzen Modells, wie bei den Teilen. Die Toleranz ist max(1,5 mm, 2 %).
   - Höchstens 10 Zeilen „Outline deviations (fix them)“, zum Beispiel
     `height 72 % (y 44.6…59.4 mm): x model -40.2…40.1, measured -33.0…33.1 mm (off by 7.2 mm)`.
8. **Manifest:** `profile: list[ProfileBand] = []`. Alte Manifeste bleiben gültig.
9. **Anzeige:**
   - Der Tag bekommt „· Umriss aus N Bildern“, mit N = größtes `sources`.
   - Fortschritt `measuring`: „Vermesse Teile und Umriss …“.
   - Fotos ohne Ansicht stehen unter QUELLEN als „Foto · combi.de“.

## 4. Kosten

Mehr Zahlen in der Antwort des Vermessens und ein Bild mehr: geschätzt +0,05–0,10 $ pro Modell. Die Grenze bleibt
1,60 $.

## 5. Sicherheit

- HTML wird nur gelesen (stdlib `html.parser`, `json`), nie ausgeführt.
- Adressen aus Seiten werden mit den bisherigen Regeln geladen und nur als Bild an Claude gegeben.

## 6. Tests

- **Rein:**
  - Bilder aus HTML: JSON-LD-Varianten, Meta-Tags, relative Adressen, `http` fällt weg, die Seite selbst fällt weg;
  - `fetch_page`;
  - Scheiben parsen;
  - Profil pro Ansicht;
  - Kreuzprüfung (Median, Ausreißer, Rang bei 2 Quellen);
  - Streifenbreite aus Dreiecken;
  - Abweichungen;
  - Texte.
- **Builder:** Kamerabild im Vermessen, Seitenbilder, Profil in CAD, Prüfung und Manifest.
- **Web:** Tag mit Umriss.
- **Echt:** Die Flasche wird aus dem gespeicherten Ausschnitt neu gebaut.
