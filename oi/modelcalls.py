"""The three Claude calls of the precision model (sub-project 6): research, CAD program and visual check."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CadPart:
    name: str
    color: str  # "#rrggbb"
    scad: str  # OpenSCAD statements that make exactly this part
