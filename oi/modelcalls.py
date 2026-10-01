"""The three Claude calls of the precision model (sub-project 6): research, CAD program and visual check.

Research uses the web search and the plain web fetch and answers as text that ends in one JSON block: whether the
search's citations combine with structured output is not documented, so the server reads the block itself. CAD and
check calls carry no tools and use structured output. Limits are enforced after parsing, never in a schema: a paid
answer is never thrown away for one entry too many.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any

from oi.config import Lang, Settings
from oi.contracts import DrawingRef, Measure, MeasureSheet, Source
from oi.identify import GERMANY, IdentifyError, _clip, _language, _with_content
from oi.modelprompts import RESEARCH_PROMPT

MAX_MEASURES, MAX_FEATURES, MAX_SOURCES = 30, 20, 6
MAX_MM = 5000.0  # nothing held up to a webcam is longer than 5 m
RESEARCH_MAX_TOKENS = 16000
RESEARCH_EFFORT = "medium"
SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 3}
FETCH_TOOL = {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 3, "max_content_tokens": 15000}
KINDS = ("drawing", "datasheet", "estimate")


@dataclass(frozen=True)
class CadPart:
    name: str
    color: str  # "#rrggbb"
    scad: str  # OpenSCAD statements that make exactly this part


@dataclass(frozen=True)
class ResearchRequest:
    model: str  # "Apple iPhone 14"
    category: str
    language: Lang


@dataclass(frozen=True)
class ResearchResult:
    sheet: MeasureSheet
    allowed_urls: set[str]  # what the search and fetch found: the only URLs the server may download
    searches: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float
    model: str


def build_research_request(s: Settings, req: ResearchRequest) -> dict[str, Any]:
    content = [{"type": "text", "text": f"Product: {req.model}\nCategory: {req.category}"}]
    request = _with_content(s, RESEARCH_PROMPT.format(language=_language(req.language)), content, None)
    search = dict(SEARCH_TOOL)
    if req.language == "de":
        search["user_location"] = dict(GERMANY)
    request["tools"] = [search, dict(FETCH_TOOL)]
    request["max_tokens"] = RESEARCH_MAX_TOKENS
    if "effort" in request.get("output_config", {}):
        request["output_config"]["effort"] = RESEARCH_EFFORT
    if not request.get("output_config"):
        request.pop("output_config", None)
    return request


def _get(item: Any, key: str) -> Any:
    return item.get(key) if isinstance(item, dict) else getattr(item, key, None)


def _found_urls(blocks: list[Any]) -> set[str]:
    urls: set[str] = set()
    for block in blocks:
        kind, content = _get(block, "type"), _get(block, "content")
        if kind == "web_search_tool_result" and isinstance(content, list):
            urls |= {u for u in (_get(r, "url") for r in content) if isinstance(u, str)}
        elif kind == "web_fetch_tool_result" and _get(content, "type") == "web_fetch_result":
            if isinstance(url := _get(content, "url"), str):
                urls.add(url)
    return urls


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value) if 0 < value <= MAX_MM else None


def _index(value: Any, count: int) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < count else None


def parse_research(blocks: list[Any]) -> tuple[MeasureSheet, set[str]]:
    """The measure sheet from the last ```json block of the answer, repaired and clipped, and the found URLs."""
    text = "".join(_get(b, "text") or "" for b in blocks if _get(b, "type") == "text")
    fences = re.findall(r"```json\s*(.*?)```", text, re.S)
    try:
        data = json.loads(fences[-1]) if fences else None
    except ValueError as error:
        raise IdentifyError("schema") from error
    if not isinstance(data, dict):
        raise IdentifyError("schema")
    sources = [Source(title=_clip(s.get("title") or s.get("url"), 120), url=s["url"])
               for s in data.get("sources") or [] if isinstance(s, dict) and isinstance(s.get("url"), str)
               and s["url"].startswith(("https://", "http://"))][:MAX_SOURCES]
    size = data.get("size_mm")
    numbers = [_number(v) for v in size] if isinstance(size, list) and len(size) == 3 else [None]
    measures = []
    for raw in data.get("measures") or []:
        value = _number(raw.get("value_mm")) if isinstance(raw, dict) else None
        if value is None or not _clip(raw.get("label", ""), 60):
            continue
        source = _index(raw.get("source"), len(sources))
        kind = raw.get("kind") if raw.get("kind") in KINDS and source is not None else "estimate"
        measures.append(Measure(label=_clip(raw["label"], 60), value_mm=value, source=source, kind=kind))
    drawing = data.get("drawing")
    ref = (DrawingRef(url=drawing["url"], find=_clip(drawing.get("find") or "", 120))
           if isinstance(drawing, dict) and isinstance(drawing.get("url"), str) and drawing["url"].startswith("https://")
           else None)
    sheet = MeasureSheet(
        size_mm=tuple(numbers) if None not in numbers else None,  # type: ignore[arg-type]
        size_source=_index(data.get("size_source"), len(sources)),
        measures=measures[:MAX_MEASURES],
        features=[_clip(f, 200) for f in data.get("features") or [] if isinstance(f, str) and _clip(f, 200)
                  ][:MAX_FEATURES],
        sources=sources, drawing=ref)
    return sheet, _found_urls(blocks)
