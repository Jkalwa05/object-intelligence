"""The technical drawing for the precision model (sub-project 6, spec §4.3).

The research names a PDF or an image and, for a PDF, words that stand on the right page ("iPhone 14 Dimensional
Drawing"). The web fetch would hand Claude a whole PDF as text only; instead the server loads it, finds the page with
the most of those words and renders at most two such pages as images, so Claude sees the drawing itself.
"""

from __future__ import annotations

import asyncio
import io
import logging
import math
import re
from collections.abc import Awaitable, Callable

import pypdfium2 as pdfium
from PIL import Image

from oi import download
from oi.contracts import DrawingRef

log = logging.getLogger(__name__)

Picture = tuple[bytes, str]  # (data, media type) of an image for Claude
Fetch = Callable[[str, set[str]], Awaitable[tuple[bytes, str]]]
LONG_EDGE = 2000  # pixels: enough to read dimension figures, small enough for the API's image limits


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) >= 3 or any(c.isdigit() for c in w)}


FIGURE = re.compile(r"\d+[.,]\d+")  # dimension figures such as 71.50 or 146,7


def find_pages(pdf: bytes, find: str, limit: int = 2) -> list[int]:
    """0-based indices of the pages with the most of `find`'s words (at least half of them). Among equally good pages
    the ones with the most dimension figures come first: a drawing is full of them, a table of contents is not."""
    wanted = _words(find)
    if not wanted:
        return []
    document = pdfium.PdfDocument(pdf)
    try:
        pages = []
        for index in range(len(document)):
            text = document[index].get_textpage().get_text_range()
            pages.append((len(wanted & _words(text)), len(FIGURE.findall(text)), index))
    finally:
        document.close()
    best = max((matches for matches, _, _ in pages), default=0)
    if best < max(1, math.ceil(len(wanted) / 2)):
        return []
    chosen = sorted((p for p in pages if p[0] == best), key=lambda p: (-p[1], p[2]))
    return [index for _, _, index in chosen][:limit]


def _scaled_png(image: Image.Image, long_edge: int) -> bytes:
    image.thumbnail((long_edge, long_edge))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def render_pages(pdf: bytes, pages: list[int], dpi: int = 150, long_edge: int = LONG_EDGE) -> list[bytes]:
    """The pages as PNG images, scaled down to `long_edge` pixels."""
    document = pdfium.PdfDocument(pdf)
    try:
        return [_scaled_png(document[index].render(scale=dpi / 72).to_pil().convert("RGB"), long_edge)
                for index in pages]
    finally:
        document.close()


def _scaled_image(data: bytes, media: str) -> Picture:
    image = Image.open(io.BytesIO(data))
    if max(image.size) <= LONG_EDGE:
        return data, media
    if media == "image/jpeg":
        image.thumbnail((LONG_EDGE, LONG_EDGE))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, "JPEG", quality=90)
        return buffer.getvalue(), media
    return _scaled_png(image, LONG_EDGE), "image/png"


async def drawing_pictures(ref: DrawingRef | None, allowed: set[str], fetch: Fetch = download.fetch
                           ) -> tuple[list[Picture], list[int]]:
    """The drawing as images for Claude and the 1-based PDF pages they come from; ([], []) if there is none."""
    if ref is None:
        return [], []
    try:
        data, media = await fetch(ref.url, allowed)
        if media == "application/pdf":
            pages = await asyncio.to_thread(find_pages, data, ref.find)
            pictures = await asyncio.to_thread(render_pages, data, pages)
            return [(png, "image/png") for png in pictures], [index + 1 for index in pages]
        return [await asyncio.to_thread(_scaled_image, data, media)], []
    except (download.DownloadError, pdfium.PdfiumError, OSError, ValueError) as error:
        log.info("no drawing from %s: %s", ref.url, error)
        return [], []
