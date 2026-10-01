"""The CAD compiler of the precision model (sub-project 6): OpenSCAD as WebAssembly in Node, one process per part.

Claude's OpenSCAD code runs only here, inside OpenSCAD's own in-memory file system (no access to the Mac's files, no
network), with BOSL2 for roundings and cut-outs. A part that hangs is stopped after 30 s; empty or oversized results
count as errors, which go back to Claude in the next check round.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import shutil
import struct
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:  # modelcalls imports HEADER from here
    from oi.modelcalls import CadPart

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "web" / "scad" / "compile.mjs"
PACKAGE = Path("web") / "node_modules" / "openscad-wasm-prebuilt"
BOSL2_COMMIT = "d05f0ca97d57cc072e627c34c7c0fde7aecbed9a"  # pinned: the model code must not change under our feet
BOSL2_URL = f"https://github.com/BelfrySCAD/BOSL2/archive/{BOSL2_COMMIT}.zip"
HEADER = "include <BOSL2/std.scad>\n$fn = 48;\n"
MAX_PART_TRIANGLES = 200_000
MAX_MODEL_TRIANGLES = 600_000


def scad_file(shared: str, code: str) -> str:
    """The OpenSCAD file of one part: BOSL2 and the resolution, the shared variables and modules, then the part."""
    return f"{HEADER}{shared}\n{code}\n"


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - a fixed https URL
        return response.read()


def ensure_bosl2(models_dir: Path, download: Callable[[str], bytes] | None = None) -> Path:
    """The folder that contains BOSL2/ at the pinned commit, downloaded once (only its root .scad files)."""
    parent = models_dir / f"BOSL2-{BOSL2_COMMIT}"
    if (parent / "BOSL2" / "std.scad").exists():
        return parent
    archive = zipfile.ZipFile(io.BytesIO((download or _download)(BOSL2_URL)))
    staging = parent.with_name(parent.name + ".tmp")
    shutil.rmtree(staging, ignore_errors=True)
    (staging / "BOSL2").mkdir(parents=True)
    for name in archive.namelist():
        folder, _, file = name.partition("/")
        if folder.startswith("BOSL2-") and file.endswith(".scad") and "/" not in file:
            (staging / "BOSL2" / file).write_bytes(archive.read(name))
    shutil.rmtree(parent, ignore_errors=True)
    os.replace(staging, parent)
    return parent


def compiler_problem(repo: Path = REPO) -> str | None:
    """Why the precision model cannot be built on this Mac, in German, or None."""
    if shutil.which("node") is None:
        return "Node.js fehlt"
    if not (repo / PACKAGE).exists():
        return "web/node_modules fehlt (npm --prefix web install)"
    return None


@dataclass(frozen=True)
class CompiledPart:
    name: str
    color: str
    stl: bytes | None  # binary STL, None if the part failed
    triangles: int
    errors: list[str]


class Compiler(Protocol):
    async def compile(self, shared: str, parts: list[CadPart]) -> list[CompiledPart]: ...


class ScadCompiler:
    def __init__(self, bosl2_parent: Path, node: str = "node", script: Path = SCRIPT, parallel: int = 4,
                 timeout_s: float = 30.0) -> None:
        self._lib = bosl2_parent
        self._node = node
        self._script = script
        self._slots = asyncio.Semaphore(parallel)
        self._timeout_s = timeout_s

    async def compile(self, shared: str, parts: list[CadPart]) -> list[CompiledPart]:
        results = await asyncio.gather(*(self._one(shared, part) for part in parts))
        total, checked = 0, []
        for result in results:  # the whole model has a limit too: the parts that push it over it fail
            if result.stl is not None and total + result.triangles > MAX_MODEL_TRIANGLES:
                result = CompiledPart(result.name, result.color, None, 0,
                                      [f"zu viele Dreiecke im ganzen Modell (höchstens {MAX_MODEL_TRIANGLES})"])
            total += result.triangles if result.stl is not None else 0
            checked.append(result)
        return checked

    async def _one(self, shared: str, part: CadPart) -> CompiledPart:
        def failed(*errors: str) -> CompiledPart:
            return CompiledPart(part.name, part.color, None, 0, list(errors))

        job = json.dumps({"code": scad_file(shared, part.scad), "lib": str(self._lib)}).encode()
        async with self._slots:
            process = await asyncio.create_subprocess_exec(
                self._node, str(self._script), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)
            try:
                out, _ = await asyncio.wait_for(process.communicate(job), self._timeout_s)
            except TimeoutError:
                process.kill()
                await process.wait()
                return failed(f"Zeitlimit {self._timeout_s:g} s überschritten")
        try:
            answer = json.loads(out)
            errors = [str(e) for e in answer.get("errors", [])][:20]
            stl = base64.b64decode(answer["stl"]) if answer.get("ok") and answer.get("stl") else None
        except (ValueError, KeyError, TypeError):
            log.warning("the compiler gave no answer for %s", part.name)
            return failed("Der Compiler hat nicht geantwortet.")
        if stl is None:
            return failed(*(errors or ["Keine Geometrie erzeugt."]))
        triangles = int.from_bytes(stl[80:84], "little") if len(stl) >= 84 else 0
        if triangles == 0:
            return failed("leere Geometrie")
        if triangles > MAX_PART_TRIANGLES:
            return failed(f"zu viele Dreiecke ({triangles}, höchstens {MAX_PART_TRIANGLES})")
        return CompiledPart(part.name, part.color, stl, triangles, errors)


class FakeCompiler:
    """For tests: every part becomes a 10 mm cube, set 20 mm apart on x; names in `broken` fail to parse."""

    def __init__(self, broken: set[str] | frozenset[str] = frozenset()) -> None:
        self.broken = set(broken)
        self.calls: list[list[str]] = []

    async def compile(self, shared: str, parts: list[CadPart]) -> list[CompiledPart]:
        self.calls.append([p.name for p in parts])
        return [CompiledPart(p.name, p.color, None, 0, ["ERROR: Parser error"]) if p.name in self.broken
                else CompiledPart(p.name, p.color, cube_stl(10.0, (20.0 * i, 0.0, 0.0)), 12, [])
                for i, p in enumerate(parts)]


def cube_stl(size: float, offset: tuple[float, float, float]) -> bytes:
    """A binary STL of an axis-aligned cube (12 triangles)."""
    h = size / 2
    v = [(offset[0] + x * h, offset[1] + y * h, offset[2] + z * h) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6),
             (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    data = bytearray(80) + struct.pack("<I", len(faces))
    for a, b, c in faces:
        data += struct.pack("<12fH", 0, 0, 0, *v[a], *v[b], *v[c], 0)
    return bytes(data)
