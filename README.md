# Object Intelligence

Hold any object up to your Mac's camera. Object Intelligence finds the thing in your hand, tells you honestly how
sure it is what it is, builds a true-to-scale hologram of it and answers questions you ask out loud.

![The hologram of a Sony DualShock 3 in full screen: measure lines for width, height and depth, a numbered tag on
every part, next to the parts list and the product profile](docs/media/hologram-fullscreen.png)

<img src="docs/media/sidebar.png" width="360" align="right" alt="The sidebar entry of the controller: certain, the
evidence, a spoken question with its answer and sources, the hologram and the profile">

Most "what is this?" tools send a photo to a model and print whatever comes back. Object Intelligence is built the
other way round:

- **A local pipeline does the seeing.** A detector and tracker run on every frame on the Mac. Apple Vision finds your
  hand, and only the object your fingers lie on is identified.
- **Claude does the knowing.** It gets a crop with nothing but the object. It returns structured evidence, not a
  verdict.
- **An evidence book decides.** It turns several views into an honest level: *certain*, *likely*, *unsure* or
  *category only*. When two products look alike, the entry says so and asks for the side that tells them apart.

Everything is in German by default (`OI_LANGUAGE=en` switches to English). The pictures in this README are rendered
from real, cached answers of Claude for a DualShock 3; the photo of the object is left out of them.

<br clear="right">

## What it does

The project was built in five sub-projects, each with its own design document:

1. **See and identify.** YOLOE-26 (open vocabulary, prompt-free) and BoT-SORT track everything in view. Apple Vision
   confirms your hands and outlines them. The object with at least three finger joints on it gets the green box.
   - A snapshot, the sharpest frame of half a second, goes to Claude.
   - The first seconds calibrate the background: lamps, shelves and stairs are named once and frozen. They never steal
     the focus.
   - Your face, hair, glasses, shirt and necklace are never marked.
2. **Product profile.** Once an object is at least *likely*, it gets a short description and 4 to 8 technical facts.
   Release date, launch price and a few things worth knowing follow. It all comes from Claude's own knowledge and is
   always marked *laut Claude*.
3. **Hologram and sidebar.** Claude describes the product as primitives in millimetres (boxes, rounded boxes,
   cylinders, cones, spheres, capsules), and three.js builds a model to scale.
   - Every identified object stays pinned in the sidebar. The one in your hand is expanded and linked to its box.
   - Two tracks of the same physical object are merged after one small comparison.
   - If an object stays *unsure*, you tap the right candidate and it becomes *certain*, marked *von dir bestätigt*.
4. **Questions by voice.** Hold the space bar, ask ("Wie schwer ist dieser Controller?") and let go.
   - Whisper (MLX) turns your voice into text on the Mac.
   - Claude answers in one to three sentences. It searches the web only when the question needs something current,
     such as a price, and then names its sources.
   - The answer is read aloud.
5. **Polish.** The interface is dark Apple glass.
   - The hologram carries the photo of the object on the side that faces you.
   - "⤢" opens it in full screen with measure lines for width, height and depth and a numbered tag on every part.
     The parts list, the profile and the trivia sit beside it.
   - You can start the whole program with a double-click.

## Principles

- **Levels, not fake percentages.** A number a language model makes up ("87 %") is not a measured probability. The
  interface shows levels, and exact shares appear only in the telemetry corner (`D`). A result becomes *certain* only
  in three ways: through two independent views, through a model name readable on the object, or through your own tap.
- **Privacy by construction.**
  - What goes to Claude is the object alone: everything outside its outline is painted grey.
  - A crop that could show a person is never sent. Faces are found locally (OpenCV YuNet) and never leave the Mac.
  - The one whole frame that is sent, for naming the background, has every person painted grey first.
  - Your voice is transcribed on the Mac; only the text of the question leaves it.
- **Costs are bounded and visible.** At most 4 calls per object and 150 per session, answers included. Every call is
  logged in `runs/` with its crop, answer, tokens, cost and latency. Profiles and holograms are cached per model in
  `cache/`, so each costs one call, ever. Measured with Claude Opus 5.5:

  | Call | Cost | Time |
  |---|---|---|
  | Identify the object in your hand | 1.3–1.7 ct | 6–10 s |
  | Profile | about 1.2 ct | 6 s |
  | Hologram | about 1.8 ct | 10 s |
  | "Is this the same object?" | 0.4–0.5 ct | 3–5 s |
  | Spoken question | about 3 ct | 4 s |
  | Spoken question with web search | about 10 ct | 14–35 s |

  A web search is expensive because the pages it finds add about 20,000 input tokens, so an answer may search only
  once.

## How it works

```mermaid
flowchart LR
  subgraph browser["Browser: React + TypeScript"]
    camera["Camera"]
    mic["Microphone, only while Space is held"]
    hud["HUD canvas, sidebar, hologram (three.js), voice"]
  end
  subgraph mac["Your Mac: Python + FastAPI"]
    detect["YOLOE-26 + BoT-SORT on every frame"]
    people["Apple Vision hands, YuNet faces"]
    focus["Focus: the object your fingers are on"]
    snapshot["Sharpest snapshot, object pixels only"]
    belief["Evidence book: honest level"]
    whisper["Whisper (MLX): speech to text"]
    cache[("cache/: profiles and shapes")]
  end
  claude[("Claude API")]

  camera -- "JPEG frames, up to 12/s" --> detect
  detect --> focus
  people --> focus
  focus --> snapshot
  snapshot -- "object crop" --> claude
  claude -- "evidence" --> belief
  belief -- "identity" --> hud
  detect -- "boxes and outlines" --> hud
  mic -- "16 kHz audio" --> whisper
  whisper -- "question text" --> claude
  claude -- "profile, shape, answers" --> cache
  cache --> hud
```

The decision logic is plain Python with unit tests: focus, snapshots, trigger, evidence book, privacy rules and
merging. The detector, Claude and Whisper sit behind small interfaces with fakes, so the whole pipeline is tested
without a camera, a model or a network. Browser and server talk over one WebSocket with typed messages; a JSON
fixture keeps both sides of the protocol in step.

**Stack.**
- **Server:** Python 3.12 with uv, FastAPI and uvicorn. Ultralytics YOLOE-26 with BoT-SORT, Apple Vision through
  PyObjC, OpenCV YuNet and mlx-whisper (`whisper-large-v3-turbo`).
- **Claude:** the Anthropic SDK with structured outputs and the web search tool.
- **Browser:** React 19 with TypeScript, zustand, Vite and three.js; an AudioWorklet records the microphone.
- **Tests:** pytest and Vitest.

## Start

macOS on Apple Silicon with [uv](https://docs.astral.sh/uv/) and [Node.js](https://nodejs.org):

```bash
uv sync
npm --prefix web install
cp .env.example .env   # then put your Anthropic API key into .env (it never goes into git)
```

Then double-click **`Object Intelligence.command`** in Finder. It builds the browser part when needed, starts the
server and opens http://127.0.0.1:8766. If the app is already running, it only opens the browser. From a terminal:

```bash
uv run python -m oi                 # the same, without the build step
uv run python -m oi --no-browser --port 8799
```

On the first start the YOLOE weights download (about 38 MB), and so does the Whisper model (about 1.5 GB). The
browser asks for the camera at once and for the microphone the first time you hold Space. Without an API key the app
runs in local mode with boxes, IDs and coarse labels only.

| Key | |
|---|---|
| hold `Space` | ask a question about the object in your hand (or the last opened entry) |
| `M` | voice on or off (answers to your questions are always read aloud) |
| `D` | telemetry: frame rates, latencies, calls, costs and exact shares |
| `S` | mirror view |
| `R` | calibrate the background again |
| `Esc` | close the full-screen hologram |

Settings such as `OI_MODEL=claude-sonnet-5-5` (faster), `OI_LANGUAGE=en` or `OI_MAX_CALLS_SESSION` are read from the
environment or `.env`.

## Tests

```bash
uv run pytest               # 268 tests: all logic, no model, no network
uv run pytest -m model      # loads the real YOLOE weights
uv run pytest -m claude     # one real Claude call, about 2 cents
npm --prefix web test       # 52 tests: geometry, sidebar state, hologram maths, voice and labels
```

`--fake-claude` gives canned answers without any API call. It exists for the automated tests; real identification
needs Claude.

## Documents

| Sub-project | Design | Plan |
|---|---|---|
| 1 See and identify | [spec](docs/superpowers/specs/2026-09-30-see-and-identify-design.md) | [plan](docs/superpowers/plans/2026-09-30-see-and-identify.md), [acceptance](docs/acceptance/sp1-checklist.md) |
| 2 Product profile | [spec](docs/superpowers/specs/2026-10-01-product-profile-design.md) | [plan](docs/superpowers/plans/2026-10-01-product-profile.md) |
| 3 Hologram and sidebar | [spec](docs/superpowers/specs/2026-10-01-hologram-design.md) | [plan](docs/superpowers/plans/2026-10-01-hologram.md) |
| 4 Questions by voice | [spec](docs/superpowers/specs/2026-10-01-questions-voice-design.md) | |
| 5 Polish and portfolio | [spec](docs/superpowers/specs/2026-10-01-polish-design.md) | |

## License

[AGPL-3.0](LICENSE). The detector, YOLOE by Ultralytics, is itself licensed under AGPL-3.0.
