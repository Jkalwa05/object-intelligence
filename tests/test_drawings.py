import io

import matplotlib
import pytest
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from PIL import Image

from oi.contracts import DrawingRef
from oi.download import DownloadError
from oi.drawings import drawing_pictures, find_pages, render_pages


def make_pdf(*pages: str) -> bytes:
    """A PDF with one line of text per page; TrueType fonts so that the text can be read back."""
    buffer = io.BytesIO()
    with matplotlib.rc_context({"pdf.fonttype": 42}), PdfPages(buffer) as pdf:
        for text in pages:
            figure = Figure(figsize=(8.27, 11.69))
            figure.text(0.1, 0.9, text, fontsize=14)
            pdf.savefig(figure)
    return buffer.getvalue()


PDF = make_pdf("Einleitung", "iPhone 14 Dimensional Drawing 71.5", "iPhone 15 Dimensional Drawing")


def test_find_pages_picks_the_page_with_the_words():
    assert find_pages(PDF, "iPhone 14 Dimensional Drawing") == [1]
    assert find_pages(PDF, "Dimensional Drawing") == [1, 2]  # equally good: both, the earlier first
    assert find_pages(PDF, "Dimensional Drawing", limit=1) == [1]
    assert find_pages(PDF, "Galaxy S23 Ultra") == []


def test_among_equally_good_pages_the_drawing_with_the_most_figures_comes_first():
    pdf = make_pdf("iPhone 14 Inhalt und Hinweise", "iPhone 14 71.50 146.70 7.80 10.73 4.25 R 9.00")
    assert find_pages(pdf, "iPhone 14") == [1, 0]
    assert find_pages(pdf, "iPhone 14", limit=1) == [1]


def test_a_drawing_made_of_lines_beats_a_page_of_terms():
    terms = "iPhone 14 Dimensional Drawings. These Guidelines are made available to you for informational purposes only."
    pdf = make_pdf(terms, "iPhone 14 | 1 2022-09-21", "iPhone 14 | 2 2022-09-21")  # Apple: figures are vector paths
    assert find_pages(pdf, "iPhone 14 Dimensions") == [1, 2]


def test_render_pages_gives_png():
    [png] = render_pages(PDF, [1], dpi=100, long_edge=600)
    image = Image.open(io.BytesIO(png))
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and max(image.size) <= 600


def png(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (240, 240, 240)).save(buffer, "PNG")
    return buffer.getvalue()


async def test_drawing_pictures_from_pdf_image_or_error():
    ref = DrawingRef(url="https://developer.apple.com/a.pdf", find="iPhone 14 Dimensional Drawing")

    async def pdf(url, allowed):
        assert (url, allowed) == (ref.url, {ref.url})
        return PDF, "application/pdf"

    pictures, pages = await drawing_pictures(ref, {ref.url}, fetch=pdf)
    assert pages == [2] and len(pictures) == 1 and pictures[0][1] == "image/png"

    async def image(url, allowed):
        return png(3000, 1000), "image/png"

    pictures, pages = await drawing_pictures(ref, {ref.url}, fetch=image)
    assert pages == [] and pictures[0][1] == "image/png"
    assert Image.open(io.BytesIO(pictures[0][0])).size == (2000, 667)  # big images are scaled down

    async def refused(url, allowed):
        raise DownloadError("nur https")

    assert await drawing_pictures(ref, {ref.url}, fetch=refused) == ([], [])
    assert await drawing_pictures(None, set(), fetch=refused) == ([], [])

    async def broken_pdf(url, allowed):
        return b"%PDF-1.7 broken", "application/pdf"

    assert await drawing_pictures(ref, {ref.url}, fetch=broken_pdf) == ([], [])


@pytest.mark.parametrize("find", ["", "a b"])
def test_find_pages_without_usable_words_finds_nothing(find):
    assert find_pages(PDF, find) == []
