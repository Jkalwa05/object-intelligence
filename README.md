# Object Intelligence

Hold any object up to your Mac's camera. Object Intelligence finds and tracks everything in view, picks the object
you are holding, and identifies it as precisely as the visible evidence honestly allows. When two products look
alike, it says so, and it asks for the one view that would tell them apart ("Show me the bottom side: Lightning or
USB-C?").

This is sub-project 1 of 5 ("see and identify"). Sourced facts, 3D models, voice questions and polish follow in
their own sub-projects.

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
│ HUD canvas + info card    │ ◀──── tracks ────────── │ focus:      which object is held      │
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
detector and a body zone keep them out). If two candidates look alike from one side, the card asks for the view that
separates them, for example "Zeig mir bitte die Unterseite" for iPhone 14 (Lightning) and 15 (USB-C).

Keys: `M` mutes the voice, `D` shows the telemetry (including which quality check a crop fails), `S` toggles the mirror
view, `R` calibrates the scene again. Settings such as `OI_MODEL=claude-sonnet-5-5` (faster), `OI_LANGUAGE=en` or
`OI_MIN_SHARPNESS` are read from the environment or `.env`. `--fake-claude` gives canned answers without any API call;
it is meant for the automated tests, real identification needs Claude.

## Tests

```bash
uv run pytest               # all logic, no model, no network
uv run pytest -m model      # loads the real YOLOE weights
uv run pytest -m claude     # one real Claude call, about 2 cents
npm --prefix web test       # browser logic (geometry, card placement, state, voice rules)
```

## Documents

- Design: [`docs/superpowers/specs/2026-09-30-see-and-identify-design.md`](docs/superpowers/specs/2026-09-30-see-and-identify-design.md)
- Plan: [`docs/superpowers/plans/2026-09-30-see-and-identify.md`](docs/superpowers/plans/2026-09-30-see-and-identify.md)
- Acceptance checklist: [`docs/acceptance/sp1-checklist.md`](docs/acceptance/sp1-checklist.md)

## Roadmap

1. **See and identify** (this repository, now)
2. Facts with sources: an object profile where every value has a citation
3. 3D: generic, generated or exact models, honestly labelled
4. Questions and voice: "How heavy is it?", answered only from the profile
5. Polish and portfolio

## License

[AGPL-3.0](LICENSE). The detector, YOLOE by Ultralytics, is itself licensed under AGPL-3.0.
