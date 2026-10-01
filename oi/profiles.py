"""Product profiles by name and language (sub-project 2), kept on disk so the same product never costs twice.

One store is shared by every browser connection. A broken or outdated cache file is ignored, a cache that cannot be
written stays in memory: the profile panel must never take the program down.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from pydantic import ValidationError

from oi.config import Lang
from oi.contracts import ProductProfile

log = logging.getLogger(__name__)


def _key(product: str, lang: Lang) -> str:
    return f"{lang}:{' '.join(product.lower().split())}"


class ProfileStore:
    def __init__(self, path: Path | None) -> None:
        """`path=None` keeps everything in memory (tests)."""
        self._path = path
        self._profiles: dict[str, ProductProfile] = {}
        if path is None or not path.exists():
            return
        try:
            raw = json.loads(path.read_text())
        except (OSError, ValueError):
            log.warning("ignoring the unreadable profile cache %s", path)
            return
        for key, value in raw.items() if isinstance(raw, dict) else ():
            try:
                self._profiles[key] = ProductProfile.model_validate(value)
            except ValidationError:
                continue

    def get(self, product: str, lang: Lang) -> ProductProfile | None:
        return self._profiles.get(_key(product, lang))

    def put(self, product: str, lang: Lang, profile: ProductProfile) -> None:
        self._profiles[_key(product, lang)] = profile
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._path.with_suffix(".tmp")
            temporary.write_text(json.dumps({k: v.model_dump(mode="json") for k, v in self._profiles.items()},
                                            indent=2, ensure_ascii=False))
            os.replace(temporary, self._path)
        except OSError:
            log.warning("could not write the profile cache %s, keeping profiles in memory", self._path)
