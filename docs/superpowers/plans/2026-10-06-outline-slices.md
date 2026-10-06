# Umriss in Scheiben (Teilprojekt 8) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure the outline of every product in 20 height bands on the drawing, web photos and the camera photo,
cross-validate the bands, build to them and check the model band by band.

**Architecture:**
- `download.fetch_page` and `oi/pageimages.py` find product images on the found pages.
- The measure call returns `slices` per view.
- `oi/measure.py` turns them into a cross-validated `profile` and compares the built mesh with it.
- The builder adds the camera photo and the page images to the measuring, and passes profile and outline deviations
  on.

**Tech Stack:** Python 3.12 (stdlib html.parser, numpy), Anthropic SDK, React.

**Spec:** `docs/superpowers/specs/2026-10-06-outline-slices-design.md`

## Global Constraints

- **Constants:**
  - `SLICES = 20`, `AGREE = 0.08`, `AGREE_MIN_MM = 1.5`, `CENTRE_AGREE = 0.04`, `MAX_OUTLINE_DEVIATIONS = 10`;
  - `MAX_PAGES = 3`, `PAGE_LIMIT = 3_000_000`, `MAX_PHOTOS = 4`.
- **Source rank:** drawing 3, camera 2, photo 1.
- **Unchanged rules:**
  - The download rules (https, public addresses, ≤ 3 redirects).
  - The 1.60 $ cap, the reserves and 2 check rounds.
- **Old manifests** (no `profile`, photos with a view) load.
- **Checks:** ruff `--select F,E9,E402` clean, lines ≤ 120, pytest and Vitest green, web build ok.
- **Commits:** Co-Authored-By line, push to `origin main` at the end. No subagents.

## Review Focus

1. **A crate photo** (a different, wider shape) must not win against the camera and the drawing →
   `test_cross_validation_drops_the_outlier` (Task 3).
2. **Two disagreeing sources** → the higher rank wins → `test_two_sources_prefer_the_higher_rank` (Task 3).
3. **A band hidden by a hand** (`null`) is skipped, not zero → `test_hidden_bands_are_skipped` (Task 3).
4. **A page that is not HTML, too big, or not allowed** → no images, the build goes on →
   `test_fetch_page_rules` and `test_page_images_skip_failures` (Task 2).
5. **No camera photo and no pictures** → no measuring, as before → existing builder test (Task 5).

---

### Task 1: Contracts

**Files:** `oi/contracts.py`, `tests/test_contracts.py`, `tests/fixtures/protocol-examples.json`

**Produces:**
- `ProfileBand(y: Range, x: Range | None, z: Range | None, sources: int)`;
- `ModelManifest.profile: list[ProfileBand] = []`;
- `PhotoRef.view: PhotoView | None = None`.

- [ ] **Step 1: Test.** `test_old_manifest_still_loads` also asserts `manifest.profile == []`.
  `test_photo_without_view` checks that `PhotoRef(url="https://a/b.jpg")` has `view is None`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement, then regenerate the fixture.
- [ ] **Step 4:** PASS, full suite.
- [ ] **Step 5:** Commit.

### Task 2: Images from found pages

**Files:** `oi/download.py`, create `oi/pageimages.py`, `tests/test_download.py`, create `tests/test_pageimages.py`

**Produces:**
- `fetch_page(url, allowed, *, transport=None, resolve=None, timeout_s=30.0) -> str`.
  - Implemented by giving `fetch` a `limits: Mapping[str, int] = LIMITS` parameter.
  - Decodes UTF-8 with replacement.
- `images_in_html(html: str, page: str) -> list[str]`:
  - JSON-LD `image` (string, list, or `{url}`, at any depth), then `og:image`, `og:image:url`,
    `og:image:secure_url`, `twitter:image`;
  - absolute, https only, without the page itself, in that order, unique.
- `async page_images(pages: list[str], allowed: set[str], fetch_page=download.fetch_page) -> list[str]`:
  - the first `MAX_PAGES` allowed pages;
  - a failing page is logged and skipped.

- [ ] **Step 1: Tests.**
  - `test_fetch_page_rules`: html ok (decoded); `image/png` refused; over 3 MB refused; not allowed refused.
  - `test_images_in_html`:
    - JSON-LD with `"image": "https:\/\/cdn/a.jpg"`, a list, `{"url": …}` nested in `@graph`;
    - og/twitter meta; relative `/img/b.png` made absolute;
    - `http://` dropped; the page's own URL dropped; duplicates once; broken JSON ignored.
  - `test_page_images_skip_failures`: 4 pages, the 2nd raising `DownloadError` → images of pages 1 and 3 (the 4th
    is never asked).
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS, full suite.
- [ ] **Step 5:** Commit.

### Task 3: Slices, profile, cross-validation, outline check

**Files:** `oi/measure.py`, `tests/test_measure.py`

**Produces:**
- `ViewBoxes.slices: list[tuple[float, float] | None] = []` (frozen dataclass default via `field`).
- `parse_measure` reads `slices`:
  - only for front, back and side views;
  - exactly 20 entries, else `[]`;
  - a bad entry becomes `None`.
- `profile(views, sizes_px, size_mm, ranks: list[int]) -> list[ProfileBand]`: 20 bands top to bottom; bands
  without any value are left out.
- `profile_text(bands) -> str`.
- `outline_deviations(triangles: np.ndarray, bands, size_mm) -> list[str]`: `triangles` has shape (n, 3, 3) and is
  the whole model.

- [ ] **Step 1: Tests.** Picture 2000 × 1000 px and front object (0.1, 0.0, 0.9, 0.97) unless stated.
  - `test_front_slices_in_millimetres`: slice 0 = [0.4, 0.6] → band y 43.65…48.5, x −20.0…20.0.
  - `test_side_slices_give_depth`: `side-front-right` → z.
  - `test_hidden_bands_are_skipped`: all `None` except slice 5 → only that band.
  - `test_cross_validation_drops_the_outlier`: camera 40 mm, drawing 40.5 mm, crate photo 70 mm wide → x from the two
    agreeing, `sources == 2`.
  - `test_two_sources_prefer_the_higher_rank`: photo 70 mm vs camera 40 mm → 40 mm, `sources == 1`.
  - `test_parse_slices`: 19 entries → `[]`; `[0.6, 0.4]` → `None`; top view slices ignored.
  - `test_outline_deviations_measure_each_band`:
    - a 160 × 97 × 55 box mesh built from `cube_stl` triangles;
    - a band measured 40 mm wide → a line `height 98 % (…): x model -80.0…80.0, measured -20.0…20.0 mm (off by 60.0 mm)`;
    - a matching band → no line; at most 10 lines.
  - `test_profile_text`: lines like `height 98 % (y 43.6…48.5 mm): x -20.0…20.0 mm (2 pictures)`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement as spec §3.4–3.7.
- [ ] **Step 4:** PASS, full suite.
- [ ] **Step 5:** Commit.

### Task 4: Prompts and requests

**Files:** `oi/modelprompts.py`, `oi/modelcalls.py`, `tests/test_modelcalls.py`

**Produces:**
- `MEASURE_SCHEMA` views gain `slices` (array of `null` or number arrays).
- `MEASURE_PROMPT` explains the 20 slices and `null`.
- `CAD_PROMPT` gets the outline rule. `CHECK_PROMPT` gets "Outline deviations".
- `CadRequest.outline: str = ""`; `CheckRequest.outline: str = ""` and
  `CheckRequest.outline_deviations: list[str] = []`.
- `_photos` labels a view `None` as "view unknown".

- [ ] **Step 1: Tests.**
  - The CAD content holds the outline text.
  - The check content holds `"Outline deviations (fix them):\n…"`.
  - Empty → absent.
  - `MEASURE_SCHEMA` has `slices`.
  - `_photos` with `None` → `"Reference photo (view unknown):"`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS, full suite.
- [ ] **Step 5:** Commit.

### Task 5: Builder

**Files:** `oi/builder.py`, `tests/test_builder.py`

- [ ] **Step 1: Tests** (fake fetch serves PNGs; a `fetch_page` fake serves HTML with one JSON-LD image).
  - `test_camera_photo_is_measured_without_web_pictures`: no drawing or photos, but a size and a crop → a measure
    request whose last picture is labelled `camera photo of the real object …`.
  - `test_page_images_join_the_photos`:
    - the sheet's source page gives an image;
    - the measure pictures contain `photo, view unknown`;
    - the manifest sheet lists the page image with `view None`.
  - `test_profile_reaches_cad_check_and_manifest`:
    - the fake measure has front slices;
    - `cad_requests[0].outline` names `height`;
    - `check_requests[0].outline_deviations` is not empty (10 mm cube vs 160 mm);
    - `manifest.profile` is not empty.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3: Implement.**
  - `ModelBuilder(..., fetch_page=download.fetch_page)`.
  - Ranks per picture: drawing 3, photo 1, camera 2.
  - Mesh for the check: `np.concatenate` of the compiled parts' triangles.
- [ ] **Step 4:** PASS, full suite.
- [ ] **Step 5:** Commit.

### Task 6: Browser

**Files:** `web/src/protocol.ts`, `web/src/hud/modelText.ts`, `web/src/hud/HologramFullscreen.tsx`, tests and fixtures.

- [ ] **Step 1: Tests.**
  - `sourceTag` with a profile of max `sources` 3 → `"… · Umriss aus 3 Bildern"` (en `"… · outline from 3 pictures"`).
  - `progressText("measuring")` → `"Vermesse Teile und Umriss …"`.
  - `viewText(null, "de")` → `"Foto"`. The QUELLEN list then shows "Foto · domain" for these.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implement. TS types: `ProfileBand`, `ModelManifest.profile`, `PhotoRef.view: PhotoView | null`.
- [ ] **Step 4:** Tests PASS, build ok.
- [ ] **Step 5:** Commit.

### Task 7: Live build and docs

- [ ] **Step 1: Live build.**
  - Rebuild "mineau Maria-Quelle, medium" from `runs/2026-10-06_21-26-28/009_track-2.jpg`.
  - Print statuses, cost, the number of bands and their sources, and the deviations.
  - Render the old and the new model.
- [ ] **Step 2: Docs.**
  - README: the measuring bullet mentions the outline and the camera.
  - `ERKLAERUNG.md`: a section for sub-project 8, and bug 26 (the bottle without photos).
- [ ] **Step 3:** Full checks, commit, push.
