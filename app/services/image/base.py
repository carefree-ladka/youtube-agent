"""Abstract text-to-image provider interface.

Keeps the thumbnail pipeline decoupled from any specific image-generation
backend (diffusers today, Ollama/FLUX or a hosted API later).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ImageProvider(ABC):
    """Contract for generating a raster image from a text prompt."""

    @abstractmethod
    async def generate(self, prompt: str, width: int, height: int) -> bytes | None:
        """Generate an image and return PNG bytes, or None if unavailable.

        Implementations should never raise for expected failure modes (model not
        installed, backend disabled); they return None so the caller can fall
        back gracefully.
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider can actually produce images."""
        raise NotImplementedError
