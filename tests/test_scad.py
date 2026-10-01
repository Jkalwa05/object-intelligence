import io
import struct
import sys
import time
import zipfile
from pathlib import Path

import pytest

from oi import scad
from oi.config import Settings
from oi.mesh import bounds, read_stl
from oi.modelcalls import CadPart
from oi.scad import (BOSL2_COMMIT, HEADER, ScadCompiler, compiler_problem, ensure_bosl2, scad_file)

FAKE_NODE = Path(__file__).parent / "fixtures" / "fake_node.py"


def fake_compiler(tmp_path: Path, **kw) -> ScadCompiler:
    return ScadCompiler(tmp_path, node=sys.executable, script=FAKE_NODE, **kw)


def part(name: str, code: str = "cube(1);") -> CadPart:
    return CadPart(name=name, color="#9fc4e8", scad=code)


def test_scad_file_puts_header_shared_then_part():
    text = scad_file("w = 71.5;", "cube(w);")
    assert text.startswith(HEADER) and text.index("w = 71.5;") < text.index("cube(w);")
    assert HEADER == "include <BOSL2/std.scad>\n$fn = 48;\n"


async def test_compiler_runs_one_process_per_part_and_keeps_order(tmp_path):
    results = await fake_compiler(tmp_path).compile("", [part(f"Teil {i}") for i in range(6)])
    assert [r.name for r in results] == [f"Teil {i}" for i in range(6)]
    assert all(r.stl is not None and r.triangles == 12 and r.color == "#9fc4e8" for r in results)
    assert all(f"lib={tmp_path}" in r.errors for r in results)  # the folder that holds BOSL2/
    broken = await fake_compiler(tmp_path).compile("", [part("gut"), part("kaputt", "ERROR")])
    assert broken[0].stl is not None and broken[1].stl is None and "Parser error" in broken[1].errors[0]


async def test_a_hanging_part_times_out_alone(tmp_path):
    started = time.perf_counter()
    results = await fake_compiler(tmp_path, timeout_s=0.5).compile("", [part("hängt", "SLEEP"), part("gut")])
    assert time.perf_counter() - started < 5
    assert results[0].stl is None and results[0].errors == ["Zeitlimit 0.5 s überschritten"]
    assert results[1].stl is not None


async def test_empty_geometry_and_too_many_triangles_are_errors(tmp_path, monkeypatch):
    results = await fake_compiler(tmp_path).compile("", [part("leer", "EMPTY"), part("riesig", "HUGE")])
    assert (results[0].stl, results[0].errors) == (None, ["leere Geometrie"])
    assert (results[1].stl, results[1].errors) == (None, ["zu viele Dreiecke (250000, höchstens 200000)"])
    monkeypatch.setattr(scad, "MAX_MODEL_TRIANGLES", 20)
    whole = await fake_compiler(tmp_path).compile("", [part("eins"), part("zwei")])
    assert whole[0].stl is not None and whole[1].stl is None
    assert whole[1].errors == ["zu viele Dreiecke im ganzen Modell (höchstens 20)"]


def test_compiler_problem_names_missing_node_or_modules(tmp_path, monkeypatch):
    monkeypatch.setattr(scad.shutil, "which", lambda name: None)
    assert compiler_problem(tmp_path) == "Node.js fehlt"
    monkeypatch.setattr(scad.shutil, "which", lambda name: "/usr/local/bin/node")
    assert compiler_problem(tmp_path) == "web/node_modules fehlt (npm --prefix web install)"
    (tmp_path / "web" / "node_modules" / "openscad-wasm-prebuilt").mkdir(parents=True)
    assert compiler_problem(tmp_path) is None


def test_ensure_bosl2_extracts_only_root_scad_files(tmp_path):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        for name in ("std.scad", "shapes3d.scad", "tests/test_shapes.scad", "README.md"):
            z.writestr(f"BOSL2-{BOSL2_COMMIT}/{name}", f"// {name}")
    calls = []

    def download(url: str) -> bytes:
        calls.append(url)
        return archive.getvalue()

    parent = ensure_bosl2(tmp_path, download)
    assert parent == tmp_path / f"BOSL2-{BOSL2_COMMIT}"
    assert sorted(p.name for p in (parent / "BOSL2").iterdir()) == ["shapes3d.scad", "std.scad"]
    assert calls == [f"https://github.com/BelfrySCAD/BOSL2/archive/{BOSL2_COMMIT}.zip"]
    assert ensure_bosl2(tmp_path, download) == parent and len(calls) == 1  # already there: no second download


# --- the real compiler (uv run pytest -m scad) ---------------------------------------------------------------------

def real_compiler() -> ScadCompiler:
    return ScadCompiler(ensure_bosl2(Settings().models_dir))


@pytest.mark.scad
async def test_real_openscad_compiles_a_bosl2_part():
    body = CadPart(name="Gehäuse", color="#9fc4e8", scad="""
difference() {
  cuboid([w, h, d], rounding=9, edges="Z");
  translate([-20, 55, d / 2]) cyl(d=13, h=4);
}""")
    [result] = await real_compiler().compile("w = 71.5; h = 146.7; d = 7.8;", [body])
    assert result.stl is not None and result.triangles > 100, result.errors
    low, high = bounds(read_stl(result.stl))
    assert [round(b - a, 2) for a, b in zip(low, high, strict=True)] == [71.5, 146.7, 7.8]


@pytest.mark.scad
async def test_real_openscad_cannot_read_files_on_the_mac(tmp_path):
    host = tmp_path / "secret.stl"  # a real cube on the Mac: if OpenSCAD could read it, the part would have geometry
    host.write_bytes(b"\0" * 80 + struct.pack("<I", 1) + struct.pack("<12fH", 0, 0, 0, 0, 0, 0, 9, 0, 0, 0, 9, 0, 0))
    [result] = await real_compiler().compile("", [CadPart(name="Fühler", color="#000000", scad=f'import("{host}");')])
    assert result.stl is None and result.triangles == 0
