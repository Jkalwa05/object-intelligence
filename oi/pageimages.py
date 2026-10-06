"""Product images on the pages the research found (sub-project 8, spec §3.1).

Shops and manufacturers name their product image in the page's structured data (JSON-LD "image") or in its preview
tags (og:image, twitter:image). Claude's web fetch hands it the page as text, where such links get lost, so the server
reads them itself. The HTML is only parsed, never run.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

from oi import download

log = logging.getLogger(__name__)

MAX_PAGES = 3
META = ("og:image", "og:image:url", "og:image:secure_url", "twitter:image")
FetchPage = Callable[[str, set[str]], Awaitable[str]]


class _Collector(HTMLParser):
    """Collects the preview tags and the text of every JSON-LD block."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: list[str] = []
        self.data: list[str] = []
        self._in_data = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        named = dict(attrs)
        key = (named.get("property") or named.get("name") or "").lower()
        if tag == "meta" and key in META and named.get("content"):
            self.meta.append(named["content"] or "")
        elif tag == "script" and (named.get("type") or "").lower() == "application/ld+json":
            self._in_data = True
            self.data.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_data = False

    def handle_data(self, data: str) -> None:
        if self._in_data:
            self.data[-1] += data


def _ld_images(node: Any, found: list[str]) -> None:
    """Every "image" at any depth of a JSON-LD block: a URL, a list of them, or an ImageObject with a url."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "image":
                for item in value if isinstance(value, list) else [value]:
                    if isinstance(item, str):
                        found.append(item)
                    elif isinstance(item, dict) and isinstance(item.get("url"), str):
                        found.append(item["url"])
            else:
                _ld_images(value, found)
    elif isinstance(node, list):
        for item in node:
            _ld_images(item, found)


def images_in_html(html: str, page: str) -> list[str]:
    """The page's product images: JSON-LD first, then the preview tags; absolute https URLs, each once."""
    collector = _Collector()
    collector.feed(html)
    found: list[str] = []
    for text in collector.data:
        try:
            _ld_images(json.loads(text), found)
        except ValueError:
            continue  # a broken block: the next one may still name the picture
    found += collector.meta
    urls = [urljoin(page, url.strip()) for url in found]
    return [url for url in dict.fromkeys(urls) if url.startswith("https://") and url != page]


async def page_images(pages: list[str], allowed: set[str], fetch_page: FetchPage = download.fetch_page) -> list[str]:
    """The images of the first MAX_PAGES pages the research found, in order; a page that cannot be read is skipped."""
    images: list[str] = []
    for page in [p for p in pages if p in allowed][:MAX_PAGES]:
        try:
            images += images_in_html(await fetch_page(page, allowed), page)
        except download.DownloadError as error:
            log.info("no images from %s: %s", page, error)
    return list(dict.fromkeys(images))
