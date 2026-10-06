"""Safe downloads of technical drawings for the precision model (sub-project 6, spec §4.4).

The server only loads what the research call found itself: the URL appeared in its search or fetch results or on a
fetched page (a drawing on a CDN), or it lies on the same host as such a page. It loads only over https, only from
public addresses (checked again after every redirect), only PDFs and PNG/JPEG/WebP/SVG images, and only up to a
size limit. What it loads is never executed: it goes to Claude as an image; an SVG is rendered to PNG first.

Known limit: the address is checked before httpx connects, and httpx resolves the name once more. A server that
answers the second lookup with a private address (DNS rebinding) could slip through; the body would still only be
read as a PDF or image and shown to Claude.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Callable, Mapping
from urllib.parse import urljoin, urlsplit

import httpx

PDF_LIMIT = 60_000_000
IMAGE_LIMIT = 8_000_000
LIMITS = {"application/pdf": PDF_LIMIT, "image/png": IMAGE_LIMIT, "image/jpeg": IMAGE_LIMIT,
          "image/webp": IMAGE_LIMIT, "image/svg+xml": IMAGE_LIMIT}  # SVG only to be rendered on the server
PAGE_LIMIT = 3_000_000  # a web page, read for its product images (sub-project 8)
PAGE_LIMITS = {"text/html": PAGE_LIMIT, "application/xhtml+xml": PAGE_LIMIT}
MAX_REDIRECTS = 3


class DownloadError(Exception):
    """A download that was refused or failed; the reason is the message."""


def _resolve(host: str) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)]


async def _check(url: str, resolve: Callable[[str], list[str]]) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise DownloadError(f"nur https: {url}")
    try:
        addresses = [parts.hostname.strip("[]")] if _is_ip(parts.hostname) else \
            await asyncio.to_thread(resolve, parts.hostname)
    except (OSError, KeyError) as error:
        raise DownloadError(f"unbekannter Host {parts.hostname}") from error
    if not addresses or not all(ipaddress.ip_address(a.split("%")[0]).is_global for a in addresses):
        raise DownloadError(f"keine öffentliche Adresse: {parts.hostname}")


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


async def fetch(url: str, allowed: set[str], *, transport: httpx.AsyncBaseTransport | None = None,
                resolve: Callable[[str], list[str]] | None = None, timeout_s: float = 30.0,
                limits: Mapping[str, int] = LIMITS) -> tuple[bytes, str]:
    """(body, media type) of an allowed file of a type in `limits` (PDFs and images by default); every refusal or
    failure raises DownloadError."""
    if url not in allowed and urlsplit(url).hostname not in {urlsplit(a).hostname for a in allowed}:
        raise DownloadError("Die Recherche hat diese Adresse nicht gefunden.")
    resolve = resolve or _resolve
    try:
        async with httpx.AsyncClient(transport=transport, timeout=timeout_s, follow_redirects=False) as client:
            current = url
            for _ in range(MAX_REDIRECTS + 1):
                await _check(current, resolve)
                async with client.stream("GET", current) as response:
                    if response.is_redirect:
                        current = urljoin(current, response.headers.get("location", ""))
                        continue
                    if response.status_code != 200:
                        raise DownloadError(f"HTTP {response.status_code}")
                    media = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if media not in limits:
                        raise DownloadError(f"falscher Typ: {media or 'unbekannt'}")
                    limit = limits[media]
                    declared = response.headers.get("content-length", "")
                    if declared.isdigit() and int(declared) > limit:
                        raise DownloadError("zu groß")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body += chunk
                        if len(body) > limit:
                            raise DownloadError("zu groß")
                    return bytes(body), media
    except httpx.HTTPError as error:
        raise DownloadError(f"Download fehlgeschlagen: {error.__class__.__name__}") from error
    raise DownloadError("zu viele Weiterleitungen")


async def fetch_page(url: str, allowed: set[str], *, transport: httpx.AsyncBaseTransport | None = None,
                     resolve: Callable[[str], list[str]] | None = None, timeout_s: float = 30.0) -> str:
    """The text of an allowed web page, under the same rules, to read its product images (sub-project 8)."""
    body, _ = await fetch(url, allowed, transport=transport, resolve=resolve, timeout_s=timeout_s, limits=PAGE_LIMITS)
    return body.decode("utf-8", errors="replace")
