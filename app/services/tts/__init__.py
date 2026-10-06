"""Text-to-speech provider abstraction and implementations."""

from app.services.tts.base import TTSProvider
from app.services.tts.edge_tts_provider import EdgeTTSProvider

__all__ = ["TTSProvider", "EdgeTTSProvider"]
