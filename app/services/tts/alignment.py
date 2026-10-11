"""Optional per-word subtitle alignment via faster-whisper.

Some TTS backends (notably local voice-cloning models like F5-TTS) produce only
audio, with no word-boundary events. To keep the karaoke-synced subtitles that
``edge-tts`` gives us for free, we can transcribe the generated audio with
``faster-whisper`` and read back accurate per-word timestamps.

This module is intentionally soft-dependency: if ``faster-whisper`` is not
installed (it lives in ``requirements-voice.txt``), ``align_words`` returns an
empty list and callers fall back to estimated subtitle timings.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path

from app.core.logging import get_logger
from app.services.tts.base import WordMark

logger = get_logger(__name__)

# Our settings carry human language names (e.g. "English"); map the common ones
# to Whisper's ISO codes. Unknown languages pass through as auto-detect (None).
_LANG_CODES: dict[str, str] = {
    "english": "en", "spanish": "es", "french": "fr", "german": "de",
    "italian": "it", "portuguese": "pt", "hindi": "hi", "japanese": "ja",
    "korean": "ko", "chinese": "zh", "arabic": "ar", "russian": "ru",
    "dutch": "nl", "polish": "pl", "turkish": "tr",
}


def _resolve_device(device: str) -> str:
    """Pick a CTranslate2-compatible device (it has no MPS backend)."""
    dev = (device or "auto").strip().lower()
    if dev in ("cpu", "cuda"):
        return dev
    try:  # auto: use CUDA only when actually available, else CPU.
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:  # noqa: BLE001
        pass
    return "cpu"


@lru_cache(maxsize=4)
def _load_model(model_size: str, device: str):  # type: ignore[no-untyped-def]
    """Load (and cache) a faster-whisper model. Raises if the lib is missing."""
    from faster_whisper import WhisperModel

    compute_type = "float16" if device == "cuda" else "int8"
    logger.info("Loading faster-whisper (%s, device=%s, %s)", model_size, device, compute_type)
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def _decode_16k_mono(audio_path: Path):  # type: ignore[no-untyped-def]
    """Load audio as a 16 kHz mono float32 numpy array, or None on failure."""
    try:
        import numpy as np
        import soundfile as sf

        data, sr = sf.read(str(audio_path), dtype="float32", always_2d=False)
        if getattr(data, "ndim", 1) > 1:  # stereo -> mono
            data = data.mean(axis=1)
        if sr != 16000:
            # Linear resample to 16 kHz (adequate for ASR word timing).
            n_out = int(round(len(data) * 16000 / sr))
            if n_out <= 0:
                return None
            x_old = np.linspace(0.0, 1.0, num=len(data), endpoint=False)
            x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
            data = np.interp(x_new, x_old, data).astype("float32")
        return np.ascontiguousarray(data, dtype="float32")
    except Exception as exc:  # noqa: BLE001 - fall back to path-based decode
        logger.info("Array decode failed (%s); letting faster-whisper read the file.", exc)
        return None


def is_available() -> bool:
    """True if faster-whisper can be imported."""
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


async def align_words(
    audio_path: Path,
    *,
    model_size: str = "base",
    device: str = "auto",
    language: str = "English",
) -> list[WordMark]:
    """Return per-word timings for ``audio_path``, or [] if unavailable.

    Runs the (blocking) transcription in a worker thread so it never stalls the
    event loop. Any failure degrades gracefully to an empty list.
    """
    if not is_available():
        logger.info("faster-whisper not installed; skipping word alignment.")
        return []

    lang = _LANG_CODES.get((language or "").strip().lower())
    resolved = _resolve_device(device)

    def _run() -> list[WordMark]:
        model = _load_model(model_size, resolved)
        # Decode to a 16 kHz mono float32 array ourselves and hand that to
        # faster-whisper. This avoids its internal PyAV decode path, which can
        # break on version mismatches (open() metadata_errors kwarg), and works
        # directly on the WAV our TTS wrote.
        audio = _decode_16k_mono(audio_path)
        source = audio if audio is not None else str(audio_path)
        segments, _ = model.transcribe(
            source, word_timestamps=True, language=lang
        )
        marks: list[WordMark] = []
        for seg in segments:
            for w in seg.words or []:
                word = (w.word or "").strip()
                if word and w.end > w.start:
                    marks.append(WordMark(word=word, start=float(w.start), end=float(w.end)))
        return marks

    try:
        marks = await asyncio.to_thread(_run)
        logger.info("Aligned %d words via faster-whisper (%s)", len(marks), model_size)
        return marks
    except Exception as exc:  # noqa: BLE001 - degrade to estimated subtitles
        logger.warning("Word alignment failed (%s); will estimate subtitles.", exc)
        return []
