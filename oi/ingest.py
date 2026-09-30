"""Frames from the browser: the binary message format (spec §2.1) and the latest-frame-wins slot."""

from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass

import cv2
import numpy as np
from pydantic import ValidationError

from oi.contracts import FrameHeader

MAX_HEADER_BYTES = 4096

RawFrame = tuple[FrameHeader, bytes]


class FrameFormatError(ValueError):
    """A browser message that is not a valid frame."""


def parse_frame_message(data: bytes) -> RawFrame:
    """Split `uint32 header length (big-endian) | JSON header | JPEG bytes`."""
    if len(data) < 4:
        raise FrameFormatError("message shorter than the 4-byte header length")
    (length,) = struct.unpack(">I", data[:4])
    if length > MAX_HEADER_BYTES or length > len(data) - 4:
        raise FrameFormatError(f"bad header length {length}")
    try:
        header = FrameHeader.model_validate_json(data[4:4 + length])
    except ValidationError as error:
        raise FrameFormatError(f"bad frame header ({error.error_count()} errors)") from error
    return header, data[4 + length:]


@dataclass(frozen=True)
class Frame:
    frame_id: int
    t: float  # seconds on the browser's capture clock
    image: np.ndarray  # BGR, height x width x 3


def decode_frame(raw: RawFrame) -> Frame:
    header, jpeg = raw
    try:
        image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR) if jpeg else None
    except cv2.error as error:
        raise FrameFormatError("not a decodable JPEG") from error
    if image is None:
        raise FrameFormatError("not a decodable JPEG")
    return Frame(frame_id=header.frame_id, t=header.t_capture_ms / 1000.0, image=image)


class FrameSlot:
    """Holds only the newest frame; a frame nobody picked up in time is replaced and counted as dropped."""

    def __init__(self) -> None:
        self._raw: RawFrame | None = None
        self._ready = asyncio.Event()
        self.dropped = 0

    def put(self, raw: RawFrame) -> None:
        if self._raw is not None:
            self.dropped += 1
        self._raw = raw
        self._ready.set()

    async def get(self) -> RawFrame:
        while self._raw is None:
            self._ready.clear()
            await self._ready.wait()
        raw, self._raw = self._raw, None
        return raw
