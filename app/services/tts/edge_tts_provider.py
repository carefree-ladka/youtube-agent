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
from app.services.tts.base import TTSProvider, WordMark

logger = get_logger(__name__)

# edge-tts reports offsets/durations in 100-nanosecond ("tick") units.
_TICKS_PER_SECOND = 10_000_000


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

    async def synthesize_timed(
        self, text: str, output_path: Path
    ) -> tuple[Path, list[WordMark]]:
        """Synthesize audio and capture precise per-word timings via streaming.

        edge-tts emits ``WordBoundary`` events as it streams; we collect them to
        build perfectly-synced subtitles without any separate speech-to-text.
        """
        if not text.strip():
            raise ValueError("Cannot synthesize empty text.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Synthesizing timed audio with edge-tts (voice=%s, rate=%s, pitch=%s)",
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
            boundary="WordBoundary",  # per-word timings for subtitle sync
        )

        marks: list[WordMark] = []
        with output_path.open("wb") as audio_file:
            async for chunk in communicate.stream():
                chunk_type = chunk.get("type")
                if chunk_type == "audio" and chunk.get("data"):
                    audio_file.write(chunk["data"])
                elif chunk_type in ("WordBoundary", "SentenceBoundary"):
                    start = chunk.get("offset", 0) / _TICKS_PER_SECOND
                    dur = chunk.get("duration", 0) / _TICKS_PER_SECOND
                    word = (chunk.get("text") or "").strip()
                    if word:
                        marks.append(WordMark(word=word, start=start, end=start + dur))

        logger.info("Audio written to %s (%d word marks)", output_path, len(marks))
        return output_path, marks

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
