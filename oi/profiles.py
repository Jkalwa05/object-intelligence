"""Product profiles (sub-project 2), kept on disk so a product never costs twice."""

from __future__ import annotations

from pathlib import Path

from oi.cache import JsonCache, normalize
from oi.config import Lang
from oi.contracts import ProductProfile


class ProfileStore:
    """Profiles by product name and language: an English profile is another profile."""

    def __init__(self, path: Path | None) -> None:
        self._cache = JsonCache(path, ProductProfile)

    def get(self, product: str, lang: Lang) -> ProductProfile | None:
        return self._cache.get(f"{lang}:{normalize(product)}")

    def put(self, product: str, lang: Lang, profile: ProductProfile) -> None:
        self._cache.put(f"{lang}:{normalize(product)}", profile)
