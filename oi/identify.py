"""Identification (spec §2.5): the Claude request, parsing its answer, a free fake, and the startup probe.

Identification sees only the focus crop. The one exception is the scene call after a calibration (spec §9): it gets
the whole frame, with every person painted grey first (privacy.mask_people). The product profile (sub-project 2)
sends no image at all, only the product's name. Limits such as "at most 4 candidates"
are enforced after the answer arrives (by truncating), not in the JSON schema, so a paid call is never rejected over
one extra candidate.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import anthropic

from oi import lines
from oi.config import Lang, Settings
from oi.contracts import Candidate, Depth, NextView, Observation, ProductProfile, ProfileFact, SceneItemWire

MAX_TOKENS = 16000
FALLBACK_BETA = "server-side-fallback-2026-07-01"
EFFORT_AND_FALLBACK_MODELS = frozenset({"claude-opus-5-5", "claude-sonnet-5-5"})

SYSTEM_PROMPT = """You identify the single object shown in a camera crop that a person is holding up.
- Identify it as specifically as the visible evidence allows: category, then brand, then model, then variant. Never go beyond what you can see.
- List up to 4 candidates, most plausible first. Evidence must be features visible in this image (logos, shapes, buttons, ports, printed text).
- Copy any text you can read on the object into readable_text.
- Set distinguishable to false if the top candidates cannot be told apart from the outside.
- If you are unsure, put into next_view the one view that best separates the top two candidates and the reason. next_view.view is a short noun phrase that fits after "Please show me", for example "the bottom side".
- If no specific product is recognizable, return candidates without brand or model and describe the object in generic_description, for example "red ceramic mug".
- self_assessment is your own confidence: high, medium or low.
- Write all free text (category, evidence, next_view, generic_description) in {language}."""

_NULLABLE_STRING: dict[str, Any] = {"anyOf": [{"type": "string"}, {"type": "null"}]}
_STRINGS: dict[str, Any] = {"type": "array", "items": {"type": "string"}}
OBSERVATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "candidates": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "brand": _NULLABLE_STRING,
                "model_name": _NULLABLE_STRING,
                "variant": _NULLABLE_STRING,
                "depth": {"type": "string", "enum": ["category", "brand", "model", "variant"]},
                "evidence": _STRINGS,
            },
            "required": ["brand", "model_name", "variant", "depth", "evidence"],
            "additionalProperties": False,
        }},
        "readable_text": _STRINGS,
        "distinguishable": {"type": "boolean"},
        "next_view": {"anyOf": [{
            "type": "object",
            "properties": {"view": {"type": "string"}, "reason": {"type": "string"}},
            "required": ["view", "reason"],
            "additionalProperties": False,
        }, {"type": "null"}]},
        "self_assessment": {"type": "string", "enum": ["high", "medium", "low"]},
        "generic_description": _NULLABLE_STRING,
    },
    "required": ["category", "candidates", "readable_text", "distinguishable", "next_view", "self_assessment",
                 "generic_description"],
    "additionalProperties": False,
}


SCENE_MAX_ITEMS = 15
SCENE_PROMPT = """You name the objects in one camera image of a room, so that a heads-up display can label them.
- A flat grey area hides a person. Never describe it or guess anything about who it is.
- Name every clearly visible object or piece of furniture, at most {max_items}, the most prominent first.
- Each name is short and as specific as the visible evidence allows, for example {examples}. Write the names in {language}.
- box is [x1, y1, x2, y2] in integers from 0 to 1000 relative to the image width and height (x to the right, y down), tight around the object."""
SCENE_EXAMPLES = {"de": '"Pendelleuchte", "Raumspartreppe" or "Aktenordner"',
                  "en": '"pendant lamp", "space-saving staircase" or "ring binder"'}
SCENE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {"name": {"type": "string"}, "box": {"type": "array", "items": {"type": "integer"}}},
        "required": ["name", "box"],
        "additionalProperties": False,
    }}},
    "required": ["items"],
    "additionalProperties": False,
}
MIN_SCENE_BOX = 5  # of 1000: anything thinner is no object

PROFILE_PROMPT = """You write a short product profile for a heads-up display, from your own knowledge.
- Only facts about exactly this model. Leave a field out (null, or fewer entries) rather than guess.
- If you do not know this exact model well, set known to false and leave everything else empty.
- summary: one or two sentences: what it is, what it is for, who it is for.
- facts: the 4 to 8 most telling technical facts for this kind of product (for a phone for example chip, display, camera, battery; for a lamp type, material, socket, power), each as a short label and value.
- released: when it came out, month and year if known.
- launch_price: the recommended retail price at launch in Germany in euros if known, otherwise with its currency.
- trivia: one or two interesting, true facts about this product.
- Write everything in {language}."""
PROFILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "known": {"type": "boolean"},
        "summary": {"type": "string"},
        "facts": {"type": "array", "items": {
            "type": "object",
            "properties": {"label": {"type": "string"}, "value": {"type": "string"}},
            "required": ["label", "value"],
            "additionalProperties": False,
        }},
        "released": _NULLABLE_STRING,
        "launch_price": _NULLABLE_STRING,
        "trivia": _STRINGS,
    },
    "required": ["known", "summary", "facts", "released", "launch_price", "trivia"],
    "additionalProperties": False,
}
MAX_FACTS, MAX_TRIVIA = 8, 2


@dataclass(frozen=True)
class IdentifyRequest:
    jpeg: bytes
    coarse_label: str
    history: str
    pending_view: NextView | None
    language: Lang


@dataclass(frozen=True)
class IdentifyResult:
    observation: Observation
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float
    model: str


@dataclass(frozen=True)
class SceneRequest:
    jpeg: bytes  # the whole frame, people already painted grey
    language: Lang


@dataclass(frozen=True)
class SceneResult:
    items: list[SceneItemWire]  # boxes normalized to 0..1
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float
    model: str


@dataclass(frozen=True)
class ProductRequest:
    product: str  # the display name, e.g. "Apple iPhone 14"
    category: str
    language: Lang


@dataclass(frozen=True)
class ProductResult:
    profile: ProductProfile
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float
    model: str


class IdentifyError(Exception):
    def __init__(self, reason: Literal["refusal", "schema", "timeout", "api", "connection"]) -> None:
        super().__init__(reason)
        self.reason = reason


class Identifier(Protocol):
    model_label: str

    async def identify(self, req: IdentifyRequest) -> IdentifyResult: ...

    async def describe_scene(self, req: SceneRequest) -> SceneResult: ...

    async def describe_product(self, req: ProductRequest) -> ProductResult: ...


def format_history(observations: list[Observation], lang: Lang) -> str:
    """Earlier answers for this object, as text, so old images never have to be sent again."""
    if not observations:
        return "none"
    rows = []
    for i, o in enumerate(observations, start=1):
        names = " | ".join(lines.display_name(c, o.category, o.generic_description, lang) for c in o.candidates[:3])
        evidence = ", ".join(o.candidates[0].evidence) if o.candidates else ""
        rows.append(f"{i}) {names or o.generic_description or o.category}"
                    + (f" (evidence: {evidence})" if evidence else ""))
    return "\n".join(rows)


def request_text(req: IdentifyRequest) -> str:
    """The text that goes next to the crop; also stored in the call log."""
    text = [f"Coarse detector label: {req.coarse_label}", f"Previous observations of this object: {req.history}"]
    if req.pending_view is not None:
        text.append(f"Requested view: {req.pending_view.view} ({req.pending_view.reason})")
    return "\n".join(text)


def _request(s: Settings, system: str, jpeg: bytes | None, text: str, schema: dict[str, Any]) -> dict[str, Any]:
    output_config: dict[str, Any] = {"format": {"type": "json_schema", "schema": schema}}
    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    if jpeg is not None:
        content.insert(0, {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                       "data": base64.standard_b64encode(jpeg).decode()}})
    request: dict[str, Any] = {
        "model": s.model,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": content}],
        "output_config": output_config,
    }
    if s.model in EFFORT_AND_FALLBACK_MODELS:  # Haiku 4.5 knows neither effort nor server-side fallbacks
        output_config["effort"] = s.effort
        request["betas"] = [FALLBACK_BETA]
        request["fallbacks"] = "default"
    return request


def _language(lang: Lang) -> str:
    return "German" if lang == "de" else "English"


def build_request(s: Settings, req: IdentifyRequest) -> dict[str, Any]:
    return _request(s, SYSTEM_PROMPT.format(language=_language(req.language)), req.jpeg, request_text(req),
                    OBSERVATION_SCHEMA)


def build_scene_request(s: Settings, req: SceneRequest) -> dict[str, Any]:
    system = SCENE_PROMPT.format(max_items=SCENE_MAX_ITEMS, examples=SCENE_EXAMPLES[req.language],
                                 language=_language(req.language))
    return _request(s, system, req.jpeg, "Name the objects.", SCENE_SCHEMA)


def cost_usd(model: str, input_tokens: int, output_tokens: int, prices: Any) -> float:
    price_in, price_out = prices[model]
    return input_tokens / 1e6 * price_in + output_tokens / 1e6 * price_out


def parse_observation(text: str) -> Observation:
    try:
        data = json.loads(text)
        data["candidates"] = data.get("candidates", [])[:4]
        for c in data["candidates"]:
            c["evidence"] = c.get("evidence", [])[:5]
        data["readable_text"] = data.get("readable_text", [])[:10]
        return Observation.model_validate(data)
    except (ValueError, TypeError, AttributeError) as error:  # JSONDecodeError and ValidationError are ValueErrors
        raise IdentifyError("schema") from error


def build_profile_request(s: Settings, req: ProductRequest) -> dict[str, Any]:
    return _request(s, PROFILE_PROMPT.format(language=_language(req.language)), None,
                    f"Product: {req.product}\nCategory: {req.category}", PROFILE_SCHEMA)


def _clip(text: Any, limit: int) -> str:
    """Whitespace collapsed, at most `limit` characters: the panel has room for short values only."""
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def parse_profile(text: str) -> ProductProfile:
    """Claude's profile, trimmed to what the panel shows; an unknown product keeps nothing but `known=False`."""
    try:
        data = json.loads(text)
        if not data["known"]:
            return ProductProfile(known=False, summary="", facts=[], released=None, launch_price=None, trivia=[])
        facts = [ProfileFact(label=_clip(f["label"], 40), value=_clip(f["value"], 120)) for f in data["facts"]
                 if _clip(f.get("label", ""), 40) and _clip(f.get("value", ""), 120)]
        released, price = data.get("released"), data.get("launch_price")
        return ProductProfile(known=True, summary=_clip(data["summary"], 400), facts=facts[:MAX_FACTS],
                              released=_clip(released, 80) if released and _clip(released, 80) else None,
                              launch_price=_clip(price, 80) if price and _clip(price, 80) else None,
                              trivia=[_clip(t, 200) for t in data["trivia"] if _clip(t, 200)][:MAX_TRIVIA])
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        raise IdentifyError("schema") from error


def parse_scene(text: str) -> list[SceneItemWire]:
    """Claude's scene answer as display items: boxes clipped to the image and ordered, junk dropped, at most 15."""
    try:
        raw = json.loads(text)["items"]
        items = []
        for entry in raw:
            name, box = str(entry.get("name", "")).strip(), entry.get("box")
            if not name or not isinstance(box, list) or len(box) != 4:
                continue
            x1, y1, x2, y2 = (min(1000.0, max(0.0, float(v))) for v in box)
            (x1, x2), (y1, y2) = sorted((x1, x2)), sorted((y1, y2))
            if x2 - x1 < MIN_SCENE_BOX or y2 - y1 < MIN_SCENE_BOX:
                continue
            items.append(SceneItemWire(label=name, box=(x1 / 1000, y1 / 1000, x2 / 1000, y2 / 1000)))
        return items[:SCENE_MAX_ITEMS]
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        raise IdentifyError("schema") from error


class ClaudeIdentifier:
    def __init__(self, settings: Settings, client: anthropic.AsyncAnthropic | None = None) -> None:
        self._s = settings
        self._client = client if client is not None else anthropic.AsyncAnthropic()
        self.model_label = settings.model

    async def identify(self, req: IdentifyRequest) -> IdentifyResult:
        text, usage, latency = await self._call(build_request(self._s, req))
        observation = parse_observation(text)
        return IdentifyResult(observation=observation, input_tokens=usage.input_tokens,
                              output_tokens=usage.output_tokens,
                              cost_usd=cost_usd(self._s.model, usage.input_tokens, usage.output_tokens, self._s.prices),
                              latency_s=latency, model=self._s.model)

    async def describe_scene(self, req: SceneRequest) -> SceneResult:
        text, usage, latency = await self._call(build_scene_request(self._s, req))
        return SceneResult(items=parse_scene(text), input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                           cost_usd=cost_usd(self._s.model, usage.input_tokens, usage.output_tokens, self._s.prices),
                           latency_s=latency, model=self._s.model)

    async def describe_product(self, req: ProductRequest) -> ProductResult:
        text, usage, latency = await self._call(build_profile_request(self._s, req))
        return ProductResult(profile=parse_profile(text), input_tokens=usage.input_tokens,
                             output_tokens=usage.output_tokens,
                             cost_usd=cost_usd(self._s.model, usage.input_tokens, usage.output_tokens, self._s.prices),
                             latency_s=latency, model=self._s.model)

    async def _call(self, request: dict[str, Any]) -> tuple[str, Any, float]:
        """(answer text, usage, latency); every failure becomes an IdentifyError."""
        client = self._client.with_options(timeout=self._s.claude_timeout_s)
        started = time.monotonic()
        try:
            if "betas" in request:
                response = await client.beta.messages.create(**request)
            else:
                response = await client.messages.create(**request)
        except anthropic.APITimeoutError as error:  # subclass of APIConnectionError, so it comes first
            raise IdentifyError("timeout") from error
        except anthropic.APIConnectionError as error:
            raise IdentifyError("connection") from error
        except anthropic.APIStatusError as error:
            raise IdentifyError("api") from error
        latency = time.monotonic() - started
        if response.stop_reason == "refusal":
            raise IdentifyError("refusal")
        if response.stop_reason == "max_tokens":
            raise IdentifyError("schema")
        text = next((block.text for block in response.content if getattr(block, "type", None) == "text"), "")
        return text, response.usage, latency


def canned_observation(coarse_label: str, lang: Lang) -> Observation:
    """What the free fake answers: an iPhone doubt for phones, a plain category for everything else."""
    if "phone" in coarse_label.lower():
        de = lang == "de"
        view = (NextView(view="die Unterseite", reason="Lightning oder USB-C") if de
                else NextView(view="the bottom side", reason="Lightning or USB-C"))
        evidence = ["Apple-Logo", "zwei Kameras diagonal"] if de else ["Apple logo", "two cameras diagonally"]
        candidates = [Candidate(brand="Apple", model_name=m, variant=None, depth=Depth.MODEL, evidence=evidence)
                      for m in ("iPhone 14", "iPhone 13")]
        return Observation(category="Smartphone", candidates=candidates, readable_text=[], distinguishable=True,
                           next_view=view, self_assessment="low", generic_description=None)
    return Observation(category=coarse_label, candidates=[], readable_text=[], distinguishable=True, next_view=None,
                       self_assessment="medium", generic_description=coarse_label)


class FakeIdentifier:
    """Costs nothing: answers from a script (tests) or with canned answers (`--fake-claude`)."""

    model_label = "fake"

    def __init__(self, script: Sequence[Observation | IdentifyError] | None = None, delay_s: float = 0.0,
                 scene: Sequence[SceneItemWire] | IdentifyError | None = None,
                 profile: ProductProfile | IdentifyError | None = None) -> None:
        self._script = list(script) if script is not None else None
        self._delay = delay_s
        self._scene = scene
        self._profile = profile
        self.requests: list[IdentifyRequest] = []
        self.scene_requests: list[SceneRequest] = []
        self.product_requests: list[ProductRequest] = []

    async def identify(self, req: IdentifyRequest) -> IdentifyResult:
        self.requests.append(req)
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._script is None:
            observation = canned_observation(req.coarse_label, req.language)
        else:
            item = self._script.pop(0) if len(self._script) > 1 else self._script[0]  # the last entry repeats
            if isinstance(item, IdentifyError):
                raise item
            observation = item
        return IdentifyResult(observation=observation, input_tokens=0, output_tokens=0, cost_usd=0.0,
                              latency_s=self._delay, model=self.model_label)

    async def describe_scene(self, req: SceneRequest) -> SceneResult:
        """The scripted scene, or no items at all: canned names would only pretend to see the room."""
        self.scene_requests.append(req)
        if self._delay:
            await asyncio.sleep(self._delay)
        if isinstance(self._scene, IdentifyError):
            raise self._scene
        return SceneResult(items=list(self._scene or []), input_tokens=0, output_tokens=0, cost_usd=0.0,
                           latency_s=self._delay, model=self.model_label)

    async def describe_product(self, req: ProductRequest) -> ProductResult:
        """The scripted profile, or "I don't know this product": canned facts would only pretend to know it."""
        self.product_requests.append(req)
        if self._delay:
            await asyncio.sleep(self._delay)
        if isinstance(self._profile, IdentifyError):
            raise self._profile
        profile = self._profile or ProductProfile(known=False, summary="", facts=[], released=None, launch_price=None,
                                                  trivia=[])
        return ProductResult(profile=profile, input_tokens=0, output_tokens=0, cost_usd=0.0, latency_s=self._delay,
                             model=self.model_label)


async def choose_identifier(s: Settings, fake: bool,
                            client_factory: Callable[[], Any] = anthropic.AsyncAnthropic,
                            ) -> tuple[Identifier | None, str | None, Literal["hybrid", "lokal"]]:
    """Startup probe: (identifier or None, notice for the HUD or None, mode)."""
    if fake:
        return FakeIdentifier(), None, "hybrid"
    client = None
    try:
        client = client_factory()
        await client.models.retrieve(s.model)
    except anthropic.APIConnectionError:
        return ClaudeIdentifier(s, client), lines.notice_text("unreachable", s.language), "hybrid"
    except anthropic.NotFoundError:
        return None, lines.notice_text("model_missing", s.language, model=s.model), "lokal"
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError, TypeError):
        return None, lines.notice_text("no_key", s.language), "lokal"
    except anthropic.APIStatusError:  # overloaded, rate limited or a server error right now: keep Claude
        return ClaudeIdentifier(s, client), lines.notice_text("unreachable", s.language), "hybrid"
    except anthropic.AnthropicError:  # no credentials at all
        return None, lines.notice_text("no_key", s.language), "lokal"
    return ClaudeIdentifier(s, client), None, "hybrid"
