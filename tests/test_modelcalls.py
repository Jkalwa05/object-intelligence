import json
from types import SimpleNamespace as NS

import pytest

from oi.config import Settings
from oi.identify import IdentifyError
from oi.modelcalls import ResearchRequest, build_research_request, parse_research

# The cost and request tests use fixed Opus prices and effort: independent of the default model.
OPUS = Settings(model="claude-opus-5-5", effort="low")

RESEARCH_REQ = ResearchRequest(model="Apple iPhone 14", category="Smartphone", language="de")
SHEET = {
    "size_mm": [71.5, 146.7, 7.8], "size_source": 0,
    "measures": [{"label": "Kameraplateau Breite", "value_mm": 30.4, "source": 1, "kind": "drawing"}],
    "features": ["Kameraplateau oben links"],
    "sources": [{"title": "iPhone 14 – Technische Daten", "url": "https://www.apple.com/de/iphone-14/specs/"},
                {"title": "Dimensional Drawings", "url": "https://developer.apple.com/accessories/drawings.pdf"}],
    "drawing": {"url": "https://developer.apple.com/accessories/drawings.pdf", "find": "iPhone 14 Dimensions"},
}


def answer(sheet: dict, prose: str = "Ich habe die Maße gefunden.") -> list:
    search = NS(type="web_search_tool_result", content=[NS(url="https://www.apple.com/de/iphone-14/specs/", title="a"),
                                                       NS(url="https://developer.apple.com/accessories/drawings.pdf",
                                                          title="b")])
    fetched = NS(type="web_fetch_tool_result", content=NS(type="web_fetch_result",
                                                          url="https://www.apple.com/de/iphone-14/specs/"))
    failed = NS(type="web_fetch_tool_result", content=NS(type="web_fetch_tool_result_error", error_code="x"))
    return [NS(type="server_tool_use"), search, fetched, failed,
            NS(type="text", text=f"{prose}\n```json\n{json.dumps(sheet)}\n```")]


def test_research_request_has_search_fetch_and_no_image():
    request = build_research_request(Settings(), RESEARCH_REQ)
    search, fetch = request["tools"]
    assert (search["type"], search["max_uses"], search["user_location"]["country"]) == ("web_search_20260209", 3, "DE")
    assert (fetch["type"], fetch["max_uses"], fetch["max_content_tokens"]) == ("web_fetch_20250910", 3, 15000)
    content = request["messages"][0]["content"]
    assert all(block["type"] == "text" for block in content) and "Apple iPhone 14" in content[0]["text"]
    assert request["output_config"] == {"effort": "medium"} and request["max_tokens"] == 16000
    assert "Never fetch PDF" in request["system"] and "German" in request["system"]
    english = build_research_request(Settings(), ResearchRequest("Apple iPhone 14", "Smartphone", "en"))
    assert "user_location" not in english["tools"][0]


def test_parse_research_reads_the_json_and_the_allowed_urls():
    sheet, allowed = parse_research(answer(SHEET))
    assert sheet.size_mm == (71.5, 146.7, 7.8) and sheet.size_source == 0
    assert sheet.measures[0].label == "Kameraplateau Breite" and sheet.measures[0].kind == "drawing"
    assert sheet.drawing is not None and sheet.drawing.find == "iPhone 14 Dimensions"
    assert allowed == {"https://www.apple.com/de/iphone-14/specs/", "https://developer.apple.com/accessories/drawings.pdf"}
    two = answer(SHEET)  # a draft block first: the last json block counts
    two[-1] = NS(type="text", text="```json\n{\"size_mm\": null}\n```\nNoch einmal:\n" + two[-1].text)
    assert parse_research(two)[0].size_mm == (71.5, 146.7, 7.8)


def test_research_reads_photos():
    photos = [{"url": "https://a/1.png", "view": "front"}, {"url": "http://a/2.png", "view": "back"},
              {"url": "https://a/3.png", "view": "bottom"}, {"view": "top"},
              {"url": "https://a/4.webp", "view": "side-front-left"}, {"url": "https://a/5.png", "view": "top"},
              {"url": "https://a/6.png", "view": "back"}, {"url": "https://a/7.png", "view": "front"}]
    sheet, _ = parse_research(answer({**SHEET, "photos": photos}))
    assert [(p.url, p.view) for p in sheet.photos] == [
        ("https://a/1.png", "front"), ("https://a/4.webp", "side-front-left"), ("https://a/5.png", "top"),
        ("https://a/6.png", "back")]
    assert parse_research(answer(SHEET))[0].photos == []


def test_links_in_fetched_pages_are_found():
    blocks = answer(SHEET)
    page = NS(type="document", source=NS(type="text", media_type="text/plain",
              data="Drawing ![x](https://cdn.example.com/d.svg) and photo https://cdn.example.com/p.webp. "
                   "Old http://old.example.com/a.png"))
    fetched = NS(type="web_fetch_result", url="https://www.dimensions.com/e/ds3", content=page)
    blocks.insert(2, NS(type="web_fetch_tool_result", content=fetched))
    _, allowed = parse_research(blocks)
    assert {"https://cdn.example.com/d.svg", "https://cdn.example.com/p.webp",
            "https://www.dimensions.com/e/ds3"} <= allowed  # a drawing on a CDN, linked from the fetched page
    assert not any(url.startswith("http://") for url in allowed)


def test_parse_research_clips_and_repairs():
    messy = {
        **SHEET, "size_source": 7,
        "measures": [{"label": "Maß", "value_mm": 1.0, "source": 0, "kind": "datasheet"}] * 34
                    + [{"label": "negativ", "value_mm": -3, "source": 0, "kind": "drawing"},
                       {"label": "riesig", "value_mm": 9000, "source": 0, "kind": "drawing"}],
        "features": ["x"] * 25,
        "sources": SHEET["sources"] * 4,
        "drawing": {"url": "http://developer.apple.com/a.pdf", "find": "iPhone"},
    }
    messy["measures"][0] = {"label": "falsche Quelle", "value_mm": 5.0, "source": 9, "kind": "drawing"}
    messy["measures"][1] = {"label": "unbekannte Art", "value_mm": 5.0, "source": 0, "kind": "guess"}
    sheet, _ = parse_research(answer(messy))
    assert len(sheet.measures) == 30 and len(sheet.features) == 20 and len(sheet.sources) == 6
    assert sheet.size_source is None
    assert (sheet.measures[0].source, sheet.measures[0].kind) == (None, "estimate")
    assert sheet.measures[1].kind == "estimate"
    assert all(0 < m.value_mm <= 5000 for m in sheet.measures)
    assert sheet.drawing is None  # only https


@pytest.mark.parametrize("text", ["Keine Daten gefunden.", "```json\n[1, 2]\n```", "```json\n{kaputt\n```"])
def test_parse_research_without_json_is_a_schema_error(text):
    with pytest.raises(IdentifyError):
        parse_research([NS(type="text", text=text)])


# --- CAD and check calls (Task 8) -----------------------------------------------------------------------------------

from oi.contracts import MeasureSheet  # noqa: E402
from oi.modelcalls import (CadPart, CadProgram, CadRequest, CheckAnswer, CheckRequest, ClaudeModelCalls,  # noqa: E402
                           FakeModelCalls, apply_check, build_cad_request, build_check_request, parse_cad,
                           parse_check, scad_source)
from oi.scad import HEADER  # noqa: E402

SHEET_OBJ = MeasureSheet.model_validate(SHEET)
PNG = b"\x89PNG\r\n\x1a\nfake"
BODY = {"name": "Gehäuse", "color": "#9fc4e8", "scad": "cuboid([w, h, d], rounding=9, edges=\"Z\");"}
CAD = {"shared": "w = 71.5; h = 146.7; d = 7.8;", "parts": [BODY], "notes": "Tasten angenähert"}
PROGRAM = CadProgram(shared="w = 71.5;", parts=[CadPart("Gehäuse", "#9fc4e8", "cube(w);"),
                                                CadPart("Linse", "#111111", "cyl(d=13, h=2);")], notes="")


def cad_request(**kw) -> CadRequest:
    base = dict(model="Apple iPhone 14", category="Smartphone", sheet=SHEET_OBJ,
                drawings=[(PNG, "image/png"), (PNG, "image/png")], jpeg=b"\xff\xd8crop", language="de")
    return CadRequest(**{**base, **kw})


def check_request(**kw) -> CheckRequest:
    base = dict(model="Apple iPhone 14", sheet=SHEET_OBJ, drawings=[(PNG, "image/png")], jpeg=b"\xff\xd8crop",
                program=PROGRAM, renders=[PNG] * 4, errors={"Linse": ["ERROR: Parser error"]},
                size_hint="Breite 80,0 mm statt 71,5 mm", round=1, rounds=2, language="de")
    return CheckRequest(**{**base, **kw})


def media(content: list) -> list[str]:
    return [b["source"]["media_type"] for b in content if b["type"] == "image"]


def test_cad_request_carries_sheet_drawings_and_crop():
    request = build_cad_request(Settings(), cad_request())
    content = request["messages"][0]["content"]
    assert media(content) == ["image/png", "image/png", "image/jpeg"]
    text = " ".join(b["text"] for b in content if b["type"] == "text")
    assert "Kameraplateau Breite" in text and "Apple iPhone 14" in text
    assert request["output_config"]["effort"] == "high" and request["output_config"]["format"]["type"] == "json_schema"
    assert request["max_tokens"] == 32000 and "cuboid(" in request["system"] and "German" in request["system"]
    assert media(build_cad_request(Settings(), cad_request(drawings=[], jpeg=None))["messages"][0]["content"]) == []


def test_parse_cad_limits_colours_and_unique_names():
    long_part = {"name": "zu lang", "color": "#000000", "scad": "x" * 12001}
    program = parse_cad(json.dumps({**CAD, "parts": [BODY, {**BODY, "color": "blau"}, {**BODY, "name": "x" * 60},
                                                     long_part, {"name": "leer", "color": "#000000", "scad": "  "}]
                                    + [BODY] * 50}))
    assert len(program.parts) == 40
    assert [p.name for p in program.parts[:3]] == ["Gehäuse", "Gehäuse 2", "x" * 39 + "…"]
    assert program.parts[1].color == "#9aa0a6" and program.shared.startswith("w = 71.5")
    assert all(p.name not in ("zu lang", "leer") for p in program.parts)
    assert len({p.name for p in program.parts}) == 40


@pytest.mark.parametrize("text", [json.dumps({**CAD, "parts": []}), json.dumps({**CAD, "shared": "x" * 20001}),
                                  "kaputt"])
def test_parse_cad_without_parts_is_a_schema_error(text):
    with pytest.raises(IdentifyError):
        parse_cad(text)


def test_check_request_labels_the_four_views_and_the_round():
    request = build_check_request(Settings(), check_request())
    content = request["messages"][0]["content"]
    text = " ".join(b["text"] for b in content if b["type"] == "text")
    for label in ("vorn", "hinten", "rechts", "oben", "Runde 1 von 2", "ERROR: Parser error", "Breite 80,0 mm",
                  "cube(w);", "Kameraplateau Breite"):
        assert label in text, label
    assert media(content) == ["image/png"] * 5 + ["image/jpeg"]
    assert request["output_config"]["effort"] == "high"
    answer = parse_check(json.dumps({"verdict": "fix", "issues": ["Linse zu groß"] * 12, "shared": None,
                                     "parts": [{"name": "Linse", "color": "#111111", "scad": "cyl(d=10, h=2);"}],
                                     "remove": ["Blitz"]}))
    assert (answer.verdict, len(answer.issues), answer.shared, answer.remove) == ("fix", 10, None, ["Blitz"])
    assert parse_check(json.dumps({"verdict": "super", "issues": [], "shared": None, "parts": [],
                                   "remove": []})).verdict == "fix"


def test_apply_check_replaces_appends_and_removes():
    answer = CheckAnswer(verdict="fix", issues=[], shared="w = 70;",
                         parts=[CadPart("Linse", "#222222", "cyl(d=12, h=2);"), CadPart("Blitz", "#ffffff", "sphere(2);")],
                         remove=["Gehäuse"])
    fixed = apply_check(PROGRAM, answer)
    assert fixed.shared == "w = 70;"
    assert [(p.name, p.scad) for p in fixed.parts] == [("Linse", "cyl(d=12, h=2);"), ("Blitz", "sphere(2);")]
    same = apply_check(PROGRAM, CheckAnswer("good", [], None, [], []))
    assert same == PROGRAM


def test_scad_source_has_header_shared_and_every_part():
    source = scad_source(PROGRAM)
    assert source.startswith(HEADER) and "w = 71.5;" in source
    assert source.index("// --- Gehäuse") < source.index("cube(w);") < source.index("// --- Linse")


class StreamClient:
    """Stands in for the Anthropic client's streaming calls: answers `final` after `delay` seconds."""

    def __init__(self, final, delay: float = 0.0) -> None:
        from types import SimpleNamespace
        self.final, self.delay, self.options, self.calls = final, delay, {}, []
        self.messages = SimpleNamespace(stream=self._stream)
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def with_options(self, **options):
        self.options = options
        return self

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_final_message(self):
        import asyncio
        await asyncio.sleep(self.delay)
        return self.final


async def test_claude_model_calls_stream_without_retries_and_report_cost():
    from types import SimpleNamespace

    from oi.identify import ClaudeIdentifier
    from tests.test_identify import response
    usage = SimpleNamespace(input_tokens=30000, output_tokens=2000,
                            server_tool_use=SimpleNamespace(web_search_requests=2, web_fetch_requests=1))
    client = StreamClient(SimpleNamespace(stop_reason="end_turn", usage=usage, content=answer(SHEET)))
    calls = ClaudeModelCalls(ClaudeIdentifier(OPUS, client), OPUS)
    result = await calls.research(RESEARCH_REQ)
    assert result.sheet.size_mm == (71.5, 146.7, 7.8) and result.searches == 2
    assert result.cost_usd == pytest.approx(30000 * 4 / 1e6 + 2000 * 20 / 1e6 + 2 * 0.01)
    assert client.options["max_retries"] == 0  # a retried CAD call would be paid twice
    assert client.calls[0]["tools"][0]["type"] == "web_search_20260209"
    client = StreamClient(response(json.dumps(CAD)))
    cad = await ClaudeModelCalls(ClaudeIdentifier(OPUS, client), OPUS).build_cad(cad_request())
    assert cad.program.parts[0].name == "Gehäuse" and cad.cost_usd == pytest.approx(2000 * 4 / 1e6 + 500 * 20 / 1e6)
    client = StreamClient(response(json.dumps({"verdict": "good", "issues": [], "shared": None, "parts": [],
                                               "remove": []})))
    checked = await ClaudeModelCalls(ClaudeIdentifier(OPUS, client), OPUS).check_cad(check_request())
    assert checked.answer.verdict == "good" and client.options["max_retries"] == 0


async def test_the_precision_model_has_its_own_claude_model():
    from oi.identify import ClaudeIdentifier
    from tests.test_identify import response
    settings = Settings(model="claude-sonnet-5-5", cad_model="claude-opus-5-5")  # identify with Sonnet, build with Opus
    client = StreamClient(response(json.dumps(CAD)))
    cad = await ClaudeModelCalls(ClaudeIdentifier(settings, client), settings).build_cad(cad_request())
    assert client.calls[0]["model"] == cad.model == "claude-opus-5-5"
    assert cad.cost_usd == pytest.approx(2000 * 4 / 1e6 + 500 * 20 / 1e6)  # at Opus prices
    client = StreamClient(response(json.dumps({"verdict": "good", "issues": [], "shared": None, "parts": [],
                                               "remove": []})))
    checked = await ClaudeModelCalls(ClaudeIdentifier(settings, client), settings).check_cad(check_request())
    assert client.calls[0]["model"] == checked.model == "claude-opus-5-5"


async def test_a_model_call_that_runs_past_its_deadline_is_a_timeout():
    import time

    from oi.identify import ClaudeIdentifier
    from tests.test_identify import response
    settings = Settings(model_timeout_s=0.2)
    client = StreamClient(response(json.dumps(CAD)), delay=5.0)
    started = time.perf_counter()
    with pytest.raises(IdentifyError) as error:
        await ClaudeModelCalls(ClaudeIdentifier(settings, client), settings).build_cad(cad_request())
    assert error.value.reason == "timeout" and time.perf_counter() - started < 2


async def test_fake_model_calls_follow_the_script():
    fake = FakeModelCalls(research=SHEET_OBJ, cad=PROGRAM, costs=(0.3, 0.0, 0.3, 0.2),
                          checks=[CheckAnswer("fix", ["Linse"], None, [], []), IdentifyError("api")])
    researched = await fake.research(RESEARCH_REQ)
    assert researched.sheet == SHEET_OBJ and researched.cost_usd == 0.3
    assert SHEET["drawing"]["url"] in researched.allowed_urls
    assert (await fake.build_cad(cad_request())).program == PROGRAM
    assert (await fake.check_cad(check_request())).answer.verdict == "fix"
    with pytest.raises(IdentifyError):
        await fake.check_cad(check_request())
    assert (await fake.check_cad(check_request())).answer.verdict == "good"  # script used up: good
    assert len(fake.check_requests) == 3 and len(fake.research_requests) == len(fake.cad_requests) == 1
    plain = FakeModelCalls()
    assert (await plain.research(RESEARCH_REQ)).sheet == MeasureSheet.estimated()
    assert (await plain.build_cad(cad_request())).program.parts
    with pytest.raises(IdentifyError):
        await FakeModelCalls(cad=IdentifyError("timeout")).build_cad(cad_request())


# --- sub-project 7: measuring, product names, photos, part map and deviations ------------------------------------

def measure_request(**kw):
    from oi.modelcalls import MeasureRequest
    base = dict(model="Sony DualShock 3", sheet=SHEET_OBJ, language="de",
                pictures=[((PNG, "image/png"), "technical drawing page 1"), ((PNG, "image/png"), "photo, front")])
    return MeasureRequest(**{**base, **kw})


def texts(request: dict) -> list[str]:
    return [b["text"] for b in request["messages"][0]["content"] if b["type"] == "text"]


def test_measure_request_numbers_the_pictures():
    from oi.modelcalls import build_measure_request
    from oi.modelprompts import MEASURE_SCHEMA
    request = build_measure_request(OPUS, measure_request())
    assert "Picture 1 (technical drawing page 1):" in texts(request) and "Picture 2 (photo, front):" in texts(request)
    assert sum(b["type"] == "image" for b in request["messages"][0]["content"]) == 2
    assert request["output_config"]["format"]["schema"] == MEASURE_SCHEMA
    assert (request["max_tokens"], request["output_config"]["effort"]) == (16000, "high")
    assert "German" in request["system"] and "fractions" in request["system"]


async def test_measure_call_parses_views_and_costs():
    from oi.identify import ClaudeIdentifier
    from tests.test_identify import response
    views = {"views": [{"picture": 2, "view": "front", "object": [0.1, 0.0, 0.9, 0.97],
                        "parts": [{"name": "Dreieck-Taste", "box": [0.7, 0.2, 0.75, 0.3]}]}], "notes": "ok"}
    settings = Settings(model="claude-sonnet-5-5", cad_model="claude-opus-5-5")
    client = StreamClient(response(json.dumps(views)))
    result = await ClaudeModelCalls(ClaudeIdentifier(settings, client), settings).measure(measure_request())
    assert result.views[0].parts[0][0] == "Dreieck-Taste" and result.notes == "ok"
    assert client.calls[0]["model"] == result.model == "claude-opus-5-5"
    assert result.cost_usd == pytest.approx(2000 * 4 / 1e6 + 500 * 20 / 1e6)


async def test_same_product_matches_only_a_candidate():
    from oi.identify import ClaudeIdentifier
    from oi.modelcalls import SameProductRequest, build_same_product_request, parse_same_product
    from oi.modelprompts import SAME_PRODUCT_SCHEMA
    from tests.test_identify import FakeClient, response
    candidates = ["Sony DualShock 3", "Apple iPhone 14"]
    assert parse_same_product('{"match": "Sony DualShock 3"}', candidates) == "Sony DualShock 3"
    assert parse_same_product('{"match": "Sony DualShock 4"}', candidates) is None
    assert parse_same_product('{"match": null}', candidates) is None
    with pytest.raises(IdentifyError):
        parse_same_product("vielleicht", candidates)
    req = SameProductRequest("Sony PlayStation 3 DualShock 3", candidates, "de")
    request = build_same_product_request(OPUS, req)
    assert "Sony PlayStation 3 DualShock 3" in texts(request)[0] and "1. Sony DualShock 3" in texts(request)[0]
    assert request["output_config"]["format"]["schema"] == SAME_PRODUCT_SCHEMA
    settings = Settings(model="claude-sonnet-5-5", cad_model="claude-opus-5-5")
    client = FakeClient(reply=response('{"match": "Sony DualShock 3"}'))
    result = await ClaudeModelCalls(ClaudeIdentifier(settings, client), settings).same_product(req)
    assert result.match == "Sony DualShock 3" and client.calls[0]["model"] == result.model == "claude-opus-5-5"


def test_cad_and_check_requests_carry_photos_map_and_deviations():
    photos = [((PNG, "image/png"), "front")]
    mapped = "Measured parts …\nDreieck-Taste: x 44.0…50.0 mm (1 view)"
    cad = build_cad_request(OPUS, cad_request(photos=photos, part_map=mapped))
    assert "Reference photo (front):" in texts(cad) and mapped in texts(cad)
    assert sum(b["type"] == "image" for b in cad["messages"][0]["content"]) == 4  # 2 drawing pages, crop, photo
    off = "Dreieck-Taste: x model 48.0…54.0, measured 44.0…50.0 mm (off by 4.0 mm)"
    check = build_check_request(OPUS, check_request(photos=photos, part_map=mapped, deviations=[off]))
    assert "Reference photo (front):" in texts(check) and mapped in texts(check)
    assert f"Measured deviations (fix them):\n{off}" in texts(check)
    plain = texts(build_check_request(OPUS, check_request())) + texts(build_cad_request(OPUS, cad_request()))
    assert not any("Measured" in t or "Reference photo" in t for t in plain)


async def test_fake_measure_and_same_product_follow_the_script():
    from oi.measure import ViewBoxes
    from oi.modelcalls import SameProductRequest
    front = ViewBoxes(1, "front", (0.1, 0.0, 0.9, 0.97), [])
    fake = FakeModelCalls(measure=[front], same="Sony DualShock 3", costs=(0.0, 0.07, 0.0, 0.0))
    measured = await fake.measure(measure_request())
    assert measured.views == [front] and measured.cost_usd == 0.07
    assert (await fake.same_product(SameProductRequest("x", ["Sony DualShock 3"], "de"))).match == "Sony DualShock 3"
    assert (len(fake.measure_requests), len(fake.same_requests)) == (1, 1)
    assert (await FakeModelCalls().measure(measure_request())).views == []
    failing = FakeModelCalls(measure=IdentifyError("api"), same=IdentifyError("api"))
    with pytest.raises(IdentifyError):
        await failing.measure(measure_request())
    with pytest.raises(IdentifyError):
        await failing.same_product(SameProductRequest("x", ["y"], "de"))


# --- sub-project 8: the outline ----------------------------------------------------------------------------------

def test_outline_reaches_cad_and_check():
    outline = "Measured outline in 20 bands …\nheight 98 % (y 43.6…48.5 mm): x -20.0…20.0 mm (2 pictures)"
    cad = build_cad_request(OPUS, cad_request(outline=outline, photos=[((PNG, "image/png"), None)]))
    assert outline in texts(cad) and "Reference photo (view unknown):" in texts(cad)
    off = "height 98 % (y 43.6…48.5 mm): x model -80.0…80.0, measured -20.0…20.0 mm (off by 60.0 mm)"
    check = build_check_request(OPUS, check_request(outline=outline, outline_deviations=[off]))
    assert outline in texts(check) and f"Outline deviations (fix them):\n{off}" in texts(check)
    plain = texts(build_check_request(OPUS, check_request())) + texts(build_cad_request(OPUS, cad_request()))
    assert not any("outline" in t.lower() for t in plain)


def test_measure_schema_and_prompt_ask_for_slices():
    from oi.modelprompts import CAD_PROMPT, CHECK_PROMPT, MEASURE_PROMPT, MEASURE_SCHEMA
    view = MEASURE_SCHEMA["properties"]["views"]["items"]
    assert "slices" in view["properties"] and "slices" in view["required"]
    assert "tilt" in view["properties"] and "tilt" in view["required"] and "grey background" in MEASURE_PROMPT
    assert "20" in MEASURE_PROMPT and "null" in MEASURE_PROMPT and "camera" in MEASURE_PROMPT
    assert "rotate_extrude" in CAD_PROMPT and "outline deviations" in CHECK_PROMPT.lower()
