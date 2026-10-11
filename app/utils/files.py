"""Filesystem helpers for creating and writing organized project output."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from slugify import slugify


def make_project_dir(output_root: Path, topic: str) -> Path:
    """Create a unique, human-readable project directory for a run.

    Layout example: ``output/2026-09-20_143012_how-to-invest``
    """
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    slug = slugify(topic)[:60] or "untitled"
    project_dir = output_root / f"{stamp}_{slug}"
    (project_dir / "thumbnails").mkdir(parents=True, exist_ok=True)
    (project_dir / "audio").mkdir(parents=True, exist_ok=True)
    return project_dir


def slug_filename(text: str, suffix: str = "", *, max_len: int = 60, fallback: str = "video") -> str:
    """Return a filesystem-safe, human-readable file name from arbitrary text.

    Slugifies ``text`` (e.g. a video title) and appends ``suffix`` (such as
    ".mp4"). Falls back to ``fallback`` when the text slugifies to nothing.
    """
    slug = slugify(text or "")[:max_len].strip("-") or fallback
    return f"{slug}{suffix}"


def audio_duration_seconds(path: Path) -> float | None:
    """Best-effort audio duration in seconds, or None if it can't be read.

    Tries ``soundfile`` (handles wav/flac/ogg) then the stdlib ``wave`` module
    for PCM wav. Used to time subtitles/scenes when a TTS provider returns no
    word marks (e.g. a local voice-cloning backend).
    """
    try:
        import soundfile as sf  # optional (installed with voice extras)

        info = sf.info(str(path))
        if info.samplerate:
            return float(info.frames) / float(info.samplerate)
    except Exception:  # noqa: BLE001 - fall through to the stdlib reader
        pass

    try:
        import wave

        with wave.open(str(path), "rb") as wav:
            rate = wav.getframerate()
            if rate:
                return wav.getnframes() / float(rate)
    except Exception:  # noqa: BLE001 - unknown/compressed format
        return None
    return None


def write_social_files(project_dir: Path, metadata: dict) -> list[Path]:
    """Write human-friendly, copy-paste-ready social files (no JSON quotes).

    Produces a ``social/`` folder with per-platform text plus standalone tag and
    keyword lists, so tags/hashtags can be pasted straight into YouTube/Instagram
    without stripping quotes or brackets.
    """
    social_dir = project_dir / "social"
    written: list[Path] = []

    def _commas(items: list) -> str:
        return ", ".join(str(i).strip() for i in (items or []) if str(i).strip())

    def _spaces(items: list) -> str:
        return " ".join(str(i).strip() for i in (items or []) if str(i).strip())

    def _lines(items: list) -> str:
        return "\n".join(str(i).strip() for i in (items or []) if str(i).strip())

    yt = metadata.get("youtube", {}) or {}
    yt_tags = yt.get("tags", []) or []
    yt_text = (
        f"TITLE\n{yt.get('title', '')}\n\n"
        f"DESCRIPTION\n{yt.get('description', '')}\n\n"
        f"TAGS (comma-separated - paste into YouTube's Tags box)\n{_commas(yt_tags)}\n\n"
        f"HASHTAGS\n{_spaces(yt.get('hashtags', []))}\n\n"
        f"CHAPTERS\n{_lines(yt.get('chapters', []))}"
    )
    written.append(write_text(social_dir / "youtube.txt", yt_text))

    ig = metadata.get("instagram", {}) or {}
    ig_text = (
        f"CAPTION\n{ig.get('caption', '')}\n\n"
        f"HASHTAGS\n{_spaces(ig.get('hashtags', []))}"
    )
    written.append(write_text(social_dir / "instagram.txt", ig_text))

    li = metadata.get("linkedin", {}) or {}
    li_text = (
        f"POST\n{li.get('post', '')}\n\n"
        f"HASHTAGS\n{_spaces(li.get('hashtags', []))}"
    )
    written.append(write_text(social_dir / "linkedin.txt", li_text))

    titles = metadata.get("titles", []) or []
    if titles:
        written.append(
            write_text(
                social_dir / "title_options.txt",
                "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles)),
            )
        )

    # Standalone, one-paste lists for the fields creators copy most often.
    if yt_tags:
        written.append(write_text(social_dir / "tags.txt", _commas(yt_tags)))
    if metadata.get("keywords"):
        written.append(write_text(social_dir / "keywords.txt", _commas(metadata["keywords"])))

    return written


def write_text(path: Path, content: str) -> Path:
    """Write UTF-8 text, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_json(path: Path, data: Any) -> Path:
    """Write pretty-printed JSON, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
