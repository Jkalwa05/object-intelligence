import json
from types import SimpleNamespace as NS

import pytest

from oi.config import Settings
from oi.identify import IdentifyError
from oi.modelcalls import ResearchRequest, build_research_request, parse_research

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
