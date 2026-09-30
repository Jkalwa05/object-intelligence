"""Identification (spec §2.5): the Claude request, parsing its answer, a free fake, and the startup probe.

Only the focus crop is sent, never the whole frame. Limits such as "at most 4 candidates" are enforced after the
answer arrives (by truncating), not in the JSON schema, so a paid call is never rejected over one extra candidate.
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
from pydantic import ValidationError

from oi import lines
from oi.config import Lang, Settings
from oi.contracts import Candidate, Depth, NextView, Observation

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


class IdentifyError(Exception):
    def __init__(self, reason: Literal["refusal", "schema", "timeout", "api", "connection"]) -> None:
        super().__init__(reason)
        self.reason = reason


class Identifier(Protocol):
    model_label: str

    async def identify(self, req: IdentifyRequest) -> IdentifyResult: ...


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


def build_request(s: Settings, req: IdentifyRequest) -> dict[str, Any]:
    output_config: dict[str, Any] = {"format": {"type": "json_schema", "schema": OBSERVATION_SCHEMA}}
    request: dict[str, Any] = {
        "model": s.model,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT.format(language="German" if req.language == "de" else "English"),
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.standard_b64encode(req.jpeg).decode()}},
            {"type": "text", "text": request_text(req)},
        ]}],
        "output_config": output_config,
    }
    if s.model in EFFORT_AND_FALLBACK_MODELS:  # Haiku 4.5 knows neither effort nor server-side fallbacks
        output_config["effort"] = s.effort
        request["betas"] = [FALLBACK_BETA]
        request["fallbacks"] = "default"
    return request


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


class ClaudeIdentifier:
    def __init__(self, settings: Settings, client: anthropic.AsyncAnthropic | None = None) -> None:
        self._s = settings
        self._client = client if client is not None else anthropic.AsyncAnthropic()
        self.model_label = settings.model

    async def identify(self, req: IdentifyRequest) -> IdentifyResult:
        request = build_request(self._s, req)
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
        observation = parse_observation(text)
        usage = response.usage
        return IdentifyResult(observation=observation, input_tokens=usage.input_tokens,
                              output_tokens=usage.output_tokens,
                              cost_usd=cost_usd(self._s.model, usage.input_tokens, usage.output_tokens, self._s.prices),
                              latency_s=latency, model=self._s.model)


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

    def __init__(self, script: Sequence[Observation | IdentifyError] | None = None, delay_s: float = 0.0) -> None:
        self._script = list(script) if script is not None else None
        self._delay = delay_s
        self.requests: list[IdentifyRequest] = []

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
    except (anthropic.AnthropicError, TypeError):
        return None, lines.notice_text("no_key", s.language), "lokal"
    return ClaudeIdentifier(s, client), None, "hybrid"
