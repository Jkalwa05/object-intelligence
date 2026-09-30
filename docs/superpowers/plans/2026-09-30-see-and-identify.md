# Sehen & Identifizieren – Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein lokales Programm, das Objekte im Mac-Kamerabild live mit stabilen IDs umrahmt, das gehaltene Objekt über
mehrere Ansichten mit Claude identifiziert und Stufe, Kandidaten und Indizien als Glas-HUD am Objekt zeigt und ausspricht.

**Architecture:** Das Python-Paket `oi` (FastAPI, WebSocket `/ws`) enthält die ganze KI: YOLOE-26 prompt-free mit
BoT-SORT auf MPS, Fokus-Wähler, Ansichten-Sammler, Auslöser, Claude-Identifikation und Indizien-Buch. Der Browser
(`web/`, Vite + React + TypeScript) zeigt das Kamerabild, schickt JPEGs und zeichnet das HUD. Die Entscheidungslogik ist
reine, getestete Python-Logik; Detektor und Claude sitzen hinter Protokollen mit Fakes.

**Tech Stack:** Python 3.12, uv, FastAPI, uvicorn, ultralytics (YOLOE), torch (MPS), OpenCV, NumPy, Pydantic 2,
anthropic SDK, pytest + pytest-asyncio; Vite, React, TypeScript, zustand, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-30-see-and-identify-design.md` (Verweise wie „§2.4“ zeigen dorthin)

## Global Constraints

- Python `>=3.12,<3.13` mit uv. Das Paket `oi/` liegt im Repo-Wurzelordner, es gibt keinen Build (`[tool.uv] package = false`, pytest `pythonpath = ["."]`).
- `cv2` kommt über `ultralytics` (opencv-python). **Kein** zusätzliches `opencv-python-headless`, sonst kollidieren zwei cv2-Pakete.
- Nur lokal auf `127.0.0.1`, Port `8766`; macOS Apple Silicon, `device="mps"`.
- Claude: Standard `claude-opus-5-5` mit `effort: "low"`; erlaubt sind `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-4-5`. An Claude geht nur der Ausschnitt des Fokus-Objekts (lange Kante ≤ 1024 px, JPEG-Qualität 90), nie das ganze Bild.
- Grenzen: 4 Aufrufe pro Objekt, 150 pro Sitzung, 2 gleichzeitig.
- Sprache `de` (Standard) oder `en`. Alle Zeilen für Karte und Stimme kommen vom Server (`oi/lines.py`).
- Werte im Code und Protokoll: Stufen `certain`, `likely`, `unsure`, `category_only` (= SICHER, WAHRSCHEINLICH, UNSICHER, NUR KATEGORIE der Spec); Status `analysing`, `ready`, `error`, `paused`; Modus `hybrid`, `lokal`.
- Alle Server-Nachrichten sind JSON mit `type`, `ts`, `seq`; Koordinaten auf 0–1 normalisiert; Contract-Version 1.
- Look „Glas“: Text `#fff` auf `rgba(22,22,28,.6)`, `backdrop-filter: blur(8px)` plus `-webkit-backdrop-filter` (Safari), Radius 10 px, Schrift `-apple-system`, einfarbig, kein Glow.
- Web-Laufzeit-Abhängigkeiten nur `react`, `react-dom`, `zustand`; Animationen per CSS und Canvas.
- `uv run pytest` läuft ohne Modell und ohne Netz; die Marker `model` und `claude` laufen nur gezielt. Keine aufgenommenen Videos.
- Jede Commit-Nachricht endet mit der Zeile `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Objekt am Bildrand oder halb im Bild:** Es gibt keinen Claude-Aufruf, und nach 2 s kommt „Bitte ganz ins Bild.“ (Task 8: `test_edge_object_gets_full_view_hint`).
2. **Zwei ähnliche Objekte gleichzeitig**, etwa zwei Controller: Der Fokus flackert nicht, und eine Antwort landet nie beim falschen Track (Task 8: `test_two_similar_objects_do_not_flicker`, `test_result_stays_with_original_track_after_focus_switch`).
3. **Dürftige Claude-Antworten** (keine Kandidaten, ein einzelner Kandidat mit „low“, keine `next_view`, mehr als 4 Kandidaten): Es gibt keine Ausnahme, sondern eine ehrliche Zeile (Task 5: `test_single_candidate_low_self_assessment`, `test_category_only`; Task 6: `test_truncates_overlong_lists`).
4. **Kaputte Nachrichten vom Browser** (zu kurzer Header, Müll-JSON, kein JPEG, unbekannter `type`): Sie werden ignoriert, die Verbindung bleibt offen (Task 2: `test_parse_rejects_garbage`; Task 9: `test_malformed_messages_are_ignored`).
5. **Neu laden oder zweiter Tab:** Die neue Verbindung ersetzt die alte, der Tracker startet frisch, und laufende Aufrufe der alten Verbindung werden abgebrochen (Task 9: `test_second_connection_replaces_first`).

---

### Task 1: Projektgerüst, Konfiguration, Contracts

**Files:**
- Create: `pyproject.toml`, `.python-version`, `oi/__init__.py`, `oi/config.py`, `oi/contracts.py`, `tests/test_config.py`, `tests/test_contracts.py`, `tests/fixtures/protocol-examples.json`

**Interfaces:**
- Produces `oi/config.py`: `Lang = Literal["de", "en"]`; `@dataclass(frozen=True) class Settings` mit den Feldern unten; `Settings.from_env(env: Mapping[str, str] | None = None) -> Settings` (`None` bedeutet `os.environ`). `from_env` wirft `ValueError`, wenn die Sprache nicht `de`/`en` ist oder das Modell nicht in `prices` steht.
- Produces `oi/contracts.py`: `CONTRACT_VERSION = 1`; `Level`, `Depth` (StrEnum); `Status = Literal["analysing","ready","error","paused"]`; Pydantic-Modelle (`extra="forbid"`) `Candidate`, `NextView`, `Observation`, `Track`, `RankedCandidate`, `BeliefState` mit `BeliefState.empty(display_name: str) -> BeliefState`, `FrameHeader`, `WireTrack` mit `WireTrack.from_track(t: Track, w: int, h: int) -> WireTrack`, `TracksMsg`, `IdentityMsg` mit `IdentityMsg.from_belief(track_id: int, status: Status, b: BeliefState) -> IdentityMsg`, `TelemetryMsg`, `NoticeMsg`, `ServerMsg` (Union, Diskriminator `type`), `FocusMsg`, `RecheckMsg`, `ClientMsg`; `parse_client_message(text: str) -> ClientMsg | None`; `protocol_examples() -> list[dict]`.

`Settings`-Felder (Name = Standardwert):

```text
model="claude-opus-5-5"  effort="low"  language="de"
max_calls_object=4  max_calls_session=150  max_concurrent_calls=2
detector="yoloe-26s-seg-pf.pt"  detector_fallback="yoloe-11s-seg-pf.pt"  imgsz=640  conf=0.25  device="mps"
focus_weights=(0.30, 0.20, 0.25, 0.15, 0.10)          # size, center, hand, steady, new
focus_switch_margin=0.15  focus_switch_hold_s=0.5  min_area=0.01  max_area=0.60  min_age_frames=3
excluded_labels=("person","man","woman","boy","girl","child","baby","face","head","hand","arm","finger")
hand_labels=("hand",)
min_sharpness=60.0  dhash_min_distance=14  aspect_change=0.25  crop_margin=0.12  crop_long_edge=1024
crop_jpeg_quality=90  min_box_side_px=120  edge_margin=0.01  steady_min=0.6  steady_hold_s=0.5
best_of_window_s=0.4  hint_after_s=2.0  claude_timeout_s=20.0  log_calls=True  runs_dir=Path("runs")  port=8766
prices={"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-4-5": (1.0, 5.0)}  # $ je 1 Mio. Tokens (ein, aus)
```

Umgebungsvariablen (§6): `OI_MODEL`, `OI_EFFORT`, `OI_LANGUAGE`, `OI_MAX_CALLS_OBJECT`, `OI_MAX_CALLS_SESSION`,
`OI_DETECTOR`, `OI_MIN_SHARPNESS`, `OI_LOG_CALLS` (`0`/`1`), `OI_PORT`.

Modell-Festlegungen, Felder wie in §2.2, §2.5, §2.6 und §2.7:
- `Level`: `certain|likely|unsure|category_only`. `Depth`: `category|brand|model|variant`.
- `Candidate`: `brand`, `model_name`, `variant` jeweils `str | None`; `depth`; `evidence: list[str]` (max 5).
- `Observation`: `candidates` max 4, `readable_text` max 10, `self_assessment: Literal["high","medium","low"]`.
- `Track`: `box: tuple[float, float, float, float]` und `polygon: list[tuple[float, float]]`, beide in Pixeln des vollen Bildes.
- `RankedCandidate(name: str, share: float)`.
- `BeliefState`: `level: Level | None`, `display_name`, `candidates: list[RankedCandidate]`, `evidence`, `view_request: NextView | None`, `final`, `calls_used`, `line`.
- Server-Nachrichten: `ts: float = 0.0` und `seq: int = 0`; der Server stempelt beides.
- `IdentityMsg`: `track_id`, `status` und die `BeliefState`-Felder flach.
- `TelemetryMsg`: zusätzlich zu §2.7 das Feld `language: Lang`, weil der Browser die Sprache für seine festen Texte braucht.

- [ ] **Step 1: Gerüst anlegen.**
  - `pyproject.toml`: Name `object-intelligence`, `requires-python = ">=3.12,<3.13"`.
  - Abhängigkeiten: `fastapi`, `uvicorn[standard]`, `ultralytics`, `torch`, `numpy`, `pydantic>=2`, `anthropic`; Gruppe `dev`: `pytest`, `pytest-asyncio`, `httpx`.
  - `[tool.uv] package = false`.
  - `[tool.pytest.ini_options]`: `pythonpath = ["."]`, `asyncio_mode = "auto"`, Marker `model` („lädt YOLOE-Gewichte“) und `claude` („echter API-Aufruf, ca. 2 Cent“), `addopts = "-m 'not model and not claude'"`.
  - `.python-version` mit `3.12`.

  Danach `uv sync`. Erwartet: Das Environment wird ohne Fehler erstellt.

- [ ] **Step 2: Failing tests schreiben**

```python
# tests/test_config.py
def test_defaults_match_spec():
    s = Settings()
    assert (s.model, s.effort, s.language) == ("claude-opus-5-5", "low", "de")
    assert (s.max_calls_object, s.max_calls_session, s.max_concurrent_calls) == (4, 150, 2)
    assert (s.min_sharpness, s.dhash_min_distance, s.crop_long_edge, s.port) == (60.0, 14, 1024, 8766)
    assert s.focus_weights == (0.30, 0.20, 0.25, 0.15, 0.10)

def test_env_overrides():
    s = Settings.from_env({"OI_MODEL": "claude-sonnet-5-5", "OI_MAX_CALLS_SESSION": "10", "OI_MIN_SHARPNESS": "80",
                           "OI_LOG_CALLS": "0", "OI_LANGUAGE": "en", "OI_PORT": "9000"})
    assert (s.model, s.max_calls_session, s.min_sharpness, s.log_calls, s.language, s.port) == \
        ("claude-sonnet-5-5", 10, 80.0, False, "en", 9000)

@pytest.mark.parametrize("env", [{"OI_LANGUAGE": "fr"}, {"OI_MODEL": "gpt-5"}])
def test_invalid_values_rejected(env):
    with pytest.raises(ValueError):
        Settings.from_env(env)

# tests/test_contracts.py
def test_observation_limits():            # 5 Kandidaten -> pydantic.ValidationError
def test_wire_track_is_normalized():      # box (128,72,640,360) bei 1280x720 -> (0.1,0.1,0.5,0.5); Polygonpunkt (128,72) -> (0.1,0.1)
def test_server_message_dump_has_type():  # TracksMsg(...).model_dump(mode="json") hat type "tracks", seq 0
def test_parse_client_message():          # '{"type":"focus","track_id":3}' -> FocusMsg(3); track_id null -> None-Pin;
                                          # '{"type":"nope"}' -> None; 'kaputt' -> None
def test_protocol_examples_fixture_is_current():
    assert json.loads(Path("tests/fixtures/protocol-examples.json").read_text()) == protocol_examples()
```

- [ ] **Step 3: Tests laufen lassen.** `uv run pytest -v`. Erwartet: FAIL mit `ModuleNotFoundError: oi.config`.
- [ ] **Step 4: `oi/config.py` und `oi/contracts.py` gemäß Interfaces implementieren.** `protocol_examples()` liefert je ein Beispiel für `TracksMsg` (ein Track), `IdentityMsg` (Status `ready`, Stufe `likely`), `TelemetryMsg` und `NoticeMsg`, jeweils als `model_dump(mode="json")`. Die Fixture erzeugt man mit `uv run python -c "import json; from oi.contracts import protocol_examples; print(json.dumps(protocol_examples(), indent=2, ensure_ascii=False))" > tests/fixtures/protocol-examples.json`.
- [ ] **Step 5: Tests laufen lassen.** `uv run pytest -v`. Erwartet: alle PASS.
- [ ] **Step 6: Commit.** `feat: project skeleton, settings and shared contracts`

---

### Task 2: Bild-Empfang, Telemetrie, Nachvollzieh-Protokoll

**Files:**
- Create: `oi/ingest.py`, `oi/telemetry.py`, `tests/test_ingest.py`, `tests/test_telemetry.py`

**Interfaces:**
- Consumes: `FrameHeader`, `TelemetryMsg`, `Settings`.
- Produces `oi/ingest.py`:
  - `class FrameFormatError(ValueError)`
  - `RawFrame = tuple[FrameHeader, bytes]`
  - `parse_frame_message(data: bytes) -> RawFrame`. Aufbau wie in §2.1; ein Header über 4096 Byte ist ein Fehler.
  - `@dataclass(frozen=True) class Frame(frame_id: int, t: float, image: np.ndarray)`, wobei `t = t_capture_ms / 1000` und das Bild BGR ist.
  - `decode_frame(raw: RawFrame) -> Frame` wirft `FrameFormatError`, wenn `cv2.imdecode` `None` liefert.
  - `class FrameSlot` mit `put(raw: RawFrame) -> None`, `async get() -> RawFrame` und `dropped: int`.
- Produces `oi/telemetry.py`:
  - `class Telemetry(settings, mode: Literal["hybrid","lokal"], model_label: str, clock: Callable[[], float] = time.monotonic)` mit `frame_processed(det_ms: float)`, `set_sharpness(v: float | None)`, `call_started()`, `call_finished(latency_s: float, cost_usd: float)`, `call_failed()`, der Eigenschaft `calls_session: int` und `snapshot(frames_dropped: int) -> TelemetryMsg`. `fps_processed` = Bilder der letzten 2,0 s geteilt durch 2,0; `det_ms` = Mittel der letzten 30 Werte, 0,0 wenn es keine gibt; `id_ms_last` = Latenz des letzten erfolgreichen Aufrufs in ms.
  - `@dataclass class CallRecord(n: int, track_id: int, jpeg: bytes, request_text: str, observation: dict | None, error: str | None, input_tokens: int, output_tokens: int, cost_usd: float, latency_s: float, model: str, level_after: str | None)`
  - `class CallLog(runs_dir: Path, enabled: bool, now: Callable[[], datetime] = datetime.now)` mit `write(r: CallRecord) -> None`. Der Sitzungsordner `runs_dir/<%Y-%m-%d_%H-%M-%S>` entsteht beim ersten `write`. Dateien: `{n:03d}_track{track_id}.jpg` und `.json`; die JSON-Datei enthält alle Felder außer `jpeg`.

- [ ] **Step 1: Failing tests schreiben**

```python
def frame_bytes(header: dict, jpeg: bytes) -> bytes:
    h = json.dumps(header).encode()
    return struct.pack(">I", len(h)) + h + jpeg

def test_parse_roundtrip():
    hdr, jpeg = parse_frame_message(frame_bytes({"frame_id": 7, "t_capture_ms": 1500.0, "w": 1280, "h": 720}, b"\xff\xd8x"))
    assert (hdr.frame_id, jpeg) == (7, b"\xff\xd8x")

@pytest.mark.parametrize("data", [b"\x00\x00", struct.pack(">I", 9999) + b"{}", struct.pack(">I", 5) + b"nojs!x",
                                  frame_bytes({"frame_id": "a"}, b"")])
def test_parse_rejects_garbage(data):
    with pytest.raises(FrameFormatError):
        parse_frame_message(data)

def test_decode_frame():             # echtes JPEG (cv2.imencode von np.zeros((720,1280,3),np.uint8)) -> shape (720,1280,3), t == 1.5
def test_decode_rejects_non_jpeg():  # b"notajpeg" -> FrameFormatError
async def test_slot_latest_frame_wins():   # put(a); put(b); await get() is b; dropped == 1
async def test_slot_get_waits_for_put():   # get-Task ist nach sleep(0) nicht fertig; nach put(a) liefert er a
def test_telemetry_snapshot():
    # Fake-Uhr 0.0..1.9 in 0.1-Schritten, je frame_processed(10.0); call_started() x2;
    # call_finished(2.5, 0.02); call_finished(3.0, 0.03)
    snap = tel.snapshot(frames_dropped=4)
    assert snap.fps_processed == pytest.approx(10.0) and snap.det_ms == 10.0
    assert (snap.calls_session, snap.id_ms_last, snap.frames_dropped) == (2, 3000.0, 4)
    assert snap.cost_session_usd == pytest.approx(0.05)
def test_call_log_writes_files(tmp_path):  # genau ein Sitzungsordner mit 001_track5.jpg (Bytes gleich) und 001_track5.json
def test_call_log_disabled(tmp_path):      # enabled=False -> tmp_path bleibt leer
```

- [ ] **Step 2: Tests laufen lassen.** `uv run pytest tests/test_ingest.py tests/test_telemetry.py -v`. Erwartet: FAIL (Import).
- [ ] **Step 3: `oi/ingest.py` und `oi/telemetry.py` gemäß Interfaces implementieren.** `FrameSlot` nutzt ein `asyncio.Event`, und `put` überschreibt ein noch nicht abgeholtes Bild (`dropped += 1`).
- [ ] **Step 4: Tests laufen lassen.** Befehl wie in Step 2. Erwartet: PASS.
- [ ] **Step 5: Commit.** `feat: frame ingest, telemetry and call log`

---

### Task 3: Ansichten-Sammler (Qualität, Fingerabdruck, bestes Bild)

**Files:**
- Create: `oi/views.py`, `tests/helpers.py`, `tests/test_views.py`

**Interfaces:**
- Consumes: `Settings`, `Track`.
- Produces `oi/views.py`:
  - `sharpness(gray: np.ndarray) -> float`: Varianz von `cv2.Laplacian` nach Skalierung auf 256 px Breite.
  - `dhash(gray: np.ndarray) -> int`: 64 Bit, auf 9×8 skaliert, Vergleich waagerechter Nachbarn.
  - `hamming(a: int, b: int) -> int`
  - `crop_box(image, box, margin) -> np.ndarray`: 12 % Rand pro Seite, auf das Bild begrenzt.
  - `encode_for_claude(crop, long_edge: int, quality: int) -> bytes`: `INTER_AREA`, nur verkleinern.
  - `quality_q(s: float, min_sharpness: float) -> float`: `clamp(0.5 + 0.5 * (s - thr) / (4 * thr), 0.5, 1.0)`.
  - `GateFailure = Literal["cut", "small", "blurry", "unsteady"]`
  - `@dataclass class ReadyCrop(jpeg: bytes, sharpness: float, q: float, dhash: int, aspect: float, view_id: int, is_new_view: bool)`
  - `@dataclass class ViewResult(ready: ReadyCrop | None, failing: GateFailure | None, hint: GateFailure | None, sharpness: float | None)`
  - `class ViewCollector(settings)` mit `offer(track: Track, image: np.ndarray, steady: float, now: float) -> ViewResult`, `mark_sent(c: ReadyCrop) -> None` und `force_next() -> None`.
- Produces `tests/helpers.py`:
  - `sharp_image(size=(720, 1280), boxes=()) -> np.ndarray`: mittelgrau, Schachbrett mit 8-px-Feldern in jeder Box.
  - `blurry_image(...)`: wie oben, aber in den Boxen `GaussianBlur` mit Sigma 6.
  - `gradient_image()`: waagerechter Grauverlauf 256×256.
  - `trk(id, box, label="cup", score=0.9, age=10, first_seen=0.0) -> Track`

**Regeln für `offer`**, in dieser Reihenfolge; der erste Fehler ist `failing` (§2.4):
1. Abstand zu einem Bildrand < `edge_margin` · Bildbreite → `"cut"`.
2. Kürzere Box-Seite < 120 px → `"small"`.
3. Schärfe < `min_sharpness` → `"blurry"`.
4. `steady` war nicht seit ≥ `steady_hold_s` durchgehend ≥ `steady_min` → `"unsteady"`.

`hint` = der aktuelle Grund, wenn die Prüfung seit ≥ `hint_after_s` ununterbrochen scheitert, sonst `None`.

**Fenster-Algorithmus:**
- Der Sammler ist anfangs „scharf geschaltet“. Besteht die Prüfung, öffnet er ein Fenster und sammelt Ausschnitte.
- Nach `best_of_window_s` gibt er den schärfsten als `ReadyCrop` frei und schaltet sich ab.
- Wieder scharf wird er, wenn die Prüfung scheitert, wenn ein Ausschnitt ≥ `dhash_min_distance` vom zuletzt freigegebenen entfernt ist, oder durch `force_next()`.

`is_new_view` wird gegen die mit `mark_sent` gemerkten Ansichten geprüft: neu, wenn es keine gibt oder für *jede*
gilt „Hamming ≥ 14 oder Seitenverhältnis weicht ≥ 25 % ab“. Neue Ansichten bekommen fortlaufende `view_id`s (1, 2, …),
andere die ID der ähnlichsten gesendeten Ansicht.

- [ ] **Step 1: Failing tests schreiben**

```python
def test_sharpness_separates_sharp_from_blurred():   # sharpness(sharp) > 60 > sharpness(blurred)
def test_dhash_identical_zero_mirrored_far():        # hamming(dhash(g), dhash(g)) == 0; hamming(dhash(g), dhash(np.fliplr(g))) >= 14
def test_crop_margin_and_clamp():                    # box (100,100,200,200) -> shape (124,124); box (0,0,50,50) beginnt bei 0
def test_encode_limits_long_edge():                  # 2000x1000-Ausschnitt -> dekodierte lange Kante == 1024
@pytest.mark.parametrize("box,steady,reason", [((2,100,300,400),1.0,"cut"), ((500,300,560,360),1.0,"small")])
def test_gate_reasons(box, steady, reason):          # offer(...).failing == reason
def test_gate_blurry_and_unsteady():                 # unscharfes Bild -> "blurry"; scharf, aber steady=0.3 -> "unsteady"
def test_releases_sharpest_once_after_hold_and_window():
    # scharfe Angebote alle 0.1 s ab t=0 mit steady=1: bis t=0.8 kein ready; bei t in [0.9, 1.0] genau ein ready,
    # dessen sharpness das Maximum im Fenster ist; weitere Angebote derselben Ansicht bis t=2.0 -> kein weiteres ready
def test_new_view_after_turning():
    # mark_sent(erstes ready); gespiegeltes Bild anbieten -> ready.is_new_view True, view_id 2;
    # danach force_next() und wieder das Original -> is_new_view False, view_id 1
def test_hint_after_two_seconds():                   # unscharf ab t=0: hint None bei t=1.9, "blurry" bei t=2.0
def test_quality_q_mapping():                        # quality_q(60,60)==0.5; quality_q(300,60)==1.0; quality_q(1000,60)==1.0
```

- [ ] **Step 2: Tests laufen lassen.** `uv run pytest tests/test_views.py -v`. Erwartet: FAIL.
- [ ] **Step 3: `oi/views.py` und `tests/helpers.py` gemäß Interfaces und Regeln implementieren.**
- [ ] **Step 4: Tests laufen lassen.** Befehl wie in Step 2. Erwartet: PASS.
- [ ] **Step 5: Commit.** `feat: view collector with quality gate and view fingerprints`

---

### Task 4: Fokus-Wähler

**Files:**
- Create: `oi/focus.py`, `tests/test_focus.py`

**Interfaces:**
- Consumes: `Settings`, `Track`, `tests/helpers.trk`.
- Produces:
  - `split_tracks(tracks: list[Track], s: Settings) -> tuple[list[Track], list[Track]]` liefert `(visible, hands)`. `visible` ohne Labels aus `excluded_labels`, `hands` mit Labels aus `hand_labels`; Vergleich jeweils kleingeschrieben.
  - `class FocusSelector(settings)` mit `update(visible, hands, frame_w: int, frame_h: int, now: float) -> int | None`, `pin(track_id: int | None) -> None` und `steady(track_id: int) -> float` (0,0 bei unbekanntem Track).

Bewertung und Hysterese stehen genau in §2.3. Für die Geschwindigkeit gilt: Verschiebung der Boxmitte in
Bilddiagonalen pro Sekunde zwischen zwei Aufrufen, geglättet mit EMA α = 0,5. Beim ersten Auftreten ist sie 0, `steady`
also 1. Fokusfähig sind nur Tracks mit Fläche zwischen `min_area` und `max_area` und `age_frames >= min_age_frames`.
Ein angehefteter Track bleibt Fokus, solange er in `visible` vorkommt, danach gilt automatisch wieder die Bewertung.

- [ ] **Step 1: Failing tests schreiben**

```python
def test_split_excludes_people_and_collects_hands():   # person/hand/cup -> visible [cup], hands [hand]
def test_held_object_beats_larger_background_object():
    # cup 5 % Fläche, mittig, überlappt Hand vs. Monitor 30 % am Rand -> nach 2 Updates Fokus == cup.id
def test_ignores_too_small_too_large_and_too_young():  # 0,5 % / 70 % / age 2 -> None
def test_hysteresis_needs_margin_for_half_second():
    # Fokus A; B liegt 0,2 höher: bei +0,4 s noch A, bei +0,5 s B; fällt der Vorsprung zwischendurch
    # unter 0,15, beginnt die Zeit von vorn
def test_focus_lost_switches_immediately():            # A verschwindet -> sofort der beste Rest
def test_pin_overrides_until_track_disappears():       # pin(B) -> B trotz schlechterem Score; B weg -> automatisch; pin(None) löst
def test_steady_from_velocity():                       # ruhend -> steady 1.0; 10 Updates mit 0,5 Diagonalen/s -> steady < 0.1
```

- [ ] **Step 2: Tests laufen lassen.** `uv run pytest tests/test_focus.py -v`. Erwartet: FAIL.
- [ ] **Step 3: `oi/focus.py` gemäß Interfaces und §2.3 implementieren.**
- [ ] **Step 4: Tests laufen lassen.** Befehl wie in Step 2. Erwartet: PASS.
- [ ] **Step 5: Commit.** `feat: focus selector with hysteresis and pinning`

---

### Task 5: Indizien-Buch, Zeilen, Auslöser

**Files:**
- Create: `oi/lines.py`, `oi/belief.py`, `oi/trigger.py`, `tests/test_lines.py`, `tests/test_belief.py`, `tests/test_trigger.py`
- Modify: `tests/helpers.py` (neu: `cand(...)`, `obs(...)`)

**Interfaces:**
- Consumes: `Observation`, `Candidate`, `NextView`, `Level`, `BeliefState`, `RankedCandidate`, `Lang`, `Settings`, `ReadyCrop`, `GateFailure`.
- Produces `oi/lines.py`:
  - `display_name(c: Candidate, category: str, description: str | None, lang: Lang) -> str`
  - `line_certain(name, lang)`, `line_likely(name, lang)`, `line_category(description, lang)`
  - `line_unsure(a: str, b: str | None, view: str | None, distinguishable: bool, lang) -> str`
  - `hint_line(reason: GateFailure, lang)`, `error_line(lang)`, `paused_line(lang)`
  - `notice_text(key: Literal["no_key", "model_missing", "unreachable"], lang, **kw) -> str`
- Produces `oi/belief.py`: `class Belief(language: Lang)` mit `add(obs: Observation, view_id: int, q: float) -> None`, `snapshot(calls_used: int) -> BeliefState`, der Eigenschaft `is_final: bool` und der Eigenschaft `observations: list[Observation]`.
- Produces `oi/trigger.py`: `class Decision(StrEnum)` mit `CALL`, `WAIT`, `OBJECT_CAP`, `SESSION_CAP`; `@dataclass(frozen=True) class TriggerInput(is_focus: bool, ready: ReadyCrop | None, final: bool, in_flight_track: bool, in_flight_total: int, calls_track: int, calls_session: int, forced: bool)`; `decide(i: TriggerInput, s: Settings) -> Decision`.
- Produces `tests/helpers.py`: `cand(brand, model, depth="model", variant=None, ev=())` und `obs(*cands, readable=(), dist=True, view=None, reason="", sa="medium", cat="Smartphone", desc=None)`.

**Anzeige-Name** (§2.6):
- `model`: „{brand} {model_name}“, ohne `brand` nur der Modellname.
- `variant`: „{brand} {model_name}, {variant}“.
- `brand`: auf Deutsch „{brand}-{Kategorie}“, auf Englisch „{brand} {category}“.
- `category`: die Beschreibung, sonst die Kategorie, jeweils mit großem Anfangsbuchstaben.

**Zeilen, exakte Texte:**

| Funktion | de | en |
|---|---|---|
| certain | `Das ist {name}.` | `This is {name}.` |
| likely | `Das ist wahrscheinlich {name}.` | `This is probably {name}.` |
| unsure, Basis | `{a} oder {b}?`, ohne b: `Vielleicht {a}?` | `{a} or {b}?`, ohne b: `Maybe {a}?` |
| unsure, Zusatz bei view | ` Zeig mir bitte {view}.` | ` Please show me {view}.` |
| unsure, nicht unterscheidbar (mit b) | `{a} oder {b}, von außen kaum zu unterscheiden.` | `{a} or {b}, hard to tell apart from the outside.` |
| category | `{Beschreibung}, ein bestimmtes Produkt erkenne ich nicht.` | `{Description}, I can't recognize a specific product.` |
| hint cut / small / blurry+unsteady | `Bitte ganz ins Bild.` / `Bitte etwas näher.` / `Halt es bitte ruhig.` | `Please bring it fully into view.` / `Please come a bit closer.` / `Please hold it still.` |
| error | `Identifikation gerade nicht möglich.` | `Identification is not available right now.` |
| paused | `Kostenbremse erreicht, Identifikation pausiert.` | `Cost limit reached, identification paused.` |
| no_key | `Kein API-Key: nur lokale Erkennung.` | `No API key: local detection only.` |
| model_missing | `Modell {model} nicht gefunden: nur lokale Erkennung.` | `Model {model} not found: local detection only.` |
| unreachable | `Claude gerade nicht erreichbar.` | `Claude is not reachable right now.` |

**Belief:** Punkte, Anteile, Beweisstück, Stufen und „final“ genau wie in §2.6. Zusätzlich gilt:
- Kandidaten-Schlüssel: `" ".join(f"{brand or ''} {model_name or ''}".lower().split())`. Ist er leer, `"category:" + category`.
- Rangfolge: mehr Punkte zuerst, bei Gleichstand der früher aufgetauchte.
- `view_request` ist die `next_view` der letzten Beobachtung, aber nur bei `unsure` und nicht final.
- `evidence`: Indizien des Top-Kandidaten über alle Beobachtungen, in der Reihenfolge des Auftauchens, höchstens 6.
- `candidates`: die Top 3 mit Anteil.
- `line`: die passende Zeile oben; bei `level=None` leer.
- `unsure`, `a`/`b`: die Anzeige-Namen von Platz 1 und 2. Die Unterscheidbarkeit kommt aus der letzten Beobachtung.

**Auslöser, Reihenfolge:**
1. Nicht Fokus oder kein `ready` → `WAIT`.
2. Aufruf für diesen Track läuft oder `in_flight_total >= max_concurrent_calls` → `WAIT`.
3. `calls_session >= max_calls_session` → `SESSION_CAP`.
4. `forced` → `CALL`.
5. `final` → `WAIT`.
6. `calls_track >= max_calls_object` → `OBJECT_CAP`.
7. `calls_track == 0` oder `ready.is_new_view` → `CALL`.
8. Sonst `WAIT`.

- [ ] **Step 1: Failing tests schreiben**

```python
# tests/test_belief.py  (i14 = cand("Apple","iPhone 14"), i13 = cand("Apple","iPhone 13"))
def test_no_observation():                        # snapshot(0).level is None and .line == ""
def test_single_view_is_at_most_likely():         # add(obs(i14, i13), 1, 1.0) -> likely, "Das ist wahrscheinlich Apple iPhone 14."
def test_two_agreeing_views_make_certain():       # Ansichten 1 und 2, q=1 -> certain, "Das ist Apple iPhone 14.", is_final
def test_same_view_twice_is_not_two_views():      # zweimal view_id 1 -> likely
def test_close_race_is_unsure_with_view_request():
    # obs(i14,i13), obs(i13,i14, view="die Unterseite", reason="Lightning oder USB-C") in Ansichten 1 und 2 -> unsure;
    # view_request.view == "die Unterseite"; line == "Apple iPhone 14 oder Apple iPhone 13? Zeig mir bitte die Unterseite."
def test_iphone_example_ends_indistinguishable():
    # obs(i14,i13,cand("Apple","iPhone 15"), sa="low", view="die Unterseite") -> unsure, nicht final;
    # dann obs(i14,i13, sa="low", dist=False) in Ansicht 2 -> is_final,
    # line "Apple iPhone 14 oder Apple iPhone 13, von außen kaum zu unterscheiden."
def test_readable_model_name_is_decisive():       # cand("Myprotein","Essential BCAA"), readable ("MYPROTEIN","Essential BCAA 2:1:1") -> certain nach 1 Ansicht
def test_category_only():
    # obs(desc="rote Keramiktasse", cat="Tasse") ohne Kandidaten -> category_only,
    # "Rote Keramiktasse, ein bestimmtes Produkt erkenne ich nicht.", nicht final; nach zweiter Ansicht final
def test_brand_depth_display():                   # cand("Apple", None, depth="brand"), cat "Smartphone" -> "Apple-Smartphone" (de), "Apple Smartphone" (en)
def test_variant_needs_two_agreeing_observations():   # Variante "Midnight" erst nach 2 gleichen Nennungen im Namen
def test_single_candidate_low_self_assessment():  # obs(cand("Sony","WH-1000XM5"), sa="low") -> unsure, "Vielleicht Sony WH-1000XM5?"
# tests/test_lines.py: jede Zeile der Tabelle in de und en exakt; tests/test_trigger.py: je ein Test pro Regel 1–8,
# dazu test_forced_bypasses_final_and_object_cap und test_session_cap_beats_forced
```

- [ ] **Step 2: Tests laufen lassen.** `uv run pytest tests/test_lines.py tests/test_belief.py tests/test_trigger.py -v`. Erwartet: FAIL.
- [ ] **Step 3: `oi/lines.py`, `oi/belief.py`, `oi/trigger.py` und die Helfer implementieren.**
- [ ] **Step 4: Tests laufen lassen.** Befehl wie in Step 2. Erwartet: PASS.
- [ ] **Step 5: Commit.** `feat: evidence book, spoken lines and trigger policy`

---

### Task 6: Identifikation (Claude, Fake, Startprüfung)

**Files:**
- Create: `oi/identify.py`, `tests/test_identify.py`, `tests/test_live_claude.py`

**Interfaces:**
- Consumes: `Settings`, `Observation`, `NextView`, `Lang`, `lines.display_name`, `lines.notice_text`.
- Produces:
  - `@dataclass(frozen=True) class IdentifyRequest(jpeg: bytes, coarse_label: str, history: str, pending_view: NextView | None, language: Lang)`
  - `@dataclass(frozen=True) class IdentifyResult(observation: Observation, input_tokens: int, output_tokens: int, cost_usd: float, latency_s: float, model: str)`
  - `class IdentifyError(Exception)` mit `reason: Literal["refusal","schema","timeout","api","connection"]`
  - `class Identifier(Protocol)`: `model_label: str` und `async identify(req: IdentifyRequest) -> IdentifyResult`; bei `ClaudeIdentifier` ist `model_label = s.model`
  - `format_history(observations: list[Observation], lang: Lang) -> str`
  - `build_request(s: Settings, req: IdentifyRequest) -> dict`
  - `cost_usd(model: str, input_tokens: int, output_tokens: int, prices) -> float`
  - `class ClaudeIdentifier(s: Settings, client: AsyncAnthropic | None = None)`
  - `class FakeIdentifier(script: Sequence[Observation | IdentifyError] | None = None, delay_s: float = 0.0)` mit `requests: list[IdentifyRequest]` und `model_label = "fake"`
  - `async choose_identifier(s: Settings, fake: bool, client_factory=AsyncAnthropic) -> tuple[Identifier | None, str | None, Literal["hybrid","lokal"]]`

**`build_request`:**
- Grundfelder: `model`, `max_tokens=16000`, `system=SYSTEM_PROMPT.format(language="German" | "English")`.
- `messages`: genau ein User-Turn mit genau einem Bildblock (`{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data": b64(req.jpeg)}}`) und einem Textblock (Text unten).
- `output_config`: bei `claude-opus-5-5` und `claude-sonnet-5-5` `{"effort": s.effort, "format": {"type":"json_schema","schema": OBSERVATION_SCHEMA}}`, bei `claude-haiku-4-5` nur `format`. Haiku kennt kein `effort`.
- Nur bei Opus 5.5 und Sonnet 5.5: `betas=["server-side-fallback-2026-07-01"]` und `fallbacks="default"`.
- Kein `thinking`-Parameter.
- `OBSERVATION_SCHEMA` bildet `Observation` von Hand ab: alle Felder `required`, `additionalProperties: false`, Nullwerte als `anyOf` mit `{"type":"null"}`, Enums für `depth` und `self_assessment`. **Keine** `maxItems`, die Grenzen setzt der Parser durch Abschneiden.

**`ClaudeIdentifier.identify`:**
1. Enthält die Anfrage `betas`, ruft sie `client.with_options(timeout=s.claude_timeout_s).beta.messages.create(**req)` auf, sonst `...messages.create(**req)`.
2. `stop_reason == "refusal"` → `IdentifyError("refusal")`; `"max_tokens"` → `"schema"`.
3. Ersten Textblock nehmen, `json.loads`, Listen abschneiden (candidates 4, evidence 5, readable_text 10), dann `Observation.model_validate`. Ein Fehler dabei → `"schema"`.
4. Ausnahmen abbilden: `anthropic.APITimeoutError` → `"timeout"`, `anthropic.APIConnectionError` → `"connection"`, `anthropic.APIStatusError` → `"api"`.
5. Latenz mit `time.monotonic()` messen. Die Kosten aus `usage` × `prices`.

**`FakeIdentifier`:**
- Mit Drehbuch gibt er die Einträge der Reihe nach zurück oder wirft sie, nach `delay_s`.
- Ohne Drehbuch: Enthält das grobe Label „phone“, liefert er `obs(Apple iPhone 14, Apple iPhone 13, sa="low", view="die Unterseite"/"the bottom side", reason="Lightning oder USB-C"/"Lightning or USB-C")`, sonst eine Beobachtung ohne Kandidaten mit `generic_description=coarse_label`.
- Kosten 0.

**`choose_identifier`:**
- `fake=True` → `(FakeIdentifier(), None, "hybrid")`.
- Sonst `await client.models.retrieve(s.model)`:
  - Erfolg → `(ClaudeIdentifier(s, client), None, "hybrid")`
  - `APIConnectionError` → dasselbe, aber mit `notice_text("unreachable")`
  - `NotFoundError` → `(None, notice_text("model_missing", model=...), "lokal")`
  - `AuthenticationError`, `PermissionDeniedError`, `TypeError` und jede andere `anthropic.AnthropicError` → `(None, notice_text("no_key"), "lokal")`

**`SYSTEM_PROMPT`, exakter Text:**

```text
You identify the single object shown in a camera crop that a person is holding up.
- Identify it as specifically as the visible evidence allows: category, then brand, then model, then variant. Never go beyond what you can see.
- List up to 4 candidates, most plausible first. Evidence must be features visible in this image (logos, shapes, buttons, ports, printed text).
- Copy any text you can read on the object into readable_text.
- Set distinguishable to false if the top candidates cannot be told apart from the outside.
- If you are unsure, put into next_view the one view that best separates the top two candidates and the reason. next_view.view is a short noun phrase that fits after "Please show me", for example "the bottom side".
- If no specific product is recognizable, return candidates without brand or model and describe the object in generic_description, for example "red ceramic mug".
- self_assessment is your own confidence: high, medium or low.
- Write all free text (category, evidence, next_view, generic_description) in {language}.
```

**Textblock:**
- `Coarse detector label: {coarse_label}`
- `Previous observations of this object: {history}`
- nur bei offener Bitte zusätzlich `Requested view: {view} ({reason})`

`format_history` liefert `none` bei leerer Liste, sonst Zeilen `"{i}) {Name1} | {Name2} | {Name3} (evidence: {e1}, {e2})"`.

- [ ] **Step 1: Failing tests schreiben**

```python
# Fake-SDK: Klasse mit messages.create und beta.messages.create (async), die kwargs aufzeichnet und ein
# SimpleNamespace(stop_reason=..., content=[SimpleNamespace(type="text", text=...)], usage=SimpleNamespace(input_tokens=..., output_tokens=...))
# zurückgibt; with_options(**kw) gibt sich selbst zurück.
# SDK-Ausnahmen ohne Request bauen:
class _Timeout(anthropic.APITimeoutError):
    def __init__(self): Exception.__init__(self, "timeout")

def test_request_contains_only_the_crop_image():  # genau 1 Bildblock, data == b64(req.jpeg), media_type image/jpeg; Text enthält "Coarse detector label: cup"
def test_opus_request_has_effort_schema_and_default_fallback():
    r = build_request(Settings(), req)
    assert r["output_config"]["effort"] == "low" and r["output_config"]["format"]["schema"] is OBSERVATION_SCHEMA
    assert r["betas"] == ["server-side-fallback-2026-07-01"] and r["fallbacks"] == "default"
def test_haiku_request_has_no_effort_or_fallback():   # "effort" not in output_config; keine betas/fallbacks
async def test_parses_valid_response_and_computes_cost():
    # usage 2000 ein / 500 aus bei Opus -> cost_usd == pytest.approx(0.018); candidates[0].model_name == "iPhone 14"
async def test_truncates_overlong_lists():            # 6 Kandidaten in der Antwort -> 4
async def test_refusal_raises():                      # stop_reason "refusal" -> IdentifyError.reason == "refusal"
async def test_invalid_json_raises_schema_error():
async def test_timeout_maps_to_timeout():             # Fake wirft _Timeout -> reason "timeout"
async def test_fake_identifier_canned_phone():        # coarse_label "cell phone" -> sa "low", next_view.view "die Unterseite"
async def test_choose_identifier_modes():             # fake -> hybrid; Factory, deren retrieve AuthenticationError-Unterklasse wirft
                                                      # -> (None, "Kein API-Key: nur lokale Erkennung.", "lokal")
def test_format_history():                            # [] -> "none"; eine Beobachtung -> beginnt mit "1) Apple iPhone 14 | Apple iPhone 13"

# tests/test_live_claude.py
@pytest.mark.claude
async def test_real_call_returns_valid_observation(): # Ausschnitt aus ultralytics.utils.ASSETS/"bus.jpg" -> IdentifyResult, cost_usd > 0
```

- [ ] **Step 2: Tests laufen lassen.** `uv run pytest tests/test_identify.py -v`. Erwartet: FAIL.
- [ ] **Step 3: `oi/identify.py` gemäß den Festlegungen implementieren.**
- [ ] **Step 4: Tests laufen lassen.** Befehl wie in Step 2. Erwartet: PASS. Nur wenn Jonas einen API-Key eingerichtet hat, einmal `uv run pytest -m claude -v` (ca. 2 Cent). Erwartet: PASS. Liefert die API einen 400 zur Aufrufform, den Fehlertext lesen, `build_request` anhand des claude-api-Skills korrigieren und den Test wiederholen.
- [ ] **Step 5: Commit.** `feat: claude identifier with structured output, fake and startup probe`

---

### Task 7: Wahrnehmung (YOLOE + Tracker)

**Files:**
- Create: `oi/perception.py`, `oi/trackers/botsort.yaml`, `tests/test_perception.py`, `tests/test_live_model.py`

**Interfaces:**
- Consumes: `Settings`, `Track`.
- Produces:
  - `class Detector(Protocol)`: `detect(image: np.ndarray, t: float) -> list[Track]`, `reset() -> None`, `model_name: str`.
  - `class TrackAges` merkt sich pro ID `first_seen_ts` und `age_frames`.
  - `tracks_from_result(result, t: float, ages: TrackAges) -> list[Track]`.
  - `simplify_polygon(points: np.ndarray, max_points: int = 48) -> list[tuple[float, float]]`: gleichmäßige Auswahl per `np.linspace`, wenn es mehr Punkte sind.
  - `class YoloeDetector(s: Settings)`.
  - `class FakeDetector(script: list[list[Track]])` mit `reset_calls: int`.

**Festlegungen:**
- `YoloeDetector.__init__` lädt `YOLOE(s.detector)`. Scheitert das mit irgendeiner Ausnahme, lädt es `YOLOE(s.detector_fallback)`; `model_name` nennt die geladene Datei.
- `detect` ruft `model.track(image, persist=True, tracker=str(Path(__file__).parent / "trackers" / "botsort.yaml"), imgsz=s.imgsz, device=s.device, conf=s.conf, verbose=False)[0]` auf.
- `reset()` setzt `self._model.predictor = None`, damit der nächste Aufruf einen frischen Tracker baut, und leert `TrackAges`.
- `tracks_from_result` liest `result.boxes.id` (None → `[]`), `.xyxy`, `.cls`, `.conf`, `result.masks.xy` (Masken können fehlen, dann ist das Polygon leer) und `result.names`.
- `FakeDetector` liefert die Drehbuch-Einträge der Reihe nach und wiederholt danach den letzten.
- `botsort.yaml` ist eine Kopie von `ultralytics/cfg/trackers/botsort.yaml` aus dem installierten Paket, geändert: `track_buffer: 20`, `with_reid: False`.

- [ ] **Step 1: Failing tests schreiben**

```python
# Fake-Result mit numpy-Arrays: SimpleNamespace(boxes=SimpleNamespace(id=..., xyxy=..., cls=..., conf=...),
#                                               masks=SimpleNamespace(xy=[...]) oder None, names={0: "cup"})
def test_untracked_detections_are_skipped():   # boxes.id None -> []
def test_conversion_maps_fields_and_ages():    # ID 3 in zwei Aufrufen (t=1.0, t=1.1) -> age_frames 1 dann 2, first_seen_ts 1.0, label "cup"
def test_masks_missing_gives_empty_polygon():
def test_simplify_polygon_limits_points():     # 200 Punkte -> 48; 10 Punkte -> 10
def test_fake_detector_repeats_last():

# tests/test_live_model.py
@pytest.mark.model
def test_yoloe_finds_objects_on_bus_image():   # YoloeDetector(Settings()).detect(cv2.imread(str(ASSETS / "bus.jpg")), 0.0) -> mindestens 1 Track
@pytest.mark.model
def test_reset_restarts_track_ids():           # detect, reset, detect -> kleinste ID im zweiten Ergebnis == 1
```

- [ ] **Step 2: Tests laufen lassen.** `uv run pytest tests/test_perception.py -v`. Erwartet: FAIL.
- [ ] **Step 3: `oi/perception.py` und `oi/trackers/botsort.yaml` implementieren.**
- [ ] **Step 4: Tests laufen lassen.** Befehl wie in Step 2, danach `uv run pytest -m model -v` (lädt beim ersten Mal die Gewichte). Erwartet: alles PASS. Im Bericht festhalten, welche Gewichtsdatei geladen wurde.
- [ ] **Step 5: Commit.** `feat: yoloe prompt-free detector with bot-sort tracking`

---

### Task 8: Pipeline

**Files:**
- Create: `oi/pipeline.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: alle Produces aus Task 1–7 (`Frame`, `FrameSlot`, `decode_frame`, `Telemetry`, `CallLog`, `CallRecord`, `split_tracks`, `FocusSelector`, `ViewCollector`, `Belief`, `decide`, `TriggerInput`, `Decision`, `Identifier`, `IdentifyRequest`, `IdentifyError`, `format_history`, `lines.*`, `Detector`).
- Produces: `Emit = Callable[[ServerMsg], Awaitable[None]]` und `class Pipeline(s: Settings, detector: Detector, identifier: Identifier | None, telemetry: Telemetry, call_log: CallLog | None, emit: Emit)` mit:
  - `async handle_frame(frame: Frame) -> None`
  - `async on_client_message(m: FocusMsg | RecheckMsg) -> None`
  - `async run(slot: FrameSlot) -> None`: holt Rohbilder, dekodiert in `asyncio.to_thread`, überspringt `FrameFormatError` und protokolliert jede andere Ausnahme pro Bild, ohne die Schleife zu beenden.
  - `async telemetry_tick(frames_dropped: int) -> None`
  - `async wait_idle() -> None`
  - `async aclose() -> None`: bricht laufende Identifikationen ab.

**Ablauf `handle_frame`** (alle Zeitlogik nutzt `frame.t`):
1. `tracks = await asyncio.to_thread(detector.detect, frame.image, frame.t)`; die Dauer geht an `telemetry.frame_processed`.
2. `visible, hands = split_tracks(...)`, dann `focus_id = focus.update(visible, hands, w, h, frame.t)`.
3. Gibt es einen Fokus und einen Identifier: `ViewCollector` des Tracks holen oder anlegen und `offer(track, image, focus.steady(id), t)` aufrufen. Die Schärfe geht an `telemetry.set_sharpness`, ohne Fokus `set_sharpness(None)`. Aus `result.hint` wird mit `hint_line` der Hinweis. Bei `result.ready` folgt `decide(...)`.
4. Die Entscheidung:
   - `CALL`: `forced=False`, `calls += 1`, `telemetry.call_started()`, `collector.mark_sent(ready)`, dann den Identifikations-Task starten.
   - `SESSION_CAP`: einmal pro Track `IdentityMsg` mit Status `paused` und `line = paused_line`, einmal pro Sitzung `NoticeMsg("warn", paused_line)`.
   - `OBJECT_CAP` und `WAIT`: nichts.
5. `TracksMsg(frame_id, w, h, focus_id, [WireTrack.from_track(t, w, h) for t in visible], hint)` senden.
6. Zustände von Tracks löschen, die länger als 30 s nicht gesehen wurden.

**Identifikations-Task:**
1. Zuerst `IdentityMsg` mit Status `analysing` senden: bisheriger Snapshot, ohne Beobachtung `BeliefState.empty(track.label)`.
2. `IdentifyRequest(ready.jpeg, track.label, format_history(belief.observations, lang), <aktuelle view_request>, lang)`.
3. Erfolg: `belief.add(obs, ready.view_id, ready.q)`, `telemetry.call_finished`, `CallLog.write`, dann `IdentityMsg` mit Status `ready` und `snapshot(calls)`.
4. `IdentifyError`: `telemetry.call_failed`, `CallLog.write(error=reason)`, dann `IdentityMsg` mit Status `error`, Snapshot und `line = error_line`.
5. Immer: `in_flight` zurücksetzen.

**Nachrichten vom Browser:** `FocusMsg` → `focus.pin(track_id)`. `RecheckMsg` → `forced = True` und `collector.force_next()`.

- [ ] **Step 1: Failing tests schreiben**

```python
# Aufbau: FakeDetector-Drehbuch, sharp_image/blurry_image aus tests/helpers, Frames alle 0,1 s,
# emit sammelt Nachrichten in einer Liste; nach den Frames await pipeline.wait_idle()
async def test_tracks_message_excludes_people_and_normalizes():
async def test_holding_still_triggers_one_identification():
    # Tasse ruhig von t=0 bis 1.2 -> genau 1 Request (coarse_label "cup"); Status-Folge ["analysing", "ready"];
    # ready.level == "likely"; line == "Das ist wahrscheinlich Apple iPhone 14."; telemetry.calls_session == 1
async def test_no_identifier_means_tracks_only():      # identifier=None -> nur tracks, keine identity
async def test_result_stays_with_original_track_after_focus_switch():   # delay_s=0.5, während des Aufrufs FocusMsg(anderer Track) -> ready.track_id == ursprünglicher Track
async def test_session_cap_pauses_and_notifies_once(): # max_calls_session=1, zwei Objekte nacheinander -> zweites paused, genau 1 notice
async def test_recheck_calls_again():                  # nach certain (Beweisstück) -> RecheckMsg -> zweiter Request, history != "none"
async def test_identify_error_then_retry_on_new_view():# erst IdentifyError("timeout") -> status error mit Fehlerzeile; neue Ansicht -> neuer Aufruf
async def test_edge_object_gets_full_view_hint():      # Box am linken Rand ab t=0 -> bei t>=2.0 hint "Bitte ganz ins Bild.", 0 Requests
async def test_two_similar_objects_do_not_flicker():   # zwei gleich große Tassen, Scores abwechselnd um < 0,15 vorn -> focus_id über 20 Frames konstant
```

- [ ] **Step 2: Tests laufen lassen.** `uv run pytest tests/test_pipeline.py -v`. Erwartet: FAIL.
- [ ] **Step 3: `oi/pipeline.py` gemäß Ablauf implementieren.**
- [ ] **Step 4: Tests laufen lassen.** `uv run pytest -v` (der gesamte Standardlauf). Erwartet: PASS.
- [ ] **Step 5: Commit.** `feat: pipeline wiring perception, focus, views, trigger and identification`

---

### Task 9: Server und Kommandozeile

**Files:**
- Create: `oi/server.py`, `oi/__main__.py`, `tests/test_server.py`

**Interfaces:**
- Consumes: `Pipeline`, `FrameSlot`, `parse_frame_message`, `FrameFormatError`, `parse_client_message`, `Telemetry`, `CallLog`, `NoticeMsg`, `choose_identifier`, `YoloeDetector`, `Settings`.
- Produces:
  - `IdentifierFactory = Callable[[], Awaitable[tuple[Identifier | None, str | None, Literal["hybrid","lokal"]]]]`
  - `create_app(s: Settings, detector: Detector, identifier_factory: IdentifierFactory, static_dir: Path = Path("web/dist")) -> FastAPI`
  - `main(argv: list[str] | None = None) -> None` mit den Optionen `--port`, `--fake-claude` und `--no-browser`

**Festlegungen:**
- Die Lifespan-Funktion ruft `identifier_factory` genau einmal auf und merkt sich Identifier, Hinweis und Modus.
- `/ws` beim Verbinden:
  - eine vorhandene Verbindung mit Code 4000 schließen, dann `detector.reset()`
  - pro Verbindung neu anlegen: `Sender` (stempelt `seq` ab 1 und `ts=time.time()` per `model_copy(update=...)`), `Telemetry` (Modus; Modellname `identifier.model_label`, im lokalen Modus `–`), `CallLog(s.runs_dir, s.log_calls)`, `FrameSlot` und `Pipeline`
  - einen vorhandenen Start-Hinweis als `NoticeMsg("warn", ...)` senden
  - zwei Tasks starten: `pipeline.run(slot)` und einen Ticker, der jede Sekunde `pipeline.telemetry_tick(slot.dropped)` aufruft
- `/ws`, Empfangsschleife mit `websocket.receive()`:
  - Bytes → `parse_frame_message` → `slot.put`; `FrameFormatError` wird ignoriert.
  - Text → `parse_client_message` → `pipeline.on_client_message`; `None` wird ignoriert.
- `/ws` beim Beenden: Tasks abbrechen und `await pipeline.aclose()`.
- `GET /`: Gibt es `static_dir/index.html`, mountet die App `StaticFiles(directory=static_dir, html=True)` an `/`. Sonst liefert sie eine kleine HTML-Seite mit dem Satz „Frontend nicht gebaut: `npm --prefix web install && npm --prefix web run build`“.
- `main`:
  1. `Settings.from_env()` laden, `YoloeDetector(s)` bauen.
  2. `create_app(s, detector, lambda: choose_identifier(s, args.fake_claude))`.
  3. Ohne `--no-browser` öffnet ein `threading.Timer(1.5, webbrowser.open, ...)` die Seite `http://127.0.0.1:{port}`.
  4. `uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")`.

- [ ] **Step 1: Failing tests schreiben**

```python
# Starlette TestClient; FakeDetector mit einem Tasse-Track; JPEG-Bytes aus sharp_image; frame_bytes wie in Task 2
def test_ws_frame_produces_tracks_with_seq():         # Factory (FakeIdentifier(), None, "hybrid") -> erste Nachricht type "tracks", seq == 1
def test_startup_notice_in_local_mode():              # Factory (None, "Kein API-Key: nur lokale Erkennung.", "lokal") -> erste Nachricht notice mit genau diesem Text
def test_malformed_messages_are_ignored():            # b"\x00", '{"type":"nope"}', 'kaputt', danach gültiges Bild -> tracks kommt, Verbindung offen
def test_focus_message_pins_track():                  # FocusMsg(track_id=2) bei zwei Tracks -> nächste tracks-Nachricht focus_id == 2
def test_second_connection_replaces_first():          # zweite Verbindung -> erste bekommt Close-Code 4000; FakeDetector.reset_calls == 2
def test_root_without_build_shows_hint(tmp_path):     # static_dir fehlt -> GET / 200 und enthält "npm --prefix web run build"
@pytest.mark.model
def test_server_with_real_detector_sees_bus():        # YoloeDetector + bus.jpg als Bild -> tracks mit mindestens 1 Eintrag
```

- [ ] **Step 2: Tests laufen lassen.** `uv run pytest tests/test_server.py -v`. Erwartet: FAIL.
- [ ] **Step 3: `oi/server.py` und `oi/__main__.py` implementieren.**
- [ ] **Step 4: Tests laufen lassen.** `uv run pytest -v` und `uv run pytest -m model -v`. Erwartet: PASS. Dann `uv run python -m oi --fake-claude --no-browser &` starten, `curl -s http://127.0.0.1:8766/` ausführen (erwartet: die Hinweis-Seite) und den Server beenden.
- [ ] **Step 5: Commit.** `feat: fastapi websocket server and command line`

---

### Task 10: Web-Gerüst, Protokoll, Kamera, Verbindung

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/vite.config.ts`, `web/index.html`, `web/src/main.tsx`, `web/src/App.tsx`, `web/src/protocol.ts`, `web/src/protocol.test.ts`, `web/src/camera/frame.ts`, `web/src/camera/frame.test.ts`, `web/src/camera/capture.ts`, `web/src/net/socket.ts`

**Interfaces:**
- Consumes: `tests/fixtures/protocol-examples.json`, das Bild-Format aus §2.1.
- Produces:
  - `protocol.ts`: die Typen `WireTrack`, `TracksMsg`, `IdentityMsg`, `TelemetryMsg`, `NoticeMsg`, `ServerMsg`, `FocusMsg`, `RecheckMsg`, `Level`, `Status` und `Lang`, Feld für Feld wie in Task 1; dazu `isServerMsg(x: unknown): x is ServerMsg`, das `type` und alle Pflichtfelder prüft.
  - `camera/frame.ts`: `type FrameHeader = {frame_id: number; t_capture_ms: number; w: number; h: number}` und `encodeFrame(h: FrameHeader, jpeg: ArrayBuffer): ArrayBuffer`.
  - `camera/capture.ts`: `openCamera(): Promise<MediaStream>` mit `{width: 1280, height: 720, frameRate: 30}` und `startCapture(video: HTMLVideoElement, send: (b: ArrayBuffer) => void, canSend: () => boolean, fps = 12): () => void`.
  - `net/socket.ts`: `connect(url: string, h: {onMessage(m: ServerMsg): void; onStatus(s: "open" | "closed"): void}): {send(d: ArrayBuffer | string): void; bufferedAmount(): number; close(): void}`. Wiederverbinden nach 2000 ms; `onMessage` bekommt nur Nachrichten, die `isServerMsg` besteht.

**Festlegungen:**
- `capture.ts`: Canvas 1280×720, `toBlob(..., "image/jpeg", 0.8)`; gesendet wird nur, wenn `canSend()` wahr ist, also bei `bufferedAmount < 1_000_000`. `t_capture_ms` kommt aus `performance.now()`. Das Bild wird nie gespiegelt.
- WebSocket-URL: `` `ws://${location.host}/ws` ``.
- `App.tsx` zeigt vorerst das `<video>` mit `object-fit: contain` auf schwarzem Grund und den Verbindungsstatus; das HUD folgt in Task 12.

- [ ] **Step 1: Gerüst.**
  - `web/package.json`: `"type": "module"`, Skripte `dev: vite`, `build: tsc -b && vite build`, `test: vitest run`.
  - Pakete: `npm --prefix web install react react-dom zustand` und `npm --prefix web install -D vite @vitejs/plugin-react typescript vitest @types/react @types/react-dom @types/node`.
  - `tsconfig.json`: `strict`, `jsx: react-jsx`, `module: ESNext`, `moduleResolution: bundler`, `target: ES2022`.
  - `vite.config.ts` (`defineConfig` aus `vitest/config`): React-Plugin, Proxy `/ws` → `ws://127.0.0.1:8766` mit `ws: true`, `build.outDir: "dist"`, `test.environment: "node"`.
  - `index.html` mit `<div id="root">` und dem Titel „Object Intelligence“.
- [ ] **Step 2: Failing tests schreiben**

```ts
// protocol.test.ts
test("fixture messages are valid", () => {
  const xs = JSON.parse(readFileSync(new URL("../../tests/fixtures/protocol-examples.json", import.meta.url), "utf8"));
  expect(xs.length).toBe(4);
  for (const x of xs) expect(isServerMsg(x)).toBe(true);
});
test("incomplete message is rejected", () => expect(isServerMsg({ type: "tracks" })).toBe(false));
// frame.test.ts
test("encodeFrame layout", () => {
  const buf = encodeFrame({ frame_id: 7, t_capture_ms: 1234.5, w: 1280, h: 720 }, new Uint8Array([0xff, 0xd8, 0xff]).buffer);
  const n = new DataView(buf).getUint32(0);               // big-endian Header-Länge
  expect(JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, n)))).toEqual({ frame_id: 7, t_capture_ms: 1234.5, w: 1280, h: 720 });
  expect([...new Uint8Array(buf, 4 + n)]).toEqual([0xff, 0xd8, 0xff]);
});
```

- [ ] **Step 3: Tests laufen lassen.** `npm --prefix web test`. Erwartet: FAIL.
- [ ] **Step 4: Module implementieren.**
- [ ] **Step 5: Tests und Build.** `npm --prefix web test` und `npm --prefix web run build`. Erwartet: PASS, und `web/dist/index.html` existiert.
- [ ] **Step 6: Commit.** `feat: web scaffold with protocol types, camera capture and socket`

---

### Task 11: HUD-Logik (Geometrie, Platzierung, Glättung, Zustand, Texte, Stimme)

**Files:**
- Create: `web/src/hud/geometry.ts`, `web/src/hud/placement.ts`, `web/src/hud/smoothing.ts`, `web/src/store.ts`, `web/src/i18n.ts`, `web/src/voice/speech.ts`, dazu je eine `*.test.ts`

**Interfaces:**
- Consumes: `protocol.ts`.
- Produces:
  - `geometry.ts`:
    - `type Rect = {x: number; y: number; w: number; h: number}`
    - `videoContentRect(view: {w: number; h: number}, video: {w: number; h: number}): Rect` für `object-fit: contain`
    - `toScreen(box: [number, number, number, number], content: Rect, mirrored: boolean): Rect`
    - `toScreenPoints(poly: [number, number][], content: Rect, mirrored: boolean): [number, number][]`
    - `hitTest(p: {x: number; y: number}, boxes: {id: number; rect: Rect}[]): number | null`, die kleinste Box, die den Punkt enthält
  - `placement.ts`: `class CardPlacer` mit `place(box: Rect, card: {w: number; h: number}, viewport: {w: number; h: number}, now: number): {x: number; y: number; side: "left" | "right" | "below" | "above"}`
  - `smoothing.ts`: `smoothRect(prev: Rect, target: Rect, dtMs: number, tauMs = 80): Rect` mit `a = 1 - exp(-dt / tau)`
  - `store.ts`:
    - `type HudState = {tracks: TracksMsg | null; identities: Record<number, IdentityMsg>; telemetry: TelemetryMsg | null; notices: NoticeMsg[]; connection: "open" | "closed"; mirrored: boolean; muted: boolean; showTelemetry: boolean; cameraError: string | null}`
    - `initialState` und `applyServerMessage(s: HudState, m: ServerMsg): HudState` (rein)
    - `useHud`, ein zustand-Store mit `receive`, `toggleMirror`, `toggleMute`, `toggleTelemetry`, `setConnection` und `setCameraError`
  - `i18n.ts`: `t(key: I18nKey, lang: Lang): string`
  - `voice/speech.ts`:
    - `NOVELTY_VOICES`, übernommen aus `Dead-EV3/kalwa/ui/static/js/speech.js:6`
    - `pickVoice<V extends {name: string; lang: string}>(voices: V[], lang: Lang): V | null`
    - `class SpeechGate` mit `consider(e: {trackId: number; line: string; kind: "result" | "hint"}, now: number, focusId: number | null, muted: boolean): string | null` und `focusChanged(): void`

**Festlegungen:**
- **Platzierung** (§3):
  - Seite mit mehr freiem Platz, Abstand 24 px zur Box.
  - Seitenwechsel nur, wenn die andere Seite 500 ms ununterbrochen ≥ 20 % mehr Platz bietet. Passt die Karte auf der aktuellen Seite gar nicht mehr hin (Platz < Kartenbreite + 24), wird sofort gewechselt.
  - `y` = Box-Oberkante, begrenzt auf 8 px Rand.
  - Passt die Karte auf keine Seite, kommt sie darunter; passt sie dort auch nicht, darüber.
  - Die Karte überlappt die Box nie.
- **`applyServerMessage`:** `tracks` wird ersetzt, `identity` pro `track_id` gespeichert, `telemetry` ersetzt. Von den `notice`s bleiben die letzten 3.
- **i18n-Schlüssel**, jeweils mit Deutsch und Englisch:

  | Schlüssel | de | en |
  |---|---|---|
  | `level.certain` | SICHER | CERTAIN |
  | `level.likely` | WAHRSCHEINLICH | LIKELY |
  | `level.unsure` | UNSICHER | UNSURE |
  | `level.category_only` | NUR KATEGORIE | CATEGORY ONLY |
  | `analysing` | ANALYSIERE … | ANALYSING … |
  | `recheck` | Neu prüfen | Check again |
  | `showMe` | Zeig mir bitte | Please show me |
  | `cameraDenied` | Kein Kamerazugriff. Erlaube ihn unter Systemeinstellungen → Datenschutz & Sicherheit → Kamera. | No camera access. Allow it in System Settings → Privacy & Security → Camera. |
  | `retry` | Erneut versuchen | Try again |
  | `reconnecting` | Verbindung verloren, verbinde neu … | Connection lost, reconnecting … |

  Dazu Telemetrie-Beschriftungen für jedes Feld aus §3.
- **SpeechGate:**
  - Leere Zeilen, Tracks außerhalb des Fokus und Stummschaltung ergeben `null`.
  - `result`: sprechen, wenn diese Zeile für diesen Track noch nie gesprochen wurde.
  - `hint`: sprechen, wenn seit dem letzten Hinweis ≥ 5000 ms vergangen sind.
  - `focusChanged()` vergisst nichts, der Aufrufer bricht aber das laufende Sprechen ab.
- **pickVoice:** die erste Stimme, deren `lang` mit `de` bzw. `en` beginnt und deren Basisname (Text vor „ (“) nicht in `NOVELTY_VOICES` steht.

- [ ] **Step 1: Failing tests schreiben**

```ts
test("contain letterbox", () => expect(videoContentRect({w: 1000, h: 600}, {w: 1280, h: 720})).toEqual({x: 0, y: 18.75, w: 1000, h: 562.5}));
test("mirrored mapping", () => expect(toScreen([0.1, 0.2, 0.3, 0.4], {x: 0, y: 0, w: 1000, h: 500}, true)).toEqual({x: 700, y: 100, w: 200, h: 100}));
test("hitTest picks smallest", ...);   // Punkt in großer und kleiner Box -> ID der kleinen; außerhalb -> null
// Karte 300x200, Viewport 1400x600:
// Box {x:300,y:200,w:200,h:200} -> side "right", x 524, y 200.
// Box nach x 800 (links 800, rechts 400): bei now+400 noch "right", bei now+500 "left".
// Box y 550 -> y = 600-200-8 = 392.
// Viewport 500x600, Box {x:150,y:50,w:200,h:200} -> side "below", y 274 (>= Box-Unterkante 250 + 24).
test("card placement", ...);
test("smoothing", ...);                // dt 80 -> ~63,2 % Richtung Ziel; dt 0 -> prev; dt 2000 -> ~ Ziel
test("reducer", ...);                  // tracks ersetzt; identity pro track_id; 4 notices -> 3 bleiben
test("i18n complete", ...);            // jeder Schlüssel hat nicht-leeres de und en
test("pickVoice skips novelty voices", () =>
  expect(pickVoice([{name: "Zarvox", lang: "de-DE"}, {name: "Anna (Deutsch (Deutschland))", lang: "de-DE"}], "de")?.name).toMatch(/^Anna/));
test("gate speaks a result once per track", ...);   // neue Zeile -> Zeile; dieselbe nochmal -> null; anderer Track ohne Fokus -> null; stumm -> null
test("hints at most every 5 s", ...);               // t=0 -> Zeile; t=4000 -> null; t=5000 -> Zeile
```

- [ ] **Step 2: Tests laufen lassen.** `npm --prefix web test`. Erwartet: FAIL.
- [ ] **Step 3: Module implementieren.**
- [ ] **Step 4: Tests laufen lassen.** Befehl wie in Step 2. Erwartet: PASS.
- [ ] **Step 5: Commit.** `feat: hud geometry, card placement, state, texts and speech gate`

---

### Task 12: HUD-Oberfläche und Bedienung

**Files:**
- Create: `web/src/hud/Overlay.tsx`, `web/src/hud/InfoCard.tsx`, `web/src/hud/Telemetry.tsx`, `web/src/hud/Banner.tsx`, `web/src/styles.css`
- Modify: `web/src/App.tsx`

**Interfaces:**
- Consumes: alles aus Task 10 und 11.
- Produces: die sichtbare Oberfläche; keine neuen exportierten Funktionen.

**Festlegungen (§3):**
- **Overlay:** Ein Canvas deckt das Video ab; die `requestAnimationFrame`-Schleife glättet jede Box mit `smoothRect`.
  - Eckklammern: Arme 14 px, Linie 2 px; weiß mit 35 % Deckkraft, beim Fokus 100 %.
  - Der Fokus schnappt beim Wechsel in 200 ms von 8 px Abstand auf 0.
  - Objekte ohne Fokus bekommen das Label „#{id} {label}“.
  - Fokus-Umriss: 1 px weiß aus `toScreenPoints`. Scanlinie bei Status `analysing`, von oben nach unten in 2,4 s.
  - Eine Verbindungslinie führt von der Boxkante zur Karte.
  - Klick → `hitTest`: auf eine Box `{"type":"focus","track_id": id}`, ins Leere `track_id: null`.
- **InfoCard:**
  - Inhalt und Reihenfolge wie in §3: Name, Stufe (i18n), bis zu 3 Balken ohne Zahlen, Indizien-Kacheln mit `animation-delay: i*80ms`, dann die Bitte „{showMe} {view}“ mit Pfeil und Begründung.
  - Knopf `recheck` sendet `{"type":"recheck","track_id": ...}`.
  - Die Karte blendet in 200 ms ein, ihre Position kommt von `CardPlacer`.
- **Telemetry:** oben links, sichtbar bei `showTelemetry`.
  - Video-fps misst der Browser per `requestVideoFrameCallback`.
  - Dazu alle Felder der `TelemetryMsg` und die Anteile der Fokus-Kandidaten als Zahlen mit 2 Nachkommastellen.
- **Banner:** Glasbanner oben mittig.
  - Neuester `notice`: `info` verschwindet nach 6 s, `warn`/`error` bleiben bis zum nächsten.
  - Kamerafehler mit Text `cameraDenied` und Knopf `retry`, der `openCamera` erneut aufruft.
  - Bei `connection === "closed"` der Text `reconnecting`.
- **App:**
  - Tasten: `m` → `toggleMute`, `d` → `toggleTelemetry`, `s` → `toggleMirror`.
  - Spiegelung per CSS `transform: scaleX(-1)` am Video; das Overlay rechnet über `mirrored`.
  - Stimme: Bei jeder neuen `IdentityMsg` des Fokus-Tracks läuft `line` durch `SpeechGate` (Art `result`), bei `TracksMsg.hint` durch das Gate mit Art `hint`. Gibt das Gate eine Zeile zurück, wird sie per `speechSynthesis` mit der Stimme aus `pickVoice` gesprochen.
  - Bei einem Fokuswechsel `gate.focusChanged()` und `speechSynthesis.cancel()`.
  - Die Sprache kommt aus `telemetry.language`, Standard `de`.
- **`styles.css`:**
  - Tokens `--glass-bg: rgba(22,22,28,.6)`, `--glass-blur: 8px`, `--radius: 10px`, `--text: #fff`.
  - `font-family: -apple-system, system-ui, sans-serif`, `body { background: #000; margin: 0 }`.
  - Video und Overlay füllen den Viewport.

- [ ] **Step 1: Komponenten und `styles.css` bauen, `App.tsx` verdrahten.**
- [ ] **Step 2: Prüfen.** `npm --prefix web test` und `npm --prefix web run build`. Erwartet: PASS, `web/dist` gebaut.
- [ ] **Step 3: Rauchtest.**
  1. `uv run python -m oi --fake-claude --no-browser &` starten.
  2. `curl -s http://127.0.0.1:8766/ | grep -c 'id="root"'` ergibt `1`.
  3. Mit einem kleinen Python-WebSocket-Client ein Bild (bus.jpg) senden; erwartet: `tracks` mit mindestens einem Eintrag.
  4. Den Server beenden.
- [ ] **Step 4: Commit.** `feat: glass hud with overlay, info card, telemetry, banner and voice`

---

### Task 13: README, Abnahme-Checkliste, Gesamtprüfung

**Files:**
- Create: `README.md`, `docs/acceptance/sp1-checklist.md`

**Festlegungen:**
- **`README.md`**, auf Englisch fürs Portfolio:
  - was das Projekt ist und die Ehrlichkeits-Prinzipien (Stufen statt Prozenten, nur der Ausschnitt geht an Claude)
  - Setup: `uv sync`, `npm --prefix web install`, `npm --prefix web run build`
  - Start: `uv run python -m oi`, dazu `--fake-claude` und `--no-browser`; der API-Key per `ANTHROPIC_API_KEY` oder `ant auth login`
  - Tests: Standardlauf, `-m model`, `-m claude` (kostet ca. 2 Cent) und `npm --prefix web test`
  - eine Architekturskizze aus §2
  - Hinweis auf die Teilprojekte 2–5
- **`sp1-checklist.md`**, auf Deutsch:
  - eine Tabelle mit den 5 Gegenständen aus §1 und den Spalten „Box folgt?“, „ID stabil?“, „Stufe und Name passend?“, „Bitte um Ansicht sinnvoll?“, „Zeit bis 1. Ergebnis“, „Kosten“, „Notizen“
  - die Richtwerte aus §1
  - der Abschnitt „Kalibrierung“: gemessener Schärfewert, gewählte Schwelle `OI_MIN_SHARPNESS`
  - die Schlusszeile „Teilprojekt 1 abgenommen: ja / nein (Jonas, Datum)“

- [ ] **Step 1: README und Checkliste schreiben.**
- [ ] **Step 2: Gesamtprüfung.** `uv run pytest -v`, `uv run pytest -m model -v`, `npm --prefix web test`, `npm --prefix web run build`. Erwartet: alles PASS. `uv run pytest -m claude -v` nur, wenn ein API-Key vorhanden ist; sonst im Bericht „nicht gelaufen, kein Key“ vermerken.
- [ ] **Step 3: Commit.** `docs: readme and acceptance checklist for sub-project 1`
- [ ] **Step 4: Übergabe an Jonas.** Er startet `uv run python -m oi`, gibt die Kamera frei, kalibriert mit der Telemetrie (`d`) die Schärfe-Schwelle und füllt die Checkliste mit den 5 Gegenständen aus. Teilprojekt 1 ist fertig, wenn er „abgenommen: ja“ einträgt.
