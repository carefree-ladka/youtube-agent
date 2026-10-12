"""F5-TTS provider: LOCAL zero-shot voice cloning (opt-in).

F5-TTS clones a voice from a short reference clip and reads arbitrary text in
that voice, entirely offline. It is selected with ``TTS_PROVIDER=f5`` and its
heavy dependencies live in ``requirements-voice.txt`` so the base app stays
light.

LICENSE NOTE: the F5-TTS *code* is MIT, but the pretrained *weights* are
CC-BY-NC (non-commercial). Review the license before using cloned audio
commercially.

Unlike edge-tts, F5-TTS emits no word-boundary events, so:
  * audio is written as 24 kHz WAV (we return the real ``.wav`` path), and
  * per-word subtitle timings are recovered with the optional faster-whisper
    aligner; if that is unavailable the caller estimates timings from the real
    audio duration.
"""

from __future__ import annotations

import asyncio
import random
from pathlib import Path

from app.config import Settings
from app.core.logging import get_logger
from app.services.tts import alignment
from app.services.tts.base import TTSProvider, WordMark

# F5 sets PYTHONHASHSEED from the seed; keep it within the valid 32-bit range so
# it never crashes child processes (faster-whisper/ctranslate2 workers).
_MAX_SEED = 2**32 - 1

logger = get_logger(__name__)


class F5TTSError(RuntimeError):
    """Raised when F5-TTS is misconfigured or unavailable, with a fix hint."""


class F5TTSProvider(TTSProvider):
    """Text-to-speech backed by a locally-run F5-TTS model (voice cloning)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ref_audio = (settings.f5_ref_audio or "").strip()
        self._ref_text = (settings.f5_ref_text or "").strip()
        self._model_name = settings.f5_model
        self._device = (settings.f5_device or "auto").strip().lower()
        self._speed = settings.f5_speed
        self._speed_short = settings.f5_speed_short
        self._target_rms = settings.f5_target_rms
        self._peak = settings.f5_peak
        self._remove_silence = settings.f5_remove_silence
        self._sentence_pause = settings.f5_sentence_pause
        self._paragraph_pause = settings.f5_paragraph_pause
        self._seed = settings.f5_seed
        self._model = None  # lazily loaded F5TTS instance (expensive)

    # ------------------------------------------------------------------ #
    # Model loading
    # ------------------------------------------------------------------ #
    def _load_model(self):  # type: ignore[no-untyped-def]
        """Import and construct the F5TTS model once, with actionable errors."""
        if self._model is not None:
            return self._model
        try:
            from f5_tts.api import F5TTS
        except Exception as exc:  # noqa: BLE001 - missing optional dependency
            raise F5TTSError(
                "F5-TTS is not installed. Install the voice extras with "
                "`pip install -r requirements-voice.txt` (TTS_PROVIDER=f5)."
            ) from exc

        device = None if self._device in ("", "auto") else self._device
        logger.info("Loading F5-TTS model '%s' (device=%s)", self._model_name, device or "auto")
        try:
            self._model = F5TTS(model=self._model_name, device=device)
        except Exception as exc:  # noqa: BLE001
            raise F5TTSError(
                f"Failed to load F5-TTS model '{self._model_name}': {exc}. "
                "The weights download from Hugging Face on first use (several GB); "
                "check your connection and disk space."
            ) from exc
        return self._model

    def _validate_ref(self) -> str:
        """Ensure a reference voice clip is configured and present."""
        if not self._ref_audio:
            raise F5TTSError(
                "No reference voice set. Point F5_REF_AUDIO at a short (~6-12s) "
                "clean clip of the voice to clone."
            )
        ref = Path(self._ref_audio).expanduser()
        if not ref.is_file():
            raise F5TTSError(f"F5_REF_AUDIO file not found: {ref}")
        return str(ref)

    # ------------------------------------------------------------------ #
    # Synthesis
    # ------------------------------------------------------------------ #
    async def synthesize(
        self, text: str, output_path: Path, *, content_type: str = "long"
    ) -> Path:
        """Clone the reference voice and read ``text``; returns the WAV path.

        Shorts/reels are spoken a little faster (``F5_SPEED_SHORT``); the output
        is loudness-boosted so narration isn't quiet.
        """
        if not text.strip():
            raise ValueError("Cannot synthesize empty text.")

        ref_file = self._validate_ref()
        # F5-TTS writes WAV; honor the caller's stem but force a .wav suffix.
        wav_path = output_path.with_suffix(".wav")
        wav_path.parent.mkdir(parents=True, exist_ok=True)

        speed = self._speed_short if content_type == "short" else self._speed
        # Always pass a bounded seed: F5 writes it to PYTHONHASHSEED, and a value
        # above 2**32-1 crashes spawned Python workers.
        seed = (
            int(self._seed)
            if self._seed is not None and 0 <= int(self._seed) <= _MAX_SEED
            else random.randint(0, _MAX_SEED)
        )
        segments = _split_sentences(text)
        logger.info(
            "Synthesizing with F5-TTS (ref=%s, device=%s, speed=%s, %d sentence(s), pauses=%.2f/%.2fs)",
            Path(ref_file).name, self._device, speed, len(segments),
            self._sentence_pause, self._paragraph_pause,
        )

        def _infer() -> None:
            import numpy as np
            import soundfile as sf

            model = self._load_model()
            sr = int(getattr(model, "target_sample_rate", 24000))
            sentence_gap = np.zeros(int(sr * max(self._sentence_pause, 0.0)), dtype=np.float32)
            paragraph_gap = np.zeros(int(sr * max(self._paragraph_pause, 0.0)), dtype=np.float32)

            pieces: list = []
            for i, (sentence, para_break) in enumerate(segments):
                wav, _sr, _ = model.infer(
                    ref_file=ref_file,
                    ref_text=self._ref_text,  # "" -> transcribed once, then cached
                    gen_text=sentence,
                    remove_silence=self._remove_silence,
                    target_rms=self._target_rms,
                    speed=speed,
                    seed=seed,
                )
                pieces.append(np.asarray(wav, dtype=np.float32))
                # Human pause after each sentence (longer breath at paragraph breaks).
                if i < len(segments) - 1:
                    pieces.append(paragraph_gap if para_break else sentence_gap)

            final = np.concatenate(pieces) if pieces else np.zeros(1, dtype=np.float32)
            sf.write(str(wav_path), final, sr)

        try:
            await asyncio.to_thread(_infer)
        except F5TTSError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise F5TTSError(f"F5-TTS synthesis failed: {exc}") from exc

        if not wav_path.is_file():
            raise F5TTSError("F5-TTS produced no audio file.")
        _boost_loudness(wav_path, self._peak)
        logger.info("Audio written to %s", wav_path)
        return wav_path

    async def synthesize_timed(
        self, text: str, output_path: Path, *, language: str = "English", content_type: str = "long"
    ) -> tuple[Path, list[WordMark]]:
        """Synthesize cloned speech and recover per-word timings when possible.

        Uses the optional faster-whisper aligner (``TTS_ALIGN``). If alignment
        is disabled or unavailable, returns no marks so the caller estimates
        subtitle timings from the real audio length.
        """
        wav_path = await self.synthesize(text, output_path, content_type=content_type)

        if not self._settings.tts_align:
            return wav_path, []

        marks = await alignment.align_words(
            wav_path,
            model_size=self._settings.align_model,
            device=self._settings.align_device,
            language=language,
        )
        return wav_path, marks

    async def list_voices(self) -> list[dict]:
        """Report the configured cloned voice (F5-TTS has no voice catalog)."""
        ref = self._ref_audio or "(not set)"
        return [
            {
                "name": "cloned",
                "gender": None,
                "locale": None,
                "friendly": f"F5-TTS cloned voice from {Path(ref).name if self._ref_audio else ref}",
            }
        ]


def _split_sentences(text: str) -> list[tuple[str, bool]]:
    """Split narration into sentences, flagging paragraph breaks.

    Returns a list of ``(sentence, is_paragraph_end)``. A sentence followed by a
    blank line (paragraph break) is marked so the synthesizer inserts a longer
    "breath" pause there. Falls back to the whole text as one segment.
    """
    import re

    text = (text or "").strip()
    if not text:
        return []

    # Mark paragraph breaks, then split into sentences on terminal punctuation.
    paragraphs = re.split(r"\n\s*\n", text)
    segments: list[tuple[str, bool]] = []
    for p, para in enumerate(paragraphs):
        para = para.replace("\n", " ").strip()
        if not para:
            continue
        sentences = re.findall(r"[^.!?]+(?:[.!?]+|$)", para)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            sentences = [para]
        for i, sent in enumerate(sentences):
            is_last_in_para = i == len(sentences) - 1
            is_last_para = p == len(paragraphs) - 1
            # Paragraph-length breath only between paragraphs (not at the very end).
            segments.append((sent, is_last_in_para and not is_last_para))
    return segments or [(text, False)]


def _boost_loudness(wav_path: Path, peak: float) -> None:
    """Peak-normalize a WAV in place so narration is nice and loud.

    Scales the signal so its loudest sample reaches ``peak`` (0..1). Only boosts
    (never attenuates below the current level unless it clips), and is a no-op if
    ``peak`` <= 0 or soundfile/numpy aren't available. Best-effort: never raises.
    """
    if not peak or peak <= 0:
        return
    try:
        import numpy as np
        import soundfile as sf

        data, sr = sf.read(str(wav_path), dtype="float32", always_2d=False)
        current = float(np.max(np.abs(data))) if data.size else 0.0
        if current <= 0:
            return
        gain = min(peak / current, 32.0)  # cap to avoid blowing up near-silence
        if gain <= 1.0:
            return  # already at/above target; leave it alone
        out = np.clip(data * gain, -1.0, 1.0)
        sf.write(str(wav_path), out, sr)
    except Exception as exc:  # noqa: BLE001 - loudness is a nice-to-have
        logger.info("Loudness normalization skipped (%s).", exc)
