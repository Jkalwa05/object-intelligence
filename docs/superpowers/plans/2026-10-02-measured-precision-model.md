# Vermessenes Präzisionsmodell (Teilprojekt 7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure every visible part of a product on reference images from the web, build the CAD model to those
millimetres, check it part by part, and keep a model Jonas likes.

**Architecture:**
- The research also returns product photos.
- The download accepts SVG (rendered with resvg) and WebP, and links found on fetched pages.
- A new measure call gives boxes per view. The pure module `oi/measure.py` turns them into a part map in mm and later
  into a deviation list for the checks.
- A `kept` flag in the manifest decides between reusing a model and building it anew.

**Tech Stack:** Python 3.12 (uv, pydantic, httpx, Pillow, resvg-py), Anthropic SDK, React + three.js, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-02-measured-precision-model-design.md`

## Global Constraints

- **Claude model:** every precision-model call goes through `ClaudeModelCalls`, which already sends
  `Settings.cad_model` (Opus). `same_product` does too.
- **Budget:**
  - Cap 1.60 $.
  - `RESERVE = {"research": 0.45, "measure": 0.25, "cad": 0.45, "check": 0.35}`.
  - 2 check rounds, at most 5 new models per server run.
- **Download:** only https, public addresses, ≤ 3 redirects. Images (png, jpeg, webp, svg+xml) ≤ 8 MB, PDF ≤ 60 MB.
- **Measuring constants (spec §5–6):**
  - `ASPECT_TOLERANCE = 0.12`, `DEPTH_TOLERANCE = 0.25`, `OUTSIDE = 0.02`;
  - `MIN_TOLERANCE_MM = 1.5`, `RELATIVE_TOLERANCE = 0.02`;
  - `MAX_DEVIATIONS = 20`, `MAX_VIEWS = 6`, `MAX_VIEW_PARTS = 40`, `MAX_PHOTOS = 4`.
- **Views:** `"front" | "back" | "side-front-left" | "side-front-right" | "top"` (top: front edge at the bottom).
- **Old manifests and sheets** (without `kept`, `part_map`, `photos`) must still load.
- **Texts:** UI texts German and English as in spec §8. Code comments in English. Lines ≤ 120.
- **Checks:** ruff `--select F,E9,E402` clean, `uv run pytest -q` and `npm --prefix web test` green, `npm --prefix web run build` ok.
- **Commits:** authored by Jonas, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No subagents.

## Review Focus

1. **A drawing with several views in one image** (dimensions.com): every view is measured with its own object box →
   `test_one_picture_with_three_views` (Task 3).
2. **Sticks that stick out** make the depth box larger than the known depth: still measured (≤ 25 %), scaled by the
   known axis → `test_side_view_scales_by_height_and_tolerates_protruding_parts` (Task 3).
3. **An unkept stored model after a restart:** built anew once per run, not on every pick-up; without a builder it is
   still shown → `test_unkept_model_is_rebuilt_once_per_run`, `test_without_builder_stored_models_still_show`
   (Task 6).
4. **Old manifests** load with `kept=False`, `part_map=[]`, `photos=[]` → `test_old_manifest_still_loads` (Task 1).
5. **A failing measure call** leaves an empty part map, and the build goes on → `test_measure_error_builds_without_map`
   (Task 5).

---

### Task 1: Contracts and research photos

**Files:** `oi/contracts.py`, `oi/modelcalls.py`, `oi/modelprompts.py`, `tests/test_contracts.py`,
`tests/test_modelcalls.py`

**Produces:**
- `PhotoView` (Literal of the 5 views); `PhotoRef(url: str, view: PhotoView)`; `MeasureSheet.photos: list[PhotoRef] = []`.
- `Range = tuple[float, float]`; `MeasuredPart(name: str, x: Range | None, y: Range | None, z: Range | None, views: int)`.
- `ModelManifest.kept: bool = False`, `ModelManifest.part_map: list[MeasuredPart] = []`.
- `ModelStatus` gains `"measuring"`.
- `KeepMsg(type="keep", model: str, kept: bool)` in `AnyClientMsg`.
- `parse_research` fills `photos`. `_found_urls` also returns https URLs written in the text of fetched pages.

- [ ] **Step 1: Write the failing tests.**
  - `test_old_manifest_still_loads`: the JSON of a manifest without `kept`/`part_map`/`sheet.photos` validates, with
    `kept is False`, `part_map == []`, `sheet.photos == []`.
  - `test_keep_message_parses`: `{"type": "keep", "model": "Sony DualShock 3", "kept": true}` →
    `KeepMsg(model="Sony DualShock 3", kept=True)`.
  - `test_research_reads_photos`:
    - an answer with 6 photos keeps the first 4 valid ones;
    - it drops `http://`, `view: "bottom"` and a missing `url`;
    - result: `[PhotoRef(url="https://a/1.png", view="front"), …]`.
  - `test_links_in_fetched_pages_are_found`: a `web_fetch_tool_result` whose document text contains
    `![x](https://cdn.example.com/d.svg)` and `https://cdn.example.com/p.webp.` adds both URLs, without the trailing dot.
    It ignores `http://` links.
- [ ] **Step 2:** `uv run pytest -q tests/test_contracts.py tests/test_modelcalls.py` → FAIL (names missing).
- [ ] **Step 3: Implement.**
  - `RESEARCH_PROMPT`:
    - the JSON gains `"photos": [{"url": "https://...", "view": "front"}]`;
    - one rule: up to 4 photos of exactly this product, each straight from one side with the whole product in view
      on a plain background;
    - prefer official product or press images, else Wikipedia/Wikimedia or large retailers;
    - only URLs from the search or fetch results;
    - name the 5 views and the top convention.
  - URL regex: `https://[^\s"'<>()\[\]]+`, stripped of `.,;:`.
- [ ] **Step 4:** the same command → PASS; then `uv run pytest -q` → all green.
- [ ] **Step 5:** commit `feat: research returns product photos; links on fetched pages may be downloaded`.

### Task 2: Download SVG, WebP and photos

**Files:** `pyproject.toml` (`uv add resvg-py==0.5.0`), `oi/download.py`, `oi/drawings.py`, `tests/test_download.py`,
`tests/test_drawings.py`

**Produces:**
- `LIMITS` gains `image/webp` and `image/svg+xml` (8 MB).
- `_svg_png(data: bytes) -> bytes`: long edge `LONG_EDGE` (render with `width=2000`; if taller than wide, with
  `height=2000`).
- `_scaled_image` turns SVG into `(png, "image/png")`.
- `picture_size(picture: Picture) -> tuple[int, int]`.
- `async photo_pictures(photos: list[PhotoRef], allowed: set[str], fetch: Fetch = download.fetch) -> list[tuple[Picture, PhotoView]]`:
  in order, at most 4, a failed one is logged and skipped.

- [ ] **Step 1: Write the failing tests.**
  - `test_svg_and_webp_are_accepted`: a mock transport answering `image/svg+xml` and `image/webp` → returned with
    their media type; `image/gif` still raises `DownloadError`.
  - `test_svg_drawing_becomes_a_png`: a 300×100 SVG with a rect and the text "160 mm" → `drawing_pictures` returns one
    `image/png` whose `picture_size` is `(2000, 667)` (±1).
  - `test_photo_pictures_skip_failures`: 5 photos, the 2nd raising `DownloadError` → 3 pictures from photos 1, 3, 4,
    with views kept (the 5th is never fetched).
  - `test_broken_svg_means_no_drawing`: `b"<svg"` → `([], [])`.
- [ ] **Step 2:** `uv run pytest -q tests/test_download.py tests/test_drawings.py` → FAIL.
- [ ] **Step 3: Implement.** `resvg_py.svg_to_bytes(svg_string=..., width=...)`. A resvg error (exception) counts like
  `ValueError` in `drawing_pictures`.
- [ ] **Step 4:** PASS; full suite green.
- [ ] **Step 5:** commit `feat: SVG drawings (resvg), WebP and product photos are loaded`.

### Task 3: The pure measuring module

**Files:** create `oi/measure.py`, `tests/test_measure.py`

**Produces:**
- `Box2 = tuple[float, float, float, float]` (left, top, right, bottom as fractions).
- `ViewBoxes(picture: int, view: PhotoView, object: Box2, parts: list[tuple[str, Box2]])`.
- `parse_measure(text: str, pictures: int) -> tuple[list[ViewBoxes], str]`: invalid JSON raises
  `IdentifyError("schema")`.
- `part_map(views, sizes_px: list[tuple[int, int]], size_mm: Vec3) -> list[MeasuredPart]`.
- `map_text(parts) -> str`.
- `deviations(built: dict[str, tuple[Vec3, Vec3]], parts, size_mm: Vec3) -> list[str]`.

- [ ] **Step 1: Write the failing tests.** Sizes (160, 97, 55), pictures 2000×1000 px unless stated.
  - `test_front_view_in_millimetres`: object box (0.1, 0.0, 0.9, 0.97) → 1600×970 px, kx = ky = 0.1. A part at
    (0.1, 0.0, 0.2, 0.097) → x −80.0…−60.0, y 38.8…48.5, within 0.01.
  - `test_back_view_mirrors_x`: the same box as `back` → x 64.0…80.0.
  - `test_side_view_scales_by_height_and_tolerates_protruding_parts`:
    - object 640 px wide × 970 px high → k = 0.1, depth 64 mm vs 55 (+16 %, kept);
    - a part at the right edge in `side-front-right` → z ends at +32.0;
    - the same part in `side-front-left` → z starts at −32.0.
  - `test_top_view_gives_x_and_z`: object 1600×550 px → k = 0.1; a part in the bottom-left corner box → x −80…, z …+27.5.
  - `test_views_out_of_proportion_are_left_out`: a front box with kx/ky = 1.25 → `[]`; a side box with depth 90 mm →
    `[]`.
  - `test_one_picture_with_three_views`: three `ViewBoxes` with `picture=1` and different boxes all contribute; a
    part in front and top gets x averaged from both and `views == 2`.
  - `test_names_merge_case_and_space_insensitively`: `"Dreieck-Taste"` and `" dreieck-taste "` → one part, with the
    first spelling.
  - `test_parts_outside_the_object_are_dropped`: a box 5 % right of the object → absent.
  - `test_parse_measure_drops_bad_boxes`: wrong length, values outside 0…1, left ≥ right, unknown view, picture 0
    or > `pictures`, more than 6 views / 40 parts → dropped or cut. Not JSON → `IdentifyError`.
  - `test_map_text_lines`: `"Dreieck-Taste: x 44.0…50.0, y 20.1…26.0 mm (2 views)"`, and `None` axes are left out.
  - `test_deviations_tolerance_missing_and_order`:
    - built boxes centred by their union;
    - x tolerance = max(1.5, 3.2) = 3.2;
    - a part 2.0 mm off in x → no line;
    - 4.0 mm off → `"…: x model …, measured … mm (off by 4.0 mm)"`;
    - a missing part → `"Steuerkreuz: missing in the model (measured x …)"`;
    - order: largest first; 25 offenders → 20 lines.
- [ ] **Step 2:** `uv run pytest -q tests/test_measure.py` → FAIL (module missing).
- [ ] **Step 3: Implement.**
  - Spec §5.3 table; origin = centre of each view's object box.
  - h and v are the distances from that centre in px × k, rightwards and downwards.
  - Averages per axis over the views that show the axis.
- [ ] **Step 4:** PASS; full suite green.
- [ ] **Step 5:** commit `feat: measure parts on reference images and compare the model with them`.

### Task 4: The measure and same-product calls; photos, map and deviations in CAD and check

**Files:** `oi/modelcalls.py`, `oi/modelprompts.py`, `tests/test_modelcalls.py`

**Produces:**
- `MeasureRequest(model, sheet, pictures: list[tuple[Picture, str]], language)`, `MeasureResult(views, notes, input_tokens, output_tokens, cost_usd, latency_s, model)`
  and `build_measure_request`.
- `SameProductRequest(model: str, candidates: list[str], language)`, `SameProductResult(match: str | None, …tokens, cost, latency, model)`,
  `build_same_product_request` and `parse_same_product(text, candidates) -> str | None`.
- `CadRequest` gains `photos: list[tuple[Picture, PhotoView]] = []` and `part_map: str = ""`.
- `CheckRequest` gains the same plus `deviations: list[str] = []`.
- `ModelCalls`, `ClaudeModelCalls` and `FakeModelCalls` gain `measure` and `same_product`. The fake takes
  `measure: list[ViewBoxes] | IdentifyError | None` and `same: str | None | IdentifyError`, and its
  `costs` grow to 4 values (research, measure, CAD, check).

- [ ] **Step 1: Write the failing tests.**
  - `test_measure_request_numbers_the_pictures`:
    - texts `"Picture 1 (technical drawing page 1):"` and `"Picture 2 (photo, front):"` before each image;
    - schema `MEASURE_SCHEMA`; `max_tokens` 16000; effort high on Opus;
    - the model is `cad_model` through `ClaudeModelCalls`.
  - `test_measure_call_parses_views_and_costs` (StreamClient as in the existing cost test) → views parsed, cost at
    Opus prices.
  - `test_same_product_matches_only_a_candidate`: `{"match": "Sony DualShock 3"}` → that name; an unknown name or
    `null` → `None`; not JSON → `IdentifyError`.
  - `test_cad_and_check_requests_carry_photos_map_and_deviations`:
    - the CAD content has `"Reference photo (front):"` + image and the part map text;
    - the check content has the photos, `"Measured deviations (fix them):"` with the lines, and the map;
    - empty map → no such texts.
  - The existing tests stay green; the fake cost tuple is updated where the tests pass `costs`.
- [ ] **Step 2:** `uv run pytest -q tests/test_modelcalls.py` → FAIL.
- [ ] **Step 3: Implement.**
  - `MEASURE_PROMPT` as spec §5.1.
  - `SAME_PRODUCT_PROMPT`: is the new name the same product (model and generation) as one of the candidates? Answer
    with that exact candidate or null.
  - `CAD_PROMPT` and `CHECK_PROMPT` each get one rule: use the part map's names and millimetres; fix the listed
    deviations; reference photos show the real product.
- [ ] **Step 4:** PASS; full suite green.
- [ ] **Step 5:** commit `feat: measure call, product-name check, and photos, map and deviations for CAD and check`.

### Task 5: The builder measures and checks with numbers

**Files:** `oi/builder.py`, `tests/test_builder.py`

**Consumes:** Tasks 1–4.

- [ ] **Step 1: Write the failing tests**, with the builder helpers in `tests/test_builder.py`, a fake fetch that serves
  PNGs for the drawing and the photos, and a sheet with size (160, 97, 55) and two photos.
  - `test_measuring_step_feeds_cad_and_checks`:
    - statuses `researching, drawing, measuring, modeling, building, checking, ready`;
    - `cad_requests[0].part_map` contains a measured name;
    - `check_requests[0].deviations` lists that part, because the fake CAD cube is far off;
    - the manifest `part_map` is not empty, and the notes say `Noch 1 Abweichungen` / `1 deviation` style text
      (German: `Noch N Abweichungen über der Toleranz.`).
  - `test_no_pictures_or_no_size_means_no_measuring`: no drawing and no photos → no `measuring` status, no measure
    request; the same with `size_mm=None`.
  - `test_measure_error_builds_without_map`: the fake measure raises `IdentifyError("api")` → the model is still
    ready, with `part_map == []`.
  - `test_measure_respects_the_reserve`: research cost 1.20 → the measure is skipped (1.20 + 0.25 > 1.60), and the
    build stops before CAD as before.
- [ ] **Step 2:** `uv run pytest -q tests/test_builder.py` → FAIL.
- [ ] **Step 3: Implement.**
  - Photos are loaded in the `drawing` step.
  - Labels: `technical drawing page n` and `photo, <view>`.
  - `sizes_px` come from `picture_size`.
  - Built boxes come from `bounds(read_stl(stl))` per compiled part.
  - The final deviations are computed in `_finish` from the kept parts.
- [ ] **Step 4:** PASS; full suite green.
- [ ] **Step 5:** commit `feat: the builder measures the parts and checks the model against them`.

### Task 6: Keep a model, build the others anew

**Files:** `oi/modelstore.py`, `oi/builder.py`, `oi/pipeline.py`, `tests/test_modelstore.py`, `tests/test_builder.py`,
`tests/test_pipeline.py`

**Produces:**
- `ModelStore.set_kept(model: str, kept: bool) -> ModelManifest | None` (memory and disk);
  `ModelStore.kept() -> list[ModelManifest]` (memory and every folder on disk).
- `ModelBuilder.request` skips only kept stored models or names already asked for in this run.
- `ModelBuilder.state` returns `None` for an unkept stored model that was not asked for in this run.
- `async ModelBuilder.kept(model: str) -> ModelManifest | None`: own name first; else one `same_product` call over
  the other kept names, cached per normalised name for the run. An `IdentifyError` counts as no match. The call is
  logged as `same product`.
- `Pipeline` handles `KeepMsg` and follows spec §7 in `_want_model`.

- [ ] **Step 1: Write the failing tests.**
  - `test_keep_is_stored_and_listed` (modelstore): `set_kept("Apple iPhone 14", True)` → returned manifest `kept`; a
    new `ModelStore(tmp_path)` reads it as kept; `kept()` lists exactly it; an unknown model → `None`.
  - `test_unkept_model_is_rebuilt_once_per_run` (builder):
    - a stored unkept model → `state()` is `None`;
    - `request()` builds; a second `request()` does nothing;
    - after the build `state()` is ready with the new manifest.
  - `test_kept_model_is_never_rebuilt` (builder): stored kept → `request()` does nothing and `state()` is ready.
  - `test_kept_matches_other_names_once` (builder):
    - kept "Sony DualShock 3";
    - `kept("Sony PlayStation 3 DualShock 3")` with the fake `same` = "Sony DualShock 3" → that manifest;
    - a second call does not ask again;
    - with no kept models → `None` without a call.
  - `test_keep_message_updates_every_entry` (pipeline): a ready model shown under two names → `KeepMsg` → store kept,
    and both entries get a `ModelMsg` with `manifest.kept`.
  - `test_without_builder_stored_models_still_show` (pipeline): no builder, stored unkept → ready message.
- [ ] **Step 2:** `uv run pytest -q tests/test_modelstore.py tests/test_builder.py tests/test_pipeline.py` → FAIL.
- [ ] **Step 3: Implement.** When a kept model is shown under another name, register that entry under the kept model's
  normalised name too, so later keep messages reach it.
- [ ] **Step 4:** PASS; full suite green.
- [ ] **Step 5:** commit `feat: keep a precision model; models not kept are built anew once per run`.

### Task 7: Browser

**Files:**
- `web/src/protocol.ts`, `web/src/hud/modelText.ts`, `web/src/hud/HologramFullscreen.tsx`, `web/src/hud/Sidebar.tsx`;
- `web/src/App.tsx`, `web/src/i18n.ts`, `web/src/styles.css`;
- `web/src/hud/modelText.test.ts`, test fixtures that build manifests.

**Produces:**
- Types `PhotoRef`, `MeasuredPart`, `KeepMsg`; `ModelManifest.kept/part_map`; `MeasureSheet.photos`; `"measuring"`.
- `sourceTag` appends ` · N Teile vermessen` / ` · N parts measured`.
- `progressText` covers `measuring`, plus the new `drawing` and `checking` texts of spec §8.
- `viewText(view, lang)`.
- Full screen: an `onKeep(model: string, kept: boolean)` prop and a keep pill next to the tag (`aria-pressed`). The
  photos are listed under QUELLEN.

- [ ] **Step 1: Write the failing tests** (`modelText.test.ts`).
  - `sourceTag` with 18 measured parts → `"CAD · Maße laut dimensions.com · 18 Teile vermessen"`; with none → as before.
  - `progressText("measuring", 0, "de")` → `"Vermesse die Teile auf Zeichnung und Fotos …"`.
  - `viewText("side-front-left", "de")` → `"Seite"`.
- [ ] **Step 2:** `npm --prefix web test` → FAIL.
- [ ] **Step 3: Implement.**
  - The pill uses `.pill`. When kept, it gets a green style (`.pill.kept`).
  - App sends `{type: "keep", model, kept}`.
- [ ] **Step 4:** `npm --prefix web test` PASS and `npm --prefix web run build` ok.
- [ ] **Step 5:** commit `feat: progress of the measuring, measured parts in the tag, keep button`.

### Task 8: Existing models, live build, docs

- [ ] **Step 1:** Set `kept: true` on `apple-iphone-14`, `apple-iphone-15` and `neosupps-creatine-monohydrate` through
  `ModelStore(...).set_kept(manifest.model, True)` in a scratchpad script. Check the manifests.
- [ ] **Step 2: Live build.**
  - `PYTHONPATH=$(pwd)` scratchpad script: the real `ModelBuilder` with `ClaudeModelCalls`, the real compiler and an
    in-memory `ModelStore`.
  - Product `"Sony PlayStation 3 DualShock 3"`, crop from `runs/2026-10-02_15-30-14/002_track-2.jpg`.
  - Print statuses, cost, part-map size and deviations.
  - Render four views of old and new with the scratchpad three.js harness.
  - Expected: drawing used (`drawing` + measured parts > 10), cost ≤ 1.60 $.
- [ ] **Step 3: Docs.**
  - README: the measuring step in the precision-model section, and the keep button.
  - `ERKLAERUNG.md`: the new step, the part map, the deviation check, keep. Add bug 24: the SVG drawing that never
    arrived.
- [ ] **Step 4:** full checks; commit `docs: the measured precision model`; push to `origin main`.
