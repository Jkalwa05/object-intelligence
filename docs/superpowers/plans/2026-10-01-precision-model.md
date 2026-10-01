# Präzisionsmodell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Once an article is certain, research its dimensions and drawing, let Claude write OpenSCAD (BOSL2), compile
it in Node, check it visually in up to two rounds, cache it, and show it as a CAD hologram.

**Architecture:** An app-level `ModelBuilder` (one job at a time, survives reconnects) runs research → drawing →
CAD → compile → check rounds and stores `cache/models/<slug>/`. Pipelines listen to it and send `model` messages per
sidebar entry. The browser loads the STL parts over a new HTTP route and draws them in the existing hologram look.
The quick primitive hologram of sub-project 3 is removed.

**Tech Stack:** Python 3.12, FastAPI, pydantic, Anthropic SDK, httpx, pypdfium2 (new), matplotlib; Node 24 with
`openscad-wasm-prebuilt` 1.2.0 (new) and BOSL2 at commit `d05f0ca97d57cc072e627c34c7c0fde7aecbed9a`; React 19,
TypeScript, zustand, three (STLLoader), Vitest.

**Spec:** `docs/superpowers/specs/2026-10-01-precision-model-design.md`

## Global Constraints

- Trigger only at level certain with a model-depth product (`Belief.product()` while the snapshot is certain).
- Research: `web_search_20260209` (max_uses 3, DE location for German) + `web_fetch_20250910` (max_uses 3,
  max_content_tokens 15000), no image, effort medium, free-text answer ending in one ```json block. CAD and check:
  structured output (json_schema), effort high, `max_tokens` 32000, timeout `model_timeout_s` (360 s).
- Budget per product 1.60 $ (`max_model_cost_usd`); step reserves research 0.45 $, CAD 0.45 $, check 0.35 $; at most
  5 new models per server run (`max_models_session`); at most 2 check rounds (`model_check_rounds`).
- Limits after parsing (never in the schema): measures ≤ 30, features ≤ 20, sources ≤ 6, parts ≤ 40, `shared` ≤
  20000 chars, part code ≤ 12000 chars, issues ≤ 10; per part ≤ 200000 triangles, model ≤ 600000; 30 s per part,
  ≤ 4 Node processes at once.
- Downloads: https only, URL must be in the call's search/fetch results, public IPs only (also after each of ≤ 3
  redirects), types pdf/png/jpeg, PDF ≤ 60 MB, image ≤ 8 MB, 30 s; never executed.
- OpenSCAD runs only inside `openscad-wasm-prebuilt` (in-memory FS, `--backend=manifold`); Claude's code runs nowhere
  else.
- Every call counts in the shared `SessionBudget` and goes to the call log with `track_id` −2 and request text
  `model research: …`, `model cad: …`, `model check n: …`.
- German UI texts exactly as in spec §3 and §8; the badge reads „CAD · Maße laut <domain>“ or „CAD · Maße geschätzt“.
- Never call the project a demo.

## Review Focus

- Research alone already costs more than the cap (Claude fetched a big PDF anyway): no CAD call, status `failed`,
  cost logged (test in Task 9).
- OpenSCAD code that never finishes or yields empty geometry: that part fails with a reason that goes back to Claude,
  the rest of the model survives (tests in Tasks 4 and 9).
- Two model names with the same slug, or a manifest whose `model` differs from the asked name: never served under
  the wrong name (test in Task 2).
- The browser reconnects while a model is being built: the new connection gets the current status and the result
  (test in Task 10).
- Two entries for one model ("Apple iPhone 14" and "Apple iPhone 14, Blau"): both get every `model` message (test in
  Task 10).

---

### Task 1: Contracts, settings, removal of the quick hologram (server side)

**Files:** Modify `oi/contracts.py`, `oi/config.py`, `oi/identify.py`, `oi/profiles.py`, `oi/pipeline.py`,
`oi/server.py`, `oi/__main__.py`, `tests/fixtures/protocol-examples.json`, `tests/test_contracts.py`,
`tests/test_identify.py`, `tests/test_profiles.py`, `tests/test_pipeline.py`, `tests/test_live_claude.py`,
`web/src/protocol.ts`, `web/src/protocol.test.ts`

**Interfaces — Produces (contracts.py, after `Source`):**
- `MeasureKind = Literal["drawing", "datasheet", "estimate"]`
- `Measure(label: str, value_mm: float, source: int | None, kind: MeasureKind)`
- `DrawingRef(url: str, find: str)`
- `MeasureSheet(size_mm: Vec3 | None, size_source: int | None, measures: list[Measure], features: list[str],
  sources: list[Source], drawing: DrawingRef | None)` with `@classmethod estimated() -> MeasureSheet` (all empty)
- `ModelPart(name: str, color: str, file: str, min_mm: Vec3, max_mm: Vec3, triangles: int)`
- `ModelManifest(model: str, slug: str, parts: list[ModelPart], size_mm: Vec3, sheet: MeasureSheet,
  drawing_pages: list[int], notes: str, verdict: Literal["good", "fix", "unchecked"], rounds: int, cost_usd: float,
  created: str)`
- `ModelStatus = Literal["queued", "researching", "drawing", "modeling", "building", "checking", "ready", "failed",
  "limit"]`
- `ModelMsg(_ServerMsg)`: `type="model"`, `product: str`, `status: ModelStatus`, `round: int = 0`,
  `manifest: ModelManifest | None = None`; in `ServerMsg` instead of `ShapeMsg`
- `RebuildMsg(type="rebuild", name: str)` in `AnyClientMsg`
- `Settings`: `max_model_cost_usd=1.60`, `max_models_session=5`, `model_check_rounds=2`, `model_timeout_s=360.0`,
  `model_cache=<repo>/cache/models`, `models_dir=<repo>/models`; env `OI_MAX_MODEL_COST_USD` (float),
  `OI_MAX_MODELS_SESSION`, `OI_MODEL_CHECK_ROUNDS` (int)
- identify.py: `_image(data: bytes, media_type: str = "image/jpeg")`; `ClaudeIdentifier._create` renamed to public
  `create(request, timeout_s: float | None = None)`

**Ruling (record in ledger):** the browser shows the spec's `waiting` text itself when an entry has no `model` message;
the server never sends `waiting`.

- [ ] **Step 1: Tests first.**
  - `test_model_message_travels`: a ready `ModelMsg` with one part and a sheet round-trips through `model_dump(mode="json")`.
  - `test_rebuild_is_a_client_message`: `parse_client_message('{"type":"rebuild","name":"X"}')` is a `RebuildMsg`.
  - `test_settings_for_models`: defaults 1.60/5/2/360, `OI_MAX_MODELS_SESSION=3` works.
  - In `protocol_examples()` replace the shape example by a ready `ModelMsg` (`seq=7`); regenerate the fixture
    (count stays 8).
  - Delete every shape test: `test_shape_message_travels`, the shape tests in `test_identify.py`, the hologram
    section and the `shape=`/`shape_requests` uses in `test_pipeline.py` (the confirm test keeps its profile
    assertions), `test_shapes_are_kept_per_model_across_a_restart`, and `test_real_hologram_of_an_iphone_14_has_its_size`.
- [ ] **Step 2:** Run `uv run pytest -q tests/test_contracts.py tests/test_config.py`. Expected: FAIL (names missing).
- [ ] **Step 3: Implement.** Add the types above. Remove these and their wiring in the pipeline, server and main:
  - `ShapePart`, `ProductShape`, `ShapeMsg`;
  - `SHAPE_PROMPT`, `SHAPE_SCHEMA`, `build_shape_request`, `parse_shape`, `_part`, `_vec3` (only if unused),
    `ShapeRequest`, `ShapeResult`, `describe_shape`, `FakeIdentifier(shape=…)`;
  - `ShapeStore` and `shape_cache`;
  - `_want_shape`, `_fetch_shape`, `_write_shape_log`, `_shapes*`.
- [ ] **Step 4: Web protocol.** Add the TS types `Measure`, `MeasureSheet`, `ModelPart`, `ModelManifest`, `ModelMsg`
  and `RebuildMsg`. `REQUIRED.model = ["product", "status", "round", "manifest"]`. Keep the TS `ShapeMsg` until
  Task 11 so the UI still compiles. `protocol.test.ts`: a `model` message without `manifest` is rejected.
- [ ] **Step 5: Run everything.** `uv run pytest -q`, `npm --prefix web test`, `npm --prefix web run build`.
  Expected: all green.
- [ ] **Step 6: Commit** `feat: contracts for the precision model; the quick hologram goes`

### Task 2: Model store

**Files:** Create `oi/modelstore.py`, `tests/test_modelstore.py`

**Interfaces — Produces:**
- `slug(model: str) -> str`: lowercase, every run of non `a-z0-9` becomes `-`, trimmed, at most 80 chars; empty
  becomes `"model"`
- `class ModelStore(root: Path | None)` (`None` keeps everything in memory):
  - `get(model) -> ModelManifest | None`: `None` if missing, unreadable, if `manifest.model` differs from `model`
    after `cache.normalize`, or if a part file is missing;
  - `put(manifest, stls: list[bytes], scad: str) -> None`: writes `part-NN.stl`, `model.scad`, then
    `manifest.json` last;
  - `file(slug, name) -> bytes | None`: only names in the manifest or `model.scad`; slug must match `[a-z0-9-]+`.

- [ ] **Step 1: Tests.**
  - `test_slug`: "Apple iPhone 14" → "apple-iphone-14"; "Sony DualShock 3 (CECHZC2E)" → "sony-dualshock-3-cechzc2e";
    "" → "model".
  - `test_put_get_and_files_on_disk(tmp_path)`.
  - `test_get_refuses_a_manifest_of_another_model` ("Apple iPhone 14" stored, "apple iphone-14" asked → None).
  - `test_file_serves_only_listed_files` (`../manifest.json`, `part-99.stl`, `x/../model.scad` → None).
  - `test_memory_store`.
- [ ] **Step 2:** Run `uv run pytest -q tests/test_modelstore.py`. Expected: FAIL (module missing).
- [ ] **Step 3:** Implement. Writes use a temp file plus `os.replace`, like `JsonCache`. An `OSError` on write keeps
  the entry in memory.
- [ ] **Step 4:** Run it again. Expected: PASS.
- [ ] **Step 5: Commit** `feat: models are kept per product on disk`

### Task 3: Meshes and check renders

**Files:** Create `oi/mesh.py`, `oi/render.py`, `tests/test_mesh.py`

**Interfaces — Produces:**
- `read_stl(data: bytes) -> np.ndarray` with shape (n, 3, 3), float32. Binary STL only. `ValueError` if the size does
  not match the triangle count.
- `bounds(tri) -> tuple[Vec3, Vec3]`, raising `ValueError` for 0 triangles.
- `union(boxes: list[tuple[Vec3, Vec3]]) -> tuple[Vec3, Vec3]`.
- `size_hint(size: Vec3, expected: Vec3 | None, tolerance=0.10) -> str | None`: German text naming every axis that is
  off by more than 10 %.
- `VIEWS = ("vorn", "hinten", "rechts", "oben")`.
- `render_views(parts: list[tuple[np.ndarray, str]], size=512) -> list[bytes]`: 4 PNGs.
  - matplotlib Agg, orthographic, model (x, y, z) mapped to mpl (x, −z, y).
  - Views (elev, azim): front (0, −90), back (0, 90), right (0, 0), top (35, −55).
  - Lambert shading of the part colour, light grey background.

- [ ] **Step 1: Tests.** Use a helper `cube_stl(size, offset)` that writes a binary STL of 12 triangles.
  - `test_read_stl_and_bounds`.
  - `test_broken_stl_raises`.
  - `test_size_hint` (71.5 vs 80 → names Breite; within 10 % → None).
  - `test_render_views_are_four_png_of_the_right_size_and_not_blank`: PNG magic bytes, 512×512 via `PIL.Image`, more
    than one colour.
  - `test_front_and_back_differ_for_an_asymmetric_model` (a small cube offset towards +z on a big one).
- [ ] **Step 2:** Run `uv run pytest -q tests/test_mesh.py`. Expected: FAIL.
- [ ] **Step 3:** Implement. Disable the axes and draw the polygons by depth.
- [ ] **Step 4:** PASS. Also time the four views of a 50k-triangle model and write the time into the ledger. Keep it
  under about 5 s per view; if it is slower, draw fewer triangles (keep every n-th one) for the check views only.
- [ ] **Step 5: Commit** `feat: read STL parts and render four check views`

### Task 4: OpenSCAD compiler

**Files:**
- Create `web/scad/compile.mjs`, `oi/scad.py`, `tests/test_scad.py`, `tests/fixtures/fake_node.py`
- Modify `web/package.json` (dependency `openscad-wasm-prebuilt@1.2.0`), `pyproject.toml` (marker
  `scad: runs the real OpenSCAD compiler (needs node and web/node_modules)` and dependency `pypdfium2`, used in
  Task 6)

**Interfaces — Consumes:** `CadPart(name: str, color: str, scad: str)` from `oi/modelcalls.py`. Create that file in
this task with only this dataclass; Task 8 fills the rest.

**Interfaces — Produces:**
- `BOSL2_COMMIT = "d05f0ca97d57cc072e627c34c7c0fde7aecbed9a"`
- `HEADER = "include <BOSL2/std.scad>\n$fn = 48;\n"`
- `scad_file(shared: str, code: str) -> str` (HEADER + shared + code)
- `ensure_bosl2(models_dir: Path, download: Callable[[str], bytes] | None = None) -> Path`
  - It fetches `https://github.com/BelfrySCAD/BOSL2/archive/<commit>.zip` into `models/BOSL2-<commit>/BOSL2/`, root
    `*.scad` files only, and returns the parent folder.
- `compiler_problem(repo: Path) -> str | None`: German reason, or `None`.
  - "Node.js fehlt" when there is no `node` in PATH.
  - "web/node_modules fehlt (npm --prefix web install)" when the package is missing.
- `@dataclass(frozen=True) CompiledPart(name: str, color: str, stl: bytes | None, triangles: int, errors: list[str])`
- `class Compiler(Protocol)`: `async compile(shared: str, parts: list[CadPart]) -> list[CompiledPart]`
- `class ScadCompiler(bosl2_parent: Path, node: str = "node", script: Path = <repo>/web/scad/compile.mjs, parallel=4,
  timeout_s=30.0)`
  - One process per part.
  - stdin JSON `{"code": scad_file(...), "lib": "<bosl2_parent>"}`, stdout one JSON
    `{"ok": bool, "stl": base64 | null, "triangles": int, "errors": [str]}`.
  - A timeout kills the process, with the error "Zeitlimit 30 s überschritten".
  - Over 200000 triangles, or the model over 600000: the error "zu viele Dreiecke".
  - 0 triangles: the error "leere Geometrie".
- `class FakeCompiler(broken: set[str] = frozenset())`
  - Each part gets a 10 mm cube STL shifted by its index × 20 mm on x.
  - Names in `broken` get `errors=["ERROR: Parser error"]`.
  - Records `calls: list[list[str]]`.

**compile.mjs:**
- reads stdin;
- `createOpenSCAD({print, printErr})`, then `getInstance()`;
- writes `<lib>/BOSL2/*.scad` into `/BOSL2/` and the code to `/model.scad`;
- `callMain(["/model.scad", "--backend=manifold", "-o", "/out.stl", "--export-format=binstl"])`;
- collects at most 20 lines containing ERROR or WARNING;
- prints the JSON; the triangle count is read from STL bytes 80–84.

- [ ] **Step 1: Tests (unmarked, with `tests/fixtures/fake_node.py`).** The fake reads stdin, then sleeps when the
  code contains `SLEEP`, prints a scripted JSON when it contains `EMPTY` or `ERROR`, else returns a cube.
  - `test_scad_file_puts_header_shared_then_part`.
  - `test_compiler_runs_one_process_per_part_and_keeps_order`.
  - `test_a_hanging_part_times_out_alone` (`timeout_s=0.5`).
  - `test_empty_geometry_and_too_many_triangles_are_errors`.
  - `test_compiler_problem_names_missing_node_or_modules(tmp_path, monkeypatch)`.
  - `test_ensure_bosl2_extracts_only_root_scad_files(tmp_path)` with an in-memory zip.
- [ ] **Step 2: Tests (marker `scad`, real).**
  - `test_real_openscad_compiles_a_bosl2_part`: rounded cuboid with a cylinder cut, triangles > 100, `bounds` ≈
    71.5 × 146.7 × 7.8.
  - `test_real_openscad_cannot_read_files_on_the_mac`: write `{"secret": 4711}` to a temp file on the Mac, compile
    `data = import("<that path>"); echo(data=data); cube(1);` through `ScadCompiler`, and assert "4711" appears
    neither in the errors nor in the STL. `compile.mjs` never passes `--enable=import-function`.
- [ ] **Step 3:** Run `uv run pytest -q tests/test_scad.py`. Expected: FAIL.
- [ ] **Step 4:** Implement. Then `npm --prefix web install openscad-wasm-prebuilt@1.2.0`.
- [ ] **Step 5:** Run `uv run pytest -q tests/test_scad.py` and `uv run pytest -q -m scad tests/test_scad.py`.
  Expected: PASS.
- [ ] **Step 6: Commit** `feat: OpenSCAD with BOSL2 compiles each part in Node`

### Task 5: Safe downloads

**Files:** Create `oi/download.py`, `tests/test_download.py`

**Interfaces — Produces:**
- `class DownloadError(Exception)`
- `PDF_LIMIT = 60_000_000`, `IMAGE_LIMIT = 8_000_000`
- `async def fetch(url: str, allowed: set[str], *, transport: httpx.AsyncBaseTransport | None = None,
  resolve: Callable[[str], list[str]] | None = None, timeout_s: float = 30.0) -> tuple[bytes, str]`
  - Returns (body, media type in `{"application/pdf", "image/png", "image/jpeg"}`).
  - Redirects are followed by hand, at most 3, and every hop is checked again.
  - `resolve` defaults to `socket.getaddrinfo`; every address must be `ipaddress.ip_address(a).is_global`.

- [ ] **Step 1: Tests with `httpx.MockTransport` and a fake resolver.**
  - `test_downloads_an_allowed_pdf`.
  - `test_refuses_urls_not_found_by_the_research`.
  - `test_refuses_http_localhost_and_private_addresses` (`http://…`, `https://localhost/x.pdf`, a host resolving to
    `10.0.0.5` or `127.0.0.1`).
  - `test_rechecks_every_redirect` (redirect to a private host → error).
  - `test_refuses_wrong_types_and_oversized_bodies` (`text/html`; a 9 MB image).
- [ ] **Step 2:** Run `uv run pytest -q tests/test_download.py`. Expected: FAIL.
- [ ] **Step 3:** Implement. The body is streamed and aborted at the limit.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat: safe downloads for drawings`

### Task 6: Technical drawings

**Files:** Create `oi/drawings.py`, `tests/test_drawings.py`; `uv add pypdfium2`

**Interfaces — Produces:**
- `Picture = tuple[bytes, str]` (data, media type)
- `find_pages(pdf: bytes, find: str, limit: int = 2) -> list[int]` (0-based)
  - Words of `find` with ≥ 3 letters, lowercased. A page counts when it contains at least half of them.
  - The best scores come first; a tie keeps the earlier page.
- `render_pages(pdf: bytes, pages: list[int], dpi: int = 150, long_edge: int = 2000) -> list[bytes]` (PNG)
- `async def drawing_pictures(ref: DrawingRef | None, allowed: set[str], fetch=download.fetch) ->
  tuple[list[Picture], list[int]]`: pictures and their 1-based pages ([] for an image). Every error gives ([], []).

- [ ] **Step 1: Tests.** A 3-page PDF made with matplotlib `PdfPages`: page texts "Einleitung", "iPhone 14
  Dimensional Drawing 71.5", "iPhone 15 Dimensional Drawing".
  - `test_find_pages_picks_the_page_with_the_words` (→ [1]).
  - `test_render_pages_gives_png`.
  - `test_drawing_pictures_from_pdf_image_or_error` (fetch fakes: pdf; png; raising `DownloadError` → ([], [])).
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat: find and render the page of a technical drawing`

### Task 7: The research call

**Files:** Create `oi/modelprompts.py` (prompts and schemas); extend `oi/modelcalls.py`; create
`tests/test_modelcalls.py`; extend `tests/test_live_claude.py`

**Interfaces — Produces (modelcalls.py):**
- `@dataclass(frozen=True) ResearchRequest(model: str, category: str, language: Lang)`
- `ResearchResult(sheet: MeasureSheet, allowed_urls: set[str], searches: int, input_tokens: int, output_tokens: int,
  cost_usd: float, latency_s: float, model: str)`
- `build_research_request(s: Settings, req) -> dict`: system `RESEARCH_PROMPT`, two tools as in the Global
  Constraints, effort `medium`, `max_tokens` 16000, no `output_config.format`.
- `parse_research(blocks: list[Any]) -> tuple[MeasureSheet, set[str]]`
  - The JSON comes from the last ```json fence of all text blocks.
  - Limits and dropping:
    - measures and features are cut to their limits;
    - measures with value ≤ 0 or > 5000 are dropped;
    - an invalid `source` index becomes `None`, and then `kind` becomes "estimate";
    - `size_source` out of range becomes `None`.
  - Allowed URLs are the `url`s of `web_search_tool_result` items and `web_fetch_tool_result.content.url`.
  - No JSON raises `IdentifyError("schema")`.
- `RESEARCH_PROMPT` says (English, like the other prompts):
  - prefer official manufacturer data sheets and drawings;
  - never fetch PDF files, report PDF links in `drawing` with a `find` text from the page title;
  - every number carries `source` and `kind`;
  - x = width, y = height, z = depth (front towards +z);
  - end with exactly one ```json block in the format of `MeasureSheet`.

- [ ] **Step 1: Tests with fake blocks** (`SimpleNamespace(type=…, text=…)`).
  - `test_research_request_has_search_fetch_and_no_image`.
  - `test_parse_research_reads_the_json_and_the_allowed_urls`.
  - `test_parse_research_clips_and_repairs`.
  - `test_parse_research_without_json_is_a_schema_error`.
  - Cost: `searches × SEARCH_PRICE_USD` plus tokens, tested via `ClaudeModelCalls` in Task 8.
  - Live (marker `claude`): `test_real_research_finds_the_iphone_14_size`: `size_mm` ≈ (71.5, 146.7, 7.8) ± 1 and at
    least one source.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS (unmarked).
- [ ] **Step 5: Commit** `feat: Claude researches dimensions and drawings with sources`

### Task 8: CAD and check calls

**Files:** Extend `oi/modelprompts.py`, `oi/modelcalls.py`, `tests/test_modelcalls.py`

**Interfaces — Produces (modelcalls.py):**
- `CadProgram(shared: str, parts: list[CadPart], notes: str)`
- `CadRequest(model: str, category: str, sheet: MeasureSheet, drawings: list[Picture], jpeg: bytes | None,
  language: Lang)` and `CadResult(program, tokens…, cost_usd, latency_s, model)`
- `CheckAnswer(verdict: Literal["good", "fix"], issues: list[str], shared: str | None, parts: list[CadPart],
  remove: list[str])`
- `CheckRequest(model, sheet, drawings, jpeg, program: CadProgram, renders: list[bytes], errors: dict[str, list[str]],
  size_hint: str | None, round: int, rounds: int, language)` and `CheckResult(answer, tokens…)`
- Request builders:
  - `build_cad_request(s, req) -> dict`: content = sheet as JSON text, drawings as images, the crop, then the task;
    system `CAD_PROMPT` + `BOSL2_GUIDE`; schema `CAD_SCHEMA`.
  - `build_check_request(s, req) -> dict`: content = the renders labelled "vorn", "hinten", "rechts", "oben",
    drawings, crop, sheet, `scad_source(program)`, errors per part, size hint, "Runde n von N".
- Parsers:
  - `parse_cad(text) -> CadProgram`: limits from Global Constraints, colour `#rrggbb` else `#9aa0a6`, names clipped
    to 40 and made unique (" 2", " 3"), parts with empty code dropped; no part left raises `IdentifyError("schema")`.
  - `parse_check(text) -> CheckAnswer`.
- `apply_check(program, answer) -> CadProgram`: same name replaces, new names are appended, `remove` deletes; `shared`
  is replaced when not `None`.
- `scad_source(program) -> str`: the whole file, with every part as a commented section.
- `class ModelCalls(Protocol)`: `research`, `build_cad`, `check_cad`.
- `class ClaudeModelCalls(identifier: ClaudeIdentifier)`: uses `identifier.create(request, s.model_timeout_s)` and
  `cost_usd`.
- `class FakeModelCalls(research: MeasureSheet | IdentifyError | None = None, cad: CadProgram | IdentifyError | None
  = None, checks: list[CheckAnswer | IdentifyError] | None = None, costs: tuple[float, float, float] = (0, 0, 0))`
  - Records `research_requests`, `cad_requests`, `check_requests`.
  - `research=None` returns `MeasureSheet.estimated()`.
  - `checks` are popped in order; when empty, "good".
- `CAD_PROMPT`:
  - coordinates (origin centre, x right, y up, z towards the viewer = front, millimetres);
  - one part per visible component;
  - real colours;
  - use BOSL2 for roundings and cut-outs;
  - shared variables for main dimensions;
  - no `import`, no `include` besides the header, no `surface`.
- `CHECK_PROMPT`: compare renders with drawing and photo; list concrete deviations; return only changed parts;
  "good" when nothing important is off.
- `BOSL2_GUIDE`: the signatures and one example line each for `cuboid`, `cyl`, `prismoid`, `rect_tube`, `tube`,
  `offset_sweep`, `skin`, `rotate_extrude`, `hull`, `difference`, `attach`/`position`, `text` (for logos).

- [ ] **Step 1: Tests.**
  - `test_cad_request_carries_sheet_drawings_and_crop` (2 PNG drawings → media type image/png, crop image/jpeg,
    effort high, schema present).
  - `test_parse_cad_limits_colours_and_unique_names`.
  - `test_parse_cad_without_parts_is_a_schema_error`.
  - `test_check_request_labels_the_four_views_and_the_round`.
  - `test_apply_check_replaces_appends_and_removes`.
  - `test_scad_source_has_header_shared_and_every_part`.
  - `test_claude_model_calls_report_cost_and_use_the_model_timeout` (fake client like the existing identify tests;
    research cost includes 2 searches × 0.01).
  - `test_fake_model_calls_follow_the_script`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat: Claude writes and checks the CAD program`

### Task 9: The model builder

**Files:** Create `oi/builder.py`, `tests/test_builder.py`

**Interfaces — Consumes:** Tasks 2–8.

**Interfaces — Produces:**
- `Listener = Callable[[str, ModelStatus, int, ModelManifest | None], Awaitable[None]]` (model, status, round,
  manifest)
- `class ModelBuilder(settings, calls: ModelCalls, compiler: Compiler, store: ModelStore, budget: SessionBudget,
  call_log: CallLog | None, fetch=download.fetch, render=render_views, now=datetime.now)`
  - `listen(listener) -> Callable[[], None]`.
  - `state(model) -> tuple[ModelStatus, int, ModelManifest | None] | None`: a cached model is ("ready", rounds,
    manifest).
  - `async request(model, category, jpeg: bytes | None) -> None`:
    - cached, running or queued: nothing to do;
    - after `max_models_session` new builds: state "limit" and notify;
    - else "queued", notify, and start the worker.
  - `async rebuild(model) -> None`: only from "failed".
  - `async wait_idle()`, `async aclose()`.
- The job:

  ```
  researching → (drawing if sheet.drawing) → modeling → building → checking 1 → building → checking 2 → building
  → ready
  ```

  - Before each step: if `spent + reserve(step) > max_model_cost_usd`, skip it.
    - Before CAD, skipping means "failed".
    - Before a check it means "keep the current model" and `notes += " Budget erreicht."`.
  - A research `IdentifyError` gives `MeasureSheet.estimated()`. A CAD error gives "failed".
  - Recompile only parts whose code changed, or all parts when `shared` changed.
  - Every check gets `size_hint(size of the union of the part bounds, sheet.size_mm)` and the errors per part.
  - Parts still failing after the last round are dropped and named in `notes`. No part compiled gives "failed".
  - `size_mm` = `sheet.size_mm` if present, else the union of the part bounds.
  - verdict: "good" if a check said good, "fix" if rounds ran out, "unchecked" if no check ran.
  - Each call: `budget.calls += 1` when it starts, `budget.cost_usd += cost` when it ends; a log record with
    `track_id=-2`.

- [ ] **Step 1: Tests** (FakeModelCalls, FakeCompiler, `ModelStore(None)`, a fake `fetch` and a fake `render` that
  returns 4 PNG bytes; collect notifications in a list).
  - `test_a_good_first_check_ends_early_with_the_statuses_in_order` → researching, modeling, building, checking(1),
    ready; store has it; 1 check request.
  - `test_drawing_step_only_with_a_candidate`.
  - `test_compile_errors_go_to_the_next_check_and_broken_parts_drop_out` (broken stays broken → notes names it, model
    ready without it).
  - `test_nothing_compiles_means_failed`.
  - `test_research_error_means_estimated_measures`.
  - `test_research_over_the_cap_stops_before_cad` (costs (1.7, 0, 0) → failed, no cad request, budget cost 1.7).
  - `test_budget_ends_checks_early` (costs (0.5, 0.5, 0.4) with cap 1.60 → one check only, notes "Budget erreicht.").
  - `test_one_job_at_a_time_and_queue_order`.
  - `test_session_limit_after_five_new_models` (`max_models_session=1` → second model "limit"; a cached one is still
    ready).
  - `test_rebuild_only_after_failure`.
  - `test_calls_count_in_the_session_budget_and_the_log` (a fake CallLog collects records; request texts start with
    "model research:", "model cad:", "model check 1:").
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement. Listener errors are logged, never fatal.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat: the builder researches, models, compiles and checks one product at a time`

### Task 10: Pipeline and server

**Files:** Modify `oi/pipeline.py`, `oi/server.py`, `oi/__main__.py`, `tests/test_pipeline.py`,
`tests/test_server.py`, `tests/test_main.py` (if it builds the app)

**Interfaces — Consumes:** `ModelBuilder`, `ModelStore`, `ModelMsg`, `RebuildMsg`, `ScadCompiler`,
`compiler_problem`, `ensure_bosl2`, `ClaudeModelCalls`.

**Interfaces — Produces:**
- `Pipeline(…, models: ModelStore | None = None, builder: ModelBuilder | None = None)` replaces `shapes`.
  - `_want_model(product: Product, jpeg)` is called whenever the snapshot is certain: after an identification, after
    `_confirm`, after `_merge`.
  - Entry names are mapped per model. A cached manifest gives an immediate ready message; otherwise the current
    `builder.state` is sent, then `builder.request`.
  - Listener: every builder event goes to every mapped name as `ModelMsg`.
  - `RebuildMsg` goes to `builder.rebuild(model of that name)`.
  - `aclose` unsubscribes.
- `create_app(…, models: ModelStore | None = None, compiler: Compiler | None = None,
  model_calls: Callable[[Identifier | None], ModelCalls | None] = default_model_calls)`
  - The lifespan builds `app.state.builder` when models, compiler and calls exist, with an app-level
    `CallLog(settings.runs_dir, settings.log_calls)` and the shared budget.
  - `GET /models/{slug}/{file}` (before the static mount) answers with `app.state.models.file(...)`:
    `model/stl` or `text/plain; charset=utf-8`, else 404.
  - `app.state.model_notice` (German reason) is sent like the existing notice.
- `default_model_calls(identifier)`: `ClaudeModelCalls` for a `ClaudeIdentifier`, else `None` (fake mode builds no
  models).
- `__main__`: `models = None if fake else ModelStore(settings.model_cache)`.
  - The compiler is built only if there is no `compiler_problem` and `ensure_bosl2` succeeds.
  - Otherwise `compiler=None` and the notice "3D-Modelle aus: <Grund>".

- [ ] **Step 1: Tests.**
  - `test_a_certain_product_asks_the_builder_and_every_entry_hears_it` (readable model name → certain; two names for
    one model both get "queued"…"ready").
  - `test_a_likely_product_asks_nothing`.
  - `test_a_cached_model_is_ready_at_once_without_builder`.
  - `test_a_reconnected_pipeline_gets_the_running_status_and_the_result` (second Pipeline on the same builder).
  - `test_rebuild_message_reaches_the_builder`.
  - Server: `test_model_files_are_served_and_nothing_else` (200 for a listed part, 404 for `../manifest.json`, an
    unknown slug, `part-99.stl`).
  - `test_no_builder_in_fake_mode`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Full `uv run pytest -q`. Expected: all green.
- [ ] **Step 5: Commit** `feat: certain products get their precision model`

### Task 11: Browser

**Files:**
- Modify `web/src/protocol.ts` (drop TS `ShapeMsg`/`ShapePart`, add `RebuildMsg` to the client messages),
  `web/src/store.ts`, `web/src/store.test.ts`, `web/src/i18n.ts`, `web/src/hud/shapeMath.ts`,
  `web/src/hud/shapeMath.test.ts`, `web/src/hud/hologramScene.ts`, `web/src/hud/Hologram.tsx`,
  `web/src/hud/HologramFullscreen.tsx`, `web/src/hud/Sidebar.tsx`, `web/src/App.tsx`, `web/src/styles.css`
- Create `web/src/hud/modelText.ts` and its test

**Interfaces — Produces:**
- store: `models: Record<string, ModelMsg>` (case "model", reset on reconnect).
  `fullscreenView(s) -> { identity, model: ModelMsg, profile? } | null` (needs status ready with a manifest).
- shapeMath:
  - `partSize(p: ModelPart): Vec3`, `partCenter(p: ModelPart): Vec3`;
  - `fitDistance(size: Vec3, fovDegrees): number` (replaces the parts version);
  - `partGeometry`, `outlinePoints` and `partDescription` are removed; `spread`, `millimetres` and `formatSize` stay.
- modelText.ts:
  - `domain(url): string` ("https://www.apple.com/x" → "apple.com");
  - `sourceTag(m: ModelManifest, lang): string` (the spec's badge);
  - `progressText(status, round, rounds, lang): string` (spec §3; `round`/`rounds` filled in);
  - `kindText(kind, lang)`.
- hologramScene:
  - `loadModel(manifest): Promise<Model>`: `STLLoader().loadAsync("/models/<slug>/<file>")` per part.
  - Hologram look: fill opacity 0.28 in the part colour, `EdgesGeometry(geometry, 20)` in `EDGE`,
    `userData.part = index`.
  - `addLabels(model, manifest, lang)`: measure lines from `manifest.size_mm`, pins at `partCenter`.
- Sidebar:
  - The hologram section exists for levels likely, unsure and certain.
  - Without a `model` message it shows `model.waiting`.
  - With one it shows the progress text, a `limit` text, or `failed` plus the „Neu bauen“ button (`onRebuild(name)`
    → `{type: "rebuild", name}` in App).
  - When ready it shows the canvas, size, badge and ⤢.
- Fullscreen panel:
  - TEILE: number, name, `formatSize(partSize)`;
  - MASSE: label, value in mm, kind, source link;
  - QUELLEN: links;
  - then the profile and trivia as before.

- [ ] **Step 1: Tests.**
  - store: `test_model_messages_per_entry_and_the_fullscreen_needs_a_ready_model`.
  - modelText:
    - `test_domain_and_badge`: "CAD · Maße laut apple.com"; a sheet without `size_source` gives
      "CAD · Maße geschätzt";
    - `test_progress_texts` ("Prüfe gegen Zeichnung und Foto (Runde 1/2) …");
    - `test_kind_texts`.
  - shapeMath: `test_part_size_center_and_fit_distance`.
  - Remove the primitive tests (`each primitive …`, `an oval cylinder …`, `round parts …`, `every part is described …`).
- [ ] **Step 2:** Run `npm --prefix web test`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `npm --prefix web test` and `npm --prefix web run build`. Expected: green.
- [ ] **Step 5: Visual check.** Use Playwright against a throwaway preview with a manifest and two real STL parts
  from Task 4, served by vite plus a mocked `/models` path. Check the sidebar progress, the ready state and the
  fullscreen. Delete the throwaway files afterwards.
- [ ] **Step 6: Commit** `feat: the sidebar shows the precision model with its sources`

### Task 12: Live verification, docs, finish

**Files:** Modify `docs/superpowers/specs/2026-10-01-precision-model-design.md` (measured duration and cost),
`README.md`, `ERKLAERUNG.md`

- [ ] **Step 1: One real build** with a small script in the scratchpad: real `ClaudeModelCalls`, `ScadCompiler` and
  `ModelStore(settings.model_cache)`, for "Apple iPhone 14" with the crop `runs/2026-09-30_23-25-44/001_track72.jpg`.
  - Record duration per step, cost, rounds, verdict and drawing pages.
  - Screenshot the fullscreen via the preview.
  - Budget: at most 1.60 $; stop and report if a step misbehaves.
- [ ] **Step 2: Spec.** Replace the estimates in spec §3 (duration) and §9 (cost) with the measured values (marked
  „gemessen am …“).
- [ ] **Step 3: README and ERKLAERUNG.**
  - README: sub-project 6 in the list, the costs table (precision model), the stack (OpenSCAD-WASM, BOSL2,
    pypdfium2), the test counts, the `scad` marker.
  - ERKLAERUNG: a section on Teilprojekt 6 (what/how/why), glossary entries (OpenSCAD, BOSL2, STL, WebAssembly,
    Manifold, SSRF), new bugs found, an updated table of contents.
- [ ] **Step 4: Full verification.**
  - `uv run pytest -q`, `uv run pytest -q -m "model or scad"`, `npm --prefix web test`, `npm --prefix web run build`,
    `uvx ruff check --select F,E9 oi tests`.
  - Self-review of the whole branch against the spec.
- [ ] **Step 5: Commit, merge, push.** Commit `docs: the precision model, measured`, merge into main, push.
