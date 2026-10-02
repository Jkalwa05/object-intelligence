import httpx
import pytest

from oi.download import IMAGE_LIMIT, DownloadError, fetch

PDF = b"%PDF-1.7\n%drawing\n"
HOSTS = {"developer.apple.com": ["17.253.144.10"], "localhost": ["127.0.0.1"], "intranet.example": ["10.0.0.5"],
         "evil.example": ["192.168.1.2"], "cdn.example": ["93.184.216.34"], "v6.example": ["::ffff:127.0.0.1"]}


def resolve(host: str) -> list[str]:
    return HOSTS[host]


def transport(routes: dict[str, httpx.Response]) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        return routes[str(request.url)]
    return httpx.MockTransport(handle)


async def test_downloads_an_allowed_pdf():
    url = "https://developer.apple.com/accessories/guidelines.pdf"
    routes = {url: httpx.Response(200, headers={"content-type": "application/pdf"}, content=PDF)}
    assert await fetch(url, {url}, transport=transport(routes), resolve=resolve) == (PDF, "application/pdf")


async def test_refuses_urls_not_found_by_the_research():
    url = "https://developer.apple.com/accessories/guidelines.pdf"
    routes = {url: httpx.Response(200, headers={"content-type": "application/pdf"}, content=PDF)}
    with pytest.raises(DownloadError):
        await fetch(url, set(), transport=transport(routes), resolve=resolve)


@pytest.mark.parametrize("url", ["http://developer.apple.com/a.pdf", "https://localhost/a.pdf",
                                 "https://intranet.example/a.pdf", "https://127.0.0.1/a.pdf",
                                 "https://[::1]/a.pdf", "https://v6.example/a.pdf", "ftp://developer.apple.com/a.pdf"])
async def test_refuses_http_localhost_and_private_addresses(url):
    routes = {url: httpx.Response(200, headers={"content-type": "application/pdf"}, content=PDF)}
    with pytest.raises(DownloadError):
        await fetch(url, {url}, transport=transport(routes), resolve=resolve)


async def test_rechecks_every_redirect():
    start = "https://cdn.example/a.pdf"
    routes = {start: httpx.Response(302, headers={"location": "https://evil.example/a.pdf"}),
              "https://evil.example/a.pdf": httpx.Response(200, headers={"content-type": "application/pdf"},
                                                           content=PDF)}
    with pytest.raises(DownloadError):
        await fetch(start, {start}, transport=transport(routes), resolve=resolve)
    loop = {f"https://cdn.example/{i}.pdf": httpx.Response(302, headers={"location": f"/{i + 1}.pdf"})
            for i in range(5)}
    with pytest.raises(DownloadError):  # more than 3 redirects
        await fetch("https://cdn.example/0.pdf", {"https://cdn.example/0.pdf"}, transport=transport(loop),
                    resolve=resolve)
    ok = {start: httpx.Response(301, headers={"location": "/b.pdf"}),
          "https://cdn.example/b.pdf": httpx.Response(200, headers={"content-type": "application/pdf"}, content=PDF)}
    assert await fetch(start, {start}, transport=transport(ok), resolve=resolve) == (PDF, "application/pdf")


async def test_refuses_wrong_types_and_oversized_bodies():
    url = "https://cdn.example/x"
    for response in (httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>"),
                     httpx.Response(200, headers={"content-type": "image/png"}, content=b"\0" * (IMAGE_LIMIT + 1)),
                     httpx.Response(200, headers={"content-type": "image/jpeg", "content-length": str(IMAGE_LIMIT + 1)},
                                    content=b"\xff\xd8"),
                     httpx.Response(404, headers={"content-type": "image/png"}, content=b"")):
        with pytest.raises(DownloadError):
            await fetch(url, {url}, transport=transport({url: response}), resolve=resolve)
    png = httpx.Response(200, headers={"content-type": "image/png; charset=binary"}, content=b"\x89PNG")
    assert await fetch(url, {url}, transport=transport({url: png}), resolve=resolve) == (b"\x89PNG", "image/png")


async def test_a_link_on_a_page_the_research_saw_is_allowed_but_not_other_hosts():
    seen = {"https://developer.apple.com/accessories/dimensional-drawings/"}  # the research fetched this page
    pdf = "https://developer.apple.com/download/files/accessories/dimensional-drawings/iphone-14.pdf"
    routes = {pdf: httpx.Response(200, headers={"content-type": "application/pdf"}, content=PDF)}
    assert await fetch(pdf, seen, transport=transport(routes), resolve=resolve) == (PDF, "application/pdf")
    other = "https://cdn.example/iphone-14.pdf"
    with pytest.raises(DownloadError):
        await fetch(other, seen, transport=transport({other: routes[pdf]}), resolve=resolve)
