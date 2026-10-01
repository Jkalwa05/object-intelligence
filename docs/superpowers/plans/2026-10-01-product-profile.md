# Produkt-Steckbrief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A "Steckbrief" panel with Claude's product knowledge next to the info card once a product is likely or certain.

**Architecture:** `Belief.product()` decides when; a shared, disk-backed `ProfileStore` makes every product cost at
most one text-only Claude call; a new `profile` server message feeds a second glass panel that moves with the card.

**Tech Stack:** Python 3.12 (FastAPI, Pydantic, Anthropic SDK), React 19 + TypeScript + zustand, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-product-profile-design.md`

## Global Constraints

- No sources, but every value is visibly "laut Claude"; unknown products say so instead of guessing.
- Profiles only for level likely/certain at model or variant depth.
- One call per product and language, ever (disk cache `cache/profiles.json`, git-ignored); counts toward the budget.
- Text-only request: no image leaves the Mac for a profile.
- Never call the project a demo.

## Review Focus

- Profile arrives after the identity changed to another product: the browser shows it only for its own name.
- Identity drops from likely to unsure: the panel disappears.
- Corrupt or unwritable cache file: no crash, memory cache keeps working.
- Two objects of the same product: one call, the second is served from the cache.
- Reconnect: a new connection gets the cached profile again without a call.

### Task 1: Contracts and `Belief.product()`
**Files:** `oi/contracts.py`, `oi/belief.py`, `tests/test_belief.py`, `tests/test_contracts.py`,
`tests/fixtures/protocol-examples.json`
- Produces: `ProfileFact(label, value)`, `ProductProfile(known, summary, facts≤8, released, launch_price, trivia≤2)`,
  `ProfileMsg(product, status, summary, facts, released, launch_price, trivia, line)`, `Belief.product() -> tuple[str,
  str] | None`.
- Tests: `test_product_needs_likely_and_a_model` (likely/certain model → (name, category); unsure, category-only,
  brand-only → None); `test_profile_message_travels`; fixture regenerated (6 messages).

### Task 2: The Claude call
**Files:** `oi/identify.py`, `oi/telemetry.py`, `tests/test_identify.py`, `tests/test_telemetry.py`
- Produces: `ProductRequest(product, category, language)`, `ProductResult(profile, tokens, cost, latency, model)`,
  `build_profile_request`, `parse_profile`, `ClaudeIdentifier.describe_product`, `FakeIdentifier(profile=...)`.
- Tests: request has no image and names product/category/language; parse truncates and empties unknown profiles;
  Claude result cost; fake script; CallLog writes no `.jpg` for an empty image.

### Task 3: `ProfileStore`
**Files:** `oi/profiles.py`, `oi/config.py`, `.gitignore`, `tests/test_profiles.py`
- Produces: `ProfileStore(path: Path | None)`, `get(product, lang)`, `put(product, lang, profile)`.
- Tests: memory round trip with normalised keys; disk round trip across instances; corrupt file → empty; unwritable
  path → memory only.

### Task 4: Pipeline and server
**Files:** `oi/pipeline.py`, `oi/server.py`, `tests/test_pipeline.py`
- Consumes Tasks 1–3. Pipeline gets `profiles: ProfileStore | None`; server shares one store across connections.
- Tests: likely → loading then ready; unsure → nothing; same product again → cache, no call; error → error status, not
  cached; no budget → nothing; reconnect (new pipeline, same store) → ready without call.

### Task 5: Browser
**Files:** `web/src/protocol.ts`, `web/src/store.ts`, `web/src/i18n.ts`, `web/src/hud/ProfilePanel.tsx`,
`web/src/hud/InfoCard.tsx`, `web/src/App.tsx`, `web/src/hud/Overlay.tsx`, `web/src/styles.css`, tests
- Produces: `profiles` in the store, `focusProfile(s)`, the panel, the group that moves card and panel, voice line.
- Tests: protocol validation; `focusProfile` only for likely/certain and the identity's own name; texts.

### Task 6: Docs, real call, finish
- README and SP1 spec overview list sub-project 2 as "Produkt-Steckbrief (ohne Quellen)"; real `-m claude` test;
  smoke test on port 8799; memory; merge, push.
