"""All thresholds, limits, prices and model names in one place (spec §6)."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

Lang = Literal["de", "en"]

# US dollars per million tokens: (input, output)
DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


def _parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in ("1", "true", "yes", "on"):
        return True
    if lowered in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"expected 0 or 1, got {value!r}")


@dataclass(frozen=True)
class Settings:
    model: str = "claude-sonnet-5-5"
    effort: str = "high"
    language: Lang = "de"
    max_calls_object: int = 4
    max_calls_session: int = 150
    max_concurrent_calls: int = 2
    detector: str = "yoloe-26s-seg-pf.pt"
    detector_fallback: str = "yoloe-11s-seg-pf.pt"
    imgsz: int = 640
    conf: float = 0.25
    device: str = "mps"
    focus_weights: tuple[float, float, float, float, float] = (0.30, 0.20, 0.25, 0.15, 0.10)  # size, center, hand, steady, new
    focus_switch_margin: float = 0.15
    focus_switch_hold_s: float = 0.5
    min_area: float = 0.01
    max_area: float = 0.60
    min_age_frames: int = 3
    excluded_labels: tuple[str, ...] = ("person", "man", "woman", "boy", "girl", "child", "baby", "adult", "toddler",
                                        "preacher", "portrait", "selfie", "body", "face", "head", "hair", "beard",
                                        "eye", "ear", "nose", "mouth", "forehead", "neck", "shoulder", "chest", "skin",
                                        "hand", "arm", "finger", "leg", "foot")
    hand_labels: tuple[str, ...] = ("hand",)
    # privacy veto (never send a crop that is really a person or holds a face): whole persons and face parts
    person_labels: tuple[str, ...] = ("person", "man", "woman", "boy", "girl", "child", "baby", "adult", "toddler",
                                      "preacher", "portrait", "selfie", "body")
    face_labels: tuple[str, ...] = ("face", "head", "hair", "beard", "eye", "ear", "nose", "mouth", "forehead")
    mask_dilate: float = 0.04  # the object outline is widened by 4 % of the box before everything else is greyed out
    min_sharpness: float = 60.0
    dhash_min_distance: int = 14
    aspect_change: float = 0.25
    crop_margin: float = 0.12
    crop_long_edge: int = 1024
    crop_jpeg_quality: int = 90
    min_box_side_px: int = 120
    edge_margin: float = 0.01
    best_of_window_s: float = 0.5  # the snapshot: the sharpest frame of the first half second goes out
    capture_patience_s: float = 2.0  # if no frame was sharp enough by then, the sharpest one goes out anyway
    claude_timeout_s: float = 20.0
    log_calls: bool = True
    runs_dir: Path = Path("runs")
    profile_cache: Path = Path(__file__).resolve().parent.parent / "cache" / "profiles.json"  # sub-project 2
    cad_model: str = "claude-opus-5-5"  # the precision model's own Claude model: Sonnet built cruder models
    max_model_cost_usd: float = 1.60  # the precision model (sub-project 6): hard cap per product, about 1.50 €
    max_models_session: int = 5  # new precision models per server run
    model_check_rounds: int = 2
    model_timeout_s: float = 600.0  # deadline of a whole streamed model call (CAD with a drawing took 140 s)
    model_cache: Path = Path(__file__).resolve().parent.parent / "cache" / "models"
    models_dir: Path = Path(__file__).resolve().parent.parent / "models"  # YuNet and BOSL2 live here
    port: int = 8766
    prices: Mapping[str, tuple[float, float]] = field(default_factory=lambda: dict(DEFAULT_PRICES), hash=False)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Defaults overridden by the OI_* environment variables (empty values count as unset)."""
        env = os.environ if env is None else env
        parsers: dict[str, tuple[str, Callable[[str], Any]]] = {
            "OI_MODEL": ("model", str),
            "OI_CAD_MODEL": ("cad_model", str),
            "OI_EFFORT": ("effort", str),
            "OI_LANGUAGE": ("language", str),
            "OI_MAX_CALLS_OBJECT": ("max_calls_object", int),
            "OI_MAX_CALLS_SESSION": ("max_calls_session", int),
            "OI_DETECTOR": ("detector", str),
            "OI_MIN_SHARPNESS": ("min_sharpness", float),
            "OI_DHASH_MIN_DISTANCE": ("dhash_min_distance", int),
            "OI_LOG_CALLS": ("log_calls", _parse_bool),
            "OI_PORT": ("port", int),
            "OI_MAX_MODEL_COST_USD": ("max_model_cost_usd", float),
            "OI_MAX_MODELS_SESSION": ("max_models_session", int),
            "OI_MODEL_CHECK_ROUNDS": ("model_check_rounds", int),
        }
        updates = {name: parse(env[key]) for key, (name, parse) in parsers.items() if env.get(key, "").strip()}
        settings = replace(cls(), **updates)
        if settings.language not in ("de", "en"):
            raise ValueError(f"OI_LANGUAGE must be de or en, got {settings.language!r}")
        for key, model in (("OI_MODEL", settings.model), ("OI_CAD_MODEL", settings.cad_model)):
            if model not in settings.prices:
                raise ValueError(f"{key} must be one of {sorted(settings.prices)}, got {model!r}")
        return settings
