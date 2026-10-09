"""Build Reel/Shorts-friendly subtitle cues from TTS word timings.

Groups precise per-word timings into short, punchy cues (a few words each) and
keeps the word-level timings inside each cue so the renderer can highlight the
currently-spoken word (karaoke style). If no word timings are available (a
provider without timing support), falls back to estimating cue timings by
distributing the script across the known audio duration.
"""

from __future__ import annotations

import re

from app.core.logging import get_logger
from app.models.video import Subtitle, SubtitleWord
from app.services.tts.base import WordMark

logger = get_logger(__name__)


def build_subtitles(
    marks: list[WordMark],
    *,
    max_words: int = 4,
    max_chars: int = 24,
    max_gap: float = 0.6,
) -> list[Subtitle]:
    """Group word marks into short cues suitable for vertical video.

    A new cue starts when adding a word would exceed ``max_words`` /
    ``max_chars``, when there is a pause longer than ``max_gap`` seconds, or
    after sentence-ending punctuation.
    """
    cues: list[Subtitle] = []
    current: list[WordMark] = []

    def flush() -> None:
        if not current:
            return
        text = " ".join(m.word for m in current).strip()
        cues.append(
            Subtitle(
                text=text,
                start=round(current[0].start, 3),
                end=round(current[-1].end, 3),
                words=[
                    SubtitleWord(word=m.word, start=round(m.start, 3), end=round(m.end, 3))
                    for m in current
                ],
            )
        )

    for mark in marks:
        if current:
            prospective_chars = len(" ".join(m.word for m in current)) + 1 + len(mark.word)
            gap = mark.start - current[-1].end
            ends_sentence = bool(re.search(r"[.!?]$", current[-1].word))
            if (
                len(current) >= max_words
                or prospective_chars > max_chars
                or gap > max_gap
                or ends_sentence
            ):
                flush()
                current = []
        current.append(mark)
    flush()

    # Prevent overlap and remove zero/negative-length cues.
    cleaned: list[Subtitle] = []
    for cue in cues:
        if cue.end <= cue.start:
            cue.end = cue.start + 0.4
        if cleaned and cue.start < cleaned[-1].end:
            cue.start = cleaned[-1].end
            if cue.end <= cue.start:
                cue.end = cue.start + 0.4
        cleaned.append(cue)

    logger.info("Built %d subtitle cues from %d word marks", len(cleaned), len(marks))
    return cleaned


def estimate_subtitles(
    script: str,
    audio_duration: float,
    *,
    max_words: int = 4,
) -> list[Subtitle]:
    """Fallback: evenly distribute script words across the audio duration.

    Used only when the TTS provider returns no word timings. Less accurate than
    real timings but keeps subtitles present and roughly in sync.
    """
    words = [w for w in re.findall(r"\S+", script) if w]
    if not words or audio_duration <= 0:
        return []

    per_word = audio_duration / len(words)
    cues: list[Subtitle] = []
    for i in range(0, len(words), max_words):
        chunk = words[i : i + max_words]
        start = round(i * per_word, 3)
        end = round(min((i + len(chunk)) * per_word, audio_duration), 3)
        cues.append(
            Subtitle(
                text=" ".join(chunk),
                start=start,
                end=end,
                words=[
                    SubtitleWord(
                        word=w,
                        start=round((i + j) * per_word, 3),
                        end=round((i + j + 1) * per_word, 3),
                    )
                    for j, w in enumerate(chunk)
                ],
            )
        )
    logger.info("Estimated %d subtitle cues (no word timings available)", len(cues))
    return cues
