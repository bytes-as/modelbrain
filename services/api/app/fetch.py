"""Web fetcher adapter (G133): plain HTTP by default; Firecrawl for JavaScript-heavy pages.

All backends return normalised text, or None when the page could not be fetched.
WEB_FETCHER=httpx (default) | firecrawl | anakin. Anakin's API is not wired in this build:
selecting it logs a warning and falls back to httpx rather than guessing an API.
"""

from __future__ import annotations

import logging
import re

import httpx

from app.config import get_settings

log = logging.getLogger("modelbrain.fetch")
TIMEOUT_S = 20.0
MAX_BYTES = 2_000_000
FIRECRAWL = "https://api.firecrawl.dev/v1/scrape"


def normalise(text: str) -> str:
    """Collapse whitespace so cosmetic reflows do not count as a licence change."""
    return re.sub(r"\s+", " ", text).strip()


class Fetcher:
    def __init__(
        self, backend: str | None = None, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        settings = get_settings()
        self.backend = (backend or settings.web_fetcher or "httpx").lower()
        if self.backend == "firecrawl" and not settings.firecrawl_api_key:
            log.warning("WEB_FETCHER=firecrawl without FIRECRAWL_API_KEY; using httpx")
            self.backend = "httpx"
        if self.backend == "anakin":
            log.warning("anakin backend is not wired in this build; using httpx")
            self.backend = "httpx"
        self._firecrawl_key = settings.firecrawl_api_key
        self._http = httpx.AsyncClient(
            timeout=TIMEOUT_S,
            follow_redirects=True,
            transport=transport,
            headers={"User-Agent": "modelbrain"},
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def text(self, url: str) -> str | None:
        try:
            if self.backend == "firecrawl":
                return await self._firecrawl(url)
            return await self._plain(url)
        except httpx.HTTPError as exc:
            log.warning("fetch failed", extra={"url": url, "error": type(exc).__name__})
            return None

    async def _plain(self, url: str) -> str | None:
        response = await self._http.get(url)
        if response.status_code != 200:
            return None
        body = response.content[:MAX_BYTES].decode("utf-8", "replace")
        if "html" in response.headers.get("content-type", ""):
            body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.S | re.I)
            body = re.sub(r"<[^>]+>", " ", body)
        return normalise(body)

    async def _firecrawl(self, url: str) -> str | None:
        response = await self._http.post(
            FIRECRAWL,
            json={"url": url, "formats": ["markdown"]},
            headers={"Authorization": f"Bearer {self._firecrawl_key}"},
        )
        if response.status_code != 200:
            return None
        data = response.json().get("data") or {}
        markdown = data.get("markdown")
        return normalise(markdown) if isinstance(markdown, str) else None
