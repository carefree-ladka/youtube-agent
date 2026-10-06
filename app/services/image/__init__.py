"""Text-to-image provider abstraction, implementations, and a factory."""

from __future__ import annotations

from app.config import Settings
from app.core.logging import get_logger
from app.services.image.base import ImageProvider

logger = get_logger(__name__)


def build_image_provider(settings: Settings) -> ImageProvider | None:
    """Return an image provider based on settings, or None if disabled.

    Importing heavy backends is deferred to here so the base app never pays the
    import cost unless image generation is actually enabled.
    """
    backend = (settings.image_backend or "none").strip().lower()
    if backend in ("", "none", "off", "disabled"):
        logger.info("Image backend disabled; thumbnails will use the gradient background.")
        return None

    if backend == "comfyui":
        from app.services.image.comfyui_provider import ComfyUIImageProvider

        return ComfyUIImageProvider(settings)

    if backend == "ollama":
        from app.services.image.ollama_flux import OllamaImageProvider

        return OllamaImageProvider(settings)

    if backend == "diffusers":
        from app.services.image.diffusers_provider import DiffusersImageProvider

        return DiffusersImageProvider(settings)

    logger.warning("Unknown IMAGE_BACKEND '%s'; falling back to gradient.", backend)
    return None


__all__ = ["ImageProvider", "build_image_provider"]
