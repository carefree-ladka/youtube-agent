"""Google "Nano Banana" image generation via the Gemini API.

Uses the Generative Language API ``:generateContent`` endpoint with a Gemini
image model (e.g. ``gemini-3-pro-image`` / ``gemini-2.5-flash-image``), which
returns the picture inline as base64 (``inlineData``). The same provider powers
BOTH thumbnail backgrounds and per-scene video assets, since both go through the
shared ``ImageProvider`` interface.

Auth: a Gemini API key (``GEMINI_API_KEY``) from https://aistudio.google.com/apikey.
NOTE: the API is billed/metered on its own free+paid tiers; a consumer Gemini
app / Google AI Pro subscription does NOT grant API access.

Like the other providers, this NEVER raises for expected failures (missing key,
safety block, bad response) - it returns None so the caller falls back to a
designed background. Every generated image carries an invisible SynthID
watermark; verify usage rights before publishing.
"""

from __future__ import annotations

import base64
import io

import httpx
from PIL import Image

from app.config import Settings
from app.core.logging import get_logger
from app.services.image.base import ImageProvider

logger = get_logger(__name__)

# Aspect ratios the Gemini image models accept, with their numeric value.
_ASPECT_RATIOS: dict[str, float] = {
    "1:1": 1.0,
    "2:3": 2 / 3,
    "3:2": 3 / 2,
    "3:4": 3 / 4,
    "4:3": 4 / 3,
    "4:5": 4 / 5,
    "5:4": 5 / 4,
    "9:16": 9 / 16,
    "16:9": 16 / 9,
    "21:9": 21 / 9,
}


def _nearest_aspect(width: int, height: int) -> str:
    """Pick the supported aspect ratio closest to the requested frame."""
    target = width / height if height else 1.0
    return min(_ASPECT_RATIOS, key=lambda name: abs(_ASPECT_RATIOS[name] - target))


class GeminiImageProvider(ImageProvider):
    """Generate background images via Google's Gemini ("Nano Banana") models."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = (settings.gemini_api_key or "").strip()
        self._model = settings.gemini_image_model
        self._base_url = settings.gemini_base_url.rstrip("/")
        self._image_size = (settings.gemini_image_size or "2K").strip()
        self._timeout = settings.gemini_image_timeout

    def is_available(self) -> bool:
        """True if an API key is configured (no network call to save quota)."""
        if not self._api_key:
            logger.warning(
                "IMAGE_BACKEND=gemini but GEMINI_API_KEY is not set; "
                "falling back to the designed background. Get a key at "
                "https://aistudio.google.com/apikey"
            )
            return False
        return True

    async def generate(self, prompt: str, width: int, height: int) -> bytes | None:
        """Generate an image for ``prompt`` and return PNG bytes, or None."""
        if not self._api_key:
            return None

        aspect = _nearest_aspect(width, height)
        url = f"{self._base_url}/models/{self._model}:generateContent"
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}
        logger.info(
            "Generating image via Gemini (model=%s, aspect=%s, size=%s)",
            self._model,
            aspect,
            self._image_size,
        )

        # First try with image config (aspect ratio + size); if a model/version
        # rejects those fields, retry with a bare image request.
        configs = [
            {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": aspect, "imageSize": self._image_size},
            },
            {"responseModalities": ["IMAGE"]},
        ]

        for attempt, generation_config in enumerate(configs):
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": generation_config,
            }
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    body = resp.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response is not None else "?"
                detail = exc.response.text[:300] if exc.response is not None else ""
                # A 400 on the first attempt often means this model version does
                # not accept imageConfig - retry once without it.
                if status == 400 and attempt == 0:
                    logger.info("Gemini rejected imageConfig (400); retrying without it.")
                    continue
                logger.warning("Gemini image generation failed (HTTP %s): %s", status, detail)
                return None
            except (httpx.HTTPError, OSError) as exc:
                logger.warning("Gemini image request failed: %s", exc)
                return None

            raw = self._extract_image(body)
            if raw is None:
                logger.warning("Gemini returned no image (safety block or text-only response).")
                return None
            return self._fit(raw, width, height)

        return None

    # ------------------------------------------------------------------ #
    # Response parsing + sizing
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_image(body: dict) -> bytes | None:
        """Pull the first inline image out of a generateContent response."""
        candidates = body.get("candidates") or []
        for cand in candidates:
            parts = ((cand or {}).get("content") or {}).get("parts") or []
            for part in parts:
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    data = inline["data"]
                    if isinstance(data, str) and data.strip().startswith("data:") and "," in data:
                        data = data.split(",", 1)[1]
                    try:
                        return base64.b64decode(data)
                    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
                        return None
        return None

    @staticmethod
    def _fit(data: bytes, width: int, height: int) -> bytes | None:
        """Cover-crop/resize the generated image to exactly width x height PNG."""
        try:
            img = Image.open(io.BytesIO(data)).convert("RGB")
        except (OSError, ValueError) as exc:
            logger.warning("Could not decode Gemini image bytes: %s", exc)
            return None
        if img.width == width and img.height == height:
            out = img
        else:
            scale = max(width / img.width, height / img.height)
            resized = img.resize(
                (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                Image.LANCZOS,
            )
            left = (resized.width - width) // 2
            top = (resized.height - height) // 2
            out = resized.crop((left, top, left + width, top + height))
        buf = io.BytesIO()
        out.save(buf, "PNG")
        return buf.getvalue()
