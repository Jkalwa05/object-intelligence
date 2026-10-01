"""Stands in for `node web/scad/compile.mjs` in the tests: reads the job from stdin, answers like the real script."""

import base64
import json
import struct
import sys
import time


def stl(count: int, triangles: int) -> bytes:
    """A binary STL header claiming `count` triangles, followed by `triangles` empty records."""
    return b"\0" * 80 + struct.pack("<I", count) + b"\0" * 50 * triangles


job = json.loads(sys.stdin.read())
code = job["code"]
if "SLEEP" in code:
    time.sleep(10)
if "ERROR" in code:
    answer = {"ok": False, "stl": None, "triangles": 0, "errors": ["ERROR: Parser error in file /model.scad, line 3"]}
else:
    data = stl(0, 0) if "EMPTY" in code else stl(250_000, 0) if "HUGE" in code else stl(12, 12)
    answer = {"ok": True, "stl": base64.b64encode(data).decode(), "triangles": 0, "errors": [f"lib={job['lib']}"]}
print(json.dumps(answer))
