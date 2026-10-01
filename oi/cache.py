"""A small JSON file cache for Claude's answers about products (sub-projects 2 and 3).

One cache is shared by every browser connection. A broken or outdated file is ignored, a file that cannot be written
leaves the cache in memory: a cache must never take the program down.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)


def normalize(key: str) -> str:
    return " ".join(key.lower().split())


class JsonCache(Generic[M]):
    def __init__(self, path: Path | None, model: type[M]) -> None:
        """`path=None` keeps everything in memory (tests, `--fake-claude`)."""
        self._path = path
        self._entries: dict[str, M] = {}
        if path is None or not path.exists():
            return
        try:
            raw = json.loads(path.read_text())
        except (OSError, ValueError):
            log.warning("ignoring the unreadable cache %s", path)
            return
        for key, value in raw.items() if isinstance(raw, dict) else ():
            try:
                self._entries[key] = model.model_validate(value)
            except ValidationError:
                continue

    def get(self, key: str) -> M | None:
        return self._entries.get(normalize(key))

    def put(self, key: str, value: M) -> None:
        self._entries[normalize(key)] = value
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._path.with_suffix(".tmp")
            temporary.write_text(json.dumps({k: v.model_dump(mode="json") for k, v in self._entries.items()},
                                            indent=2, ensure_ascii=False))
            os.replace(temporary, self._path)
        except OSError:
            log.warning("could not write the cache %s, keeping it in memory", self._path)
