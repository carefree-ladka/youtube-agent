"""Lightweight web search for topic research.

Gathers raw reference text + source links the pipeline can distill into verified
facts. Uses Wikipedia (free, reliable, no key) by default and can optionally add
DuckDuckGo results when the ``ddgs`` package is installed.

Everything here is best-effort: any failure returns empty results so the caller
simply proceeds without enrichment.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

_WIKI_API = "https://en.wikipedia.org/w/api.php"
_WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"


@dataclass
class WebSource:
    """A cited reference used during research."""

    title: str
    url: str
    snippet: str = ""


@dataclass
class SearchResult:
    """Raw material gathered for a topic before LLM distillation."""

    text: str = ""                       # concatenated reference text
    sources: list[WebSource] = field(default_factory=list)
    lead_image_url: str | None = None    # a representative image, if any


class WebSearch:
    """Fetches reference text + sources for a topic (Wikipedia + optional DDG)."""

    def __init__(
        self,
        *,
        backend: str = "wikipedia",
        timeout: float = 20.0,
        user_agent: str = "youtube-agent/0.1",
        max_results: int = 4,
    ) -> None:
        self._backend = (backend or "wikipedia").strip().lower()
        self._timeout = timeout
        self._headers = {"User-Agent": user_agent}
        self._max_results = max_results

    async def gather(self, topic: str) -> SearchResult:
        """Return reference text + sources for ``topic`` (never raises)."""
        result = SearchResult()
        if self._backend in ("none", "off", ""):
            return result

        if self._backend in ("wikipedia", "both"):
            try:
                await self._add_wikipedia(topic, result)
            except Exception as exc:  # noqa: BLE001 - best-effort
                logger.warning("Wikipedia research failed: %s", exc)

        if self._backend in ("duckduckgo", "both"):
            try:
                await self._add_duckduckgo(topic, result)
            except Exception as exc:  # noqa: BLE001 - best-effort / optional dep
                logger.warning("DuckDuckGo research failed: %s", exc)

        return result

    # ------------------------------------------------------------------ #
    # Wikipedia
    # ------------------------------------------------------------------ #
    async def _add_wikipedia(self, topic: str, result: SearchResult) -> None:
        async with httpx.AsyncClient(timeout=self._timeout, headers=self._headers) as client:
            resp = await client.get(
                _WIKI_API,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": topic,
                    "format": "json",
                    "srlimit": 3,
                },
            )
            resp.raise_for_status()
            hits = resp.json().get("query", {}).get("search", [])
            if not hits:
                return

            # Pull summaries for the top couple of matches.
            for hit in hits[:2]:
                title = hit.get("title")
                if not title:
                    continue
                try:
                    s = await client.get(_WIKI_SUMMARY.format(title=title.replace(" ", "_")))
                    s.raise_for_status()
                    data = s.json()
                except Exception:  # noqa: BLE001
                    continue
                extract = (data.get("extract") or "").strip()
                if extract:
                    result.text += f"\n\n## {title}\n{extract}"
                page_url = (
                    data.get("content_urls", {}).get("desktop", {}).get("page")
                    or f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                )
                result.sources.append(
                    WebSource(title=title, url=page_url, snippet=extract[:200])
                )
                if not result.lead_image_url:
                    img = (data.get("originalimage") or {}).get("source")
                    if img:
                        result.lead_image_url = img

    # ------------------------------------------------------------------ #
    # DuckDuckGo (optional dependency)
    # ------------------------------------------------------------------ #
    async def _add_duckduckgo(self, topic: str, result: SearchResult) -> None:
        try:
            from ddgs import DDGS
        except Exception:  # noqa: BLE001 - optional
            try:
                from duckduckgo_search import DDGS  # older package name
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    "duckduckgo backend requires `pip install -r requirements-web.txt`"
                ) from exc

        def _run() -> list[dict]:
            with DDGS() as ddgs:
                return list(ddgs.text(topic, max_results=self._max_results))

        rows = await asyncio.to_thread(_run)
        for row in rows:
            title = (row.get("title") or "").strip()
            body = (row.get("body") or "").strip()
            url = (row.get("href") or row.get("url") or "").strip()
            if body:
                result.text += f"\n\n{title}\n{body}"
            if url:
                result.sources.append(WebSource(title=title or url, url=url, snippet=body[:200]))
