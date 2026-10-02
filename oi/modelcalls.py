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
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Protocol

from oi.config import Lang, Settings
from oi.contracts import DrawingRef, Measure, MeasureSheet, PhotoRef, PhotoView, Source
from oi.drawings import MAX_PHOTOS, Picture
from oi.identify import (GERMANY, SEARCH_PRICE_USD, ClaudeIdentifier, IdentifyError, _clip, _image, _language,
                         _with_content, cost_usd)
from oi.measure import ViewBoxes, parse_measure
from oi.modelprompts import (BOSL2_GUIDE, CAD_PROMPT, CAD_SCHEMA, CHECK_PROMPT, CHECK_SCHEMA, MEASURE_PROMPT,
                             MEASURE_SCHEMA, RESEARCH_PROMPT, SAME_PRODUCT_PROMPT, SAME_PRODUCT_SCHEMA)
from oi.render import VIEWS
from oi.scad import HEADER

MAX_MEASURES, MAX_FEATURES, MAX_SOURCES = 30, 20, 6
MAX_MM = 5000.0  # nothing held up to a webcam is longer than 5 m
RESEARCH_MAX_TOKENS = 16000
RESEARCH_EFFORT = "medium"
SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 3}
FETCH_TOOL = {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 3, "max_content_tokens": 15000}
KINDS = ("drawing", "datasheet", "estimate")
MAX_PARTS, MAX_SHARED, MAX_PART_CODE, MAX_ISSUES = 40, 20_000, 12_000, 10
CAD_MAX_TOKENS = 32000
MEASURE_MAX_TOKENS = 16000
CAD_EFFORT = "high"
DEFAULT_COLOR = "#9aa0a6"


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


LINK = re.compile(r"https://[^\s\"'<>()\[\]]+")  # a link in the text of a fetched page
PHOTO_VIEWS = ("front", "back", "side-front-left", "side-front-right", "top")


def _found_urls(blocks: list[Any]) -> set[str]:
    """Search results, fetched pages and the https links written on those pages (a drawing on a CDN)."""
    urls: set[str] = set()
    for block in blocks:
        kind, content = _get(block, "type"), _get(block, "content")
        if kind == "web_search_tool_result" and isinstance(content, list):
            urls |= {u for u in (_get(r, "url") for r in content) if isinstance(u, str)}
        elif kind == "web_fetch_tool_result" and _get(content, "type") == "web_fetch_result":
            if isinstance(url := _get(content, "url"), str):
                urls.add(url)
            page = _get(_get(_get(content, "content"), "source"), "data")
            if isinstance(page, str):
                urls |= {link.rstrip(".,;:") for link in LINK.findall(page)}
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
    photos = [PhotoRef(url=p["url"], view=p["view"]) for p in data.get("photos") or []
              if isinstance(p, dict) and isinstance(p.get("url"), str) and p["url"].startswith("https://")
              and p.get("view") in PHOTO_VIEWS][:MAX_PHOTOS]
    sheet = MeasureSheet(
        size_mm=tuple(numbers) if None not in numbers else None,  # type: ignore[arg-type]
        size_source=_index(data.get("size_source"), len(sources)),
        measures=measures[:MAX_MEASURES],
        features=[_clip(f, 200) for f in data.get("features") or [] if isinstance(f, str) and _clip(f, 200)
                  ][:MAX_FEATURES],
        sources=sources, drawing=ref, photos=photos)
    return sheet, _found_urls(blocks)


# --- CAD program and visual check ------------------------------------------------------------------------------

@dataclass(frozen=True)
class CadProgram:
    shared: str  # variables and modules every part needs
    parts: list[CadPart]
    notes: str  # what is approximated


@dataclass(frozen=True)
class CadRequest:
    model: str
    category: str
    sheet: MeasureSheet
    drawings: list[Picture]
    jpeg: bytes | None  # the object-only crop of the identification
    language: Lang
    photos: list[tuple[Picture, PhotoView]] = field(default_factory=list)  # reference photos (sub-project 7)
    part_map: str = ""  # measure.map_text of the measured parts, "" when nothing was measured


@dataclass(frozen=True)
class CadResult:
    program: CadProgram
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float
    model: str


@dataclass(frozen=True)
class CheckAnswer:
    verdict: Literal["good", "fix"]
    issues: list[str]
    shared: str | None  # new shared code, or None to keep it
    parts: list[CadPart]  # changed or new parts
    remove: list[str]


@dataclass(frozen=True)
class CheckRequest:
    model: str
    sheet: MeasureSheet
    drawings: list[Picture]
    jpeg: bytes | None
    program: CadProgram
    renders: list[bytes]  # PNG, in the order of render.VIEWS
    errors: dict[str, list[str]]  # compile errors per part name
    size_hint: str | None
    round: int
    rounds: int
    language: Lang
    photos: list[tuple[Picture, PhotoView]] = field(default_factory=list)
    part_map: str = ""
    deviations: list[str] = field(default_factory=list)  # measure.deviations of the current model


@dataclass(frozen=True)
class CheckResult:
    answer: CheckAnswer
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float
    model: str


def _sheet_text(sheet: MeasureSheet) -> str:
    return "Measure sheet from the research:\n" + sheet.model_dump_json(indent=1)


def _pictures(drawings: list[Picture], jpeg: bytes | None) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []
    for number, (data, media) in enumerate(drawings, start=1):
        content += [{"type": "text", "text": f"Technical drawing {number}:"}, _image(data, media)]
    if jpeg is not None:
        content += [{"type": "text", "text": "Photo of the object the person holds (everything else is grey):"},
                    _image(jpeg)]
    return content


def _photos(photos: list[tuple[Picture, PhotoView]]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []
    for (data, media), view in photos:
        content += [{"type": "text", "text": f"Reference photo ({view}):"}, _image(data, media)]
    return content


def _measured(part_map: str, deviations: list[str] | None = None) -> list[dict[str, Any]]:
    content = [{"type": "text", "text": part_map}] if part_map else []
    if deviations:
        content.append({"type": "text", "text": "Measured deviations (fix them):\n" + "\n".join(deviations)})
    return content


def _structured(s: Settings, system: str, content: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
    request = _with_content(s, system, content, schema)
    request["max_tokens"] = CAD_MAX_TOKENS
    if "effort" in request["output_config"]:
        request["output_config"]["effort"] = CAD_EFFORT
    return request


def build_cad_request(s: Settings, req: CadRequest) -> dict[str, Any]:
    content = [{"type": "text", "text": _sheet_text(req.sheet)}, *_pictures(req.drawings, req.jpeg),
               *_photos(req.photos), *_measured(req.part_map),
               {"type": "text", "text": f"Product: {req.model}\nCategory: {req.category}\n"
                                        "Write the OpenSCAD program for this product."}]
    system = CAD_PROMPT.format(language=_language(req.language)) + "\n\n" + BOSL2_GUIDE
    return _structured(s, system, content, CAD_SCHEMA)


def scad_source(program: CadProgram) -> str:
    """The whole model as one OpenSCAD file, every part in its own commented section (model.scad)."""
    sections = [f"// --- {p.name} ({p.color})\n{p.scad}\n" for p in program.parts]
    return f"{HEADER}// --- gemeinsam\n{program.shared}\n\n" + "\n".join(sections)


def build_check_request(s: Settings, req: CheckRequest) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": f"Runde {req.round} von {req.rounds}. "
                                                              "Renders of the current CAD model:"}]
    for view, png in zip(VIEWS, req.renders, strict=False):
        content += [{"type": "text", "text": f"Render „{view}“:"}, _image(png, "image/png")]
    content += [*_pictures(req.drawings, req.jpeg), *_photos(req.photos)]
    content.append({"type": "text", "text": _sheet_text(req.sheet)})
    content += _measured(req.part_map)
    content.append({"type": "text", "text": "Current OpenSCAD program:\n" + scad_source(req.program)})
    if req.errors:
        lines = [f"{name}: {' | '.join(errors)}" for name, errors in req.errors.items()]
        content.append({"type": "text", "text": "Compile errors per part:\n" + "\n".join(lines)})
    if req.size_hint:
        content.append({"type": "text", "text": req.size_hint})
    content += _measured("", req.deviations)
    content.append({"type": "text", "text": f"Product: {req.model}. Check the model and correct it."})
    return _structured(s, CHECK_PROMPT.format(language=_language(req.language)), content, CHECK_SCHEMA)


def _parts(raw: Any) -> list[CadPart]:
    """Checked parts: code present and not too long, colour valid, names short and unique, at most 40."""
    parts: list[CadPart] = []
    names: set[str] = set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("scad"), str):
            continue
        code = item["scad"].strip()
        if not code or len(code) > MAX_PART_CODE:
            continue
        base = _clip(item.get("name") or "Teil", 40) or "Teil"
        name, number = base, 2
        while name in names:
            name, number = f"{base} {number}", number + 1
        names.add(name)
        color = item.get("color") if isinstance(item.get("color"), str) else ""
        parts.append(CadPart(name=name, color=color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else DEFAULT_COLOR,
                             scad=code))
    return parts[:MAX_PARTS]


def _json_object(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except ValueError as error:
        raise IdentifyError("schema") from error
    if not isinstance(data, dict):
        raise IdentifyError("schema")
    return data


def parse_cad(text: str) -> CadProgram:
    data = _json_object(text)
    shared = data.get("shared") if isinstance(data.get("shared"), str) else ""
    parts = _parts(data.get("parts"))
    if not parts or len(shared) > MAX_SHARED:
        raise IdentifyError("schema")
    return CadProgram(shared=shared, parts=parts, notes=_clip(data.get("notes") or "", 400))


def parse_check(text: str) -> CheckAnswer:
    data = _json_object(text)
    shared = data.get("shared")
    return CheckAnswer(
        verdict="good" if data.get("verdict") == "good" else "fix",
        issues=[_clip(i, 200) for i in data.get("issues") or [] if isinstance(i, str) and _clip(i, 200)][:MAX_ISSUES],
        shared=shared if isinstance(shared, str) and len(shared) <= MAX_SHARED else None,
        parts=_parts(data.get("parts")),
        remove=[r for r in data.get("remove") or [] if isinstance(r, str)][:MAX_PARTS])


def apply_check(program: CadProgram, answer: CheckAnswer) -> CadProgram:
    """The program after a check: same names replaced, new names appended, removed ones dropped."""
    parts = {p.name: p for p in program.parts}
    for part in answer.parts:
        parts[part.name] = part
    for name in answer.remove:
        parts.pop(name, None)
    return CadProgram(shared=program.shared if answer.shared is None else answer.shared,
                      parts=list(parts.values())[:MAX_PARTS], notes=program.notes)


# --- measuring and product names (sub-project 7) -----------------------------------------------------------------

@dataclass(frozen=True)
class MeasureRequest:
    model: str
    sheet: MeasureSheet
    pictures: list[tuple[Picture, str]]  # (picture, label): the drawing pages, then the photos
    language: Lang


@dataclass(frozen=True)
class MeasureResult:
    views: list[ViewBoxes]
    notes: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float
    model: str


@dataclass(frozen=True)
class SameProductRequest:
    model: str  # the name of the product held now
    candidates: list[str]  # the names of the kept models
    language: Lang


@dataclass(frozen=True)
class SameProductResult:
    match: str | None  # one of the candidates, or None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float
    model: str


def build_measure_request(s: Settings, req: MeasureRequest) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    for number, ((data, media), label) in enumerate(req.pictures, start=1):
        content += [{"type": "text", "text": f"Picture {number} ({label}):"}, _image(data, media)]
    content += [{"type": "text", "text": _sheet_text(req.sheet)},
                {"type": "text", "text": f"Product: {req.model}. Measure its parts on the pictures."}]
    request = _with_content(s, MEASURE_PROMPT.format(language=_language(req.language)), content, MEASURE_SCHEMA)
    request["max_tokens"] = MEASURE_MAX_TOKENS
    if "effort" in request["output_config"]:
        request["output_config"]["effort"] = CAD_EFFORT
    return request


def build_same_product_request(s: Settings, req: SameProductRequest) -> dict[str, Any]:
    names = "\n".join(f"{number}. {name}" for number, name in enumerate(req.candidates, start=1))
    content = [{"type": "text", "text": f"New name: {req.model}\nCandidates:\n{names}"}]
    return _with_content(s, SAME_PRODUCT_PROMPT, content, SAME_PRODUCT_SCHEMA)


def parse_same_product(text: str, candidates: list[str]) -> str | None:
    """The candidate Claude names, or None: a name that is not one of the candidates counts as no match."""
    match = _json_object(text).get("match")
    return match if match in candidates else None


# --- who makes the calls ----------------------------------------------------------------------------------------

class ModelCalls(Protocol):
    async def research(self, req: ResearchRequest) -> ResearchResult: ...

    async def build_cad(self, req: CadRequest) -> CadResult: ...

    async def check_cad(self, req: CheckRequest) -> CheckResult: ...

    async def measure(self, req: MeasureRequest) -> MeasureResult: ...

    async def same_product(self, req: SameProductRequest) -> SameProductResult: ...


def _text(response: Any) -> str:
    return next((b.text for b in response.content if getattr(b, "type", None) == "text"), "")


class ClaudeModelCalls:
    """The real calls, through the identifier's client, with the precision model's long timeout."""

    def __init__(self, identifier: ClaudeIdentifier, settings: Settings) -> None:
        self._identifier = identifier
        self._s = replace(settings, model=settings.cad_model)  # research, CAD and check: OI_CAD_MODEL

    async def _streamed(self, request: dict[str, Any]) -> tuple[Any, float]:
        return await self._identifier.create(request, self._s.model_timeout_s, stream=True)

    def _cost(self, usage: Any) -> float:
        return cost_usd(self._s.model, usage.input_tokens, usage.output_tokens, self._s.prices)

    async def research(self, req: ResearchRequest) -> ResearchResult:
        response, latency = await self._streamed(build_research_request(self._s, req))
        sheet, allowed = parse_research(response.content)
        usage = response.usage
        searches = int(getattr(getattr(usage, "server_tool_use", None), "web_search_requests", 0) or 0)
        return ResearchResult(sheet=sheet, allowed_urls=allowed, searches=searches, input_tokens=usage.input_tokens,
                              output_tokens=usage.output_tokens,
                              cost_usd=self._cost(usage) + searches * SEARCH_PRICE_USD, latency_s=latency,
                              model=self._s.model)

    async def build_cad(self, req: CadRequest) -> CadResult:
        response, latency = await self._streamed(build_cad_request(self._s, req))
        usage = response.usage
        return CadResult(program=parse_cad(_text(response)), input_tokens=usage.input_tokens,
                         output_tokens=usage.output_tokens, cost_usd=self._cost(usage), latency_s=latency,
                         model=self._s.model)

    async def check_cad(self, req: CheckRequest) -> CheckResult:
        response, latency = await self._streamed(build_check_request(self._s, req))
        usage = response.usage
        return CheckResult(answer=parse_check(_text(response)), input_tokens=usage.input_tokens,
                           output_tokens=usage.output_tokens, cost_usd=self._cost(usage), latency_s=latency,
                           model=self._s.model)


    async def measure(self, req: MeasureRequest) -> MeasureResult:
        response, latency = await self._streamed(build_measure_request(self._s, req))
        views, notes = parse_measure(_text(response), len(req.pictures))
        usage = response.usage
        return MeasureResult(views=views, notes=notes, input_tokens=usage.input_tokens,
                             output_tokens=usage.output_tokens, cost_usd=self._cost(usage), latency_s=latency,
                             model=self._s.model)

    async def same_product(self, req: SameProductRequest) -> SameProductResult:
        response, latency = await self._identifier.create(build_same_product_request(self._s, req))  # small: no stream
        usage = response.usage
        return SameProductResult(match=parse_same_product(_text(response), req.candidates),
                                 input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                                 cost_usd=self._cost(usage), latency_s=latency, model=self._s.model)


class FakeModelCalls:
    """Costs nothing: scripted answers for the tests. `costs` = (research, measure, CAD, check) in dollars per call;
    a used-up check script answers "good", and without a script nothing is measured and no name matches."""

    def __init__(self, research: MeasureSheet | IdentifyError | None = None,
                 cad: CadProgram | IdentifyError | None = None, checks: list[CheckAnswer | IdentifyError] | None = None,
                 costs: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
                 measure: list[ViewBoxes] | IdentifyError | None = None,
                 same: str | IdentifyError | None = None) -> None:
        self.research_sheet, self.cad, self.costs = research, cad, costs
        self.measure_views, self.same_answer = measure, same
        self.checks = list(checks or [])
        self.research_requests: list[ResearchRequest] = []
        self.cad_requests: list[CadRequest] = []
        self.check_requests: list[CheckRequest] = []
        self.measure_requests: list[MeasureRequest] = []
        self.same_requests: list[SameProductRequest] = []

    async def research(self, req: ResearchRequest) -> ResearchResult:
        self.research_requests.append(req)
        if isinstance(self.research_sheet, IdentifyError):
            raise self.research_sheet
        sheet = self.research_sheet or MeasureSheet.estimated()
        allowed = {s.url for s in sheet.sources} | ({sheet.drawing.url} if sheet.drawing else set())
        return ResearchResult(sheet=sheet, allowed_urls=allowed, searches=0, input_tokens=0, output_tokens=0,
                              cost_usd=self.costs[0], latency_s=0.0, model="fake")

    async def build_cad(self, req: CadRequest) -> CadResult:
        self.cad_requests.append(req)
        if isinstance(self.cad, IdentifyError):
            raise self.cad
        program = self.cad or CadProgram(shared="", parts=[CadPart("Gehäuse", "#9fc4e8", "cube(10, center=true);")],
                                         notes="")
        return CadResult(program=program, input_tokens=0, output_tokens=0, cost_usd=self.costs[2], latency_s=0.0,
                         model="fake")

    async def check_cad(self, req: CheckRequest) -> CheckResult:
        self.check_requests.append(req)
        answer = self.checks.pop(0) if self.checks else CheckAnswer("good", [], None, [], [])
        if isinstance(answer, IdentifyError):
            raise answer
        return CheckResult(answer=answer, input_tokens=0, output_tokens=0, cost_usd=self.costs[3], latency_s=0.0,
                           model="fake")

    async def measure(self, req: MeasureRequest) -> MeasureResult:
        self.measure_requests.append(req)
        if isinstance(self.measure_views, IdentifyError):
            raise self.measure_views
        return MeasureResult(views=list(self.measure_views or []), notes="", input_tokens=0, output_tokens=0,
                             cost_usd=self.costs[1], latency_s=0.0, model="fake")

    async def same_product(self, req: SameProductRequest) -> SameProductResult:
        self.same_requests.append(req)
        if isinstance(self.same_answer, IdentifyError):
            raise self.same_answer
        return SameProductResult(match=self.same_answer, input_tokens=0, output_tokens=0, cost_usd=0.0,
                                 latency_s=0.0, model="fake")
