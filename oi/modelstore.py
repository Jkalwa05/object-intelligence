"""Precision models on disk (sub-project 6): cache/models/<slug>/ holds manifest.json, part-NN.stl and model.scad.

A model is served only under its own name and only with the files its manifest lists: a broken or foreign folder
counts as missing, never as somebody else's model.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from pydantic import ValidationError

from oi.cache import normalize
from oi.contracts import ModelManifest

log = logging.getLogger(__name__)

MAX_SLUG = 80
SLUG = re.compile(r"[a-z0-9-]+")
SCAD = "model.scad"
MANIFEST = "manifest.json"


def slug(model: str) -> str:
    """The folder name of a model: lowercase, every run of other characters becomes one "-"."""
    text = re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")[:MAX_SLUG].strip("-")
    return text or "model"


class ModelStore:
    def __init__(self, root: Path | None) -> None:
        """`root=None` keeps everything in memory (tests, `--fake-claude`)."""
        self._root = root
        self._memory: dict[str, tuple[ModelManifest, dict[str, bytes]]] = {}

    def get(self, model: str) -> ModelManifest | None:
        found = self._load(slug(model))
        if found is None or normalize(found[0].model) != normalize(model):
            return None
        return found[0]

    def put(self, manifest: ModelManifest, stls: list[bytes], scad: str) -> None:
        files = {part.file: stl for part, stl in zip(manifest.parts, stls, strict=True)}
        files[SCAD] = scad.encode()
        self._memory[manifest.slug] = (manifest, files)
        if self._root is None:
            return
        folder = self._root / manifest.slug
        try:
            folder.mkdir(parents=True, exist_ok=True)
            for name, data in files.items():
                _write(folder / name, data)
            _write(folder / MANIFEST, manifest.model_dump_json(indent=2).encode())  # last: a complete model
        except OSError:
            log.warning("could not write the model %s, keeping it in memory", folder)

    def file(self, slug_: str, name: str) -> bytes | None:
        """A file of a stored model, only if its manifest lists it (or it is the OpenSCAD source)."""
        if not SLUG.fullmatch(slug_):
            return None
        found = self._load(slug_)
        if found is None:
            return None
        manifest, files = found
        if name != SCAD and name not in {part.file for part in manifest.parts}:
            return None
        return files.get(name)

    def _load(self, slug_: str) -> tuple[ModelManifest, dict[str, bytes]] | None:
        if slug_ in self._memory:
            return self._memory[slug_]
        if self._root is None:
            return None
        folder = self._root / slug_
        try:
            manifest = ModelManifest.model_validate_json((folder / MANIFEST).read_bytes())
            files = {part.file: (folder / part.file).read_bytes() for part in manifest.parts}
            files[SCAD] = (folder / SCAD).read_bytes() if (folder / SCAD).exists() else b""
        except (OSError, ValueError, ValidationError):
            return None
        if manifest.slug != slug_:
            return None
        self._memory[slug_] = (manifest, files)
        return self._memory[slug_]


def _write(path: Path, data: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)
