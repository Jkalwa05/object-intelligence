import base64
import json
from types import SimpleNamespace

import anthropic
import pytest

from oi.config import Settings
from oi.identify import (OBSERVATION_SCHEMA, ClaudeIdentifier, FakeIdentifier, IdentifyError, IdentifyRequest,
                         build_request, choose_identifier, format_history)
from tests.helpers import cand, obs

# The cost and request tests use fixed Opus prices and effort: independent of the default model.
OPUS = Settings(model="claude-opus-5-5", effort="low")

REQ = IdentifyRequest(jpeg=b"\xff\xd8crop", coarse_label="cup", history="none", pending_view=None, language="de")
OBS = {"category": "Smartphone", "readable_text": [], "distinguishable": True, "next_view": None,
       "self_assessment": "medium", "generic_description": None,
       "candidates": [{"brand": "Apple", "model_name": "iPhone 14", "variant": None, "depth": "model",
                       "evidence": ["Apple-Logo"]}]}


class _Timeout(anthropic.APITimeoutError):
    def __init__(self) -> None:
        Exception.__init__(self, "timeout")


class _NoKey(anthropic.AuthenticationError):
    def __init__(self) -> None:
        Exception.__init__(self, "no key")


class _Missing(anthropic.NotFoundError):
    def __init__(self) -> None:
        Exception.__init__(self, "missing")


class _Offline(anthropic.APIConnectionError):
    def __init__(self) -> None:
        Exception.__init__(self, "offline")


def response(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(stop_reason=stop_reason, usage=SimpleNamespace(input_tokens=2000, output_tokens=500),
                           content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)])


class FakeClient:
    def __init__(self, reply=None, error: Exception | None = None, retrieve_error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.options: dict = {}
        self._reply, self._error, self._retrieve_error = reply, error, retrieve_error
        self.messages = SimpleNamespace(create=self._create)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self.models = SimpleNamespace(retrieve=self._retrieve)

    def with_options(self, **options):
        self.options = options
        return self

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._reply

    async def _retrieve(self, model):
        if self._retrieve_error:
            raise self._retrieve_error
        return SimpleNamespace(id=model)


def test_request_contains_only_the_crop_image():
    content = build_request(Settings(), REQ)["messages"][0]["content"]
    images = [b for b in content if b["type"] == "image"]
    assert len(images) == 1
    assert images[0]["source"] == {"type": "base64", "media_type": "image/jpeg",
                                   "data": base64.standard_b64encode(REQ.jpeg).decode()}
    assert "Coarse detector label: cup" in content[1]["text"]


def test_pending_view_is_mentioned():
    from oi.contracts import NextView
    req = IdentifyRequest(REQ.jpeg, "cell phone", "1) Apple iPhone 14", NextView(view="die Unterseite",
                                                                               reason="Lightning oder USB-C"), "de")
    assert "Requested view: die Unterseite (Lightning oder USB-C)" in build_request(Settings(), req)["messages"][0][
        "content"][1]["text"]


def test_opus_request_has_effort_schema_and_default_fallback():
    r = build_request(OPUS, REQ)
    assert r["model"] == "claude-opus-5-5" and "German" in r["system"]
    assert r["output_config"]["effort"] == "low" and r["output_config"]["format"]["schema"] is OBSERVATION_SCHEMA
    assert r["betas"] == ["server-side-fallback-2026-07-01"] and r["fallbacks"] == "default"
    assert "thinking" not in r


def test_haiku_request_has_no_effort_or_fallback():
    r = build_request(Settings(model="claude-haiku-4-5"), REQ)
    assert "effort" not in r["output_config"] and "betas" not in r and "fallbacks" not in r


async def test_parses_valid_response_and_computes_cost():
    client = FakeClient(reply=response(json.dumps(OBS)))
    result = await ClaudeIdentifier(OPUS, client).identify(REQ)
    assert result.observation.candidates[0].model_name == "iPhone 14"
    assert result.cost_usd == pytest.approx(0.018)
    assert (result.input_tokens, result.output_tokens, result.model) == (2000, 500, "claude-opus-5-5")
    assert client.options == {"timeout": 20.0} and client.calls[0]["fallbacks"] == "default"


async def test_truncates_overlong_lists():
    many = dict(OBS, candidates=[dict(OBS["candidates"][0], model_name=f"iPhone {i}") for i in range(6)])
    result = await ClaudeIdentifier(Settings(), FakeClient(reply=response(json.dumps(many)))).identify(REQ)
    assert len(result.observation.candidates) == 4


@pytest.mark.parametrize("client,reason", [
    (FakeClient(reply=response("", stop_reason="refusal")), "refusal"),
    (FakeClient(reply=response("{not json")), "schema"),
    (FakeClient(reply=response(json.dumps({"category": "x"}))), "schema"),
    (FakeClient(error=_Timeout()), "timeout"),
    (FakeClient(error=_Offline()), "connection"),
])
async def test_failures_raise_identify_error(client, reason):
    with pytest.raises(IdentifyError) as caught:
        await ClaudeIdentifier(Settings(), client).identify(REQ)
    assert caught.value.reason == reason


async def test_fake_identifier_script_and_canned_phone():
    scripted = FakeIdentifier(script=[obs(cand("Apple", "iPhone 14")), IdentifyError("timeout")])
    assert (await scripted.identify(REQ)).observation.candidates[0].model_name == "iPhone 14"
    with pytest.raises(IdentifyError):
        await scripted.identify(REQ)
    canned = await FakeIdentifier().identify(IdentifyRequest(b"", "cell phone", "none", None, "de"))
    assert canned.observation.self_assessment == "low" and canned.observation.next_view.view == "die Unterseite"
    other = await FakeIdentifier().identify(IdentifyRequest(b"", "cup", "none", None, "de"))
    assert other.observation.candidates == [] and other.observation.generic_description == "cup"
    assert scripted.model_label == "fake" and len(scripted.requests) == 2


async def test_choose_identifier_modes():
    identifier, notice, mode = await choose_identifier(OPUS, fake=True)
    assert isinstance(identifier, FakeIdentifier) and (notice, mode) == (None, "hybrid")
    identifier, notice, mode = await choose_identifier(OPUS, False, lambda: FakeClient(retrieve_error=_NoKey()))
    assert (identifier, notice, mode) == (None, "Kein API-Key: nur lokale Erkennung.", "lokal")
    identifier, notice, mode = await choose_identifier(OPUS, False, lambda: FakeClient(retrieve_error=_Missing()))
    assert (identifier, mode) == (None, "lokal") and "claude-opus-5-5" in notice
    identifier, notice, mode = await choose_identifier(OPUS, False, lambda: FakeClient(retrieve_error=_Offline()))
    assert isinstance(identifier, ClaudeIdentifier) and (notice, mode) == ("Claude gerade nicht erreichbar.", "hybrid")
    identifier, notice, mode = await choose_identifier(OPUS, False, lambda: FakeClient())
    assert isinstance(identifier, ClaudeIdentifier) and (notice, mode) == (None, "hybrid")


def test_format_history():
    assert format_history([], "de") == "none"
    text = format_history([obs(cand("Apple", "iPhone 14", ev=("Apple-Logo",)), cand("Apple", "iPhone 13"))], "de")
    assert text.startswith("1) Apple iPhone 14 | Apple iPhone 13") and "evidence: Apple-Logo" in text


class _Overloaded(anthropic.InternalServerError):
    def __init__(self) -> None:
        Exception.__init__(self, "overloaded")


async def test_overloaded_startup_keeps_claude():
    identifier, notice, mode = await choose_identifier(Settings(), False, lambda: FakeClient(retrieve_error=_Overloaded()))
    assert isinstance(identifier, ClaudeIdentifier) and (notice, mode) == ("Claude gerade nicht erreichbar.", "hybrid")


# --- the scene: one call names and locates the background -----------------------------------------------------------

from oi.identify import SceneRequest, build_scene_request, parse_scene  # noqa: E402

SCENE_REQ = SceneRequest(jpeg=b"\xff\xd8room", language="de")


def test_scene_request_sends_one_image_and_asks_for_names_and_boxes():
    request = build_scene_request(Settings(), SCENE_REQ)
    images = [b for b in request["messages"][0]["content"] if b["type"] == "image"]
    assert len(images) == 1 and images[0]["source"]["data"] == base64.standard_b64encode(SCENE_REQ.jpeg).decode()
    assert "grey" in request["system"] and "German" in request["system"] and "0 to 1000" in request["system"]
    assert request["output_config"]["format"]["schema"]["properties"]["items"]["items"]["required"] == ["name", "box"]
    assert request["fallbacks"] == "default"


def test_scene_answer_is_cleaned_up():
    text = json.dumps({"items": [
        {"name": " Pendelleuchte ", "box": [367, 38, 475, 338]},
        {"name": "Treppe", "box": [976, 955, 798, 230]},  # corners swapped
        {"name": "Regal", "box": [-20, 0, 285, 1200]},  # reaches outside the image
        {"name": "", "box": [1, 2, 300, 400]},  # no name
        {"name": "Punkt", "box": [500, 500, 501, 501]},  # no area
        {"name": "Kaputt", "box": [1, 2, 3]},
    ] + [{"name": f"Box {i}", "box": [0, 0, 100, 100]} for i in range(20)]})
    items = parse_scene(text)
    assert [(i.label, i.box) for i in items[:3]] == [("Pendelleuchte", (0.367, 0.038, 0.475, 0.338)),
                                                    ("Treppe", (0.798, 0.23, 0.976, 0.955)),
                                                    ("Regal", (0.0, 0.0, 0.285, 1.0))]
    assert len(items) == 15


def test_scene_answer_that_is_no_json_is_a_schema_error():
    with pytest.raises(IdentifyError) as error:
        parse_scene("no json")
    assert error.value.reason == "schema"


async def test_scene_call_reports_cost_like_an_identification():
    client = FakeClient(reply=response(json.dumps({"items": [{"name": "Pendelleuchte", "box": [367, 38, 475, 338]}]})))
    result = await ClaudeIdentifier(OPUS, client).describe_scene(SCENE_REQ)
    assert [i.label for i in result.items] == ["Pendelleuchte"]
    assert result.cost_usd == pytest.approx(0.018) and result.model == "claude-opus-5-5"


async def test_scene_call_failures_raise_identify_error():
    with pytest.raises(IdentifyError) as error:
        await ClaudeIdentifier(Settings(), FakeClient(error=_Offline())).describe_scene(SCENE_REQ)
    assert error.value.reason == "connection"


async def test_fake_scene_answers_from_its_script():
    from oi.contracts import SceneItemWire
    lamp = SceneItemWire(label="Pendelleuchte", box=(0.4, 0.0, 0.5, 0.3))
    fake = FakeIdentifier(scene=[lamp])
    assert (await fake.describe_scene(SCENE_REQ)).items == [lamp] and fake.scene_requests == [SCENE_REQ]
    assert (await FakeIdentifier().describe_scene(SCENE_REQ)).items == []
    with pytest.raises(IdentifyError):
        await FakeIdentifier(scene=IdentifyError("api")).describe_scene(SCENE_REQ)


# --- product profile (sub-project 2): Claude's own knowledge, text only ---------------------------------------------

from oi.identify import ProductRequest, build_profile_request, parse_profile  # noqa: E402

PRODUCT_REQ = ProductRequest(product="Apple iPhone 14", category="Smartphone", language="de")
PROFILE = {"known": True, "summary": "Ein Smartphone von Apple.", "facts": [{"label": "Chip", "value": "A15 Bionic"}],
           "released": "September 2022", "launch_price": "999 €", "trivia": ["Erstes iPhone mit Unfallerkennung."]}


def test_profile_request_sends_no_image_only_the_name():
    request = build_profile_request(Settings(), PRODUCT_REQ)
    content = request["messages"][0]["content"]
    assert [block["type"] for block in content] == ["text"]
    assert "Apple iPhone 14" in content[0]["text"] and "Smartphone" in content[0]["text"]
    assert "German" in request["system"] and "known" in request["system"]
    assert request["output_config"]["format"]["schema"]["required"] == ["known", "summary", "facts", "released",
                                                                       "launch_price", "trivia"]


def test_profile_answer_is_trimmed():
    text = json.dumps({**PROFILE, "summary": "  Ein Smartphone von Apple.  ", "trivia": ["a", "b", "c"],
                       "facts": [{"label": f"Wert {i}", "value": str(i)} for i in range(12)]})
    profile = parse_profile(text)
    assert profile.summary == "Ein Smartphone von Apple." and len(profile.facts) == 8 and profile.trivia == ["a", "b"]
    empty = parse_profile(json.dumps({**PROFILE, "facts": [{"label": " ", "value": "x"}, {"label": "Chip", "value": ""}]}))
    assert empty.facts == []


def test_unknown_product_gives_an_empty_profile():
    profile = parse_profile(json.dumps({**PROFILE, "known": False}))
    assert (profile.known, profile.summary, profile.facts, profile.trivia, profile.released, profile.launch_price) \
        == (False, "", [], [], None, None)


async def test_profile_call_reports_cost():
    client = FakeClient(reply=response(json.dumps(PROFILE)))
    result = await ClaudeIdentifier(OPUS, client).describe_product(PRODUCT_REQ)
    assert result.profile.facts[0].value == "A15 Bionic" and result.cost_usd == pytest.approx(0.018)


async def test_fake_profile_from_script_or_unknown():
    from oi.contracts import ProductProfile
    profile = ProductProfile.model_validate(PROFILE)
    fake = FakeIdentifier(profile=profile)
    assert (await fake.describe_product(PRODUCT_REQ)).profile == profile and fake.product_requests == [PRODUCT_REQ]
    assert (await FakeIdentifier().describe_product(PRODUCT_REQ)).profile.known is False
    with pytest.raises(IdentifyError):
        await FakeIdentifier(profile=IdentifyError("api")).describe_product(PRODUCT_REQ)


# --- the same object seen twice (sub-project 3): one comparison call with small crops -------------------------------

from oi.identify import SameRequest, build_same_request, parse_same  # noqa: E402


def test_same_request_shows_the_new_object_and_the_earlier_ones():
    req = SameRequest(new_jpeg=b"\xff\xd8now", earlier=[("Sony DualShock 3", b"\xff\xd8a"), ("Pendelleuchte", b"\xff\xd8b")],
                      language="de")
    request = build_same_request(Settings(), req)
    content = request["messages"][0]["content"]
    assert [b["type"] for b in content].count("image") == 3
    texts = " ".join(b["text"] for b in content if b["type"] == "text")
    assert "1: Sony DualShock 3" in texts and "2: Pendelleuchte" in texts
    assert "same physical object" in request["system"] and "German" in request["system"]


def test_same_answer_must_name_one_of_the_earlier_objects():
    assert parse_same(json.dumps({"same_as": 2, "reason": "gleiche Form"}), 2) == (2, "gleiche Form")
    assert parse_same(json.dumps({"same_as": None, "reason": "anders"}), 2) == (None, "anders")
    assert parse_same(json.dumps({"same_as": 3, "reason": "?"}), 2)[0] is None  # there is no third one
    assert parse_same(json.dumps({"same_as": 0, "reason": "?"}), 2)[0] is None


async def test_fake_comparison_from_its_script():
    req = SameRequest(new_jpeg=b"x", earlier=[("A", b"y")], language="de")
    fake = FakeIdentifier(same=1)
    assert (await fake.compare(req)).same_as == 1 and fake.same_requests == [req]
    assert (await FakeIdentifier().compare(req)).same_as is None


# --- questions by voice (sub-project 4): Claude answers, searching the web when it needs to ------------------------

from oi.identify import AskRequest, build_ask_request, parse_answer  # noqa: E402

ASK_REQ = AskRequest(question="Was kostet das heute gebraucht?", product="Apple iPhone 14", category="Smartphone",
                     level="likely", facts="Chip: A15 Bionic; Display: 6,1 Zoll", history=[("Wie schwer ist das?",
                     "Es wiegt 172 Gramm.")], jpeg=b"\xff\xd8crop", language="de")


def test_ask_request_has_the_object_the_history_and_the_web_search():
    request = build_ask_request(Settings(), ASK_REQ)
    content = request["messages"][0]["content"]
    assert content[0]["type"] == "image"
    text = content[-1]["text"]
    for part in ("Apple iPhone 14", "Smartphone", "A15 Bionic", "Wie schwer ist das?", "172 Gramm",
                 "Was kostet das heute gebraucht?"):
        assert part in text
    assert request["tools"][0]["type"] == "web_search_20260209" and request["tools"][0]["name"] == "web_search"
    assert request["output_config"] == {"effort": "medium"}  # with low effort Claude skipped a needed search
    assert "used prices" in request["system"]
    assert "German" in request["system"] and "output_config" not in request or "format" not in request["output_config"]


def test_answer_keeps_the_text_and_the_sources():
    blocks = [SimpleNamespace(type="server_tool_use"), SimpleNamespace(type="web_search_tool_result"),
              SimpleNamespace(type="text", text="Gebraucht kostet es etwa 350 Euro.", citations=[
                  SimpleNamespace(type="web_search_result_location", url="https://a.de/x", title="A"),
                  SimpleNamespace(type="web_search_result_location", url="https://a.de/x", title="A")]),
              SimpleNamespace(type="text", text=" Neu war es teurer.", citations=None)]
    answer, sources = parse_answer(blocks)
    assert answer == "Gebraucht kostet es etwa 350 Euro. Neu war es teurer."
    assert [(s.title, s.url) for s in sources] == [("A", "https://a.de/x")]


async def test_a_search_adds_its_price():
    reply = SimpleNamespace(stop_reason="end_turn",
                            usage=SimpleNamespace(input_tokens=2000, output_tokens=500,
                                                  server_tool_use=SimpleNamespace(web_search_requests=2)),
                            content=[SimpleNamespace(type="text", text="Etwa 350 Euro.", citations=None)])
    result = await ClaudeIdentifier(OPUS, FakeClient(reply=reply)).answer(ASK_REQ)
    assert result.answer == "Etwa 350 Euro." and result.searches == 2
    assert result.cost_usd == pytest.approx(0.018 + 0.02)


async def test_fake_answers_from_its_script():
    fake = FakeIdentifier(answer="Es wiegt 172 Gramm.")
    result = await fake.answer(ASK_REQ)
    assert (result.answer, fake.ask_requests) == ("Es wiegt 172 Gramm.", [ASK_REQ])


def test_without_citations_the_pages_found_are_the_sources():
    found = SimpleNamespace(type="web_search_tool_result", content=[
        SimpleNamespace(type="web_search_result", url=f"https://shop{i}.de", title=f"Shop {i}") for i in range(5)])
    answer, sources = parse_answer([found, SimpleNamespace(type="text", text="Etwa 25 Euro.", citations=None)])
    assert answer == "Etwa 25 Euro." and [s.url for s in sources] == ["https://shop0.de", "https://shop1.de",
                                                                       "https://shop2.de"]


def test_german_questions_search_from_germany_once():
    request = build_ask_request(Settings(), ASK_REQ)
    tool = request["tools"][0]
    assert tool["max_uses"] == 1
    assert tool["user_location"] == {"type": "approximate", "country": "DE", "timezone": "Europe/Berlin"}
