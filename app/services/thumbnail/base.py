"""Abstract thumbnail generator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ThumbnailGenerator(ABC):
    """Contract for producing thumbnail images from a concept."""

    @abstractmethod
    async def generate_concept(self, topic: str, title: str) -> dict[str, Any]:
        """Return a thumbnail concept (headline, subtext, accent, mood...)."""
        raise NotImplementedError

    async def generate_background(self, concept: dict[str, Any]) -> bytes | None:
        """Optionally generate an AI background image (PNG bytes) for a concept.

        Default implementation returns None (no AI background). Subclasses with
        an image provider override this.
        """
        return None

    @abstractmethod
    def render(
        self,
        concept: dict[str, Any],
        output_dir: Path,
        background: bytes | None = None,
    ) -> list[Path]:
        """Render all thumbnail formats and return the written file paths.

        ``background`` is optional PNG bytes used behind the text overlay; when
        absent, implementations fall back to a generated gradient.
        """
        raise NotImplementedError
