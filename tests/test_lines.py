import pytest

from oi import lines
from tests.helpers import cand


def test_display_names():
    assert lines.display_name(cand("Apple", "iPhone 14"), "Smartphone", None, "de") == "Apple iPhone 14"
    assert lines.display_name(cand(None, "Lumix G9"), "Kamera", None, "de") == "Lumix G9"
    assert lines.display_name(cand("Apple", "iPhone 14", "variant", "Midnight"), "Smartphone", None, "de") == \
        "Apple iPhone 14, Midnight"
    assert lines.display_name(cand("Apple", None, "brand"), "smartphone", None, "de") == "Apple-Smartphone"
    assert lines.display_name(cand("Apple", None, "brand"), "Smartphone", None, "en") == "Apple Smartphone"
    assert lines.display_name(cand(None, None, "category"), "Tasse", "rote Keramiktasse", "de") == "Rote Keramiktasse"
    assert lines.display_name(cand(None, None, "category"), "tasse", None, "de") == "Tasse"


@pytest.mark.parametrize("lang,certain,likely", [
    ("de", "Das ist Apple iPhone 14.", "Das ist wahrscheinlich Apple iPhone 14."),
    ("en", "This is Apple iPhone 14.", "This is probably Apple iPhone 14."),
])
def test_certain_and_likely(lang, certain, likely):
    assert lines.line_certain("Apple iPhone 14", lang) == certain
    assert lines.line_likely("Apple iPhone 14", lang) == likely


def test_unsure_lines():
    a, b = "Apple iPhone 14", "Apple iPhone 13"
    assert lines.line_unsure(a, b, "die Unterseite", True, "de") == \
        "Apple iPhone 14 oder Apple iPhone 13? Zeig mir bitte die Unterseite."
    assert lines.line_unsure(a, b, None, True, "de") == "Apple iPhone 14 oder Apple iPhone 13?"
    assert lines.line_unsure(a, None, None, True, "de") == "Vielleicht Apple iPhone 14?"
    assert lines.line_unsure(a, b, "die Unterseite", False, "de") == \
        "Apple iPhone 14 oder Apple iPhone 13, von außen kaum zu unterscheiden."
    assert lines.line_unsure(a, b, "the bottom side", True, "en") == \
        "Apple iPhone 14 or Apple iPhone 13? Please show me the bottom side."
    assert lines.line_unsure(a, None, None, True, "en") == "Maybe Apple iPhone 14?"
    assert lines.line_unsure(a, b, None, False, "en") == "Apple iPhone 14 or Apple iPhone 13, hard to tell apart from the outside."


def test_category_line():
    assert lines.line_category("rote Keramiktasse", "de") == "Rote Keramiktasse, ein bestimmtes Produkt erkenne ich nicht."
    assert lines.line_category("red ceramic mug", "en") == "Red ceramic mug, I can't recognize a specific product."


@pytest.mark.parametrize("reason,de,en", [
    ("cut", "Bitte ganz ins Bild.", "Please bring it fully into view."),
    ("small", "Bitte etwas näher.", "Please come a bit closer."),
    ("blurry", "Halt es bitte ruhig.", "Please hold it still."),
    ("unsteady", "Halt es bitte ruhig.", "Please hold it still."),
])
def test_hint_lines(reason, de, en):
    assert (lines.hint_line(reason, "de"), lines.hint_line(reason, "en")) == (de, en)


def test_status_and_notice_texts():
    assert lines.error_line("de") == "Identifikation gerade nicht möglich."
    assert lines.error_line("en") == "Identification is not available right now."
    assert lines.paused_line("de") == "Kostenbremse erreicht, Identifikation pausiert."
    assert lines.paused_line("en") == "Cost limit reached, identification paused."
    assert lines.notice_text("no_key", "de") == "Kein API-Key: nur lokale Erkennung."
    assert lines.notice_text("no_key", "en") == "No API key: local detection only."
    assert lines.notice_text("model_missing", "de", model="claude-x") == \
        "Modell claude-x nicht gefunden: nur lokale Erkennung."
    assert lines.notice_text("model_missing", "en", model="claude-x") == "Model claude-x not found: local detection only."
    assert lines.notice_text("unreachable", "de") == "Claude gerade nicht erreichbar."
    assert lines.notice_text("unreachable", "en") == "Claude is not reachable right now."
