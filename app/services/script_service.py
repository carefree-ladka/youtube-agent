"""Generates TTS-ready narration scripts from a topic."""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.prompts import (
    SCRIPT_SYSTEM,
    SHORT_SCRIPT_SYSTEM,
    TECHNICAL_SCRIPT_SYSTEM,
    TECHNICAL_SHORT_SCRIPT_SYSTEM,
    build_script_prompt,
    build_short_script_prompt,
)
from app.core.topics import is_technical as _is_technical
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
        technical: bool | None = None,
    ) -> str:
        """Return a narration script ready to feed into the TTS engine.

        ``content_type`` "short" produces a tight vertical Reel/Short script;
        "long" produces a standard YouTube video script.
        """
        if technical is None:
            technical = _is_technical(topic)  # heuristic fallback
        if technical:
            logger.info("Technical topic -> accuracy-first script.")

        if content_type == "short":
            logger.info("Generating SHORT (reel) script for topic: %s", topic)
            prompt = build_short_script_prompt(
                topic=topic,
                tone=tone,
                audience=audience,
                target_seconds=target_seconds,
                language=language,
                technical=technical,
            )
            system = TECHNICAL_SHORT_SCRIPT_SYSTEM if technical else SHORT_SCRIPT_SYSTEM
            script = await self._llm.generate_text(prompt, system=system)
        else:
            logger.info("Generating script for topic: %s", topic)
            prompt = build_script_prompt(
                topic=topic,
                tone=tone,
                audience=audience,
                target_minutes=target_minutes,
                language=language,
                technical=technical,
            )
            system = TECHNICAL_SCRIPT_SYSTEM if technical else SCRIPT_SYSTEM
            script = await self._llm.generate_text(prompt, system=system)
        return self._clean(script)

    # Words that signal a model preamble/meta line we should drop.
    _PREAMBLE_HINTS = (
        "script",
        "here'",
        "here is",
        "here are",
        "sure",
        "below",
        "following",
        "narration",
        "voiceover",
        "voice-over",
        "video",
        "reel",
        "short",
    )

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

        # Drop leading blank lines, then any leading meta/preamble lines such as:
        #   "Here's a 40-second script on how closures work in JavaScript:"
        #   "Sure! Here is the voiceover:"
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        # Remove up to 2 leading preamble lines (model sometimes adds a couple).
        for _ in range(2):
            if not cleaned_lines:
                break
            if cls._is_preamble(cleaned_lines[0]):
                cleaned_lines.pop(0)
                while cleaned_lines and not cleaned_lines[0].strip():
                    cleaned_lines.pop(0)
            else:
                break

        return "\n".join(cleaned_lines).strip()

    @classmethod
    def _is_preamble(cls, line: str) -> bool:
        """True if a line looks like a model preface rather than narration.

        A preface typically ends with a colon and mentions the artifact being
        produced (script/voiceover/reel/etc.), e.g. "Here's the script:".
        """
        text = line.strip().lower()
        if not text:
            return False
        has_hint = any(h in text for h in cls._PREAMBLE_HINTS)
        if not has_hint:
            return False
        # Ends with a colon (classic preface) and is reasonably short.
        if text.endswith(":") and len(text.split()) <= 20:
            return True
        # Or a short "Sure, here's ... :" style opener without much else.
        if text.startswith(("here'", "here is", "here are", "sure")) and len(text.split()) <= 20:
            return True
        return False

    @staticmethod
    def _unquote(line: str) -> str:
        """Remove a single pair of wrapping straight/smart quotes from a line."""
        pairs = (('"', '"'), ("'", "'"), ("\u201c", "\u201d"), ("\u2018", "\u2019"))
        for start, end in pairs:
            if len(line) >= 2 and line.startswith(start) and line.endswith(end):
                return line[1:-1].strip()
        return line
