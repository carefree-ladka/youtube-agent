"""Generates TTS-ready narration scripts from a topic."""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.prompts import (
    SCRIPT_SYSTEM,
    SHORT_SCRIPT_SYSTEM,
    build_script_prompt,
    build_short_script_prompt,
)
from app.services.llm.base import LLMClient

logger = get_logger(__name__)


class ScriptService:
    """Produces clean spoken-word scripts using an LLM backend."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def generate(
        self,
        topic: str,
        *,
        content_type: str = "long",
        tone: str = "engaging and friendly",
        audience: str = "a general YouTube audience",
        target_minutes: int = 5,
        target_seconds: int = 40,
        language: str = "English",
    ) -> str:
        """Return a narration script ready to feed into the TTS engine.

        ``content_type`` "short" produces a tight vertical Reel/Short script;
        "long" produces a standard YouTube video script.
        """
        if content_type == "short":
            logger.info("Generating SHORT (reel) script for topic: %s", topic)
            prompt = build_short_script_prompt(
                topic=topic,
                tone=tone,
                audience=audience,
                target_seconds=target_seconds,
                language=language,
            )
            script = await self._llm.generate_text(prompt, system=SHORT_SCRIPT_SYSTEM)
        else:
            logger.info("Generating script for topic: %s", topic)
            prompt = build_script_prompt(
                topic=topic,
                tone=tone,
                audience=audience,
                target_minutes=target_minutes,
                language=language,
            )
            script = await self._llm.generate_text(prompt, system=SCRIPT_SYSTEM)
        return self._clean(script)

    # Words that signal a model preamble line we should drop.
    _PREAMBLE_HINTS = ("script", "here", "sure", "below", "following", "narration")

    @classmethod
    def _clean(cls, script: str) -> str:
        """Strip artifacts a model might add despite instructions."""
        cleaned_lines: list[str] = []
        for line in script.splitlines():
            stripped = line.strip()
            # Drop markdown headings and bracketed stage directions.
            if stripped.startswith("#"):
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                continue
            # Strip surrounding quotes the model sometimes wraps each line in.
            stripped = cls._unquote(stripped)
            cleaned_lines.append(stripped.replace("*", ""))

        # Drop a leading preamble line like: Here's a punchy short-form script:
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        if cleaned_lines:
            first = cleaned_lines[0].strip().lower()
            if first.endswith(":") and len(first.split()) <= 9 and any(
                h in first for h in cls._PREAMBLE_HINTS
            ):
                cleaned_lines.pop(0)

        return "\n".join(cleaned_lines).strip()

    @staticmethod
    def _unquote(line: str) -> str:
        """Remove a single pair of wrapping straight/smart quotes from a line."""
        pairs = (('"', '"'), ("'", "'"), ("\u201c", "\u201d"), ("\u2018", "\u2019"))
        for start, end in pairs:
            if len(line) >= 2 and line.startswith(start) and line.endswith(end):
                return line[1:-1].strip()
        return line
