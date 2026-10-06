from oi.download import DownloadError
from oi.pageimages import images_in_html, page_images

PAGE = "https://shop.example/p/wasser.html"


def test_images_in_html():
    html = """<html><head>
    <script type="application/ld+json">{"@type": "Product", "image": "https:\\/\\/cdn.example\\/a.jpg"}</script>
    <script type="application/ld+json">{"@graph": [{"@type": "Product",
      "image": ["https://cdn.example/b.jpg", {"@type": "ImageObject", "url": "https://cdn.example/c.jpg"}]}]}</script>
    <script type="application/ld+json">{ kaputt </script>
    <meta property="og:image" content="/img/d.png">
    <meta name="twitter:image" content="https://cdn.example/a.jpg">
    <meta property="og:image:secure_url" content="http://cdn.example/e.jpg">
    <meta property="og:image:url" content="https://shop.example/p/wasser.html">
    </head><body><img src="https://cdn.example/banner.jpg"></body></html>"""
    assert images_in_html(html, PAGE) == ["https://cdn.example/a.jpg", "https://cdn.example/b.jpg",
                                          "https://cdn.example/c.jpg", "https://shop.example/img/d.png"]
    assert images_in_html("<html>keine Bilder</html>", PAGE) == []


async def test_page_images_skip_failures():
    asked = []

    async def fetch_page(url, allowed):
        asked.append(url)
        if url.endswith("2.html"):
            raise DownloadError("weg")
        return f'<meta property="og:image" content="https://cdn.example/{url[-6]}.jpg">'
    pages = [f"https://shop.example/{i}.html" for i in range(1, 5)]
    found = await page_images(pages, set(pages), fetch_page=fetch_page)
    assert found == ["https://cdn.example/1.jpg", "https://cdn.example/3.jpg"]
    assert asked == pages[:3]  # at most 3 pages are read
    assert await page_images(["https://other.example/x.html"], set(pages), fetch_page=fetch_page) == []
    assert asked == pages[:3]  # a page the research did not find is not even asked
