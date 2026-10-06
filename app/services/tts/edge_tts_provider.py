"""edge-tts provider: free, natural-sounding neural voices (no API key).

edge-tts streams audio from Microsoft's online neural voices, which produce
smooth, human-like narration ideal for YouTube. Voice, rate, pitch, and volume
are all configurable via settings.
"""

from __future__ import annotations

from pathlib import Path

import edge_tts

from app.config import Settings
from app.core.logging import get_logger
from app.services.tts.base import TTSProvider

logger = get_logger(__name__)


class EdgeTTSProvider(TTSProvider):
    """Text-to-speech backed by edge-tts."""

    def __init__(self, settings: Settings) -> None:
        self._voice = settings.tts_voice
        self._rate = settings.tts_rate
        self._pitch = settings.tts_pitch
        self._volume = settings.tts_volume

    async def synthesize(self, text: str, output_path: Path) -> Path:
        """Generate an MP3 narration file from text."""
        if not text.strip():
            raise ValueError("Cannot synthesize empty text.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Synthesizing audio with edge-tts (voice=%s, rate=%s, pitch=%s)",
            self._voice,
            self._rate,
            self._pitch,
        )

        communicate = edge_tts.Communicate(
            text=text,
            voice=self._voice,
            rate=self._rate,
            pitch=self._pitch,
            volume=self._volume,
        )
        await communicate.save(str(output_path))
        logger.info("Audio written to %s", output_path)
        return output_path

    async def list_voices(self) -> list[dict]:
        """Return all edge-tts voices (name, gender, locale)."""
        voices = await edge_tts.list_voices()
        return [
            {
                "name": v.get("ShortName"),
                "gender": v.get("Gender"),
                "locale": v.get("Locale"),
                "friendly": v.get("FriendlyName"),
            }
            for v in voices
        ]
