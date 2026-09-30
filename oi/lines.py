"""Every sentence the HUD card shows and the voice speaks, in German and English (spec §2.6)."""

from __future__ import annotations

from typing import Literal

from oi.config import Lang
from oi.contracts import Candidate, Depth
from oi.views import GateFailure

_TEXTS: dict[str, dict[str, str]] = {
    "de": {
        "certain": "Das ist {name}.",
        "likely": "Das ist wahrscheinlich {name}.",
        "either": "{a} oder {b}?",
        "maybe": "Vielleicht {a}?",
        "show": " Zeig mir bitte {view}.",
        "indistinct": "{a} oder {b}, von außen kaum zu unterscheiden.",
        "category": "{description}, ein bestimmtes Produkt erkenne ich nicht.",
        "cut": "Bitte ganz ins Bild.",
        "small": "Bitte etwas näher.",
        "still": "Halt es bitte ruhig.",
        "person": "Bitte nur den Gegenstand zeigen, nicht vors Gesicht.",
        "error": "Identifikation gerade nicht möglich.",
        "paused": "Kostenbremse erreicht, Identifikation pausiert.",
        "no_key": "Kein API-Key: nur lokale Erkennung.",
        "model_missing": "Modell {model} nicht gefunden: nur lokale Erkennung.",
        "unreachable": "Claude gerade nicht erreichbar.",
    },
    "en": {
        "certain": "This is {name}.",
        "likely": "This is probably {name}.",
        "either": "{a} or {b}?",
        "maybe": "Maybe {a}?",
        "show": " Please show me {view}.",
        "indistinct": "{a} or {b}, hard to tell apart from the outside.",
        "category": "{description}, I can't recognize a specific product.",
        "cut": "Please bring it fully into view.",
        "small": "Please come a bit closer.",
        "still": "Please hold it still.",
        "person": "Please show only the object, not in front of your face.",
        "error": "Identification is not available right now.",
        "paused": "Cost limit reached, identification paused.",
        "no_key": "No API key: local detection only.",
        "model_missing": "Model {model} not found: local detection only.",
        "unreachable": "Claude is not reachable right now.",
    },
}

_HINT_KEYS: dict[GateFailure, str] = {"cut": "cut", "small": "small", "blurry": "still", "unsteady": "still",
                                     "person": "person"}


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:]


def display_name(c: Candidate, category: str, description: str | None, lang: Lang) -> str:
    """Name a candidate only as specifically as its depth allows."""
    if c.depth == Depth.CATEGORY or not (c.brand or c.model_name):
        return _capitalize(description or category)
    if c.depth == Depth.BRAND or not c.model_name:
        return f"{c.brand}-{_capitalize(category)}" if lang == "de" else f"{c.brand} {category}"
    name = f"{c.brand} {c.model_name}" if c.brand else c.model_name
    if c.depth == Depth.VARIANT and c.variant:
        name = f"{name}, {c.variant}"
    return name


def line_certain(name: str, lang: Lang) -> str:
    return _TEXTS[lang]["certain"].format(name=name)


def line_likely(name: str, lang: Lang) -> str:
    return _TEXTS[lang]["likely"].format(name=name)


def line_unsure(a: str, b: str | None, view: str | None, distinguishable: bool, lang: Lang) -> str:
    texts = _TEXTS[lang]
    if b and not distinguishable:
        return texts["indistinct"].format(a=a, b=b)
    base = texts["either"].format(a=a, b=b) if b else texts["maybe"].format(a=a)
    return base + (texts["show"].format(view=view) if view else "")


def line_category(description: str, lang: Lang) -> str:
    return _TEXTS[lang]["category"].format(description=_capitalize(description))


def hint_line(reason: GateFailure, lang: Lang) -> str:
    return _TEXTS[lang][_HINT_KEYS[reason]]


def error_line(lang: Lang) -> str:
    return _TEXTS[lang]["error"]


def paused_line(lang: Lang) -> str:
    return _TEXTS[lang]["paused"]


def notice_text(key: Literal["no_key", "model_missing", "unreachable"], lang: Lang, **kw: str) -> str:
    return _TEXTS[lang][key].format(**kw)
