"""Procedurally generate short UI sound effects (click/pop/whoosh) as WAV files.

Uses only the Python standard library (``wave`` + ``math``), so there are no
extra dependencies and no need to ship/download audio assets. The renderer plays
these at scene transitions for a snappy, modern feel.
"""

from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

_SAMPLE_RATE = 44100
_AMPLITUDE = 0.6  # headroom so SFX sit under the narration


def _write_wav(path: Path, samples: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(_SAMPLE_RATE)
        frames = bytearray()
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            frames += struct.pack("<h", int(clamped * 32767))
        wav.writeframes(bytes(frames))


def _click() -> list[float]:
    """A crisp UI click: short noise burst + high tick with fast decay."""
    dur = 0.05
    n = int(_SAMPLE_RATE * dur)
    out: list[float] = []
    rng = random.Random(1)
    for i in range(n):
        t = i / _SAMPLE_RATE
        env = math.exp(-t * 90.0)
        tone = math.sin(2 * math.pi * 2200 * t)
        noise = (rng.random() * 2 - 1) * 0.5
        out.append((tone * 0.6 + noise * 0.4) * env * _AMPLITUDE)
    return out


def _pop() -> list[float]:
    """A soft pop: sine with a quick downward pitch glide."""
    dur = 0.14
    n = int(_SAMPLE_RATE * dur)
    out: list[float] = []
    for i in range(n):
        t = i / _SAMPLE_RATE
        env = math.exp(-t * 28.0)
        freq = 700 * math.exp(-t * 6.0) + 180  # glide down
        out.append(math.sin(2 * math.pi * freq * t) * env * _AMPLITUDE)
    return out


def _whoosh() -> list[float]:
    """A transition whoosh: band-ish filtered noise swelling then fading."""
    dur = 0.35
    n = int(_SAMPLE_RATE * dur)
    out: list[float] = []
    rng = random.Random(7)
    prev = 0.0
    for i in range(n):
        t = i / _SAMPLE_RATE
        # Triangular swell envelope (in then out).
        env = math.sin(math.pi * (t / dur)) ** 2
        white = rng.random() * 2 - 1
        # Simple one-pole low-pass that opens up over time for a sweep feel.
        alpha = 0.04 + 0.5 * (t / dur)
        prev = prev + alpha * (white - prev)
        out.append(prev * env * _AMPLITUDE)
    return out


def _swoosh() -> list[float]:
    """A brighter, shorter transition swoosh."""
    dur = 0.22
    n = int(_SAMPLE_RATE * dur)
    out: list[float] = []
    rng = random.Random(11)
    prev = 0.0
    for i in range(n):
        t = i / _SAMPLE_RATE
        env = math.sin(math.pi * (t / dur)) ** 1.5
        white = rng.random() * 2 - 1
        alpha = 0.2 + 0.6 * (t / dur)  # opens faster -> brighter
        prev = prev + alpha * (white - prev)
        out.append(prev * env * _AMPLITUDE)
    return out


def _ding() -> list[float]:
    """A pleasant bell/notification 'ding' (two partials, long decay)."""
    dur = 0.5
    n = int(_SAMPLE_RATE * dur)
    out: list[float] = []
    for i in range(n):
        t = i / _SAMPLE_RATE
        env = math.exp(-t * 7.0)
        tone = math.sin(2 * math.pi * 1320 * t) + 0.5 * math.sin(2 * math.pi * 1976 * t)
        out.append((tone / 1.5) * env * _AMPLITUDE)
    return out


def _tick() -> list[float]:
    """A tiny, subtle tick for small UI beats."""
    dur = 0.03
    n = int(_SAMPLE_RATE * dur)
    out: list[float] = []
    rng = random.Random(3)
    for i in range(n):
        t = i / _SAMPLE_RATE
        env = math.exp(-t * 160.0)
        out.append((rng.random() * 2 - 1) * env * _AMPLITUDE * 0.8)
    return out


def _boop() -> list[float]:
    """A soft low 'boop'."""
    dur = 0.12
    n = int(_SAMPLE_RATE * dur)
    out: list[float] = []
    for i in range(n):
        t = i / _SAMPLE_RATE
        env = math.exp(-t * 24.0)
        out.append(math.sin(2 * math.pi * 300 * t) * env * _AMPLITUDE)
    return out


def _riser() -> list[float]:
    """A short rising tone for emphasis (great before a reveal/stat)."""
    dur = 0.45
    n = int(_SAMPLE_RATE * dur)
    out: list[float] = []
    for i in range(n):
        t = i / _SAMPLE_RATE
        env = (t / dur) ** 1.5  # swell up
        freq = 220 + 900 * (t / dur)  # glide up
        out.append(math.sin(2 * math.pi * freq * t) * env * _AMPLITUDE * 0.8)
    return out


def _sweep() -> list[float]:
    """A downward noise sweep for scene exits."""
    dur = 0.28
    n = int(_SAMPLE_RATE * dur)
    out: list[float] = []
    rng = random.Random(5)
    prev = 0.0
    for i in range(n):
        t = i / _SAMPLE_RATE
        env = math.exp(-t * 6.0)
        white = rng.random() * 2 - 1
        alpha = 0.55 - 0.45 * (t / dur)  # closes down -> darker sweep
        prev = prev + max(alpha, 0.05) * (white - prev)
        out.append(prev * env * _AMPLITUDE)
    return out


_GENERATORS = {
    "click": _click,
    "pop": _pop,
    "whoosh": _whoosh,
    "swoosh": _swoosh,
    "ding": _ding,
    "tick": _tick,
    "boop": _boop,
    "riser": _riser,
    "sweep": _sweep,
}


def generate_sfx(output_dir: Path) -> dict[str, str]:
    """Generate the SFX WAVs into ``output_dir`` and return {name: filename}.

    Files are only (re)generated when missing. Returns bare filenames so they can
    be referenced relative to the Remotion ``publicDir``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, str] = {}
    for name, gen in _GENERATORS.items():
        filename = f"{name}.wav"
        path = output_dir / filename
        if not path.exists() or path.stat().st_size == 0:
            try:
                _write_wav(path, gen())
            except Exception as exc:  # noqa: BLE001 - SFX are non-critical
                logger.warning("Failed to generate SFX '%s': %s", name, exc)
                continue
        result[name] = filename
    logger.info("SFX ready: %s", ", ".join(result) or "(none)")
    return result
