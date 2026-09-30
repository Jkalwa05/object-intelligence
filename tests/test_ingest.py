import asyncio
import json
import struct

import cv2
import numpy as np
import pytest

from oi.contracts import FrameHeader
from oi.ingest import FrameFormatError, FrameSlot, decode_frame, parse_frame_message


def frame_bytes(header: dict, jpeg: bytes) -> bytes:
    h = json.dumps(header).encode()
    return struct.pack(">I", len(h)) + h + jpeg


HEADER = {"frame_id": 7, "t_capture_ms": 1500.0, "w": 1280, "h": 720}


def test_parse_roundtrip():
    hdr, jpeg = parse_frame_message(frame_bytes(HEADER, b"\xff\xd8x"))
    assert (hdr.frame_id, jpeg) == (7, b"\xff\xd8x")


@pytest.mark.parametrize("data", [b"\x00\x00", struct.pack(">I", 9999) + b"{}", struct.pack(">I", 5) + b"nojs!x",
                                  frame_bytes({"frame_id": "a"}, b""), struct.pack(">I", 5000) + b"x" * 5100])
def test_parse_rejects_garbage(data):
    with pytest.raises(FrameFormatError):
        parse_frame_message(data)


def test_decode_frame():
    ok, buf = cv2.imencode(".jpg", np.zeros((720, 1280, 3), np.uint8))
    frame = decode_frame((FrameHeader(**HEADER), buf.tobytes()))
    assert frame.image.shape == (720, 1280, 3)
    assert (frame.frame_id, frame.t) == (7, 1.5)


def test_decode_rejects_non_jpeg():
    with pytest.raises(FrameFormatError):
        decode_frame((FrameHeader(**HEADER), b"notajpeg"))


async def test_slot_latest_frame_wins():
    slot, a, b = FrameSlot(), (FrameHeader(**HEADER), b"a"), (FrameHeader(**HEADER), b"b")
    slot.put(a)
    slot.put(b)
    assert await slot.get() is b
    assert slot.dropped == 1


async def test_slot_get_waits_for_put():
    slot, a = FrameSlot(), (FrameHeader(**HEADER), b"a")
    task = asyncio.create_task(slot.get())
    await asyncio.sleep(0)
    assert not task.done()
    slot.put(a)
    assert await task is a
