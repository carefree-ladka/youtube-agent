"""Real, license-aware images fetched from the web (for scene/thumbnail backgrounds).

Implements the same ``ImageProvider`` contract as the generative backends, so it
slots into the asset manager and thumbnail renderer unchanged. Instead of
generating pixels, it SEARCHES a license-aware source for a real photo matching
the scene's query, downloads it, and cover-crops it to the target size.

Default source is Openverse (CC-licensed + public domain, no API key). Optional
Pexels/Pixabay sources (free API keys) give higher-quality stock but won't have
trademarked subjects. Every image's attribution is captured so the caller can
write a credits file - a real obligation for CC-licensed media.

Best-effort: any failure returns None so the pipeline falls back to a designed
background. Mark ``search_based = True`` so the asset manager passes a clean
search query instead of a generative prompt.
"""

from __future__ import annotations

import io

import httpx
from PIL import Image

from app.config import Settings
from app.core.logging import get_logger
from app.services.image.base import ImageProvider

logger = get_logger(__name__)

_OPENVERSE = "https://api.openverse.org/v1/images/"
_PEXELS = "https://api.pexels.com/v1/search"
_PIXABAY = "https://pixabay.com/api/"


class WebImageProvider(ImageProvider):
    """Fetches real photos from a license-aware web source."""

    # Tells the asset manager to pass a raw search query (not a generative prompt).
    search_based = True

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._source = (settings.web_image_source or "openverse").strip().lower()
        self._license = settings.web_image_license
        self._safe = settings.web_safe
        self._timeout = settings.web_timeout
        self._headers = {"User-Agent": settings.web_user_agent}
        self._pexels_key = settings.pexels_api_key.strip()
        self._pixabay_key = settings.pixabay_api_key.strip()
        self._last_attribution: dict | None = None

    def is_available(self) -> bool:
        """Pexels/Pixabay need a key; Openverse/Wikimedia are always available."""
        if self._source == "pexels":
            return bool(self._pexels_key)
        if self._source == "pixabay":
            return bool(self._pixabay_key)
        return True

    def pop_attribution(self) -> dict | None:
        """Return (and clear) the attribution for the most recent fetch."""
        att, self._last_attribution = self._last_attribution, None
        return att

    async def generate(self, prompt: str, width: int, height: int) -> bytes | None:
        """Search for a real image matching ``prompt`` and return cropped PNG bytes."""
        query = (prompt or "").strip()
        if not query:
            return None
        self._last_attribution = None
        orientation = _orientation(width, height)
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers=self._headers, follow_redirects=True
            ) as client:
                hit = await self._search(client, query, orientation)
                if not hit:
                    logger.info("No web image found for '%s' (%s)", query[:50], self._source)
                    return None
                raw = await client.get(hit["image_url"])
                raw.raise_for_status()
                data = raw.content
        except Exception as exc:  # noqa: BLE001 - fall back to a designed background
            logger.warning("Web image fetch failed for '%s': %s", query[:50], exc)
            return None

        png = _to_cover_png(data, width, height)
        if png is None:
            return None
        hit["query"] = query
        self._last_attribution = hit
        logger.info(
            "Web image for '%s' -> %s (%s %s)",
            query[:40], hit.get("source") or self._source, hit.get("license"), hit.get("creator") or "",
        )
        return png

    # ------------------------------------------------------------------ #
    # Source-specific search (returns a dict with image_url + attribution)
    # ------------------------------------------------------------------ #
    async def _search(self, client: httpx.AsyncClient, query: str, orientation: str) -> dict | None:
        if self._source == "pexels":
            return await self._search_pexels(client, query, orientation)
        if self._source == "pixabay":
            return await self._search_pixabay(client, query)
        return await self._search_openverse(client, query)

    async def _search_openverse(self, client: httpx.AsyncClient, query: str) -> dict | None:
        params = {
            "q": query,
            "license_type": self._license,
            "page_size": 5,
            "mature": "false" if self._safe else "true",
        }
        resp = await client.get(_OPENVERSE, params=params)
        resp.raise_for_status()
        for item in resp.json().get("results", []):
            url = item.get("url")
            if not url:
                continue
            return {
                "provider": "openverse",
                "image_url": url,
                "title": item.get("title"),
                "creator": item.get("creator"),
                "license": (item.get("license") or "").upper(),
                "license_version": item.get("license_version"),
                "source": item.get("source"),
                "source_url": item.get("foreign_landing_url"),
            }
        return None

    async def _search_pexels(
        self, client: httpx.AsyncClient, query: str, orientation: str
    ) -> dict | None:
        resp = await client.get(
            _PEXELS,
            params={"query": query, "per_page": 3, "orientation": orientation},
            headers={"Authorization": self._pexels_key},
        )
        resp.raise_for_status()
        for photo in resp.json().get("photos", []):
            src = (photo.get("src") or {}).get("large2x") or (photo.get("src") or {}).get("original")
            if not src:
                continue
            return {
                "provider": "pexels",
                "image_url": src,
                "title": photo.get("alt") or query,
                "creator": photo.get("photographer"),
                "license": "Pexels License",
                "license_version": None,
                "source": "Pexels",
                "source_url": photo.get("url"),
            }
        return None

    async def _search_pixabay(self, client: httpx.AsyncClient, query: str) -> dict | None:
        resp = await client.get(
            _PIXABAY,
            params={
                "key": self._pixabay_key,
                "q": query,
                "per_page": 3,
                "safesearch": "true" if self._safe else "false",
                "image_type": "photo",
            },
        )
        resp.raise_for_status()
        for hit in resp.json().get("hits", []):
            src = hit.get("largeImageURL") or hit.get("webformatURL")
            if not src:
                continue
            return {
                "provider": "pixabay",
                "image_url": src,
                "title": (hit.get("tags") or query),
                "creator": hit.get("user"),
                "license": "Pixabay License",
                "license_version": None,
                "source": "Pixabay",
                "source_url": hit.get("pageURL"),
            }
        return None


def _orientation(width: int, height: int) -> str:
    if height > width:
        return "portrait"
    if width > height:
        return "landscape"
    return "square"


def _to_cover_png(data: bytes, width: int, height: int) -> bytes | None:
    """Cover-crop/resize downloaded image bytes to exactly width x height PNG."""
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:  # noqa: BLE001 - unsupported/corrupt image
        logger.warning("Could not decode web image: %s", exc)
        return None

    target = width / height
    w, h = img.size
    if w == 0 or h == 0:
        return None
    ratio = w / h
    if ratio > target:  # too wide -> crop sides
        new_w = int(h * target)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:  # too tall -> crop top/bottom
        new_h = int(w / target)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
    img = img.resize((width, height), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
