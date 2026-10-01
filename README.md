# Object Intelligence

Hold any object up to your Mac's camera. Object Intelligence finds and tracks everything in view, picks the object
you are holding, and identifies it as precisely as the visible evidence honestly allows. When two products look
alike, it says so, and it asks for the one view that would tell them apart ("Show me the bottom side: Lightning or
USB-C?").

Sub-projects 1 ("see and identify"), 2 ("product profile") and 3 ("hologram") are complete. Voice questions and the
final polish follow in their own sub-projects.

## Principles

- **Levels, not fake percentages.** The HUD says *certain*, *likely*, *unsure* or *category only*. A number that a
  language model makes up ("87 %") is not a measured probability, so exact shares only appear in the telemetry
  corner. A result becomes *certain* only through two independent views or a model name that is readable on the
  object.
- **Detection and identification are separate.** A local open-vocabulary detector (YOLOE-26, prompt-free) with
  BoT-SORT tracking runs on every frame on the Mac GPU. Only the focus object goes to Claude, as a crop in which
  everything outside the object's own outline is painted grey. A crop that could show a person is never sent: the
  focus may not cover most of a person, sit in a person's head zone or lie over a face. The one whole frame that
  leaves the Mac, for naming the background after a calibration, has every person painted grey first.
- **Costs are bounded and visible.** At most 4 calls per object and 150 per session; every call is logged in `runs/`
  with the crop, the answer, tokens, cost and latency. A measured call with Claude Opus 5.5 cost about 1.7 cents.

## How it works

```
Browser (web/, React + TypeScript)                  Python (oi/, FastAPI)
┌───────────────────────────┐  binary: JPEG 1280×720  ┌───────────────────────────────────────┐
│ camera (getUserMedia)     │ ─────── ≤ 12/s ───────▶ │ ingest:     only the newest frame     │
│ video at 30–60 fps        │                         │ perception: YOLOE-26 PF + BoT-SORT    │
│ HUD canvas + sidebar      │ ◀──── tracks ────────── │ focus:      which object is held      │
│ telemetry, voice          │ ◀── identity, telemetry │ views:      sharp, new views only     │
└───────────────────────────┘                         │ trigger:    when to ask Claude        │
                                                      │ identify:   Claude, structured output │
                                                      │ belief:     evidence → honest level   │
                                                      └───────────────────────────────────────┘
```

The decision logic (focus, views, trigger, evidence book) is plain Python with unit tests; the detector and Claude
sit behind small interfaces with fakes, so the whole pipeline is tested without a camera, a model or a network.

## Setup

macOS on Apple Silicon, [uv](https://docs.astral.sh/uv/) and Node.js:

```bash
uv sync
npm --prefix web install
npm --prefix web run build
cp .env.example .env   # then put your Anthropic API key into .env (it never goes into git)
```

The YOLOE weights (about 38 MB) download on the first start. Instead of `.env` you can also set `ANTHROPIC_API_KEY`
or log in with `ant auth login`. Without any key the app runs in local mode: boxes, IDs and coarse labels only.

## Run

```bash
uv run python -m oi                 # opens http://127.0.0.1:8766
uv run python -m oi --fake-claude   # canned answers without API calls (tests)
uv run python -m oi --no-browser --port 8766
```

For the first five seconds after start the scene is calibrated: everything that stays put (lamp, door, shelf) is
frozen. Then one Claude call names the whole background at once and says where each thing is ("Pendelleuchte",
"Raumspartreppe", "Bücherregal"), from a single frame in which every person is painted grey. These markers (violet)
never flicker and can never become the focus; press `R` to calibrate again. Without Claude the detector's own labels
stay.

Your hands get a cyan outline as soon as they are confirmed: Apple's Vision framework must be sure, see at least 6 of
the 21 hand joints and find the hand in two frames in a row. Only the object your fingers lie on (at least three
joints on it) gets a box (neon green), and only that object goes to Claude, as a crop in which everything outside its
outline is grey. You are never marked otherwise: not your face, hair, glasses, shirt or necklace (OpenCV's YuNet face
detector and a body zone keep them out, and whatever lies in the body zone and reaches the bottom edge of the
picture counts as worn, never as held). If two candidates look alike from one side, its entry asks for the view that
separates them, for example "Zeig mir bitte die Unterseite" for iPhone 14 (Lightning) and 15 (USB-C). Nobody has to
hold still: a snapshot, the sharpest frame of half a second, is taken from the video. If the tracker loses the object
for a moment and gives it a new number, entry, result and call count stay (same size and colours, gone at most 3 s).

Every identified object stays pinned in a sidebar on the right. The one in your hand is expanded on top, linked to
its box by a thin green line; the others collapse and open again with a click. An expanded entry shows the
identification, the hologram and the profile. If it stays *unsure* ("iPhone 14 or 15?"), tap the right candidate:
it becomes *certain*, marked *von dir bestätigt*, and its profile and hologram follow.
When a new object gets its first answer, Claude compares it once with the last three objects (small object-only
crops): if it is one of them seen from another side, the two entries merge into one, and two sides together can make
it *certain*. Objects in view at the same time are never merged.

- **Hologram:** once an object is at least *likely*, Claude describes its shape as primitives in millimetres (from its
  own knowledge and the object-only crop). The browser builds a true-to-scale model with three.js: neon-green edges,
  turning slowly, draggable, with its size ("71,5 × 146,7 × 7,8 mm"), marked *vereinfacht · laut Claude*.
- **Profile:** a short description (read aloud once when the voice is on), 4 to 8 technical facts, release date and
  launch price, and one or two things worth knowing, from Claude's own knowledge. There are no sources, so it always
  says *laut Claude*; if Claude does not know the exact model, it says so instead of guessing.

Profiles and holograms cost one call each per model, ever: they are kept in `cache/`.

There are no hints like "Bitte ganz ins Bild": whether the object gets a box is the feedback. The voice is off
until you press `M`.

Keys: `M` switches the voice on and off, `D` shows the telemetry (including which quality check a crop fails), `S` toggles the mirror
view, `R` calibrates the scene again. Settings such as `OI_MODEL=claude-sonnet-5-5` (faster), `OI_LANGUAGE=en` or
`OI_MIN_SHARPNESS` are read from the environment or `.env`. `--fake-claude` gives canned answers without any API call;
it is meant for the automated tests, real identification needs Claude.

## Tests

```bash
uv run pytest               # all logic, no model, no network
uv run pytest -m model      # loads the real YOLOE weights
uv run pytest -m claude     # one real Claude call, about 2 cents
npm --prefix web test       # browser logic (geometry, sidebar state, hologram maths, voice rules)
```

## Documents

- Design: [`docs/superpowers/specs/2026-09-30-see-and-identify-design.md`](docs/superpowers/specs/2026-09-30-see-and-identify-design.md)
- Plan: [`docs/superpowers/plans/2026-09-30-see-and-identify.md`](docs/superpowers/plans/2026-09-30-see-and-identify.md)
- Acceptance checklist: [`docs/acceptance/sp1-checklist.md`](docs/acceptance/sp1-checklist.md)
- Product profile (sub-project 2): [`docs/superpowers/specs/2026-10-01-product-profile-design.md`](docs/superpowers/specs/2026-10-01-product-profile-design.md),
  plan [`docs/superpowers/plans/2026-10-01-product-profile.md`](docs/superpowers/plans/2026-10-01-product-profile.md)
- Hologram and sidebar (sub-project 3): [`docs/superpowers/specs/2026-10-01-hologram-design.md`](docs/superpowers/specs/2026-10-01-hologram-design.md),
  plan [`docs/superpowers/plans/2026-10-01-hologram.md`](docs/superpowers/plans/2026-10-01-hologram.md)

## Roadmap

1. **See and identify** (complete)
2. **Product profile** (complete): Claude's own knowledge about the product, no sources, marked as such
3. **Hologram** (complete): a simplified, true-to-scale 3D model per product in a sidebar; a real scan only if needed
4. Questions and voice: ask about the object you hold
5. Polish and portfolio

## License

[AGPL-3.0](LICENSE). The detector, YOLOE by Ultralytics, is itself licensed under AGPL-3.0.
