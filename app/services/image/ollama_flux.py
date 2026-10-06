"""Ollama-backed image generation (e.g. FLUX.2 Klein).

Uses Ollama's `/api/generate` endpoint with an image-generation model. The
model returns a base64-encoded image in the ``image`` field (older/newer
builds may use an ``images`` list), which we decode into PNG bytes.

IMPORTANT: image diffusion models cannot reliably render text. We therefore ask
the model for a clean, TEXT-FREE background and let the PIL renderer draw the
actual headline on top. Never ask the model to spell the headline.
"""

from __future__ import annotations

import base64

import httpx

from app.config import Settings
from app.core.logging import get_logger
from app.services.image.base import ImageProvider

logger = get_logger(__name__)


class OllamaImageProvider(ImageProvider):
    """Generate background images via an Ollama image model."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_image_model
        self._timeout = settings.ollama_image_timeout

    def is_available(self) -> bool:
        """True if the Ollama server is reachable."""
        try:
            with httpx.Client(timeout=5.0) as client:
                client.get(f"{self._base_url}/api/version").raise_for_status()
            return True
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("Ollama not reachable for image generation: %s", exc)
            return False

    async def generate(self, prompt: str, width: int, height: int) -> bytes | None:
        """Generate an image for ``prompt`` and return PNG bytes, or None."""
        payload = {"model": self._model, "prompt": prompt, "stream": False}
        logger.info("Generating image via Ollama (model=%s)", self._model)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base_url}/api/generate", json=payload)
                resp.raise_for_status()
                body = resp.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:200] if exc.response is not None else ""
            logger.warning(
                "Ollama image generation rejected (%s). Model '%s' may not support "
                "image generation on this Ollama version. %s",
                exc.response.status_code if exc.response else "?",
                self._model,
                detail,
            )
            return None
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("Ollama image request failed: %s", exc)
            return None

        return self._decode(body)

    @staticmethod
    def _decode(body: dict) -> bytes | None:
        """Extract base64 image data from the response and decode to bytes."""
        raw = body.get("image")
        if not raw:
            images = body.get("images")
            if isinstance(images, list) and images:
                raw = images[0]
        if not raw or not isinstance(raw, str):
            logger.warning("Ollama image response had no image data.")
            return None
        # Strip an optional data URI prefix.
        if "," in raw and raw.strip().startswith("data:"):
            raw = raw.split(",", 1)[1]
        try:
            return base64.b64decode(raw)
        except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
            logger.warning("Failed to decode Ollama image base64: %s", exc)
            return None
