"""Background music bed for videos.

Two modes:
  * If a user-supplied track is configured (``VIDEO_MUSIC``), it is copied into
    the render's public dir and looped under the narration.
  * Otherwise a soft, slow, royalty-free-by-construction ambient pad is generated
    with the Python standard library (``wave`` + ``math``) - no deps, no assets,
    no licensing concerns.

The generated bed is a gentle 4-chord "breathing" pad (Am-F-C-G). Each chord
swells in and out via a raised-cosine window, so the clip starts and ends near
silence and therefore loops seamlessly in Remotion.
"""

from __future__ import annotations

import math
import shutil
import struct
import wave
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

_SAMPLE_RATE = 44100
_PEAK = 0.5  # bed is normalized low; Remotion lowers it further via musicVolume

# A calm, consonant progression. Frequencies in Hz (low octaves for a soft bed).
_CHORDS: list[tuple[float, float, float]] = [
    (220.00, 261.63, 329.63),  # A minor  (A3 C4 E4)
    (174.61, 220.00, 261.63),  # F major  (F3 A3 C4)
    (196.00, 246.94, 329.63),  # C major  (G3 B3 E4)  -> warm Cmaj add
    (196.00, 246.94, 293.66),  # G major  (G3 B3 D4)
]
_CHORD_SECONDS = 4.0


def _write_wav(path: Path, samples: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(_SAMPLE_RATE)
        frames = bytearray()
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            frames += struct.pack("<h", int(clamped * 32767))
        wav.writeframes(bytes(frames))


def _generate_pad() -> list[float]:
    """Build a soft, slow, seamlessly-looping ambient pad."""
    block = int(_SAMPLE_RATE * _CHORD_SECONDS)
    out: list[float] = []
    peak = 0.0
    for chord in _CHORDS:
        for i in range(block):
            t = i / _SAMPLE_RATE
            # Raised-cosine swell: 0 at edges, 1 at the middle -> clickless loop.
            window = math.sin(math.pi * (i / block)) ** 2
            # Slow tremolo for gentle movement.
            tremolo = 0.85 + 0.15 * math.sin(2 * math.pi * 0.12 * t)
            sample = 0.0
            for f in chord:
                sample += math.sin(2 * math.pi * f * t)
            sample = (sample / len(chord)) * window * tremolo
            out.append(sample)
            peak = max(peak, abs(sample))
    # Normalize to the bed peak.
    if peak > 0:
        gain = _PEAK / peak
        out = [s * gain for s in out]
    return out


def prepare_music(
    output_dir: Path,
    *,
    enabled: bool,
    music_path: str = "",
    filename: str = "music.wav",
) -> str | None:
    """Stage a background-music file into ``output_dir``; return its filename.

    Uses the user's ``music_path`` when provided and valid, else generates the
    soft ambient pad. Returns None when music is disabled or unavailable, so the
    caller simply renders without a bed.
    """
    if not enabled:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)

    # 1) User-supplied track (any format Remotion/Chromium can play).
    src = (music_path or "").strip()
    if src:
        p = Path(src).expanduser()
        if p.is_file():
            dest = output_dir / f"music{p.suffix.lower() or '.mp3'}"
            try:
                shutil.copyfile(p, dest)
                logger.info("Background music: using %s", p.name)
                return dest.name
            except OSError as exc:
                logger.warning("Could not stage music '%s': %s; using generated bed.", p, exc)
        else:
            logger.warning("VIDEO_MUSIC not found: %s; using generated bed.", p)

    # 2) Generated ambient pad (default).
    dest = output_dir / filename
    try:
        if not dest.exists() or dest.stat().st_size == 0:
            _write_wav(dest, _generate_pad())
        logger.info("Background music: generated ambient pad -> %s", dest.name)
        return dest.name
    except Exception as exc:  # noqa: BLE001 - music is non-critical
        logger.warning("Failed to generate music bed: %s", exc)
        return None
