import io

import matplotlib
import pytest
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from PIL import Image

from oi.contracts import DrawingRef, PhotoRef
from oi.download import DownloadError
from oi.drawings import drawing_pictures, find_pages, photo_pictures, picture_size, render_pages


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


SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="100">'
       b'<rect x="10" y="10" width="280" height="80" fill="none" stroke="#00bcd4" stroke-width="4"/>'
       b'<text x="150" y="60" font-size="20" text-anchor="middle" fill="#00bcd4">160 mm</text></svg>')


async def test_svg_drawing_becomes_a_png():
    async def fetch(url, allowed):
        return SVG, "image/svg+xml"
    pictures, pages = await drawing_pictures(DrawingRef(url="https://cdn.example/d.svg", find=""), set(), fetch=fetch)
    assert pages == [] and len(pictures) == 1 and pictures[0][1] == "image/png"
    width, height = picture_size(pictures[0])
    assert width == 2000 and abs(height - 667) <= 1  # the long edge, like a rendered PDF page


async def test_broken_svg_means_no_drawing():
    async def fetch(url, allowed):
        return b"<svg", "image/svg+xml"
    assert await drawing_pictures(DrawingRef(url="https://cdn.example/d.svg", find=""), set(), fetch=fetch) == ([], [])


async def test_photo_pictures_skip_failures():
    asked = []

    async def fetch(url, allowed):
        asked.append(url)
        if url.endswith("2.png"):
            raise DownloadError("weg")
        return png(400, 300), "image/png"
    views = ["front", "back", "top", "side-front-left", "side-front-right"]
    photos = [PhotoRef(url=f"https://cdn.example/{i}.png", view=view) for i, view in enumerate(views, start=1)]
    pictures = await photo_pictures(photos, set(), fetch=fetch)
    assert [view for _, view in pictures] == ["front", "top", "side-front-left"]
    assert picture_size(pictures[0][0]) == (400, 300)
    assert asked == [f"https://cdn.example/{i}.png" for i in range(1, 5)]  # at most 4 photos are tried


async def test_svg_cannot_read_files_of_the_mac(tmp_path):
    secret = tmp_path / "secret.png"  # a red picture on the Mac: if resvg loaded it, the drawing would turn red
    Image.new("RGB", (50, 50), (255, 0, 0)).save(secret)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="100" height="100">'
           f'<image href="{secret}" width="100" height="100"/>'
           f'<image xlink:href = \'{secret}\' width="100" height="100"/></svg>').encode()

    async def fetch(url, allowed):
        return svg, "image/svg+xml"
    [(png, _)], _ = await drawing_pictures(DrawingRef(url="https://cdn.example/d.svg", find=""), set(), fetch=fetch)
    assert Image.open(io.BytesIO(png)).convert("RGBA").getpixel((1000, 1000)) != (255, 0, 0, 255)


async def test_a_bad_picture_is_skipped_although_ultralytics_patches_pillow(monkeypatch):
    import sys
    import types

    from PIL import Image as PILImage
    loaded = sys.modules.get("ultralytics.utils.patches")  # other tests may have loaded the real patch already
    original = getattr(loaded, "_image_open", PILImage.open)

    def patched(fp, *args, **kwargs):  # what Ultralytics puts in its place: on failure it tries to pip-install pi-heif
        try:
            return original(fp, *args, **kwargs)
        except Exception:
            raise ModuleNotFoundError("No module named 'pi_heif'") from None
    monkeypatch.setattr(PILImage, "open", patched)
    monkeypatch.setitem(sys.modules, "ultralytics.utils.patches", types.SimpleNamespace(_image_open=original))

    async def fetch(url, allowed):
        return b"no picture at all", "image/png"
    assert await photo_pictures([PhotoRef(url="https://cdn.example/bad.png", view="front")], set(), fetch=fetch) == []
    assert picture_size((png(40, 20), "image/png")) == (40, 20)  # good pictures still open
