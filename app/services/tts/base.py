"""Abstract text-to-speech provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class TTSProvider(ABC):
    """Contract for turning narration text into an audio file."""

    @abstractmethod
    async def synthesize(self, text: str, output_path: Path) -> Path:
        """Render ``text`` to speech at ``output_path`` and return the path."""
        raise NotImplementedError

    @abstractmethod
    async def list_voices(self) -> list[dict]:
        """Return the available voices for this provider."""
        raise NotImplementedError
