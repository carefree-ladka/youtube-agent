"""Abstract text-to-speech provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class WordMark:
    """A spoken word with precise timing in seconds."""

    __slots__ = ("word", "start", "end")

    def __init__(self, word: str, start: float, end: float) -> None:
        self.word = word
        self.start = start
        self.end = end

    def as_dict(self) -> dict:
        return {"word": self.word, "start": self.start, "end": self.end}


class TTSProvider(ABC):
    """Contract for turning narration text into an audio file."""

    @abstractmethod
    async def synthesize(
        self, text: str, output_path: Path, *, content_type: str = "long"
    ) -> Path:
        """Render ``text`` to speech at ``output_path`` and return the path.

        ``content_type`` ("short"/"long") lets providers adjust pacing (e.g.
        F5-TTS speaks shorts/reels slightly faster).
        """
        raise NotImplementedError

    async def synthesize_timed(
        self, text: str, output_path: Path, *, language: str = "English", content_type: str = "long"
    ) -> tuple[Path, list[WordMark]]:
        """Render speech AND return per-word timings for subtitle sync.

        Default implementation produces audio with no word marks; providers that
        support timing (e.g. edge-tts) override this. ``language`` is a hint for
        providers that recover timings via speech recognition. Callers must
        handle an empty mark list by falling back to estimated timings.
        """
        path = await self.synthesize(text, output_path, content_type=content_type)
        return path, []

    @abstractmethod
    async def list_voices(self) -> list[dict]:
        """Return the available voices for this provider."""
        raise NotImplementedError
